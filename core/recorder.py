import subprocess
import datetime
import os
import shutil
import threading
import time

import config


class RecordingJob:
    """Pure-data recording job. No UI widget references."""

    _next_id = 0

    def __init__(self, channel_name, channel_id, start_time, duration_mins, output_dir, custom_name=None):
        RecordingJob._next_id += 1
        self.id            = RecordingJob._next_id
        self.channel_name  = channel_name
        self.channel_id    = channel_id
        self.start_time    = start_time
        self.duration_mins = duration_mins
        self.duration_secs = duration_mins * 60
        self.output_dir    = output_dir
        self.custom_name   = (custom_name or "").strip() or None

        self.status          = "waiting"
        self.process         = None
        self.actual_start    = None
        self.output_file     = None
        self.finish_msg      = None   # (message, color) set by bg thread, consumed by UI tick
        self.reconnect_count = 0

        self.backup_channel_id   = None
        self.backup_channel_name = None
        self.active_channel_name = channel_name

        self.live_dir = None  # path to HLS segment dir while recording is active

        self._pending_logs = []   # log lines queued by bg thread, drained by UI tick

        # UI widget refs — set by IPTVRecorderApp._add_recording_card(); None until then
        self.card_frame   = None
        self.status_label = None
        self.stop_btn     = None


def job_duration_secs(job) -> int:
    return max(1, int(getattr(job, "duration_secs", getattr(job, "duration_mins", 0) * 60)))


def job_remaining_secs(job) -> int:
    if job.actual_start:
        elapsed = (datetime.datetime.now() - job.actual_start).total_seconds()
    else:
        elapsed = (datetime.datetime.now() - job.start_time).total_seconds()
    return max(0, int(job_duration_secs(job) - elapsed))


def run_job(job):
    """
    Execute a recording job in a background thread.
    Reads credentials from config at runtime so credential changes take effect.
    """
    wait_secs = (job.start_time - datetime.datetime.now()).total_seconds()
    if wait_secs > 0:
        time.sleep(wait_secs)
    if job.status == "stopped":
        return

    job.status       = "recording"
    job.actual_start = datetime.datetime.now()
    date_str  = job.actual_start.strftime("%Y-%m-%d_%H-%M")
    name_for_file = job.custom_name or job.channel_name
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name_for_file)[:60].strip()
    base_path = os.path.join(job.output_dir, f"{safe_name}_{date_str}")

    active_id         = job.channel_id
    on_backup         = False
    fail_streak_start = None
    segment           = 0

    while job.status == "recording":
        elapsed   = (datetime.datetime.now() - job.actual_start).total_seconds()
        remaining = job_duration_secs(job) - elapsed
        if remaining <= 3:
            break

        stream_url = f"{config.SERVER_URL.rstrip('/')}/live/{config.USERNAME}/{config.PASSWORD}/{active_id}.ts"
        out = f"{base_path}.ts" if segment == 0 else f"{base_path}_part{segment}.ts"
        job.output_file = out

        live_hls_args = []
        if segment == 0:
            live_dir = os.path.join(config.DVR_BUFFER_DIR, f"live_{job.id}")
            os.makedirs(live_dir, exist_ok=True)
            job.live_dir = live_dir
            # Parallel HLS for "watch while recording" in the web UI. Browsers
            # decode AAC in MSE; AC-3/MP2 from a straight -c copy mux are often
            # silent. Keep video copy; re-encode audio to AAC (same idea as
            # live_preview.py and completed-recording remux in web_server).
            live_hls_args = [
                "-map", "0:v:0",
                "-map", "0:a:0?",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "128k",
                "-ac", "2",
                "-ar", "48000",
                "-f", "hls",
                "-hls_time", "4",
                "-hls_list_size", "0",
                "-hls_playlist_type", "event",   # seekable growing playlist for mid-recording playback
                "-hls_flags", "program_date_time",
                "-hls_segment_type", "mpegts",
                "-hls_segment_filename", os.path.join(live_dir, "seg_%06d.ts"),
                os.path.join(live_dir, "playlist.m3u8"),
            ]

        # -t MUST go before -i so it limits input duration (applies to every
        # output). Placed as an output option it only caps the first output;
        # the HLS output then has no end, ffmpeg never exits, and communicate()
        # blocks past the scheduled duration.
        cmd = [
            "ffmpeg", "-y",
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-timeout", "15000000",   # 15 s socket read timeout (microseconds)
            "-t", str(int(remaining)),
            "-i", stream_url,
            "-c", "copy",
            out,
            *live_hls_args,
        ]

        try:
            job.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                **config._SUBPROCESS_FLAGS,
            )

            # Wallclock watchdog: force-kill ffmpeg if it runs more than 30 s
            # past the scheduled remaining duration. Cheap insurance in case
            # reconnect/retry loops make content-time < wallclock-time.
            _wd_stop = threading.Event()
            _wd_deadline = time.time() + int(remaining) + 30

            def _watchdog(proc, deadline, stop_evt):
                while not stop_evt.is_set():
                    if proc.poll() is not None:
                        return
                    if time.time() >= deadline:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        # Give ffmpeg 5 s to exit cleanly, then SIGKILL.
                        for _ in range(50):
                            if proc.poll() is not None:
                                return
                            time.sleep(0.1)
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        return
                    time.sleep(1)

            threading.Thread(
                target=_watchdog,
                args=(job.process, _wd_deadline, _wd_stop),
                daemon=True,
            ).start()

            _, stderr_bytes = job.process.communicate()
            _wd_stop.set()
            retcode = job.process.returncode
            if retcode != 0 and stderr_bytes:
                err_text = stderr_bytes[-8192:].decode("utf-8", errors="replace")
                lines    = err_text.splitlines()
                _ERR_KW  = ("error", "invalid", "refused", "failed",
                             "forbidden", "unauthorized", "404", "403",
                             "401", "no such", "timeout", "unable")
                err_lines = [l.strip() for l in lines
                             if l.strip() and any(k in l.lower() for k in _ERR_KW)]
                if err_lines:
                    job._pending_logs.append(f"ffmpeg error: {err_lines[-1]}")
                else:
                    non_banner = [l.strip() for l in lines
                                  if l.strip() and not l.startswith("  lib")]
                    if non_banner:
                        job._pending_logs.append(f"ffmpeg: {non_banner[-1]}")
        except FileNotFoundError:
            job.status     = "error"
            job.finish_msg = ("Error: ffmpeg not found in PATH.", "red")
            return
        except Exception as e:
            job.status     = "error"
            job.finish_msg = (f"Error: {e}", "red")
            return

        if job.status == "stopped":
            return

        elapsed   = (datetime.datetime.now() - job.actual_start).total_seconds()
        remaining = job_duration_secs(job) - elapsed
        if remaining <= 3:
            break

        if retcode != 0:
            segment             += 1
            job.reconnect_count += 1

            if fail_streak_start is None:
                fail_streak_start = time.time()
            elif (not on_backup and job.backup_channel_id
                  and time.time() - fail_streak_start >= 120):
                on_backup               = True
                active_id               = job.backup_channel_id
                job.active_channel_name = job.backup_channel_name
                fail_streak_start       = None
                job._pending_logs.append(
                    f"Primary '{job.channel_name}' down >2 min — switching to backup '{job.backup_channel_name}'"
                )

            time.sleep(4)
        else:
            fail_streak_start = None
            break

    if job.status != "recording":
        return

    # ── Merge segments if FFmpeg restarted mid-recording ─────────────────────
    if segment > 0:
        parts = (
            [f"{base_path}.ts"] +
            [f"{base_path}_part{i}.ts" for i in range(1, segment + 1)]
        )
        parts = [p for p in parts if os.path.exists(p) and os.path.getsize(p) > 0]

        if len(parts) > 1:
            concat_txt = base_path + "_concat.txt"
            merged_tmp = base_path + "_merged.ts"
            merged_ok  = False
            try:
                with open(concat_txt, "w") as f:
                    for p in parts:
                        escaped = p.replace("'", "'\\''")
                        f.write(f"file '{escaped}'\n")
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                     "-i", concat_txt, "-c", "copy", merged_tmp],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    **config._SUBPROCESS_FLAGS,
                )
                if os.path.exists(merged_tmp) and os.path.getsize(merged_tmp) > 0:
                    final = f"{base_path}.ts"
                    os.replace(merged_tmp, final)
                    for p in parts[1:]:
                        try: os.remove(p)
                        except OSError: pass
                    job.output_file = final
                    merged_ok = True
            except Exception:
                pass
            finally:
                try: os.remove(concat_txt)
                except OSError: pass
                try: os.remove(merged_tmp)
                except OSError: pass

            job.finish_msg = (
                f"Recording complete ({len(parts)} parts merged)." if merged_ok
                else f"Complete — {len(parts)} parts (merge failed, kept separately).",
                "#2ecc71" if merged_ok else "#e67e22",
            )
        else:
            job.finish_msg = ("Recording complete.", "#2ecc71")
    else:
        job.finish_msg = ("Recording complete.", "#2ecc71")

    if job.live_dir and os.path.isdir(job.live_dir):
        try:
            shutil.rmtree(job.live_dir)
        except OSError:
            pass
        job.live_dir = None

    job.status = "complete"
