"""
core/web_server.py — HTTP server and all endpoint routing.

RemoteHandler never imports from ui/ — it talks to the app only
through a WebContext object set before the server starts.
"""

import datetime
import glob
import json
import os
import re
import socket
import threading

import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import config

# DVRManager imported for type hints only; no circular dependency risk.
from core.dvr_manager import DVRManager
from core.epg import build_guide_bundle, fetch_epg, fetch_multi_epg


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
                listings = fetch_epg(config.SERVER_URL, config.USERNAME, config.PASSWORD, channel_id, limit=12)
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
                self._json([
                    {"category_id": c.get("category_id", ""), "category_name": c.get("category_name", "")}
                    for c in cats if c.get("category_name")
                ])
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
            limit   = int(qs.get("limit", ["6"])[0])
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

        # ── Completed recordings list ─────────────────────────────────────────
        elif path == "/recordings":
            self._json(self._list_recordings())

        # ── Completed recording file serving ──────────────────────────────────
        elif path.startswith("/recordings/"):
            file_name = path[len("/recordings/"):]
            if not file_name or "/" in file_name or ".." in file_name:
                self._error(400, "invalid filename")
                return
            rec_dir = self.ctx.get_recordings_dir() if self.ctx.get_recordings_dir else None
            if not rec_dir:
                self._error(503, "recordings directory not configured")
                return
            self._serve_file_range(os.path.join(rec_dir, file_name))

        else:
            self.send_response(404)
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

    def _serve_file_range(self, path: str, content_type: str = "video/mp2t") -> None:
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
        """Fetch the IPTV stream on behalf of the client and pipe bytes through."""
        stream_url = (
            f"{config.SERVER_URL.rstrip('/')}"
            f"/live/{config.USERNAME}/{config.PASSWORD}/{channel_id}.ts"
        )
        try:
            with requests.get(stream_url, stream=True, timeout=10) as r:
                self.send_response(200)
                self.send_header("Content-Type", "video/mp2t")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
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
                    "recorded_at": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except OSError:
                pass
        return result

    def _build_recordings_response(self) -> dict:
        if not self.ctx.get_jobs:
            return {"active": [], "recent": []}
        now    = datetime.datetime.now()
        active = []
        recent = []
        for i, job in enumerate(self.ctx.get_jobs()):
            if job.status in ("waiting", "recording"):
                entry = {
                    "index":        i,
                    "channel_name": job.channel_name,
                    "status":       job.status,
                }
                if job.actual_start:
                    elapsed = int((now - job.actual_start).total_seconds())
                    entry["elapsed_secs"]   = elapsed
                    entry["remaining_secs"] = max(0, job.duration_mins * 60 - elapsed)
                if job.output_file:
                    entry["output_file"] = os.path.basename(job.output_file)
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
        return {"active": active, "recent": recent}

    def _serve_kodi_playlist(self, qs: dict):
        """Generate M3U playlist with proxy URLs for Kodi."""
        ip = self._local_ip()
        port = config.WEB_PORT

        # Get channels - try get_all_channels first, fall back to direct API fetch
        channels = []
        if self.ctx.get_all_channels:
            try:
                channels = self.ctx.get_all_channels()
            except Exception:
                pass

        # If no channels from context, fetch directly from provider API
        if not channels:
            try:
                url = (
                    f"{config.SERVER_URL}/player_api.php"
                    f"?username={config.USERNAME}&password={config.PASSWORD}"
                    f"&action=get_live_streams"
                )
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
            lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}" group-title="Live TV"{f" tvg-logo=\"{icon}\"" if icon else ""},{name}')

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


def start_web_server(ctx: WebContext) -> str:
    """
    Start the HTTP server on config.WEB_PORT.
    Returns the local LAN URL (http://192.168.x.x:PORT).
    Raises OSError if the port is already in use.
    """
    RemoteHandler.ctx = ctx
    server = ThreadingHTTPServer(("0.0.0.0", config.WEB_PORT), RemoteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect_ex(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"

    return f"http://{ip}:{config.WEB_PORT}"
