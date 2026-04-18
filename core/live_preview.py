"""
live_preview.py — Ephemeral Live DVR (copy-HLS) preview sessions for the web remote.

Spawns a single FFmpeg that remuxes the provider feed to an event HLS playlist
under config.DVR_BUFFER_DIR/live_{id}/, served at /recordings/live/{id}/playlist.m3u8.
No companion .ts archive (preview_only). Stopping removes the buffer directory.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import threading
import time

import config

_PREVIEW_ID_LOCK = threading.Lock()
_PREVIEW_NEXT_ID = 900_000


class LivePreviewSession:
    """
    One background FFmpeg writing only HLS segments (same layout as in-recording live_hls).
    """

    def __init__(self, channel_id: str):
        global _PREVIEW_NEXT_ID
        with _PREVIEW_ID_LOCK:
            _PREVIEW_NEXT_ID += 1
            self.id = _PREVIEW_NEXT_ID
        self.channel_id = channel_id
        self.live_dir: str | None = None
        self.process: subprocess.Popen | None = None
        self.error: str | None = None
        self._failed = False
        self._user_stop = False
        self._done_event = threading.Event()

    def start(self) -> bool:
        """
        Start FFmpeg and block until the playlist + first segment exist or timeout.
        Returns False on failure (self.error is set).
        """
        os.makedirs(config.DVR_BUFFER_DIR, exist_ok=True)
        self.live_dir = os.path.join(config.DVR_BUFFER_DIR, f"live_{self.id}")
        os.makedirs(self.live_dir, exist_ok=True)

        stream_url = (
            f"{config.SERVER_URL.rstrip('/')}"
            f"/live/{config.USERNAME}/{config.PASSWORD}/{self.channel_id}.ts"
        )
        playlist = os.path.join(self.live_dir, "playlist.m3u8")
        seg_pat = os.path.join(self.live_dir, "seg_%06d.ts")

        cmd = [
            "ffmpeg",
            "-y",
            "-reconnect",
            "1",
            "-reconnect_at_eof",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
            "-timeout",
            "15000000",
            "-i",
            stream_url,
            "-c",
            "copy",
            "-f",
            "hls",
            "-hls_time",
            "4",
            "-hls_list_size",
            "0",
            "-hls_playlist_type",
            "event",
            "-hls_flags",
            "program_date_time",
            "-hls_segment_type",
            "mpegts",
            "-hls_segment_filename",
            seg_pat,
            playlist,
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                **config._SUBPROCESS_FLAGS,
            )
        except FileNotFoundError:
            self.error = "ffmpeg not found in PATH"
            self._failed = True
            self._cleanup_dir()
            return False
        except OSError as e:
            self.error = str(e)
            self._failed = True
            self._cleanup_dir()
            return False

        def _waiter():
            try:
                if self.process:
                    err = self.process.communicate()[1]
                    rc = self.process.returncode
                    if rc not in (0, None) and not self._user_stop:
                        tail = (err or b"")[-2000:].decode("utf-8", errors="replace")
                        self.error = tail.strip() or f"ffmpeg exited {rc}"
                        self._failed = True
            finally:
                self._done_event.set()

        threading.Thread(target=_waiter, daemon=True).start()

        deadline = time.time() + 25.0
        while time.time() < deadline:
            if self._failed or self.error:
                self._stop_internal()
                return False
            if self.process and self.process.poll() is not None:
                self.error = self.error or "ffmpeg exited before first segment"
                self._stop_internal()
                return False
            if os.path.exists(playlist):
                segs = glob.glob(os.path.join(self.live_dir, "seg_*.ts"))
                if any(os.path.exists(s) and os.path.getsize(s) > 0 for s in segs):
                    return True
            time.sleep(0.15)

        self.error = "timed out waiting for Live DVR buffer"
        self._stop_internal()
        return False

    def _stop_internal(self) -> None:
        self._user_stop = True
        proc = self.process
        self.process = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass
            t0 = time.time()
            while proc.poll() is None and time.time() - t0 < 8:
                time.sleep(0.1)
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
        self._cleanup_dir()

    def _cleanup_dir(self) -> None:
        if not self.live_dir:
            return
        try:
            for p in glob.glob(os.path.join(self.live_dir, "*")):
                try:
                    os.remove(p)
                except OSError:
                    pass
            os.rmdir(self.live_dir)
        except OSError:
            try:
                shutil.rmtree(self.live_dir, ignore_errors=True)
            except Exception:
                pass
        self.live_dir = None


class LivePreviewManager:
    """
    At most one active Live DVR preview (NAS-friendly). Starting a new preview
    stops the previous session.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current: LivePreviewSession | None = None

    def start(self, channel_id: str) -> dict:
        cid = (channel_id or "").strip()
        if not cid:
            return {"ok": False, "error": "channel_id required"}

        with self._lock:
            if self._current:
                self._current._stop_internal()
                self._current = None
            sess = LivePreviewSession(cid)
            self._current = sess

        if not sess.start():
            with self._lock:
                if self._current is sess:
                    self._current = None
            return {
                "ok": False,
                "error": sess.error or "Live DVR failed to start",
            }

        return {
            "ok": True,
            "preview_id": sess.id,
            "live_hls_url": f"/recordings/live/{sess.id}/playlist.m3u8",
        }

    def stop(self, preview_id) -> dict:
        """Idempotent stop by session id."""
        try:
            pid = int(preview_id)
        except (TypeError, ValueError):
            return {"ok": False, "error": "invalid preview_id"}

        with self._lock:
            if not self._current or self._current.id != pid:
                return {"ok": True}
            self._current._stop_internal()
            self._current = None
        return {"ok": True}

    def stop_all(self) -> None:
        with self._lock:
            if self._current:
                self._current._stop_internal()
                self._current = None
