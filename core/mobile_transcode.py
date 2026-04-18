"""
core/mobile_transcode.py — On-demand HLS transcoder for the mobile webapp.

Wraps the upstream IPTV TS feed in ffmpeg and re-encodes to HLS so mobile
browsers (iOS Safari, Android Chrome) can play it reliably. Designed to
run on modest Synology NAS hardware:

  * max 2 concurrent transcodes (configurable)
  * idle-kill after ~25s of no segment access
  * auto-detects h264_qsv / h264_vaapi / h264_v4l2m2m, else libx264 ultrafast
  * conservative default profile: 854x480 @ 30fps, 1200k video + 96k AAC

Thread-safe. All state is guarded by `_lock`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

import config


# ── Tunable limits ──────────────────────────────────────────────────────────
MAX_CONCURRENT_TRANSCODES = 2
IDLE_TIMEOUT_SECS         = 25
WARMUP_TIMEOUT_SECS       = 8     # how long to wait for the first segment
REAPER_INTERVAL_SECS      = 5


# ── Profiles ────────────────────────────────────────────────────────────────
# Each profile is a list of ffmpeg args inserted between `-i <input>` and the
# HLS output args. Keep bitrates conservative — the NAS encodes in real time.
def _profile_args(profile: str, encoder: str) -> list[str]:
    # Common audio: AAC stereo. 96k is plenty for voice/TV.
    audio = ["-c:a", "aac", "-b:a", "96k", "-ac", "2"]

    if profile == "hd":
        scale    = "scale=-2:720"
        v_bitrate = "2500k"
        v_maxrate = "2800k"
        v_bufsize = "5000k"
        fps       = "30"
        audio     = ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    elif profile == "low":
        scale    = "scale=-2:360"
        v_bitrate = "600k"
        v_maxrate = "700k"
        v_bufsize = "1200k"
        fps       = "25"
        audio     = ["-c:a", "aac", "-b:a", "64k",  "-ac", "2"]
    else:  # "mobile" (default)
        scale    = "scale=-2:480"
        v_bitrate = "1200k"
        v_maxrate = "1400k"
        v_bufsize = "2400k"
        fps       = "30"

    # Encoder-specific flags
    if encoder == "h264_qsv":
        video = [
            "-vf", scale, "-r", fps,
            "-c:v", "h264_qsv",
            "-preset", "veryfast",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
        ]
    elif encoder == "h264_vaapi":
        # vaapi requires the scaling filter on the GPU; simplified here.
        video = [
            "-vf", f"format=nv12,hwupload,{scale.replace('scale', 'scale_vaapi')}",
            "-r", fps,
            "-c:v", "h264_vaapi",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
        ]
    elif encoder == "h264_v4l2m2m":
        video = [
            "-vf", scale, "-r", fps,
            "-c:v", "h264_v4l2m2m",
            "-b:v", v_bitrate,
        ]
    else:  # libx264 software fallback
        video = [
            "-vf", scale, "-r", fps,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "main", "-level", "4.0",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
            "-g", str(int(fps) * 2), "-keyint_min", str(int(fps) * 2),
            "-sc_threshold", "0",
            "-x264-params", "repeat-headers=1",
        ]

    return video + audio


def _detect_encoder() -> str:
    """Probe ffmpeg for available H.264 encoders. Falls back to libx264."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
            **config._SUBPROCESS_FLAGS,
        ).stdout
    except Exception:
        return "libx264"

    # Prefer Intel QSV > VAAPI > V4L2 M2M (Raspberry Pi etc.) > software.
    for enc in ("h264_qsv", "h264_vaapi", "h264_v4l2m2m"):
        if re.search(rf"\b{enc}\b", out):
            return enc
    return "libx264"


# ── Transcode session ───────────────────────────────────────────────────────
class _Session:
    __slots__ = ("channel_id", "profile", "dir", "process", "last_access", "started_at", "ready")

    def __init__(self, channel_id: str, profile: str, work_dir: str):
        self.channel_id  = channel_id
        self.profile     = profile
        self.dir         = work_dir
        self.process: subprocess.Popen | None = None
        self.last_access = time.time()
        self.started_at  = time.time()
        self.ready       = False


# ── Manager ─────────────────────────────────────────────────────────────────
class MobileTranscodeManager:
    """Singleton-style manager. Instantiated once in core/web_server.py."""

    def __init__(self):
        self._sessions: dict[str, _Session] = {}  # key = f"{channel_id}|{profile}"
        self._lock = threading.Lock()
        self._encoder = _detect_encoder()
        self._root = os.path.join(tempfile.gettempdir(), "elite_transcode")
        os.makedirs(self._root, exist_ok=True)
        print(f"[MobileTranscode] Using encoder: {self._encoder}")
        # Reaper thread: kills idle sessions
        threading.Thread(target=self._reaper_loop, daemon=True).start()

    # ── Public API ──────────────────────────────────────────────────────────
    @property
    def encoder(self) -> str:
        return self._encoder

    def ensure_session(self, channel_id: str, profile: str) -> _Session | None:
        """
        Make sure a transcode session is running for (channel_id, profile).
        Returns the session, or None if we're at capacity and no slot could
        be freed. Safe to call from request handlers on every segment fetch.
        """
        if profile not in ("mobile", "hd", "low"):
            profile = "mobile"
        key = f"{channel_id}|{profile}"

        with self._lock:
            sess = self._sessions.get(key)
            if sess is not None:
                sess.last_access = time.time()
                if sess.process and sess.process.poll() is not None:
                    # ffmpeg died; clean it up and restart
                    self._drop_locked(key)
                    sess = None
                else:
                    return sess

            # Need a new session — check capacity
            if len(self._sessions) >= MAX_CONCURRENT_TRANSCODES:
                evicted = self._evict_oldest_idle_locked()
                if not evicted and len(self._sessions) >= MAX_CONCURRENT_TRANSCODES:
                    print(f"[MobileTranscode] Capacity full ({MAX_CONCURRENT_TRANSCODES}); refusing {key}")
                    return None

            work_dir = os.path.join(self._root, re.sub(r"[^a-zA-Z0-9_\-]", "_", key))
            # Reset work dir for a clean start
            if os.path.isdir(work_dir):
                try:
                    shutil.rmtree(work_dir)
                except OSError:
                    pass
            os.makedirs(work_dir, exist_ok=True)

            sess = _Session(channel_id, profile, work_dir)
            self._sessions[key] = sess
            self._start_ffmpeg(sess)
            return sess

    def wait_for_playlist(self, sess: _Session) -> bool:
        """Block up to WARMUP_TIMEOUT_SECS for the first segment to exist."""
        pl = os.path.join(sess.dir, "index.m3u8")
        deadline = time.time() + WARMUP_TIMEOUT_SECS
        while time.time() < deadline:
            if os.path.exists(pl) and self._has_any_segment(sess.dir):
                sess.ready = True
                return True
            if sess.process and sess.process.poll() is not None:
                return False
            time.sleep(0.25)
        return os.path.exists(pl) and self._has_any_segment(sess.dir)

    def touch(self, channel_id: str, profile: str) -> None:
        """Bump last_access — called on every segment request."""
        key = f"{channel_id}|{profile}"
        with self._lock:
            sess = self._sessions.get(key)
            if sess is not None:
                sess.last_access = time.time()

    # ── Internals ───────────────────────────────────────────────────────────
    def _start_ffmpeg(self, sess: _Session) -> None:
        stream_url = (
            f"{config.SERVER_URL.rstrip('/')}"
            f"/live/{config.USERNAME}/{config.PASSWORD}/{sess.channel_id}.ts"
        )
        seg_pattern = os.path.join(sess.dir, "seg_%05d.ts")
        playlist    = os.path.join(sess.dir, "index.m3u8")

        input_args = [
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-timeout", "15000000",
            "-fflags", "+discardcorrupt+nobuffer",
            "-i", stream_url,
        ]

        hls_args = [
            "-f", "hls",
            "-hls_time", "2",
            "-hls_list_size", "6",
            "-hls_flags", "delete_segments+omit_endlist+independent_segments",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", seg_pattern,
            playlist,
        ]

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"]
        # VAAPI needs a hw device before -i
        if self._encoder == "h264_vaapi":
            cmd += ["-vaapi_device", "/dev/dri/renderD128", "-hwaccel", "vaapi"]
        cmd += input_args
        cmd += _profile_args(sess.profile, self._encoder)
        cmd += hls_args

        try:
            sess.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **config._SUBPROCESS_FLAGS,
            )
            print(f"[MobileTranscode] Started {sess.channel_id}|{sess.profile} pid={sess.process.pid}")
        except FileNotFoundError:
            print("[MobileTranscode] ERROR: ffmpeg not found in PATH")
        except Exception as e:
            print(f"[MobileTranscode] ERROR starting ffmpeg: {e}")

    def _has_any_segment(self, work_dir: str) -> bool:
        try:
            for n in os.listdir(work_dir):
                if n.startswith("seg_") and n.endswith(".ts"):
                    p = os.path.join(work_dir, n)
                    if os.path.getsize(p) > 0:
                        return True
        except OSError:
            pass
        return False

    def _evict_oldest_idle_locked(self) -> bool:
        """Find the least-recently-used session and kill it. Returns True if evicted."""
        if not self._sessions:
            return False
        key = min(self._sessions, key=lambda k: self._sessions[k].last_access)
        oldest = self._sessions[key]
        # Only evict if it hasn't been touched very recently (gives fairness)
        if time.time() - oldest.last_access < 3:
            return False
        print(f"[MobileTranscode] Evicting idle session {key}")
        self._drop_locked(key)
        return True

    def _drop_locked(self, key: str) -> None:
        sess = self._sessions.pop(key, None)
        if sess is None:
            return
        if sess.process and sess.process.poll() is None:
            try:
                sess.process.terminate()
                try:
                    sess.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    sess.process.kill()
            except Exception:
                pass
        try:
            shutil.rmtree(sess.dir, ignore_errors=True)
        except Exception:
            pass

    def _reaper_loop(self) -> None:
        while True:
            time.sleep(REAPER_INTERVAL_SECS)
            try:
                now = time.time()
                with self._lock:
                    dead = [
                        k for k, s in self._sessions.items()
                        if (now - s.last_access) > IDLE_TIMEOUT_SECS
                        or (s.process and s.process.poll() is not None)
                    ]
                    for k in dead:
                        print(f"[MobileTranscode] Reaping {k} (idle or exited)")
                        self._drop_locked(k)
            except Exception as e:
                print(f"[MobileTranscode] reaper error: {e}")


# ── Module-level singleton ──────────────────────────────────────────────────
manager = MobileTranscodeManager()
