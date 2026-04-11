"""
core/dvr_manager.py — Rolling DVR buffer manager (HLS mode).

DVRManager spawns an FFmpeg `-f hls` process that produces a rolling
`playlist.m3u8` + 2-second `.ts` segments in dvr_buffer/. FFmpeg itself
maintains the playlist window via `hls_list_size + delete_segments`, so
the m3u8 is served directly to ExoPlayer as a live HLS stream — ExoPlayer
then handles live edge, seamless segment transitions, and rebuffering.

API used by web_server.py:
    mgr.start(channel_id, channel_name)
    mgr.stop()
    mgr.get_playlist_path() -> str
    mgr.get_segments()      -> list[dict]   (debug only)
    mgr.get_status()        -> dict
"""

import datetime
import glob
import os
import subprocess
import sys
import threading
import time

import config


_SEGMENT_SECONDS  = 4                  # 4-second HLS segments — must match force_key_frames interval below
_PLAYLIST_NAME    = "playlist.m3u8"
# Manifest lists only the last 5 minutes of segments. Older segments stay on
# disk for DVR rewind, but the live playback window is always tight so every
# listed segment is guaranteed to exist.
_HLS_LIST_SIZE    = (5 * 60) // _SEGMENT_SECONDS   # = 75 segments


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
        """Stop any current session, clear the buffer, start a fresh HLS session."""
        with self._lock:
            self._stop_locked()
            self._clear_buffer()

            os.makedirs(config.DVR_BUFFER_DIR, exist_ok=True)

            stream_url = (
                f"{config.SERVER_URL.rstrip('/')}"
                f"/live/{config.USERNAME}/{config.PASSWORD}/{channel_id}.ts"
            )
            seg_pattern = os.path.join(config.DVR_BUFFER_DIR, "seg_%06d.ts")
            playlist    = os.path.join(config.DVR_BUFFER_DIR, _PLAYLIST_NAME)
            # Rolling window: (hours * 3600) / segment_seconds entries.
            cmd = [
                "ffmpeg", "-y",
                "-reconnect",            "1",
                "-reconnect_at_eof",     "1",
                "-reconnect_streamed",   "1",
                "-reconnect_delay_max",  "5",
                "-timeout",              "15000000",
                "-fflags",               "+discardcorrupt",
                "-i",                    stream_url,
                # Transcode video so we can force keyframes at every segment
                # boundary. -c:v copy produces irregular segment durations and
                # mid-GOP cuts → green frames + decoder confusion in ExoPlayer.
                # veryfast preset uses ~30-50% of one core for 1080p — fine on PC.
                "-c:v",                  "libx264",
                "-preset",               "veryfast",
                "-crf",                  "23",
                # Repeat SPS/PPS in the encoded bitstream so each HLS segment is
                # independently decodable even when ExoPlayer joins mid-stream.
                "-x264-params",          "repeat-headers=1",
                "-force_key_frames",     f"expr:gte(t,n_forced*{_SEGMENT_SECONDS})",
                "-c:a",                  "aac",
                "-b:a",                  "192k",
                "-ac",                   "2",
                # Keep audio clock aligned with the live source so emulator
                # underruns and A/V drift do not build up over time.
                "-af",                   "aresample=async=1000:first_pts=0",
                "-f",                    "hls",
                "-hls_time",             str(_SEGMENT_SECONDS),
                "-hls_list_size",        str(_HLS_LIST_SIZE),
                "-hls_flags",            "delete_segments+omit_endlist+program_date_time",
                "-hls_segment_type",     "mpegts",
                "-hls_segment_filename", seg_pattern,
                playlist,
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

    def stop(self) -> None:
        """Stop the current DVR session. Buffer files are preserved until next start()."""
        with self._lock:
            self._stop_locked()

    def get_playlist_path(self) -> str:
        """Absolute path to the live HLS manifest (may not yet exist)."""
        return os.path.join(config.DVR_BUFFER_DIR, _PLAYLIST_NAME)

    def get_segments(self) -> list[dict]:
        """
        Return available segments, oldest first (debug / readiness only).
        Each entry: {name, size_bytes, is_active}
        """
        paths = self._list_segment_paths()
        if not paths:
            return []
        return [
            {
                "name":       os.path.basename(p),
                "size_bytes": self._safe_getsize(p),
                "is_active":  i == len(paths) - 1,
            }
            for i, p in enumerate(paths)
        ]

    def get_status(self) -> dict:
        job       = self._job
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
        if paths:
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
        # On Windows, FFmpeg holds segment files open; orphaned FFmpeg processes
        # (e.g. from a previous server run) must be killed before we can delete.
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "ffmpeg.exe"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(0.5)  # brief wait for handles to close
            except Exception:
                pass

        buf = config.DVR_BUFFER_DIR
        if not os.path.isdir(buf):
            return
        for pattern in ("seg_*.ts", _PLAYLIST_NAME, "playlist.m3u8.tmp"):
            for path in glob.glob(os.path.join(buf, pattern)):
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
