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
# Override the concurrent-transcode cap via the MAX_TRANSCODES env var
# (set in docker-compose.yml). Default 3 — sized for Synology DS1621xs+
# (Xeon D-1527, 4C/8T). Drop to 2 on Celeron-class NAS; raise for beefier hosts.
try:
    MAX_CONCURRENT_TRANSCODES = max(1, int(os.getenv("MAX_TRANSCODES", "3")))
except ValueError:
    MAX_CONCURRENT_TRANSCODES = 3

IDLE_TIMEOUT_SECS    = 25
WARMUP_TIMEOUT_SECS  = 10    # how long to wait for the first segment (60fps needs a beat longer)
REAPER_INTERVAL_SECS = 5


# ── Profiles ────────────────────────────────────────────────────────────────
# Each profile is a list of ffmpeg args inserted between `-i <input>` and the
# HLS output args. Keep bitrates conservative — the NAS encodes in real time.
def _profile_args(profile: str, encoder: str) -> list[str]:
    # Common audio: AAC stereo. 96k is plenty for voice/TV.
    audio = ["-c:a", "aac", "-b:a", "96k", "-ac", "2"]

    # FPS note: ffmpeg uses -r as a MAX target. If upstream is 30fps it stays
    # 30fps (no frame duplication at copy level). 60fps here lets sports /
    # 50-60fps broadcasts pass through smoothly instead of being decimated.
    if profile == "hd":
        scale    = "scale=-2:720"
        v_bitrate = "3000k"
        v_maxrate = "3400k"
        v_bufsize = "6000k"
        fps       = "60"
        audio     = ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    elif profile == "low":
        scale    = "scale=-2:360"
        v_bitrate = "700k"
        v_maxrate = "800k"
        v_bufsize = "1400k"
        fps       = "30"
        audio     = ["-c:a", "aac", "-b:a", "64k",  "-ac", "2"]
    else:  # "mobile" (default)
        scale    = "scale=-2:480"
        v_bitrate = "1600k"
        v_maxrate = "1800k"
        v_bufsize = "3200k"
        fps       = "60"

    # Cap output fps at `fps` (won't upsample a 30fps source to 60) and
    # force a keyframe every 2s so HLS segment boundaries are always on a
    # keyframe — works identically for 30fps and 60fps sources.
    fps_cap = ["-fpsmax", fps]
    keyframes = ["-force_key_frames", "expr:gte(t,n_forced*2)"]

    # Encoder-specific flags
    if encoder == "h264_qsv":
        video = [
            "-vf", scale, *fps_cap,
            "-c:v", "h264_qsv",
            "-preset", "veryfast",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
            *keyframes,
        ]
    elif encoder == "h264_vaapi":
        # vaapi requires the scaling filter on the GPU; simplified here.
        video = [
            "-vf", f"format=nv12,hwupload,{scale.replace('scale', 'scale_vaapi')}",
            *fps_cap,
            "-c:v", "h264_vaapi",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
            *keyframes,
        ]
    elif encoder == "h264_v4l2m2m":
        video = [
            "-vf", scale, *fps_cap,
            "-c:v", "h264_v4l2m2m",
            "-b:v", v_bitrate,
            *keyframes,
        ]
    else:  # libx264 software fallback
        video = [
            "-vf", scale, *fps_cap,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-profile:v", "main", "-level", "4.1",
            "-b:v", v_bitrate, "-maxrate", v_maxrate, "-bufsize", v_bufsize,
            # Large -g lets -force_key_frames dominate; disables scene-cut keyframes.
            "-g", "240", "-keyint_min", "48",
            "-sc_threshold", "0",
            *keyframes,
            "-x264-params", "repeat-headers=1",
        ]

    return video + audio


def _hw_device_present() -> bool:
    """True if an Intel/AMD render node is exposed to the container."""
    for node in ("/dev/dri/renderD128", "/dev/dri/renderD129"):
        if os.path.exists(node):
            return True
    return False


def _v4l2_device_present() -> bool:
    """True if a V4L2 M2M video device is present (Raspberry Pi etc.)."""
    try:
        return any(n.startswith("video") for n in os.listdir("/dev"))
    except OSError:
        return False


def _encoder_actually_works(enc: str) -> bool:
    """
    Run a 1-frame transcode with the encoder against ffmpeg's built-in
    test source. If ffmpeg exits 0 the encoder is really usable; if it
    crashes (missing hardware, missing driver, etc.) we fall back.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc=size=320x180:rate=1",
        "-frames:v", "1",
    ]
    if enc == "h264_vaapi":
        cmd = (
            ["ffmpeg", "-hide_banner", "-loglevel", "error",
             "-vaapi_device", "/dev/dri/renderD128",
             "-f", "lavfi", "-i", "testsrc=size=320x180:rate=1",
             "-frames:v", "1",
             "-vf", "format=nv12,hwupload"]
        )
    cmd += ["-c:v", enc, "-f", "null", "-"]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True, text=True, timeout=8,
            **config._SUBPROCESS_FLAGS,
        )
        return r.returncode == 0
    except Exception:
        return False


def _detect_encoder() -> str:
    """
    Probe ffmpeg for a *working* H.264 encoder. We require:
      1. The encoder is compiled into ffmpeg, AND
      2. The required /dev device is exposed to the container, AND
      3. A 1-frame smoke-test transcode actually succeeds.
    Falls back to libx264 otherwise.
    """
    try:
        encoders_out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
            **config._SUBPROCESS_FLAGS,
        ).stdout
    except Exception as e:
        print(f"[MobileTranscode] ffmpeg probe failed ({e}); using libx264")
        return "libx264"

    candidates = []
    if re.search(r"\bh264_qsv\b",     encoders_out) and _hw_device_present():
        candidates.append("h264_qsv")
    if re.search(r"\bh264_vaapi\b",   encoders_out) and _hw_device_present():
        candidates.append("h264_vaapi")
    if re.search(r"\bh264_v4l2m2m\b", encoders_out) and _v4l2_device_present():
        candidates.append("h264_v4l2m2m")

    for enc in candidates:
        if _encoder_actually_works(enc):
            print(f"[MobileTranscode] Hardware encoder {enc} verified OK")
            return enc
        else:
            print(f"[MobileTranscode] {enc} is compiled in but smoke-test failed; skipping")

    return "libx264"


# ── Transcode session ───────────────────────────────────────────────────────
class _Session:
    __slots__ = ("channel_id", "profile", "dir", "process", "last_access",
                 "started_at", "ready", "_log_fh")

    def __init__(self, channel_id: str, profile: str, work_dir: str):
        self.channel_id  = channel_id
        self.profile     = profile
        self.dir         = work_dir
        self.process: subprocess.Popen | None = None
        self.last_access = time.time()
        self.started_at  = time.time()
        self.ready       = False
        self._log_fh     = None


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

        log_path = os.path.join(sess.dir, "ffmpeg.log")
        try:
            sess._log_fh = open(log_path, "wb")
            sess.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=sess._log_fh,
                **config._SUBPROCESS_FLAGS,
            )
            print(f"[MobileTranscode] Started {sess.channel_id}|{sess.profile} pid={sess.process.pid} enc={self._encoder}")
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

    def _tail_ffmpeg_log(self, sess: _Session, nbytes: int = 800) -> str:
        """Return the last `nbytes` of ffmpeg's stderr for this session."""
        path = os.path.join(sess.dir, "ffmpeg.log")
        try:
            with open(path, "rb") as f:
                try:
                    f.seek(-nbytes, os.SEEK_END)
                except OSError:
                    f.seek(0)
                data = f.read()
            return data.decode("utf-8", errors="replace").strip()
        except OSError:
            return ""

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
        if sess._log_fh is not None:
            try:
                sess._log_fh.close()
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
                    dead = []
                    for k, s in self._sessions.items():
                        exited = s.process and s.process.poll() is not None
                        idle = (now - s.last_access) > IDLE_TIMEOUT_SECS
                        if exited or idle:
                            reason = "exited" if exited else "idle"
                            if exited:
                                rc = s.process.returncode if s.process else "?"
                                tail = self._tail_ffmpeg_log(s)
                                if tail:
                                    print(f"[MobileTranscode] Reaping {k} ({reason}, rc={rc})\n--- ffmpeg tail ---\n{tail}\n--- end ---")
                                else:
                                    print(f"[MobileTranscode] Reaping {k} ({reason}, rc={rc})")
                            else:
                                print(f"[MobileTranscode] Reaping {k} ({reason})")
                            dead.append(k)
                    for k in dead:
                        self._drop_locked(k)
            except Exception as e:
                print(f"[MobileTranscode] reaper error: {e}")


# ── Module-level singleton ──────────────────────────────────────────────────
manager = MobileTranscodeManager()
