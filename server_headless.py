"""
server_headless.py — Headless entrypoint for ELITE IPTV DVR (NAS/Docker deployment).

Skips the customtkinter GUI entirely. Starts web server, DVR manager, 
recording scheduler, and tunnel directly.

Environment variables (optional, fall back to credentials.json):
  SERVER_URL, USERNAME, PASSWORD
  TUNNEL_PROVIDER (instatunnel|cloudflare)
  INSTATUNNEL_API_KEY, INSTATUNNEL_SUBDOMAIN
  CLOUDFLARE_TUNNEL_TOKEN, CLOUDFLARE_DOMAIN
  RECORDINGS_DIR
"""

import datetime
import json
import os
import queue
import signal
import sys
import threading
import time
from pathlib import Path

import config
from core.channels import parse_m3u_channels
from core.credentials import load_credentials
from core.dvr_manager import DVRManager
from core.live_preview import LivePreviewManager
from core.recorder import RecordingJob, run_job, job_duration_secs
from core.tunnel import TunnelManager
from core.web_server import WebContext, start_web_server


class HeadlessServer:
    """Headless server orchestrator — no GUI dependencies."""

    def __init__(self):
        self.recording_jobs: list[RecordingJob] = []
        self.channel_map: dict[str, str] = {}
        self.all_channel_names: list[str] = []
        self.output_dir: str = os.getenv("RECORDINGS_DIR", config._APP_DIR)
        self.dvr_manager = DVRManager()
        self.live_preview = LivePreviewManager()
        self.tunnel_mgr = TunnelManager()
        self.web_actions: queue.Queue = queue.Queue()
        self._log_entries: list[str] = []
        self._channels_loaded = False
        self._running = True

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def _log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self._log_entries.append(entry)
        if len(self._log_entries) > 200:
            self._log_entries.pop(0)
        print(entry)

    def _load_credentials_from_env(self):
        """Load credentials from environment variables, falling back to file."""
        env_vars = {
            "SERVER_URL": "SERVER_URL",
            "USERNAME": "USERNAME",
            "PASSWORD": "PASSWORD",
            "TUNNEL_PROVIDER": "TUNNEL_PROVIDER",
            "INSTATUNNEL_API_KEY": "INSTATUNNEL_API_KEY",
            "INSTATUNNEL_SUBDOMAIN": "INSTATUNNEL_SUBDOMAIN",
            "CLOUDFLARE_TUNNEL_TOKEN": "CLOUDFLARE_TUNNEL_TOKEN",
            "CLOUDFLARE_DOMAIN": "CLOUDFLARE_DOMAIN",
        }

        for config_key, env_key in env_vars.items():
            value = os.getenv(env_key, "").strip()
            if value:
                setattr(config, config_key, value)
                self._log(f"Loaded {config_key} from environment")

        # Fall back to credentials.json for any missing values
        load_credentials()

    def _fetch_channels(self):
        """Fetch channel list from trimmed M3U or provider API."""
        try:
            trimmed_path = Path(getattr(config, "TRIMMED_M3U_PATH", "")).expanduser()
            if trimmed_path.exists() and trimmed_path.is_file() and trimmed_path.stat().st_size > 0:
                m3u_text = trimmed_path.read_text(encoding="utf-8", errors="replace")
                source_label = str(trimmed_path)
            else:
                url = f"{config.SERVER_URL}/get.php?username={config.USERNAME}&password={config.PASSWORD}&type=m3u_plus&output=ts"
                import requests
                response = requests.get(url, timeout=60)
                m3u_text = response.text
                source_label = url

            self.channel_map = parse_m3u_channels(m3u_text)
            self.all_channel_names = sorted(self.channel_map.keys())
            self._channels_loaded = True
            self._log(f"Loaded {len(self.all_channel_names):,} channels from {source_label}")
        except Exception as e:
            self._log(f"Error fetching channels: {e}")
            self._channels_loaded = True  # Mark as loaded even on error to unblock

    def _get_channel_id(self, name: str) -> str | None:
        return self.channel_map.get(name)

    def _web_get_status(self) -> dict:
        """Return status for web API."""
        now = datetime.datetime.now()
        recordings = []
        for job in self.recording_jobs:
            if job.status == "complete":
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": "Recording finished.", "stoppable": False})
            elif job.status == "error":
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": "Error encountered.", "stoppable": False})
            elif job.status == "stopped":
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": "Stopped by user.", "stoppable": False})
            elif job.status == "waiting":
                secs = max(0, int((job.start_time - now).total_seconds()))
                txt = f"Starts in {str(datetime.timedelta(seconds=secs))}"
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": txt, "stoppable": True})
            elif job.status == "recording" and job.actual_start:
                elapsed = int((now - job.actual_start).total_seconds())
                remaining = max(0, job_duration_secs(job) - elapsed)
                txt = (f"RECORDING  •  {str(datetime.timedelta(seconds=elapsed))} elapsed  •  "
                       f"{str(datetime.timedelta(seconds=remaining))} remaining")
                live_url = f"/recordings/live/{job.id}/playlist.m3u8" if getattr(job, "live_dir", None) else None
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": txt, "stoppable": True,
                                   "live_hls_url": live_url})
            else:
                secs = max(0, int((job.start_time - now).total_seconds()))
                recordings.append({"name": job.channel_name, "status": job.status,
                                   "status_text": f"Starts in {str(datetime.timedelta(seconds=secs))}",
                                   "stoppable": True})

        backup_info = ""
        return {
            "recordings": recordings,
            "status": f"Ready — {len(self.all_channel_names):,} channels" if self._channels_loaded else "Loading channels…",
            "backup_name": backup_info,
        }

    def _web_get_channels(self, q: str) -> list[dict]:
        """Search channels for web API."""
        if not q:
            return []
        matches = [n for n in self.all_channel_names if q.lower() in n.lower()][:25]
        return [{"name": n, "id": self.channel_map[n]} for n in matches]

    def _web_get_all_channels(self) -> list[dict]:
        """Return all channels for web API."""
        return [{"name": n, "id": self.channel_map[n]} for n in self.all_channel_names]

    def _web_get_favorites(self) -> list[dict]:
        """Return favorites for web API."""
        from core.favorites import load_favorites
        import config
        return load_favorites(config.FAVORITES_FILE)

    def _web_get_jobs(self) -> list[RecordingJob]:
        return self.recording_jobs

    def _web_get_recordings_dir(self) -> str:
        return self.output_dir

    def _persist_recording_jobs(self):
        """Persist active/waiting jobs to disk for crash recovery."""
        try:
            payload = []
            for job in self.recording_jobs:
                if job.status not in ("waiting", "recording"):
                    continue
                payload.append({
                    "channel_name": job.channel_name,
                    "channel_id": job.channel_id,
                    "start_time": job.start_time.isoformat(),
                    "duration_secs": getattr(job, "duration_secs", job.duration_mins * 60),
                    "output_dir": job.output_dir,
                    "backup_channel_id": job.backup_channel_id,
                    "backup_channel_name": job.backup_channel_name,
                })
            with open(config.SCHEDULES_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            self._log(f"Could not persist recordings: {e}")

    def _load_scheduled_recordings(self):
        """Restore scheduled recordings from previous session."""
        try:
            with open(config.SCHEDULES_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return

        if not isinstance(payload, list):
            return

        now = datetime.datetime.now()
        restored = 0
        for item in payload:
            try:
                channel_name = str(item.get("channel_name", "")).strip()
                channel_id = str(item.get("channel_id", "")).strip()
                start_time = datetime.datetime.fromisoformat(str(item.get("start_time", "")))
                duration_secs = max(1, int(item.get("duration_secs", int(item.get("duration_mins", 0)) * 60)))
            except Exception:
                continue

            if not channel_name or not channel_id:
                continue

            end_time = start_time + datetime.timedelta(seconds=duration_secs)
            if end_time <= now:
                continue

            if start_time <= now:
                remaining_secs = max(1, int((end_time - now).total_seconds()))
                job_start_time = now
                job_duration_mins = max(1, int((remaining_secs + 59) // 60))
                job_duration_secs = remaining_secs
            else:
                job_start_time = start_time
                job_duration_mins = max(1, int((duration_secs + 59) // 60))
                job_duration_secs = duration_secs

            job = RecordingJob(channel_name, channel_id, job_start_time, job_duration_mins, item.get("output_dir") or self.output_dir)
            job.duration_secs = job_duration_secs
            job.backup_channel_id = item.get("backup_channel_id") or None
            job.backup_channel_name = item.get("backup_channel_name") or None
            self.recording_jobs.append(job)
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            restored += 1

        if restored:
            self._log(f"Restored {restored} queued recording(s) from the last session.")
        self._persist_recording_jobs()

    def _process_web_actions(self):
        """Process actions queued by web API."""
        while not self.web_actions.empty():
            try:
                action = self.web_actions.get_nowait()
            except queue.Empty:
                break

            if action["type"] == "schedule":
                self._web_schedule(action)
            elif action["type"] == "stop":
                idx = action.get("index", 0)
                if 0 <= idx < len(self.recording_jobs):
                    job = self.recording_jobs[idx]
                    if job.status in ("waiting", "recording"):
                        job.status = "stopped"
                        if job.process and job.process.poll() is None:
                            job.process.terminate()
                        self._log(f"Stopped: '{job.channel_name}'")
                        self._persist_recording_jobs()
            elif action["type"] == "fav_add":
                from core.favorites import load_favorites, save_favorites
                import config
                favorites = load_favorites(config.FAVORITES_FILE)
                name = action.get("name")
                cid = action.get("id")
                if name and cid and not any(f["name"] == name for f in favorites):
                    favorites.append({"name": name, "id": cid})
                    save_favorites(config.FAVORITES_FILE, favorites)
                    self._log(f"[Remote] Saved channel: '{name}'")
            elif action["type"] == "fav_remove":
                from core.favorites import load_favorites, save_favorites
                import config
                favorites = load_favorites(config.FAVORITES_FILE)
                name = action.get("name")
                if name:
                    favorites = [f for f in favorites if f["name"] != name]
                    save_favorites(config.FAVORITES_FILE, favorites)
                    self._log(f"[Remote] Removed channel: '{name}'")
            elif action["type"] == "backup_set":
                self._log(f"[Remote] Set backup channel: '{action.get('name')}'")
            elif action["type"] == "backup_clear":
                self._log("[Remote] Cleared backup channel")

    def _web_schedule(self, action: dict):
        """Schedule a recording from web API."""
        try:
            now = datetime.datetime.now()
            if action.get("start_time") == "NOW":
                start_time = now
            else:
                start_time = datetime.datetime.strptime(action["start_time"].strip(), "%I:%M %p")
                start_time = start_time.replace(year=now.year, month=now.month, day=now.day)
                if start_time < now:
                    start_time += datetime.timedelta(days=1)

            job = RecordingJob(
                action["channel_name"],
                action["channel_id"],
                start_time,
                int(action["duration_mins"]),
                self.output_dir,
            )
            self.recording_jobs.append(job)

            if action.get("start_time") == "NOW":
                self._log(f"[Remote] Started recording '{job.channel_name}' for {job.duration_mins} min.")
            else:
                self._log(f"[Remote] Scheduled '{job.channel_name}' at {start_time.strftime('%I:%M %p')} for {job.duration_mins} min.")

            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            self._persist_recording_jobs()
        except Exception as e:
            self._log(f"[Remote] Schedule error: {e}")

    def _start_web_server(self):
        """Start the HTTP server."""
        ctx = WebContext(
            get_status_fn=self._web_get_status,
            get_channels_fn=self._web_get_channels,
            get_favorites_fn=self._web_get_favorites,
            get_log_fn=lambda: self._log_entries,
            action_queue=self.web_actions,
            dvr_manager=self.dvr_manager,
            get_all_channels_fn=self._web_get_all_channels,
            get_jobs_fn=self._web_get_jobs,
            get_recordings_dir_fn=self._web_get_recordings_dir,
            preview_start_fn=self.live_preview.start,
            preview_stop_fn=self.live_preview.stop,
        )
        url = start_web_server(ctx)
        self._log(f"Web server started at {url}")
        return url

    def _cleanup_finished_jobs(self):
        """Remove completed/stopped jobs from memory."""
        self.recording_jobs[:] = [j for j in self.recording_jobs if j.status in ("waiting", "recording")]

    def _tick(self):
        """Main loop tick — process actions, tunnel output, job status."""
        while self._running:
            # Drain tunnel output into log
            while self.tunnel_mgr.lines:
                self._log(f"[Tunnel] {self.tunnel_mgr.lines.pop(0)}")

            # Poll tunnel URL / errors
            tunnel_url = self.tunnel_mgr.url
            if tunnel_url is not None:
                self.tunnel_mgr.url = None
                self._log(f"[Tunnel] URL active: {tunnel_url}")
            tunnel_log = self.tunnel_mgr.log
            if tunnel_log is not None:
                self.tunnel_mgr.log = None
                self._log(tunnel_log)

            self._process_web_actions()
            self._cleanup_finished_jobs()

            # Persist job status periodically
            self._persist_recording_jobs()

            time.sleep(1)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self._log(f"Received signal {signum}, shutting down...")
        self._running = False
        self.tunnel_mgr.stop()
        self.live_preview.stop_all()
        for job in self.recording_jobs:
            if job.status == "recording" and job.process:
                try:
                    job.process.terminate()
                except Exception:
                    pass
        self._persist_recording_jobs()
        sys.exit(0)

    def run(self):
        """Main entrypoint — initialize and run the headless server."""
        self._log("=" * 50)
        self._log("ELITE IPTV DVR — Headless Server Starting")
        self._log("=" * 50)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Load credentials
        self._load_credentials_from_env()

        if not config.SERVER_URL or not config.USERNAME or not config.PASSWORD:
            self._log("ERROR: Missing credentials. Set SERVER_URL, USERNAME, PASSWORD environment variables")
            self._log("       or ensure credentials.json exists.")
            sys.exit(1)

        # Start tunnel if configured
        self.tunnel_mgr.start()

        # Start web server
        self._start_web_server()

        # Fetch channels
        threading.Thread(target=self._fetch_channels, daemon=True).start()

        # Restore scheduled recordings
        self._load_scheduled_recordings()

        self._log("Server ready. Press Ctrl+C to stop.")

        # Main loop
        self._tick()


def main():
    server = HeadlessServer()
    server.run()


if __name__ == "__main__":
    main()
