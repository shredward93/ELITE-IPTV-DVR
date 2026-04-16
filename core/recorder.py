import subprocess
import datetime
import os
import time

import config


class RecordingJob:
    """Pure-data recording job. No UI widget references."""

    _next_id = 0

    def __init__(self, channel_name, channel_id, start_time, duration_mins, output_dir):
        RecordingJob._next_id += 1
        self.id            = RecordingJob._next_id
        self.channel_name  = channel_name
        self.channel_id    = channel_id
        self.start_time    = start_time
        self.duration_mins = duration_mins
        self.duration_secs = duration_mins * 60
        self.output_dir    = output_dir

        self.status          = "waiting"
        self.process         = None
        self.actual_start    = None
        self.output_file     = None
        self.finish_msg      = None   # (message, color) set by bg thread, consumed by UI tick
        self.reconnect_count = 0

        self.backup_channel_id   = None
        self.backup_channel_name = None
        self.active_channel_name = channel_name

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
    safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.channel_name)[:60].strip()
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

        cmd = [
            "ffmpeg", "-y",
            "-reconnect", "1",
            "-reconnect_at_eof", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-timeout", "15000000",   # 15 s socket read timeout (microseconds)
            "-i", stream_url,
            "-t", str(int(remaining)),
            "-c", "copy",
            out,
        ]

        try:
            job.process = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                **config._SUBPROCESS_FLAGS,
            )
            _, stderr_bytes = job.process.communicate()
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

    job.status = "complete"
