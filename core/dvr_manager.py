"""
core/dvr_manager.py — Rolling DVR buffer manager.

DVRManager owns a single FFmpeg segment-mode process that writes 30-minute
.ts segments to dvr_buffer/. A cleanup thread enforces the hours and GB caps.

API used by web_server.py:
    mgr.start(channel_id, channel_name)
    mgr.stop()
    mgr.get_segments()  →  list[dict]
    mgr.get_status()    →  dict
"""

import datetime
import glob
import os
import subprocess
import threading
import time

import config


_SEGMENT_SECONDS = 1800   # 30-minute segments


class DVRJob:
    """Pure-data descriptor for the active DVR session."""

    def __init__(self, channel_id: str, channel_name: str):
        self.channel_id   = channel_id
        self.channel_name = channel_name
        self.status       = "starting"   # starting | buffering | stopped | error
        self.process      = None
        self.started_at   = datetime.datetime.now()
        self.error_msg    = None         # set when status == "error"


class DVRManager:
    """
    Manages a single rolling DVR buffer session.

    Thread-safe: start / stop / get_* may be called from any thread.
    Internal state is guarded by _lock; background threads are daemons.
    """

    def __init__(self):
        self._job  : DVRJob | None = None
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self, channel_id: str, channel_name: str) -> None:
        """Stop any current session, clear the buffer, start a fresh DVR session."""
        with self._lock:
            self._stop_locked()
            self._clear_buffer()

            os.makedirs(config.DVR_BUFFER_DIR, exist_ok=True)

            stream_url = (
                f"{config.SERVER_URL.rstrip('/')}"
                f"/live/{config.USERNAME}/{config.PASSWORD}/{channel_id}.ts"
            )
            seg_pattern = os.path.join(config.DVR_BUFFER_DIR, "seg_%03d.ts")

            cmd = [
                "ffmpeg", "-y",
                "-reconnect",        "1",
                "-reconnect_at_eof", "1",
                "-reconnect_streamed","1",
                "-reconnect_delay_max","5",
                "-timeout",          "15000000",
                "-i",                stream_url,
                "-f",                "segment",
                "-segment_time",     str(_SEGMENT_SECONDS),
                "-reset_timestamps", "1",
                "-c",                "copy",
                seg_pattern,
            ]

            job = DVRJob(channel_id, channel_name)
            try:
                job.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    **config._SUBPROCESS_FLAGS,
                )
                job.status = "buffering"
            except FileNotFoundError:
                job.status    = "error"
                job.error_msg = "ffmpeg not found in PATH"
            except Exception as e:
                job.status    = "error"
                job.error_msg = str(e)

            self._job = job

        if job.status == "buffering":
            threading.Thread(target=self._monitor_loop, args=(job,), daemon=True).start()
            threading.Thread(target=self._cleanup_loop, args=(job,), daemon=True).start()

    def stop(self) -> None:
        """Stop the current DVR session. Buffer files are preserved until next start()."""
        with self._lock:
            self._stop_locked()

    def get_segments(self) -> list[dict]:
        """
        Return available segments, oldest first.
        Each entry: {name, size_bytes, is_active}
        The last entry is always marked is_active=True (may still be growing).
        """
        paths = self._list_segment_paths()
        if not paths:
            return []
        result = []
        for i, path in enumerate(paths):
            result.append({
                "name":       os.path.basename(path),
                "size_bytes": self._safe_getsize(path),
                "is_active":  i == len(paths) - 1,
            })
        return result

    def get_status(self) -> dict:
        job = self._job
        max_bytes = int(config.DVR_MAX_GB * 1024 ** 3)

        if job is None or job.status == "stopped":
            return {
                "active":                  False,
                "channel":                 None,
                "status":                  "idle",
                "error":                   None,
                "buffer_age_secs":         0,
                "total_size_bytes":        0,
                "storage_remaining_bytes": max_bytes,
                "segment_count":           0,
            }

        paths = self._list_segment_paths()
        total = sum(self._safe_getsize(p) for p in paths)

        age_secs = 0
        if len(paths) >= 2:
            try:
                age_secs = int(
                    os.path.getmtime(paths[-1])
                    - os.path.getmtime(paths[0])
                    + _SEGMENT_SECONDS
                )
            except OSError:
                pass
        elif len(paths) == 1:
            try:
                age_secs = int(time.time() - os.path.getmtime(paths[0]))
            except OSError:
                pass

        return {
            "active":                  job.status == "buffering",
            "channel":                 job.channel_name,
            "status":                  job.status,
            "error":                   job.error_msg,
            "buffer_age_secs":         age_secs,
            "total_size_bytes":        total,
            "storage_remaining_bytes": max(0, max_bytes - total),
            "segment_count":           len(paths),
        }

    # ── Private ───────────────────────────────────────────────────────────────

    def _stop_locked(self) -> None:
        """Terminate the FFmpeg process. Must be called with self._lock held."""
        job = self._job
        if job is None:
            return
        # Mark stopped BEFORE terminating so _monitor_loop skips the error path.
        job.status = "stopped"
        self._job  = None
        if job.process:
            try:
                job.process.terminate()
                job.process.wait(timeout=5)
            except Exception:
                try:
                    job.process.kill()
                except Exception:
                    pass

    def _clear_buffer(self) -> None:
        buf = config.DVR_BUFFER_DIR
        if not os.path.isdir(buf):
            return
        for path in glob.glob(os.path.join(buf, "seg_*.ts")):
            try:
                os.remove(path)
            except OSError:
                pass

    def _monitor_loop(self, job: DVRJob) -> None:
        """Block until FFmpeg exits; surface an error if it exits unexpectedly."""
        if not job.process:
            return
        try:
            _, stderr_bytes = job.process.communicate()
        except Exception:
            return

        with self._lock:
            # Only set error if this job is still the active one AND still running.
            if self._job is job and job.status == "buffering":
                job.status = "error"
                if stderr_bytes:
                    tail  = stderr_bytes[-2048:].decode("utf-8", errors="replace")
                    lines = [l.strip() for l in tail.splitlines() if l.strip()]
                    job.error_msg = lines[-1] if lines else "ffmpeg exited unexpectedly"
                else:
                    job.error_msg = "ffmpeg exited unexpectedly"

    def _cleanup_loop(self, job: DVRJob) -> None:
        """Enforce caps every 60 s while this job is the active buffering session."""
        while True:
            time.sleep(60)
            with self._lock:
                if self._job is not job or job.status != "buffering":
                    return
            self._enforce_caps()

    def _enforce_caps(self) -> None:
        """
        Delete oldest segments to stay within DVR_MAX_HOURS and DVR_MAX_GB.
        The last segment (actively being written) is never deleted.
        """
        paths = self._list_segment_paths()
        if len(paths) < 2:
            return

        # Candidates = everything except the active (last) segment.
        candidates = list(paths[:-1])

        # Hours cap: max segments = total allowed hours / segment length
        max_segs = (config.DVR_MAX_HOURS * 3600) // _SEGMENT_SECONDS
        while len(candidates) >= max_segs:
            try:
                os.remove(candidates.pop(0))
            except OSError:
                pass

        # GB cap
        all_remaining = candidates + [paths[-1]]
        total     = sum(self._safe_getsize(p) for p in all_remaining)
        max_bytes = int(config.DVR_MAX_GB * 1024 ** 3)
        while total > max_bytes and candidates:
            path   = candidates.pop(0)
            total -= self._safe_getsize(path)
            try:
                os.remove(path)
            except OSError:
                pass

    def _list_segment_paths(self) -> list[str]:
        buf = config.DVR_BUFFER_DIR
        if not os.path.isdir(buf):
            return []
        return sorted(glob.glob(os.path.join(buf, "seg_*.ts")))

    @staticmethod
    def _safe_getsize(path: str) -> int:
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
