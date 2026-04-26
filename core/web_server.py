"""
core/web_server.py — HTTP server and all endpoint routing.

RemoteHandler never imports from ui/ — it talks to the app only
through a WebContext object set before the server starts.
"""

import datetime
import glob
import json
import math
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse

import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

import config

# DVRManager imported for type hints only; no circular dependency risk.
from core.dvr_manager import DVRManager
from core.epg import build_guide_bundle, fetch_epg, fetch_multi_epg, filter_guide_categories
from core.mobile_transcode import manager as mobile_transcode_manager
from core.recorder import job_duration_secs


def _json_iso_utc(dt: datetime.datetime) -> str:
    """
    Serialize datetimes for JSON / browsers as ISO-8601 UTC with a Z suffix.

    Naive datetimes follow the same rules as datetime.timestamp(): they are
    interpreted in the host's local timezone (Docker often uses UTC). Without
    an explicit offset, JavaScript treats 'YYYY-MM-DDTHH:mm:ss' as *local* time,
    which shifts queued recording labels for users outside the server TZ.
    """
    ts = dt.timestamp()
    utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


class _RecordingHlsSession:
    """One progressive remux job: filename → outdir, with a running ffmpeg."""
    __slots__ = (
        "filename", "outdir", "process",
        "first_seg_ready", "done_event",
        "completed", "failed", "error_tail",
    )

    def __init__(self, filename: str, outdir: str):
        self.filename         = filename
        self.outdir           = outdir
        self.process: subprocess.Popen | None = None
        self.first_seg_ready  = threading.Event()
        self.done_event       = threading.Event()
        self.completed        = False
        self.failed           = False
        self.error_tail       = ""


class _RecordingHlsCache:
    """
    Progressive HLS remux cache for completed recordings.

    First request for a filename kicks off ffmpeg asynchronously. The server
    waits only until segment 0 + the playlist are on disk (a few seconds),
    then begins serving. The player reads a growing `event`-type playlist
    and pulls new segments as they're written — encoding the tail of the
    file happens in the background while playback is already underway.

    Subsequent requests reuse the same session. /tmp/elite_rec_hls/ is
    wiped on container restart so entries don't survive deploys.
    """

    _TMPDIR     = os.path.join(tempfile.gettempdir(), "elite_rec_hls")
    _sessions:   dict[str, _RecordingHlsSession] = {}
    _locks:      dict[str, threading.Lock]       = {}
    _meta_lock   = threading.Lock()

    @classmethod
    def _lock_for(cls, filename: str) -> threading.Lock:
        with cls._meta_lock:
            if filename not in cls._locks:
                cls._locks[filename] = threading.Lock()
            return cls._locks[filename]

    @classmethod
    def get_or_start(cls, filename: str, ts_path: str) -> _RecordingHlsSession:
        """
        Return an existing session or start a new one. Non-blocking w.r.t.
        ffmpeg: returns as soon as ffmpeg is spawned. Callers that need to
        serve a playlist should then await `sess.first_seg_ready`.
        """
        with cls._lock_for(filename):
            sess = cls._sessions.get(filename)
            if sess is not None and not sess.failed:
                return sess
            # If a prior attempt failed, drop it and try again.
            if sess is not None and sess.failed:
                cls._sessions.pop(filename, None)

            safe   = re.sub(r"[^\w.\-]", "_", filename)
            outdir = os.path.join(cls._TMPDIR, safe)
            os.makedirs(outdir, exist_ok=True)

            # Wipe any stale output from a previous failed attempt — else
            # ffmpeg may refuse to start (segment files exist) or we may
            # serve a mix of new + old segments.
            import glob as _g
            for p in _g.glob(os.path.join(outdir, "*.ts")) + _g.glob(os.path.join(outdir, "*.m3u8")):
                try: os.remove(p)
                except OSError: pass

            playlist = os.path.join(outdir, "index.m3u8")
            seg_pat  = os.path.join(outdir, "seg_%05d.ts")

            # Probe audio codec. AAC → pure remux (fast, IO-bound).
            # MP2/AC3/etc → transcode to AAC for browser compatibility.
            audio_args = ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "error",
                     "-select_streams", "a:0",
                     "-show_entries", "stream=codec_name",
                     "-of", "default=nokey=1:noprint_wrappers=1",
                     ts_path],
                    capture_output=True, timeout=10,
                    **config._SUBPROCESS_FLAGS,
                )
                codec = probe.stdout.decode("utf-8", errors="replace").strip().lower()
                if codec == "aac":
                    audio_args = ["-c:a", "copy"]
                    print(f"[RecHLS] Source audio is AAC — fast remux")
                else:
                    print(f"[RecHLS] Source audio is '{codec or 'unknown'}' — transcoding to AAC")
            except Exception as exc:
                print(f"[RecHLS] ffprobe failed ({exc}); defaulting to AAC transcode")

            # -hls_playlist_type event: segments can only be appended, and
            #                           ENDLIST is written when ffmpeg exits.
            #                           Players treat it as a growing seekable
            #                           stream while encoding is in progress.
            # -hls_list_size 0        : keep every segment in the playlist.
            cmd = [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", ts_path,
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "copy",
                *audio_args,
                "-f", "hls",
                "-hls_time", "6",
                "-hls_list_size", "0",
                "-hls_playlist_type", "event",
                "-hls_flags", "independent_segments+temp_file",
                "-hls_segment_type", "mpegts",
                "-hls_segment_filename", seg_pat,
                playlist,
            ]

            sess = _RecordingHlsSession(filename, outdir)
            print(f"[RecHLS] Starting progressive remux '{filename}' → {outdir}")
            try:
                sess.process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    **config._SUBPROCESS_FLAGS,
                )
            except Exception as exc:
                sess.failed     = True
                sess.error_tail = str(exc)
                sess.first_seg_ready.set()
                sess.done_event.set()
                cls._sessions[filename] = sess
                return sess

            cls._sessions[filename] = sess

            # Watcher thread:
            #   1. Sets first_seg_ready once playlist + seg_00000 are on disk
            #      (or ffmpeg dies).
            #   2. Collects stderr and sets done_event on ffmpeg exit.
            def _watch(s: _RecordingHlsSession, pl: str):
                seg0 = os.path.join(s.outdir, "seg_00000.ts")
                while s.process.poll() is None and not s.first_seg_ready.is_set():
                    if (os.path.exists(pl)
                            and os.path.exists(seg0)
                            and os.path.getsize(seg0) > 0):
                        s.first_seg_ready.set()
                        break
                    time.sleep(0.2)
                try:
                    _, stderr_bytes = s.process.communicate(timeout=None)
                except Exception:
                    stderr_bytes = b""
                rc = s.process.returncode
                if rc == 0:
                    s.completed = True
                    print(f"[RecHLS] '{s.filename}' completed")
                else:
                    s.failed     = True
                    s.error_tail = stderr_bytes.decode("utf-8", errors="replace")[-800:]
                    print(f"[RecHLS] '{s.filename}' failed rc={rc}\n{s.error_tail}")
                # Guarantee waiters unblock even if ffmpeg died before seg 0.
                s.first_seg_ready.set()
                s.done_event.set()

            threading.Thread(target=_watch, args=(sess, playlist), daemon=True).start()
            return sess

    @classmethod
    def wait_for_startup(cls, sess: _RecordingHlsSession, timeout: float = 45.0) -> bool:
        """Block until segment 0 is ready or ffmpeg fails / times out."""
        return sess.first_seg_ready.wait(timeout=timeout)

    @classmethod
    def evict(cls, filename: str) -> None:
        """Kill any running remux for filename, remove its temp dir."""
        lock = cls._lock_for(filename)
        with lock:
            sess = cls._sessions.pop(filename, None)
            if sess and sess.process and sess.process.poll() is None:
                try:
                    sess.process.terminate()
                except Exception:
                    pass
            safe   = re.sub(r"[^\w.\-]", "_", filename)
            outdir = os.path.join(cls._TMPDIR, safe)
            if os.path.isdir(outdir):
                try:
                    shutil.rmtree(outdir)
                except OSError:
                    pass


_duration_cache: dict[tuple, float] = {}
_duration_cache_lock = threading.Lock()

_audio_codec_cache: dict[str, str] = {}
_audio_codec_cache_lock = threading.Lock()


def _probe_recording_audio_codec(ts_path: str) -> str | None:
    """Return the first audio stream codec name (e.g. 'aac', 'ac3'), cached by path."""
    with _audio_codec_cache_lock:
        if ts_path in _audio_codec_cache:
            return _audio_codec_cache[ts_path]
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-select_streams", "a:0",
             "-show_entries", "stream=codec_name",
             "-of", "default=nokey=1:noprint_wrappers=1",
             ts_path],
            capture_output=True, timeout=10,
            **config._SUBPROCESS_FLAGS,
        )
        codec = probe.stdout.decode("utf-8", errors="replace").strip().lower() or None
    except Exception:
        codec = None
    if codec:
        with _audio_codec_cache_lock:
            _audio_codec_cache[ts_path] = codec
    return codec


def _probe_recording_duration(path: str) -> float | None:
    """Return duration in seconds for a .ts recording, cached by (path, size, mtime)."""
    try:
        stat = os.stat(path)
    except OSError:
        return None
    key = (path, stat.st_size, int(stat.st_mtime))
    with _duration_cache_lock:
        if key in _duration_cache:
            return _duration_cache[key]
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=nokey=1:noprint_wrappers=1",
             path],
            capture_output=True, timeout=8,
            **config._SUBPROCESS_FLAGS,
        )
        out = proc.stdout.decode("utf-8", errors="replace").strip()
        dur = float(out) if out else None
    except Exception:
        dur = None
    with _duration_cache_lock:
        _duration_cache[key] = dur
    return dur


class StreamMuxer:
    """
    Multi-client stream multiplexer for live TV.

    Maintains a single provider connection per channel and fans out
to multiple Kodi clients. When the last client disconnects, the
    provider connection closes automatically.
    """

    def __init__(self):
        # channel_id -> {"request": Response, "clients": set(handler), "thread": Thread}
        self._streams: dict[str, dict] = {}
        self._lock = threading.Lock()

    def _read_provider_stream(self, channel_id: str, stream_url: str):
        """Background thread: read from provider, write to all connected clients."""
        try:
            with requests.get(stream_url, stream=True, timeout=10) as r:
                # Store the response so new clients can check status
                with self._lock:
                    if channel_id not in self._streams:
                        return
                    self._streams[channel_id]["request"] = r
                    self._streams[channel_id]["status_code"] = r.status_code

                if r.status_code != 200:
                    return

                for chunk in r.iter_content(chunk_size=65536):
                    if not chunk:
                        continue

                    with self._lock:
                        if channel_id not in self._streams:
                            break
                        clients = list(self._streams[channel_id]["clients"])

                    if not clients:
                        break

                    # Write to all clients (remove disconnected ones)
                    disconnected = []
                    for handler in clients:
                        try:
                            handler.wfile.write(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            disconnected.append(handler)

                    if disconnected:
                        with self._lock:
                            if channel_id in self._streams:
                                self._streams[channel_id]["clients"].difference_update(disconnected)
        except Exception:
            pass
        finally:
            # Cleanup: remove this channel's entry when done
            with self._lock:
                if channel_id in self._streams:
                    del self._streams[channel_id]

    def add_client(self, channel_id: str, handler) -> bool:
        """
        Add a client handler to a channel's multiplexed stream.
        Returns True if the client was added successfully, False otherwise.
        """
        stream_url = (
            f"{config.SERVER_URL.rstrip('/')}"
            f"/live/{config.USERNAME}/{config.PASSWORD}/{channel_id}.ts"
        )

        with self._lock:
            if channel_id not in self._streams:
                # First client for this channel - start provider connection
                self._streams[channel_id] = {
                    "request": None,
                    "clients": {handler},
                    "status_code": None,
                }
                # Start background thread to read from provider
                t = threading.Thread(
                    target=self._read_provider_stream,
                    args=(channel_id, stream_url),
                    daemon=True
                )
                t.start()
                self._streams[channel_id]["thread"] = t
            else:
                # Add to existing stream
                self._streams[channel_id]["clients"].add(handler)

            # Wait briefly for connection to establish
            import time
            for _ in range(50):  # 5 seconds max wait
                status = self._streams.get(channel_id, {}).get("status_code")
                if status is not None:
                    break
                time.sleep(0.1)

            # Check if connection succeeded
            if self._streams.get(channel_id, {}).get("status_code") != 200:
                self._streams[channel_id]["clients"].discard(handler)
                return False

        return True

    def remove_client(self, channel_id: str, handler) -> None:
        """Remove a client from a channel's stream."""
        with self._lock:
            if channel_id in self._streams:
                self._streams[channel_id]["clients"].discard(handler)


# Global StreamMuxer instance
_stream_muxer = StreamMuxer()


class WebContext:
    """
    Thin bridge between the HTTP handler and the application.
    IPTVRecorderApp constructs one of these and passes it to start_web_server().
    New fields default to None so existing call sites keep working until updated.
    """
    def __init__(
        self,
        get_status_fn,          # () -> dict  (recordings, status text, backup name)
        get_channels_fn,        # (q: str) -> list[{name, id}]  max 25
        get_favorites_fn,       # () -> list[{name, id}]
        get_log_fn,             # () -> list[str]
        action_queue,           # queue.Queue — web actions dispatched to UI thread
        dvr_manager=None,       # DVRManager instance
        get_all_channels_fn=None,   # () -> list[{name, id}]  — full list, no limit
        get_jobs_fn=None,           # () -> list[RecordingJob]
        get_recordings_dir_fn=None, # () -> str | None
        preview_start_fn=None,      # (channel_id: str) -> dict — Live DVR web remote
        preview_stop_fn=None,       # (preview_id: int) -> dict
    ):
        self.get_status          = get_status_fn
        self.get_channels        = get_channels_fn
        self.get_favorites       = get_favorites_fn
        self.get_log             = get_log_fn
        self.action_queue        = action_queue
        self.dvr_manager         = dvr_manager
        self.get_all_channels    = get_all_channels_fn
        self.get_jobs            = get_jobs_fn
        self.get_recordings_dir  = get_recordings_dir_fn
        self.preview_start       = preview_start_fn
        self.preview_stop        = preview_stop_fn


class RemoteHandler(BaseHTTPRequestHandler):
    ctx: WebContext = None  # set by start_web_server() before server starts

    _html_page: str = None

    @classmethod
    def _get_html(cls) -> str:
        if cls._html_page is None:
            html_path = os.path.join(config._BUNDLE_DIR, "static", "remote.html")
            try:
                with open(html_path, encoding="utf-8") as f:
                    cls._html_page = f.read()
            except Exception:
                cls._html_page = "<h1>Web UI not found</h1>"
        return cls._html_page

    # ── Request handlers ─────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path

        # ── Static / legacy ──────────────────────────────────────────────────
        if path == "/":
            self._html(self._get_html())

        elif path == "/api/status":
            self._json(self.ctx.get_status())

        elif path == "/api/favorites":
            self._json(self.ctx.get_favorites())

        elif path == "/api/channels":
            q = qs.get("q", [""])[0].lower().strip()
            self._json(self.ctx.get_channels(q))

        elif path == "/api/epg":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._json({"listings": []})
            else:
                try:
                    limit = int(qs.get("limit", ["12"])[0])
                except ValueError:
                    limit = 12
                limit = max(1, min(limit, 64))
                try:
                    w0 = int(qs.get("window_start_ms", ["0"])[0])
                    w1 = int(qs.get("window_end_ms", ["0"])[0])
                except ValueError:
                    w0, w1 = 0, 0
                listings = fetch_epg(
                    config.SERVER_URL,
                    config.USERNAME,
                    config.PASSWORD,
                    channel_id,
                    limit=limit,
                    window_start_ms=w0,
                    window_end_ms=w1,
                )
                self._json({"listings": listings})

        # ── Android TV: EPG category browser ─────────────────────────────────
        elif path == "/api/categories":
            try:
                url = (
                    f"{config.SERVER_URL}/player_api.php"
                    f"?username={config.USERNAME}&password={config.PASSWORD}"
                    f"&action=get_live_categories"
                )
                r = requests.get(url, timeout=8)
                cats = r.json()
                self._json(filter_guide_categories([
                    {"category_id": c.get("category_id", ""), "category_name": c.get("category_name", "")}
                    for c in cats if c.get("category_name")
                ]))
            except Exception:
                self._json([])

        elif path == "/api/channels/by-category":
            category_id = qs.get("category_id", [""])[0]
            if not category_id:
                self._json([])
                return
            try:
                url = (
                    f"{config.SERVER_URL}/player_api.php"
                    f"?username={config.USERNAME}&password={config.PASSWORD}"
                    f"&action=get_live_streams&category_id={category_id}"
                )
                r = requests.get(url, timeout=10)
                self._json([
                    {"name": s.get("name", ""), "id": str(s.get("stream_id", ""))}
                    for s in r.json() if s.get("stream_id")
                ])
            except Exception:
                self._json([])

        elif path == "/api/epg/multi":
            ids_str = qs.get("channel_ids", [""])[0]
            try:
                limit = int(qs.get("limit", ["6"])[0])
            except ValueError:
                limit = 6
            limit = max(1, min(limit, 64))
            try:
                w0 = int(qs.get("window_start_ms", ["0"])[0])
                w1 = int(qs.get("window_end_ms", ["0"])[0])
            except ValueError:
                w0, w1 = 0, 0
            if not ids_str:
                self._json([])
                return
            channel_ids = [i.strip() for i in ids_str.split(",") if i.strip()][:30]
            results = fetch_multi_epg(
                config.SERVER_URL,
                config.USERNAME,
                config.PASSWORD,
                channel_ids,
                limit=limit,
                window_start_ms=w0,
                window_end_ms=w1,
            )
            self._json(results)

        elif path == "/api/guide":
            category_id = qs.get("category_id", [""])[0].strip()
            limit = int(qs.get("limit", ["24"])[0])
            refresh = qs.get("refresh", ["0"])[0].strip().lower() in {"1", "true", "yes", "on"}
            bundle = build_guide_bundle(
                config.SERVER_URL,
                config.USERNAME,
                config.PASSWORD,
                category_id=category_id or None,
                limit=limit,
                refresh=refresh,
            )
            self._json(bundle)

        elif path == "/api/log":
            self._json({"entries": self.ctx.get_log()})

        # ── Android TV: discovery + info ─────────────────────────────────────
        elif path == "/api/info":
            count = 0
            if self.ctx.get_all_channels:
                try:
                    count = len(self.ctx.get_all_channels())
                except Exception:
                    pass
            self._json({
                "version":          config.APP_VERSION,
                "server_reachable": True,
                "channel_count":    count,
                "capabilities":     ["recording", "epg", "favorites", "stream_proxy", "dvr"],
            })

        # ── Android TV: full channel list for TV guide ────────────────────────
        elif path == "/api/channels/all":
            if self.ctx.get_all_channels:
                self._json(self.ctx.get_all_channels())
            else:
                self._json([])

        # ── Android TV: structured recordings list ────────────────────────────
        elif path == "/api/recordings":
            self._json(self._build_recordings_response())

        # ── Mobile webapp: HLS remux of a completed recording ─────────────────
        # /api/recordings/hls/<encoded_filename>/index.m3u8
        # /api/recordings/hls/<encoded_filename>/seg_NNNNN.ts
        elif path.startswith("/api/recordings/hls/"):
            self._serve_recording_hls(path)

        # ── Android TV: stream proxy URL ──────────────────────────────────────
        elif path == "/api/stream/url":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._error(400, "channel_id required")
                return
            ip        = self._local_ip()
            proxy_url = f"http://{ip}:{config.WEB_PORT}/api/stream/live?channel_id={channel_id}"
            name      = channel_id
            if self.ctx.get_all_channels:
                try:
                    name = next(
                        (ch["name"] for ch in self.ctx.get_all_channels()
                         if str(ch["id"]) == str(channel_id)),
                        channel_id,
                    )
                except Exception:
                    pass
            self._json({"proxy_url": proxy_url, "channel_name": name})

        # ── Android TV: live stream proxy ─────────────────────────────────────
        elif path == "/api/stream/live":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._error(400, "channel_id required")
                return
            self._proxy_live_stream(channel_id)

        # ── Mobile webapp: transcoded HLS playlist ────────────────────────────
        elif path == "/api/stream/mobile.m3u8":
            channel_id = qs.get("channel_id", [""])[0]
            profile    = qs.get("profile",    ["mobile"])[0]
            if not channel_id:
                self._error(400, "channel_id required")
                return
            self._serve_mobile_playlist(channel_id, profile)

        # ── Mobile webapp: transcoded HLS segments ────────────────────────────
        # /api/stream/mobile/<channel_id>/<profile>/seg_NNNNN.ts
        elif path.startswith("/api/stream/mobile/"):
            self._serve_mobile_segment(path)

        # ── Mobile webapp: playback-info helper (URL + encoder + profiles) ────
        elif path == "/api/stream/info":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._error(400, "channel_id required")
                return
            name = channel_id
            if self.ctx.get_all_channels:
                try:
                    name = next(
                        (ch["name"] for ch in self.ctx.get_all_channels()
                         if str(ch["id"]) == str(channel_id)),
                        channel_id,
                    )
                except Exception:
                    pass
            self._json({
                "channel_name":    name,
                "encoder":         mobile_transcode_manager.encoder,
                "profiles":        ["original", "data_saver", "hd", "mobile", "low"],
                "original_url":    f"/api/stream/live?channel_id={channel_id}",
                "data_saver_url":  f"/api/stream/mobile.m3u8?channel_id={channel_id}&profile=data_saver",
                "mobile_url":      f"/api/stream/mobile.m3u8?channel_id={channel_id}&profile=mobile",
                "hd_url":          f"/api/stream/mobile.m3u8?channel_id={channel_id}&profile=hd",
                "low_url":         f"/api/stream/mobile.m3u8?channel_id={channel_id}&profile=low",
            })

        # ── VLC launcher: wrap any URL in a 1-entry .m3u the OS hands to VLC ──
        # Browsers/OSes open .m3u files in the default media player (VLC on
        # most desktops). Mobile deep-link schemes handle the mobile case;
        # this endpoint is the desktop + generic-fallback path.
        elif path == "/api/vlc.m3u":
            target = qs.get("url", [""])[0]
            name   = qs.get("name", ["stream"])[0]
            if not target:
                self._error(400, "url required")
                return
            # If the client sent a relative path, anchor it to this server.
            if target.startswith("/"):
                host   = self.headers.get("Host", "")
                scheme = "https" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else "http"
                target = f"{scheme}://{host}{target}" if host else target
            body = ("#EXTM3U\n"
                    f"#EXTINF:-1,{name}\n"
                    f"{target}\n").encode("utf-8")
            safe_name = re.sub(r"[^\w.\-]", "_", name) or "stream"
            self.send_response(200)
            self.send_header("Content-Type", "audio/x-mpegurl")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}.m3u"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        # ── DVR status & segment list ─────────────────────────────────────────
        elif path == "/dvr/status":
            if self.ctx.dvr_manager:
                self._json(self.ctx.dvr_manager.get_status())
            else:
                self._error(503, "DVR not available")

        elif path == "/dvr/segments":
            if self.ctx.dvr_manager:
                self._json(self.ctx.dvr_manager.get_segments())
            else:
                self._error(503, "DVR not available")

        # ── DVR HLS playlist (the only URL ExoPlayer needs) ───────────────────
        elif path == "/dvr/playlist.m3u8":
            if not self.ctx.dvr_manager:
                self._error(503, "DVR not available")
                return
            pl_path = self.ctx.dvr_manager.get_playlist_path()
            try:
                with open(pl_path, "rb") as f:
                    data = f.read()
            except OSError:
                self._error(404, "playlist not ready")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        # ── DVR segment file serving ──────────────────────────────────────────
        # Two forms supported:
        #   /dvr/seg_000123.ts       — ExoPlayer HLS (segments resolved relative to playlist.m3u8)
        #   /dvr/stream/seg_000123.ts — legacy/debug direct path
        elif path.startswith("/dvr/stream/") or re.match(r'^/dvr/seg_\d+\.ts$', path):
            seg_name = path.rsplit("/", 1)[-1]
            if not re.match(r'^seg_\d+\.ts$', seg_name):
                self._error(400, "invalid segment name")
                return
            self._serve_file_range(os.path.join(config.DVR_BUFFER_DIR, seg_name))

        # ── Kodi: M3U playlist with proxy URLs ────────────────────────────────
        elif path == "/kodi/playlist.m3u":
            self._serve_kodi_playlist(qs)

        # ── Kodi: XMLTV EPG guide ─────────────────────────────────────────────
        elif path == "/kodi/guide.xml":
            self._serve_kodi_xmltv()

        # ── Live HLS for in-progress recordings ──────────────────────────────
        elif path.startswith("/recordings/live/"):
            self._serve_recording_live(path)

        # ── Completed recordings list ─────────────────────────────────────────
        elif path == "/recordings" or path == "/recordings/":
            ua = self.headers.get("User-Agent", "")
            print(f"[Recordings] List request from UA: {ua!r}")
            recordings = self._list_recordings()
            # Always return HTML - more compatible with Kodi and browsers
            self._serve_recordings_html(recordings)

        # ── Completed recording file serving ──────────────────────────────────
        elif path.startswith("/recordings/"):
            file_name = unquote(path[len("/recordings/"):])
            ua = self.headers.get("User-Agent", "")
            print(f"[Recordings] File request: {file_name!r} UA: {ua!r}")
            if not file_name or "/" in file_name or ".." in file_name:
                print(f"[Recordings] Invalid filename: {file_name}")
                self._error(400, "invalid filename")
                return
            rec_dir = self.ctx.get_recordings_dir() if self.ctx.get_recordings_dir else None
            print(f"[Recordings] Recordings dir: {rec_dir}")
            if not rec_dir:
                print(f"[Recordings] ERROR: Recordings directory not configured")
                self._error(503, "recordings directory not configured")
                return
            file_path = os.path.join(rec_dir, file_name)
            print(f"[Recordings] Full path: {file_path}, exists: {os.path.exists(file_path)}")
            if not os.path.exists(file_path):
                self._error(404, "file not found")
                return
            self._serve_file_range(file_path, cors=True)

        else:
            self.send_response(404)
            self.end_headers()

    def do_HEAD(self):
        """Handle HEAD requests — Kodi uses these to get file sizes before playback."""
        path = urlparse(self.path).path
        if path.startswith("/recordings/live/"):
            self.send_response(200)
            self.end_headers()
            return
        if path.startswith("/recordings/"):
            file_name = unquote(path[len("/recordings/"):])
            if not file_name or "/" in file_name or ".." in file_name:
                self.send_response(400)
                self.end_headers()
                return
            rec_dir = self.ctx.get_recordings_dir() if self.ctx.get_recordings_dir else None
            if not rec_dir:
                self.send_response(503)
                self.end_headers()
                return
            file_path = os.path.join(rec_dir, file_name)
            if not os.path.exists(file_path):
                self.send_response(404)
                self.end_headers()
                return
            file_size = os.path.getsize(file_path)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp2t")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
        else:
            self.send_response(200)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}
        path   = urlparse(self.path).path

        # ── Legacy remote-control actions ────────────────────────────────────
        if path == "/api/schedule":
            self.ctx.action_queue.put({"type": "schedule", **body})
            ch   = body.get("channel_name", "")
            st   = body.get("start_time", "")
            msg  = f"Started: {ch}" if st == "NOW" else f"Scheduled: {ch} at {st}"
            self._json({"message": msg})

        elif path == "/api/stop":
            self.ctx.action_queue.put({"type": "stop", "index": body.get("index", 0)})
            self._json({"message": "Stop requested."})

        elif path == "/api/favorites/add":
            self.ctx.action_queue.put({"type": "fav_add", "name": body.get("name"), "id": body.get("id")})
            self._json({"ok": True})

        elif path == "/api/favorites/remove":
            self.ctx.action_queue.put({"type": "fav_remove", "name": body.get("name")})
            self._json({"ok": True})

        elif path == "/api/backup/set":
            self.ctx.action_queue.put({"type": "backup_set", "id": body.get("id"), "name": body.get("name")})
            self._json({"message": f"Backup channel set to: {body.get('name')}"})

        elif path == "/api/backup/clear":
            self.ctx.action_queue.put({"type": "backup_clear"})
            self._json({"message": "Backup channel cleared"})

        # ── Android TV: record now (alias for schedule NOW) ───────────────────
        elif path == "/api/record":
            body.setdefault("start_time", "NOW")
            self.ctx.action_queue.put({"type": "schedule", **body})
            self._json({"message": f"Started: {body.get('channel_name', '')}"})

        # ── DVR control ───────────────────────────────────────────────────────
        elif path == "/dvr/start":
            if not self.ctx.dvr_manager:
                self._error(503, "DVR not available")
                return
            channel_id   = body.get("channel_id", "")
            channel_name = body.get("channel_name", channel_id)
            if not channel_id:
                self._error(400, "channel_id required")
                return
            self.ctx.dvr_manager.start(channel_id, channel_name)
            self._json({"ok": True, "channel": channel_name})

        elif path == "/dvr/stop":
            if not self.ctx.dvr_manager:
                self._error(503, "DVR not available")
                return
            self.ctx.dvr_manager.stop()
            self._json({"ok": True})

        # ── Web remote: Live DVR (ephemeral HLS buffer) ───────────────────────
        elif path == "/api/preview/start":
            channel_id = (body.get("channel_id") or "").strip()
            if not channel_id:
                self._error(400, "channel_id required")
                return
            if not self.ctx.preview_start:
                self._error(503, "live preview not available")
                return
            self._json(self.ctx.preview_start(channel_id))

        elif path == "/api/preview/stop":
            preview_id = body.get("preview_id")
            if not self.ctx.preview_stop:
                self._error(503, "live preview not available")
                return
            self._json(self.ctx.preview_stop(preview_id))

        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path.startswith("/api/recordings/"):
            filename = unquote(path[len("/api/recordings/"):])
            if not filename or "/" in filename or ".." in filename or not filename.endswith(".ts"):
                self._error(400, "invalid filename")
                return
            rec_dir = self.ctx.get_recordings_dir() if self.ctx.get_recordings_dir else None
            if not rec_dir:
                self._error(503, "recordings directory not configured")
                return
            file_path = os.path.join(rec_dir, filename)
            if not os.path.isfile(file_path):
                self._error(404, "file not found")
                return
            try:
                os.remove(file_path)
            except OSError as e:
                self._error(500, f"delete failed: {e}")
                return
            _RecordingHlsCache.evict(filename)
            self._json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _html(self, content: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _error(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def _serve_file_range(self, path: str, content_type: str = "video/mp2t", cors: bool = False) -> None:
        """Serve a file with full HTTP range-request support (required for ExoPlayer)."""
        try:
            file_size = os.path.getsize(path)
        except OSError:
            self.send_response(404)
            self.end_headers()
            return

        range_header = self.headers.get("Range", "")

        if not range_header:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            if cors:
                self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        # Parse "bytes=start-end"
        try:
            spec      = range_header.replace("bytes=", "").strip()
            start_str, end_str = spec.split("-", 1)
            start = int(start_str) if start_str else 0
            end   = int(end_str)   if end_str   else file_size - 1
            end   = min(end, file_size - 1)
            if start < 0 or start > end:
                raise ValueError
        except Exception:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{file_size}")
            self.end_headers()
            return

        length = end - start + 1
        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Accept-Ranges", "bytes")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _proxy_live_stream(self, channel_id: str) -> None:
        """
        Fetch the IPTV stream on behalf of the client and pipe bytes through.
        Uses StreamMuxer to share provider connections across multiple clients.
        """
        # Try to add this client to the multiplexed stream
        if _stream_muxer.add_client(channel_id, self):
            # Client successfully added - stream is being handled by muxer
            # Just keep connection alive until client disconnects
            try:
                while True:
                    # Check if we're still in the client list
                    import time
                    time.sleep(1)
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                _stream_muxer.remove_client(channel_id, self)
        else:
            # Muxer failed to connect - fall back to direct proxy
            stream_url = (
                f"{config.SERVER_URL.rstrip('/')}"
                f"/live/{config.USERNAME}/{config.PASSWORD}/{channel_id}.ts"
            )
            try:
                with requests.get(stream_url, stream=True, timeout=10) as r:
                    self.send_response(r.status_code if r.status_code == 200 else 502)
                    if r.status_code == 200:
                        self.send_header("Content-Type", "video/mp2t")
                        self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    if r.status_code == 200:
                        for chunk in r.iter_content(chunk_size=65536):
                            if chunk:
                                try:
                                    self.wfile.write(chunk)
                                except (BrokenPipeError, ConnectionResetError):
                                    break
            except Exception:
                try:
                    self.send_response(502)
                    self.end_headers()
                except Exception:
                    pass

    def _serve_recording_live(self, path: str):
        parts = path.split("/")
        # /recordings/live/{job_id}/filename → 5 parts after split
        if len(parts) != 5:
            self._error(404, "not found")
            return
        _, _, _, job_id_str, filename = parts
        if not re.match(r'^(playlist\.m3u8|seg_\d+\.ts)$', filename):
            self._error(404, "not found")
            return
        live_dir  = os.path.join(config.DVR_BUFFER_DIR, f"live_{job_id_str}")
        file_path = os.path.join(live_dir, filename)
        if not os.path.exists(file_path):
            self._error(404, "not found")
            return
        if filename.endswith(".m3u8"):
            try:
                with open(file_path, "rb") as f:
                    data = f.read()
            except OSError:
                self._error(404, "not found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self._serve_file_range(file_path)

    # ── Mobile transcode serving ────────────────────────────────────────────
    def _serve_mobile_playlist(self, channel_id: str, profile: str) -> None:
        """
        Ensure a transcode session is running, wait briefly for it to warm
        up, then serve the HLS playlist. Rewrites segment URLs to a same-
        origin path that the segment endpoint can parse.
        """
        sess = mobile_transcode_manager.ensure_session(channel_id, profile)
        if sess is None:
            self._error(503, "transcoder at capacity, try again shortly")
            return
        if not mobile_transcode_manager.wait_for_playlist(sess):
            self._error(504, "transcoder warmup timeout")
            return

        pl_path = os.path.join(sess.dir, "index.m3u8")
        try:
            with open(pl_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except OSError:
            self._error(404, "playlist not ready")
            return

        # Rewrite bare "seg_NNNNN.ts" lines to an absolute same-origin path
        # the segment endpoint can route to the right session.
        prefix = f"/api/stream/mobile/{channel_id}/{profile}/"
        rewritten_lines = []
        for line in raw.splitlines():
            if line and not line.startswith("#") and line.endswith(".ts"):
                rewritten_lines.append(prefix + line.strip())
            else:
                rewritten_lines.append(line)
        body = ("\n".join(rewritten_lines) + "\n").encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_mobile_segment(self, path: str) -> None:
        """Serve a single .ts segment from a running transcode session."""
        # Expected: /api/stream/mobile/<channel_id>/<profile>/seg_NNNNN.ts
        m = re.match(
            r"^/api/stream/mobile/([^/]+)/([^/]+)/(seg_\d+\.ts)$",
            path,
        )
        if not m:
            self._error(404, "not found")
            return
        channel_id, profile, seg_name = m.group(1), m.group(2), m.group(3)

        sess = mobile_transcode_manager.ensure_session(channel_id, profile)
        if sess is None:
            self._error(503, "transcoder at capacity")
            return
        mobile_transcode_manager.touch(channel_id, profile)

        seg_path = os.path.join(sess.dir, seg_name)
        # Segment may not exist yet if client raced ahead — wait for temp_file rename
        for _ in range(50):
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 0:
                break
            time.sleep(0.1)
        if not os.path.exists(seg_path):
            self._error(404, "segment not found")
            return
        self._serve_file_range(seg_path)

    def _list_recordings(self) -> list:
        if not self.ctx.get_recordings_dir:
            return []
        rec_dir = self.ctx.get_recordings_dir()
        if not rec_dir or not os.path.isdir(rec_dir):
            return []
        result = []
        for path in sorted(glob.glob(os.path.join(rec_dir, "*.ts"))):
            try:
                stat = os.stat(path)
                result.append({
                    "filename":    os.path.basename(path),
                    "size_bytes":  stat.st_size,
                    "recorded_at": _json_iso_utc(datetime.datetime.fromtimestamp(stat.st_mtime)),
                })
            except OSError:
                pass
        return result

    def _serve_recordings_html(self, recordings: list):
        """Serve HTML directory listing for Kodi browser compatibility."""
        lines = [
            "<!DOCTYPE html>",
            "<html><head><title>ELITE IPTV DVR Recordings</title></head>",
            "<body><h1>Recordings</h1><ul>"
        ]
        # Prepend live recordings (in-progress jobs with active HLS)
        if self.ctx.get_jobs:
            for job in self.ctx.get_jobs():
                if job.status == "recording" and getattr(job, "live_dir", None):
                    label = f"🔴 LIVE — {job.channel_name}"
                    href  = f"live/{job.id}/playlist.m3u8"
                    lines.append(f'<li><a href="{href}">{label}</a></li>')
        for rec in recordings:
            filename = rec["filename"]
            from urllib.parse import quote
            size_mb = rec["size_bytes"] / (1024 * 1024)
            recorded = rec["recorded_at"][:19].replace("T", " ")  # Format: YYYY-MM-DD HH:MM:SS
            lines.append(f'<li><a href="{quote(filename)}">{filename}</a> ({size_mb:.1f} MB) - {recorded}</li>')
        lines.append("</ul></body></html>")
        html = "\n".join(lines)

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        try:
            self.wfile.write(html.encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_recording_hls(self, path: str) -> None:
        """
        Serve a completed recording as HLS.

        AAC audio  → instant byterange VOD playlist (fast, no transcode).
        Other audio → progressive ffmpeg remux via _RecordingHlsCache which
                      transcodes AC3/MP2/etc to AAC so Chrome can play it.

        URL structure:
          /api/recordings/hls/<url-encoded-filename>/index.m3u8   — playlist
          /api/recordings/hls/<url-encoded-filename>/seg_NNNNN.ts — segments (remux only)
        """
        stripped = path[len("/api/recordings/hls/"):]
        slash    = stripped.rfind("/")
        if slash < 0:
            self._error(400, "Bad path"); return
        filename = unquote(stripped[:slash])
        leaf     = stripped[slash + 1:]

        if not filename or not leaf:
            self._error(400, "Bad path"); return
        if ".." in filename or "/" in filename or "\\" in filename:
            self._error(400, "Invalid filename"); return

        rec_dir = self.ctx.get_recordings_dir() if self.ctx.get_recordings_dir else None
        if not rec_dir:
            self._error(503, "Recordings dir not configured"); return

        ts_path = os.path.join(rec_dir, filename)
        if not os.path.isfile(ts_path):
            self._error(404, f"Recording not found: {filename}"); return

        audio_codec  = _probe_recording_audio_codec(ts_path)
        needs_remux  = audio_codec != "aac"  # AC3, MP2, unknown → transcode

        # ── Remux path (non-AAC audio) ────────────────────────────────────────
        # Strategy: generate a fake-complete VOD playlist immediately (after
        # waiting only for the first segment, ~3-5s), so hls.js treats the
        # stream as seekable VOD from the start.  Segment requests block until
        # ffmpeg writes the requested file — at 50-100× realtime the encoder
        # is always well ahead of normal playback.  Seeking near the end of a
        # long recording while still transcoding may stall briefly; that's the
        # only tradeoff vs waiting for full completion.
        if needs_remux:
            if leaf == "index.m3u8":
                sess = _RecordingHlsCache.get_or_start(filename, ts_path)
                ready = _RecordingHlsCache.wait_for_startup(sess, timeout=45.0)
                if not ready or sess.failed:
                    self._error(503, f"Remux failed: {sess.error_tail[:200]}"); return

                # Build a synthetic complete VOD playlist from the probed duration.
                # All segment durations are estimated at seg_dur; the final segment
                # uses the remainder.  hls.js tolerates minor EXTINF drift.
                try:
                    file_size = os.path.getsize(ts_path)
                except OSError:
                    file_size = 0
                dur = _probe_recording_duration(ts_path)
                if dur is None or dur <= 0:
                    dur = file_size * 8 / 4_000_000
                seg_dur   = 6.0
                n_segs    = max(1, int(math.ceil(dur / seg_dur)))
                tgt_dur   = int(math.ceil(seg_dur)) + 1  # headroom for GOP-aligned splits
                lines = [
                    "#EXTM3U",
                    "#EXT-X-VERSION:3",
                    "#EXT-X-PLAYLIST-TYPE:VOD",
                    f"#EXT-X-TARGETDURATION:{tgt_dur}",
                    "#EXT-X-MEDIA-SEQUENCE:0",
                ]
                for i in range(n_segs):
                    this_dur = seg_dur if i < n_segs - 1 else max(0.001, dur - i * seg_dur)
                    lines.append(f"#EXTINF:{this_dur:.6f},")
                    lines.append(f"seg_{i:05d}.ts")
                lines.append("#EXT-X-ENDLIST")
                data = ("\n".join(lines) + "\n").encode()

                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif leaf == "status":
                # Progress endpoint polled by the player UI.
                # Returns {pct: 0-100, done: bool, codec: str}
                sess  = _RecordingHlsCache._sessions.get(filename)
                codec = _probe_recording_audio_codec(ts_path) or "unknown"
                if sess is None:
                    result = {"pct": 0, "done": False, "codec": codec}
                elif sess.failed:
                    result = {"pct": -1, "done": True, "codec": codec}
                elif sess.completed:
                    result = {"pct": 100, "done": True, "codec": codec}
                else:
                    dur = _probe_recording_duration(ts_path) or 0
                    n_expected = max(1, int(math.ceil(dur / 6.0)))
                    try:
                        n_done = len(glob.glob(os.path.join(sess.outdir, "seg_*.ts")))
                    except Exception:
                        n_done = 0
                    result = {"pct": min(99, int(100 * n_done / n_expected)),
                              "done": False, "codec": codec}
                data = json.dumps(result).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif re.match(r'^seg_\d+\.ts$', leaf):
                sess = _RecordingHlsCache._sessions.get(filename)
                if not sess:
                    sess = _RecordingHlsCache.get_or_start(filename, ts_path)
                    _RecordingHlsCache.wait_for_startup(sess)
                seg_path = os.path.join(sess.outdir, leaf)
                # Block until ffmpeg writes this segment (up to 30s).
                deadline = time.time() + 30
                while not os.path.isfile(seg_path) and time.time() < deadline:
                    if sess.failed:
                        self._error(503, "Remux failed"); return
                    time.sleep(0.2)
                if not os.path.isfile(seg_path):
                    self._error(404, f"Segment not ready: {leaf}"); return
                try:
                    with open(seg_path, "rb") as f:
                        data = f.read()
                except OSError as exc:
                    self._error(500, f"Could not read segment: {exc}"); return
                self.send_response(200)
                self.send_header("Content-Type", "video/MP2T")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=31536000")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self._error(400, "Invalid leaf")
            return

        # ── Byterange path (AAC audio — instant, no transcode) ────────────────
        if leaf != "index.m3u8":
            self._error(400, "Invalid leaf"); return

        try:
            file_size = os.path.getsize(ts_path)
        except OSError as exc:
            self._error(500, f"Stat failed: {exc}"); return

        dur = _probe_recording_duration(ts_path)
        if dur is None or dur <= 0:
            dur = file_size * 8 / 4_000_000
            print(f"[RecHLS] ffprobe unavailable for '{filename}', estimating {dur:.1f}s")

        seg_dur    = 6.0
        n_segs     = max(1, int(math.ceil(dur / seg_dur)))
        bps        = file_size / dur
        ts_url     = f"/recordings/{urllib.parse.quote(filename, safe='')}"
        target_dur = int(math.ceil(seg_dur))

        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:4",
            "#EXT-X-PLAYLIST-TYPE:VOD",
            f"#EXT-X-TARGETDURATION:{target_dur}",
            "#EXT-X-MEDIA-SEQUENCE:0",
        ]
        for i in range(n_segs):
            seg_start = int(i * seg_dur * bps)
            if i < n_segs - 1:
                seg_end  = int((i + 1) * seg_dur * bps)
                seg_len  = seg_end - seg_start
                this_dur = seg_dur
            else:
                seg_len  = file_size - seg_start
                this_dur = dur - i * seg_dur
            if seg_len <= 0:
                break
            lines.append(f"#EXTINF:{this_dur:.6f},")
            lines.append(f"#EXT-X-BYTERANGE:{seg_len}@{seg_start}")
            lines.append(ts_url)
        lines.append("#EXT-X-ENDLIST")

        data = ("\n".join(lines) + "\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _build_recordings_response(self) -> dict:
        """
        Structured recordings list for the mobile webapp + Android TV.

        Returns:
          active[]    — in-progress/waiting jobs, with live_hls_url for watch-while-recording
          recent[]    — finished/error/stopped jobs still held in memory
          completed[] — all .ts files on disk (NAS recordings folder), newest first
        """
        now    = datetime.datetime.now()
        active = []
        recent = []
        active_filenames = set()  # basenames currently being written
        if self.ctx.get_jobs:
            for i, job in enumerate(self.ctx.get_jobs()):
                if job.status in ("waiting", "recording"):
                    entry = {
                        "index":        i,
                        "job_id":       getattr(job, "id", None),
                        "channel_name": job.channel_name,
                        "status":       job.status,
                    }
                    if job.actual_start:
                        elapsed = int((now - job.actual_start).total_seconds())
                        entry["elapsed_secs"]   = elapsed
                        entry["remaining_secs"] = max(0, job_duration_secs(job) - elapsed)
                        entry["started_at"]     = _json_iso_utc(job.actual_start)
                    entry["duration_secs"]    = job_duration_secs(job)
                    if getattr(job, "start_time", None):
                        entry["scheduled_start"] = _json_iso_utc(job.start_time)
                        entry["scheduled_end"]   = _json_iso_utc(
                            job.start_time + datetime.timedelta(seconds=job_duration_secs(job))
                        )
                    if job.output_file:
                        fn = os.path.basename(job.output_file)
                        entry["output_file"] = fn
                        entry["ts_url"]      = f"/recordings/{fn}"
                        active_filenames.add(fn)
                    if getattr(job, "live_dir", None):
                        entry["live_hls_url"] = f"/recordings/live/{job.id}/playlist.m3u8"
                    active.append(entry)
                else:
                    _labels = {
                        "complete": "Recording complete.",
                        "error":    "Error encountered.",
                        "stopped":  "Stopped by user.",
                    }
                    recent.append({
                        "channel_name": job.channel_name,
                        "status":       job.status,
                        "status_text":  _labels.get(job.status, job.status),
                    })

        # Completed files on disk (newest first). Exclude files that are
        # still being written by an active job — those appear in active[]
        # with the live_hls_url instead.
        completed = []
        for rec in sorted(self._list_recordings(), key=lambda r: r["recorded_at"], reverse=True):
            fn = rec["filename"]
            if fn in active_filenames:
                continue
            abs_url = f"/recordings/{fn}"
            from urllib.parse import quote as _q
            ts_path = os.path.join(self.ctx.get_recordings_dir(), fn)
            entry = {
                "filename":      fn,
                "size_bytes":    rec["size_bytes"],
                "recorded_at":   rec["recorded_at"],
                "ts_url":        abs_url,
                "download_url":  abs_url,
                # HLS remux URL — the server will convert to HLS on first fetch.
                "hls_url":       f"/api/recordings/hls/{_q(fn)}/index.m3u8",
                # VLC deep links — absolute path; the client fills in the host
                # via window.location.origin before use.
                "vlc_path":      f"/recordings/{_q(fn)}",
            }
            dur = _probe_recording_duration(ts_path)
            if dur is not None:
                entry["duration_secs"] = dur
            completed.append(entry)

        return {"active": active, "recent": recent, "completed": completed}

    def _serve_kodi_playlist(self, qs: dict):
        """Generate M3U playlist with proxy URLs for Kodi."""
        trimmed_m3u = getattr(config, "TRIMMED_M3U_PATH", "").strip()
        if trimmed_m3u and os.path.exists(trimmed_m3u):
            try:
                with open(trimmed_m3u, "rb") as f:
                    data = f.read()
                if data[:2] == b"\x1f\x8b":
                    import gzip
                    data = gzip.decompress(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            except Exception as exc:
                print(f"[Kodi] Failed to read trimmed M3U: {exc}; falling back to generated playlist")

        ip = self._local_ip()
        port = config.WEB_PORT

        # Get optional category filter
        category_id = qs.get("category_id", [""])[0].strip()

        # Get channels - try get_all_channels first, fall back to direct API fetch
        channels = []
        if self.ctx.get_all_channels:
            try:
                channels = self.ctx.get_all_channels()
            except Exception:
                pass

        # If a category filter is requested, apply it to any cached channel list too.
        if category_id and channels:
            filtered = []
            for ch in channels:
                ch_category_id = str(ch.get("category_id", "") or "")
                if ch_category_id == category_id:
                    filtered.append(ch)
            channels = filtered

        # If no channels from context, fetch directly from provider API
        if not channels:
            try:
                url = (
                    f"{config.SERVER_URL}/player_api.php"
                    f"?username={config.USERNAME}&password={config.PASSWORD}"
                    f"&action=get_live_streams"
                )
                if category_id:
                    url += f"&category_id={category_id}"
                streams = requests.get(url, timeout=15).json()
                channels = [
                    {
                        "id": str(s["stream_id"]),
                        "name": s.get("name", ""),
                        "stream_icon": s.get("stream_icon", ""),
                        "epg_channel_id": s.get("epg_channel_id", ""),
                    }
                    for s in streams if s.get("stream_id")
                ]
            except Exception as exc:
                print(f"[Kodi] Failed to fetch channels: {exc}")
                self._error(503, "Failed to fetch channel list")
                return

        # Check for DVR mode query param
        dvr_mode = qs.get("dvr", [""])[0].lower() in {"1", "true", "yes"}

        # Build M3U content
        lines = ["#EXTM3U"]
        for ch in channels:
            ch_id = ch.get("id", "")
            name = ch.get("name", ch_id)
            icon = ch.get("stream_icon", "")
            tvg_id = ch.get("epg_channel_id", ch_id)

            # tvg-name and group-title for Kodi PVR
            icon_attr = f' tvg-logo="{icon}"' if icon else ""
            lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}" group-title="Live TV"{icon_attr},{name}')

            if dvr_mode:
                # DVR HLS playlist URL
                lines.append(f"http://{ip}:{port}/dvr/playlist.m3u8")
            else:
                # Direct proxy URL
                lines.append(f"http://{ip}:{port}/api/stream/live?channel_id={ch_id}")

        m3u_content = "\n".join(lines)

        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl")
        self.send_header("Content-Length", str(len(m3u_content)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(m3u_content.encode("utf-8"))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_kodi_xmltv(self):
        """Serve cached XMLTV file for Kodi EPG."""
        trimmed_xmltv = getattr(config, "TRIMMED_XMLTV_PATH", "").strip()
        if trimmed_xmltv and os.path.exists(trimmed_xmltv):
            try:
                with open(trimmed_xmltv, "rb") as f:
                    data = f.read()
                if data[:2] == b"\x1f\x8b":
                    import gzip
                    data = gzip.decompress(data)
                self.send_response(200)
                self.send_header("Content-Type", "application/xml")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            except Exception as exc:
                print(f"[Kodi] Failed to read trimmed XMLTV: {exc}; falling back to cached/remote XMLTV")

        # Try to return the cached XMLTV file directly
        cache_path = config.XMLTV_CACHE_PATH

        if os.path.exists(cache_path):
            try:
                with open(cache_path, "rb") as f:
                    data = f.read()
                # Decompress if gzipped
                if data[:2] == b"\x1f\x8b":
                    import gzip
                    data = gzip.decompress(data)
            except Exception as exc:
                print(f"[Kodi] Failed to read cached XMLTV: {exc}")
                self._error(503, "Failed to read EPG data")
                return
        else:
            # No cache - fetch fresh
            try:
                url = (
                    f"{config.SERVER_URL}/xmltv.php"
                    f"?username={config.USERNAME}&password={config.PASSWORD}"
                )
                if config.XMLTV_SOURCE_URL:
                    url = config.XMLTV_SOURCE_URL
                r = requests.get(url, timeout=60)
                data = r.content
                if data[:2] == b"\x1f\x8b":
                    import gzip
                    data = gzip.decompress(data)
            except Exception as exc:
                print(f"[Kodi] Failed to fetch XMLTV: {exc}")
                self._error(503, "Failed to fetch EPG data")
                return

        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    @staticmethod
    def _local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect_ex(("192.168.1.1", 80))
            return s.getsockname()[0]
        except Exception:
            return "localhost"

    def log_message(self, *args):
        pass  # suppress per-request console spam


def _auto_cleanup_recordings(get_recordings_dir, max_age_days: int = 7) -> None:
    """Delete .ts files older than max_age_days. Runs hourly in a daemon thread."""
    time.sleep(30)  # let the server finish startup before first scan
    while True:
        rec_dir = get_recordings_dir() if callable(get_recordings_dir) else None
        if rec_dir and os.path.isdir(rec_dir):
            cutoff = time.time() - max_age_days * 86400
            for fname in os.listdir(rec_dir):
                if not fname.endswith(".ts"):
                    continue
                fpath = os.path.join(rec_dir, fname)
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        _RecordingHlsCache.evict(fname)
                        print(f"[AutoClean] Deleted {fname} (>{max_age_days}d old)")
                except OSError:
                    pass
        time.sleep(3600)


def start_web_server(ctx: WebContext) -> str:
    """
    Start the HTTP server on config.WEB_PORT.
    Returns the local LAN URL (http://192.168.x.x:PORT).
    Raises OSError if the port is already in use.
    """
    RemoteHandler.ctx = ctx
    server = ThreadingHTTPServer(("0.0.0.0", config.WEB_PORT), RemoteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if ctx.get_recordings_dir:
        threading.Thread(
            target=_auto_cleanup_recordings,
            args=(ctx.get_recordings_dir,),
            daemon=True,
        ).start()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect_ex(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"

    return f"http://{ip}:{config.WEB_PORT}"
