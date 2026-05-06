"""
ui/app.py — IPTVRecorderApp main window.

Imports all core modules; never calls FFmpeg directly.
"""

import datetime
import json
import os
import time
from pathlib import Path
import queue
import subprocess
import sys
import threading
import webbrowser

import requests
import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb

import config
from core.credentials import load_credentials
from core.epg import fetch_epg
from core.favorites import load_favorites, save_favorites
from core.dvr_manager import DVRManager
from core.recorder import (
    RecordingJob,
    job_duration_secs,
    normalize_schedule_start_time,
    parse_schedule_start_time_raw,
    run_job,
)
from core.startup import is_autostart_enabled
from core.tunnel import TunnelManager
from core.live_preview import LivePreviewManager
from core.web_server import WebContext, start_web_server
from ui.dialogs import SetupWizard, CredentialsDialog, RecordNowDialog


class IPTVRecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"ELITE IPTV Recorder  v{config.APP_VERSION}")
        self.geometry("1050x760")
        self.minsize(950, 700)

        if sys.platform == "win32":
            import ctypes
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    f"elite.iptv.recorder.{config.APP_VERSION}"
                )
                icon_path = os.path.join(config._BUNDLE_DIR, "icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
                elif getattr(sys, "frozen", False):
                    self.iconbitmap(sys.executable)
            except Exception:
                pass

        self.channel_map           = {}
        self.all_channel_names     = []
        self.recording_jobs        = []
        self.output_dir            = config._APP_DIR
        self.dvr_manager           = DVRManager()
        self._load_settings()
        self.m3u_text              = ""
        self._fetch_start          = datetime.datetime.now()
        self._channels_loaded      = False
        self._fetch_result         = None
        self.selected_channel_name = None
        self.selected_channel_id   = None
        self._epg_result           = None
        self._epg_channel_id       = None
        self._status_text          = "Fetching channel list…"
        self._web_actions          = queue.Queue()
        self.favorites             = []
        self._log_entries          = []
        self.backup_channel_name   = None
        self.backup_channel_id     = None
        self.current_remote_url    = None
        self.current_tunnel_url    = None

        self.tunnel_mgr = TunnelManager()
        self.live_preview = LivePreviewManager()

        self._load_favorites()
        self._build_ui()
        self._load_scheduled_recordings()
        self._tick()
        self._start_web_server()

        if not os.path.exists(config.CREDENTIALS_FILE):
            self.after(300, lambda: SetupWizard(self, self._on_settings_saved))
        else:
            threading.Thread(target=self._fetch_channels, daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=12, pady=12)

        left_pane = ctk.CTkFrame(main_container, fg_color="transparent")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_pane = ctk.CTkFrame(main_container, fg_color="transparent", width=400)
        right_pane.pack_propagate(False)
        right_pane.pack(side="right", fill="y", expand=False, padx=(10, 0))

        title_row = ctk.CTkFrame(left_pane, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(title_row, text="ELITE IPTV Recorder",
                     font=("Arial", 18, "bold")).pack(side="left")
        ctk.CTkButton(title_row, text="⚙ Settings", width=96, height=30,
                      fg_color="#484949", hover_color="#575959",
                      command=self._open_settings).pack(side="right")

        _panel_scroll = ctk.CTkScrollableFrame(left_pane, fg_color="transparent")
        _panel_scroll.pack(fill="both", expand=True)
        panel = ctk.CTkFrame(_panel_scroll)
        panel.pack(fill="x", expand=False)

        # ── Saved Channels / Favorites ──
        self.fav_section = ctk.CTkFrame(panel, fg_color="transparent")
        self.fav_section.pack(fill="x", padx=12, pady=(8, 2))
        fav_header = ctk.CTkFrame(self.fav_section, fg_color="transparent")
        fav_header.pack(fill="x")
        ctk.CTkLabel(fav_header, text="Saved Channels", font=("Arial", 12, "bold"), anchor="w").pack(side="left")
        _fav_wrapper = ctk.CTkFrame(self.fav_section, height=100, fg_color="transparent")
        _fav_wrapper.pack(fill="x", pady=(4, 0))
        _fav_wrapper.pack_propagate(False)
        self.fav_scroll = ctk.CTkScrollableFrame(_fav_wrapper, fg_color="#2E2F2F")
        self.fav_scroll.pack(fill="both", expand=True)
        self._refresh_favorites_panel()

        ctk.CTkFrame(panel, height=1, fg_color="#484949").pack(fill="x", padx=12, pady=(6, 6))

        # ── Live Sports Today (collapsible) ──
        self.sports_frame = ctk.CTkFrame(panel, fg_color="transparent")
        _spt_hdr = ctk.CTkFrame(self.sports_frame, fg_color="transparent")
        _spt_hdr.pack(fill="x", pady=(0, 2))
        self._sports_toggle_btn = ctk.CTkButton(
            _spt_hdr, text="▶  Live Sports Today", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_sports_section)
        self._sports_toggle_btn.pack(side="left", fill="x", expand=True)

        self._sports_body = ctk.CTkFrame(self.sports_frame, fg_color="transparent")
        self._sports_expanded = False

        _spt_controls = ctk.CTkFrame(self._sports_body, fg_color="transparent")
        _spt_controls.pack(fill="x", pady=(0, 4))

        self._sports_league = ctk.StringVar(value="NHL")
        self.sports_combo = ctk.CTkComboBox(
            _spt_controls, variable=self._sports_league,
            values=["NHL", "NBA", "NFL", "MLB"],
            width=80, command=self._fetch_sports
        )
        self.sports_combo.pack(side="left", padx=(0, 6))

        self.sports_refresh_btn = ctk.CTkButton(
            _spt_controls, text="Refresh", width=60,
            fg_color="#575959", hover_color="#484949",
            command=self._fetch_sports
        )
        self.sports_refresh_btn.pack(side="left")

        _spt_wrapper = ctk.CTkFrame(self._sports_body, height=150, fg_color="transparent")
        _spt_wrapper.pack(fill="x", pady=(4, 0))
        _spt_wrapper.pack_propagate(False)
        self.sports_scroll = ctk.CTkScrollableFrame(_spt_wrapper, fg_color="#2E2F2F")
        self.sports_scroll.pack(fill="both", expand=True)

        self.sports_frame.pack(fill="x", padx=12, pady=(0, 2))

        ctk.CTkFrame(panel, height=1, fg_color="#484949").pack(fill="x", padx=12, pady=(6, 6))

        # ── Channel search ──
        ctk.CTkLabel(panel, text="Search Channel", anchor="w").pack(fill="x", padx=12, pady=(0, 2))
        self.search_entry = ctk.CTkEntry(panel, placeholder_text="Loading channels — please wait…", state="disabled")
        self.search_entry.pack(fill="x", padx=12, pady=(0, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        self.results_frame = ctk.CTkScrollableFrame(panel, height=130, fg_color="#2E2F2F")
        self._results_anchor = ctk.CTkFrame(panel, height=0, fg_color="transparent")
        self._results_anchor.pack(fill="x", padx=12)

        sel_row = ctk.CTkFrame(panel, fg_color="transparent")
        sel_row.pack(fill="x", padx=12, pady=(0, 4))
        self.sel_row = sel_row
        self.selected_label = ctk.CTkLabel(sel_row, text="No channel selected", text_color="gray", anchor="w")
        self.selected_label.pack(side="left", fill="x", expand=True)
        self.save_btn = ctk.CTkButton(
            sel_row, text="Save", width=60,
            fg_color="#575959", hover_color="#484949",
            command=self._toggle_save_channel, state="disabled"
        )
        self.save_btn.pack(side="right", padx=(4, 0))
        self.preview_btn = ctk.CTkButton(
            sel_row, text="Preview", width=72,
            fg_color="#575959", hover_color="#484949",
            command=self._preview_stream, state="disabled"
        )
        self.preview_btn.pack(side="right", padx=(4, 0))

        # EPG panel — collapsible, hidden by default
        _epg_section = ctk.CTkFrame(panel, fg_color="transparent")
        _epg_section.pack(fill="x", padx=12, pady=(0, 2))
        _epg_hdr = ctk.CTkFrame(_epg_section, fg_color="transparent")
        _epg_hdr.pack(fill="x")
        self._epg_toggle_btn = ctk.CTkButton(
            _epg_hdr, text="▶  Program Guide", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_epg_section)
        self._epg_toggle_btn.pack(side="left", fill="x", expand=True)
        self._epg_expanded = False

        _epg_wrapper = ctk.CTkFrame(_epg_section, height=200, fg_color="transparent")
        _epg_wrapper.pack_propagate(False)
        self.epg_frame = ctk.CTkScrollableFrame(_epg_wrapper, fg_color="#2E2F2F")
        self.epg_frame.pack(fill="both", expand=True)
        self._epg_wrapper = _epg_wrapper

        # ── Backup Channel (optional, collapsible) ──
        self.backup_frame = ctk.CTkFrame(panel, fg_color="transparent")
        ctk.CTkFrame(self.backup_frame, height=1, fg_color="#484949").pack(fill="x", pady=(4, 6))
        _bkp_hdr = ctk.CTkFrame(self.backup_frame, fg_color="transparent")
        _bkp_hdr.pack(fill="x", pady=(0, 2))
        self._backup_toggle_btn = ctk.CTkButton(
            _bkp_hdr, text="▶  Backup Channel", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_backup_section)
        self._backup_toggle_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(_bkp_hdr, text="optional", text_color="gray40",
                     font=("Arial", 10), anchor="e").pack(side="right")

        self._backup_body = ctk.CTkFrame(self.backup_frame, fg_color="transparent")
        self._backup_expanded = False
        self.backup_search_entry = ctk.CTkEntry(
            self._backup_body, placeholder_text="Search for backup channel…", state="disabled")
        self.backup_search_entry.pack(fill="x", pady=(0, 4))
        self.backup_search_entry.bind("<KeyRelease>", self._on_backup_search_key)
        self.backup_results_frame = ctk.CTkScrollableFrame(self._backup_body, height=100, fg_color="#2E2F2F")
        self._backup_results_anchor = ctk.CTkFrame(self._backup_body, height=0, fg_color="transparent")
        self._backup_results_anchor.pack(fill="x")
        _bkp_sel_row = ctk.CTkFrame(self._backup_body, fg_color="transparent")
        _bkp_sel_row.pack(fill="x", pady=(0, 4))
        self.backup_sel_label = ctk.CTkLabel(
            _bkp_sel_row, text="No backup selected", text_color="gray40", anchor="w")
        self.backup_sel_label.pack(side="left", fill="x", expand=True)
        self.backup_clear_btn = ctk.CTkButton(
            _bkp_sel_row, text="Clear", width=54,
            fg_color="#575959", hover_color="#484949",
            command=self._clear_backup_channel, state="disabled")
        self.backup_clear_btn.pack(side="right", padx=(4, 0))
        self.backup_frame.pack(fill="x", padx=12, pady=(0, 4))

        # ── Recording Time Selection ──
        self.td_frame = ctk.CTkFrame(panel, fg_color="transparent")
        self.td_frame.pack(fill="x", padx=12, pady=(4, 6))

        # Quick preset buttons
        preset_row = ctk.CTkFrame(self.td_frame, fg_color="transparent")
        preset_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(preset_row, text="Quick Presets:", anchor="w", font=("Arial", 11)).pack(side="left", padx=(0, 8))
        for label, start, end in [("30 min", "now", 30), ("1 hour", "now", 60), ("2 hours", "now", 120), ("3 hours", "now", 180)]:
            ctk.CTkButton(preset_row, text=label, width=55, height=24, font=("Arial", 10),
                          fg_color="#575959", hover_color="#484949",
                          command=lambda s=start, d=end: self._apply_preset_duration(d)).pack(side="left", padx=2)

        # Time range row (Start Time - End Time)
        time_range_row = ctk.CTkFrame(self.td_frame, fg_color="transparent")
        time_range_row.pack(fill="x", pady=(0, 6))

        start_frame = ctk.CTkFrame(time_range_row, fg_color="transparent")
        start_frame.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(start_frame, text="Start Time (e.g., 07:00 PM)", anchor="w", font=("Arial", 11)).pack(fill="x")
        self.time_input = ctk.CTkEntry(start_frame, placeholder_text="07:00 PM")
        self.time_input.pack(fill="x")

        end_frame = ctk.CTkFrame(time_range_row, fg_color="transparent")
        end_frame.pack(side="right", expand=True, fill="x", padx=(5, 0))
        end_row = ctk.CTkFrame(end_frame, fg_color="transparent")
        end_row.pack(fill="x")
        ctk.CTkLabel(end_row, text="End Time (optional)", anchor="w", font=("Arial", 11)).pack(side="left")
        ctk.CTkButton(end_row, text="Calc", width=40, height=20, font=("Arial", 9),
                      fg_color="#575959", hover_color="#484949",
                      command=self._calc_duration_from_end_time).pack(side="right")
        self.end_time_input = ctk.CTkEntry(end_frame, placeholder_text="09:00 PM")
        self.end_time_input.pack(fill="x")

        # Duration row with clear minutes indicator
        duration_row = ctk.CTkFrame(self.td_frame, fg_color="transparent")
        duration_row.pack(fill="x", pady=(4, 0))

        dur_left = ctk.CTkFrame(duration_row, fg_color="transparent")
        dur_left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        dur_label_row = ctk.CTkFrame(dur_left, fg_color="transparent")
        dur_label_row.pack(fill="x")
        ctk.CTkLabel(dur_label_row, text="Duration", anchor="w", font=("Arial", 11, "bold")).pack(side="left")
        ctk.CTkLabel(dur_label_row, text="(minutes)", anchor="w", text_color="gray60", font=("Arial", 10)).pack(side="left", padx=(4, 0))
        self.duration_input = ctk.CTkEntry(dur_left, placeholder_text="e.g., 120 = 2 hours")
        self.duration_input.pack(fill="x")
        self.duration_input.insert(0, "180")

        dur_right = ctk.CTkFrame(duration_row, fg_color="transparent")
        dur_right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        dur_hint_row = ctk.CTkFrame(dur_right, fg_color="transparent")
        dur_hint_row.pack(fill="x")
        ctk.CTkLabel(dur_hint_row, text="≈ Hours:", anchor="w", text_color="gray60", font=("Arial", 10)).pack(side="left")
        self.hours_display_label = ctk.CTkLabel(dur_hint_row, text="3.0 hrs", anchor="w", text_color="#2ecc71", font=("Arial", 10, "bold"))
        self.hours_display_label.pack(side="left", padx=(4, 0))
        self.duration_input.bind("<KeyRelease>", self._update_hours_display)
        self.duration_input.bind("<FocusOut>", self._update_hours_display)

        ctk.CTkLabel(panel, text="Output Folder", anchor="w").pack(fill="x", padx=12, pady=(4, 2))
        folder_row = ctk.CTkFrame(panel, fg_color="transparent")
        folder_row.pack(fill="x", padx=12, pady=(0, 6))
        self.folder_label = ctk.CTkLabel(folder_row, text=self.output_dir, anchor="w", text_color="gray")
        self.folder_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(folder_row, text="Open", width=60, fg_color="#575959", hover_color="#484949",
                      command=self._open_output_folder).pack(side="right", padx=(6, 0))
        ctk.CTkButton(folder_row, text="Browse…", width=90, command=self._pick_folder).pack(side="right")

        btn_row = ctk.CTkFrame(panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(4, 10))
        self.record_now_btn = ctk.CTkButton(
            btn_row, text="Record Now", command=self._record_now, state="disabled",
            fg_color="#c0392b", hover_color="#e74c3c"
        )
        self.record_now_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.schedule_btn = ctk.CTkButton(
            btn_row, text="Schedule Recording", command=self._schedule_recording, state="disabled"
        )
        self.schedule_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.save_m3u_btn = ctk.CTkButton(
            btn_row, text="Save M3U", width=90,
            fg_color="#575959", hover_color="#484949",
            command=self._save_m3u, state="disabled"
        )
        self.save_m3u_btn.pack(side="right")

        # ── Right Pane ──
        # ACTIVE RECORDINGS (moved to top)
        ctk.CTkLabel(right_pane, text="Active Recordings", font=("Arial", 13, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.recordings_frame = ctk.CTkScrollableFrame(right_pane)
        self.recordings_frame.pack(fill="both", expand=True, pady=(0, 8))
        self.no_recordings_label = ctk.CTkLabel(self.recordings_frame, text="No recordings scheduled.", text_color="gray")
        self.no_recordings_label.pack(pady=10)

        # Status panel (moved below recordings)
        status_panel = ctk.CTkFrame(right_pane)
        status_panel.pack(fill="x", pady=(0, 8))
        self.global_status = ctk.CTkLabel(status_panel, text="Fetching channel list…", text_color="gray")
        self.global_status.pack(pady=(6, 2))

        self.startup_label = ctk.CTkLabel(status_panel, text="Startup: checking…", text_color="gray40", font=("Arial", 10))
        self.startup_label.pack(pady=(0, 4))

        remote_frame = ctk.CTkFrame(status_panel, fg_color="transparent")
        remote_frame.pack(pady=(0, 4))
        self.remote_label = ctk.CTkLabel(remote_frame, text="Remote: starting…",
                                         text_color="gray40", font=("Arial", 10), cursor="hand2")
        self.remote_label.pack(side="left")
        self.remote_label.bind("<Button-1>",
                               lambda e: webbrowser.open(self.current_remote_url) if self.current_remote_url else None)
        self.remote_copy_btn = ctk.CTkButton(
            remote_frame, text="Copy", width=40, height=20, font=("Arial", 10),
            fg_color="#575959", hover_color="#484949",
            command=self._copy_remote_url, state="disabled"
        )
        self.remote_copy_btn.pack(side="left", padx=(8, 0))

        tunnel_frame = ctk.CTkFrame(status_panel, fg_color="transparent")
        tunnel_frame.pack(pady=(0, 8))
        self.tunnel_label = ctk.CTkLabel(
            tunnel_frame,
            text="Tunnel: not configured",
            text_color="gray40",
            font=("Arial", 10),
            cursor="hand2",
        )
        self.tunnel_label.pack(side="left")
        self.tunnel_label.bind("<Button-1>", lambda e: self._open_tunnel_url())
        self.tunnel_copy_btn = ctk.CTkButton(
            tunnel_frame, text="Copy", width=40, height=20, font=("Arial", 10),
            fg_color="#575959", hover_color="#484949",
            command=self._copy_tunnel_url, state="disabled"
        )
        self.tunnel_copy_btn.pack(side="left", padx=(8, 0))
        self._refresh_remote_links()
        self._refresh_startup_status()

        ctk.CTkLabel(right_pane, text="Recording Log", font=("Arial", 13, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.log_box = ctk.CTkTextbox(right_pane, height=160, state="disabled")
        self.log_box.pack(fill="x", pady=(0, 0))

        self.after(200, self._install_window_scroll)

    # ── Favorites ─────────────────────────────────────────────────────────────

    def _load_favorites(self):
        self.favorites = load_favorites(config.FAVORITES_FILE)

    def _save_favorites(self):
        save_favorites(config.FAVORITES_FILE, self.favorites)

    def _load_settings(self):
        try:
            import json
            with open(config.SETTINGS_FILE, "r") as f:
                data = json.load(f)
            if "output_dir" in data and os.path.isdir(data["output_dir"]):
                self.output_dir = data["output_dir"]
            if "dvr_buffer_dir" in data and data["dvr_buffer_dir"]:
                config.DVR_BUFFER_DIR = data["dvr_buffer_dir"]
            if "dvr_max_hours" in data:
                try:
                    config.DVR_MAX_HOURS = int(data["dvr_max_hours"])
                except (ValueError, TypeError):
                    pass
            if "dvr_max_gb" in data:
                try:
                    config.DVR_MAX_GB = int(data["dvr_max_gb"])
                except (ValueError, TypeError):
                    pass
            if "schedule_file" in data and data["schedule_file"]:
                config.SCHEDULES_FILE = data["schedule_file"]
            if "recording_failover_secs" in data:
                try:
                    config.RECORDING_FAILOVER_SECS = max(5, int(data["recording_failover_secs"]))
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

    def _persist_recording_jobs(self):
        try:
            payload = []
            for job in self.recording_jobs:
                if job.status not in ("waiting", "recording"):
                    continue
                row = {
                    "channel_name": job.channel_name,
                    "channel_id": job.channel_id,
                    "start_time": job.start_time.isoformat(),
                    "duration_mins": int(getattr(job, "duration_mins", 0)),
                    "duration_secs": int(getattr(job, "duration_secs", job_duration_secs(job))),
                    "output_dir": job.output_dir,
                    "backup_channel_id": job.backup_channel_id,
                    "backup_channel_name": job.backup_channel_name,
                }
                if job.custom_name:
                    row["custom_name"] = job.custom_name
                payload.append(row)
            with open(config.SCHEDULES_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception:
            pass

    def _load_scheduled_recordings(self):
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

            job = RecordingJob(
                channel_name,
                channel_id,
                job_start_time,
                job_duration_mins,
                item.get("output_dir") or self.output_dir,
                custom_name=item.get("custom_name"),
            )
            job.duration_secs = job_duration_secs
            job.backup_channel_id = item.get("backup_channel_id") or None
            job.backup_channel_name = item.get("backup_channel_name") or None
            self.recording_jobs.append(job)
            self._add_recording_card(job)
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            restored += 1

        if restored:
            self._log(f"Restored {restored} queued recording(s) from the last session.")
        self._persist_recording_jobs()

    def _save_settings(self):
        try:
            import json
            with open(config.SETTINGS_FILE, "w") as f:
                json.dump({
                    "output_dir":     self.output_dir,
                    "dvr_buffer_dir": config.DVR_BUFFER_DIR,
                    "dvr_max_hours":  config.DVR_MAX_HOURS,
                    "dvr_max_gb":     config.DVR_MAX_GB,
                    "schedule_file":  config.SCHEDULES_FILE,
                    "recording_failover_secs": config.RECORDING_FAILOVER_SECS,
                }, f, indent=2)
        except Exception:
            pass

    def _refresh_favorites_panel(self):
        for w in self.fav_scroll.winfo_children():
            w.destroy()
        if not self.favorites:
            ctk.CTkLabel(self.fav_scroll, text="No saved channels yet.", text_color="gray").pack(pady=8)
            self._bind_scroll_tree(self.fav_scroll)
            return
        for fav in self.favorites:
            row = ctk.CTkFrame(self.fav_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkButton(
                row, text=fav["name"], anchor="w",
                fg_color="#484949", hover_color="#575959", height=28,
                command=lambda f=fav: self._select_channel(f["name"]),
            ).pack(side="left", fill="x", expand=True, padx=(0, 4))
            ctk.CTkButton(
                row, text="✕", width=28, height=28,
                fg_color="#333434", hover_color="#c0392b", text_color="gray",
                command=lambda n=fav["name"]: self._remove_favorite(n),
            ).pack(side="right")
        self._bind_scroll_tree(self.fav_scroll)

    def _toggle_save_channel(self):
        if not self.selected_channel_name:
            return
        names = [f["name"] for f in self.favorites]
        if self.selected_channel_name in names:
            self._remove_favorite(self.selected_channel_name)
        else:
            self.favorites.append({"name": self.selected_channel_name, "id": self.selected_channel_id})
            self._save_favorites()
            self._refresh_favorites_panel()
            self.save_btn.configure(text="Saved", fg_color="#1a6b3a")
            self._log(f"Saved: '{self.selected_channel_name}'")

    def _remove_favorite(self, name):
        self.favorites = [f for f in self.favorites if f["name"] != name]
        self._save_favorites()
        self._refresh_favorites_panel()
        if self.selected_channel_name == name:
            self.save_btn.configure(text="Save", fg_color="#F89344")
        self._log(f"Removed from favorites: '{name}'")

    def _update_save_btn_state(self):
        if not self.selected_channel_name:
            return
        already = any(f["name"] == self.selected_channel_name for f in self.favorites)
        self.save_btn.configure(
            text="Saved" if already else "Save",
            fg_color="#1a6b3a" if already else "#F89344"
        )

    # ── Web server ────────────────────────────────────────────────────────────

    def _start_web_server(self):
        ctx = WebContext(
            get_status_fn=self._web_get_status,
            get_channels_fn=lambda q: [
                {"name": n, "id": self.channel_map[n]}
                for n in self.all_channel_names
                if q.lower() in n.lower()
            ][:25],
            get_favorites_fn=lambda: list(self.favorites),
            get_log_fn=lambda: list(self._log_entries),
            action_queue=self._web_actions,
            dvr_manager=self.dvr_manager,
            get_all_channels_fn=lambda: [
                {"name": n, "id": self.channel_map[n]}
                for n in self.all_channel_names
            ],
            get_jobs_fn=lambda: list(self.recording_jobs),
            get_recordings_dir_fn=lambda: self.output_dir,
            preview_start_fn=self.live_preview.start,
            preview_stop_fn=self.live_preview.stop,
            get_settings_fn=self._web_get_settings,
        )
        try:
            url = start_web_server(ctx)
            self.current_remote_url = url
            self._refresh_remote_links()
            self._log(f"Remote control active: {url}")
            self.tunnel_mgr.start()
        except OSError:
            self.remote_label.configure(text=f"Remote: port {config.WEB_PORT} in use", text_color="#e74c3c")

    def _web_get_status(self):
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
                elapsed   = int((now - job.actual_start).total_seconds())
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
        return {
            "status": self._status_text,
            "backup_name": self.backup_channel_name,
            "recording_failover_secs": config.RECORDING_FAILOVER_SECS,
            "recordings": recordings,
        }

    def _web_get_settings(self):
        return {
            "recording_failover_secs": int(config.RECORDING_FAILOVER_SECS),
        }

    def _process_web_actions(self):
        while not self._web_actions.empty():
            action = self._web_actions.get_nowait()
            if action["type"] == "schedule":
                self._web_schedule(action)
            elif action["type"] == "stop":
                active = [j for j in self.recording_jobs if j.status in ("waiting", "recording")]
                idx = action.get("index", 0)
                if 0 <= idx < len(active):
                    self._stop_job(active[idx])
            elif action["type"] == "fav_add":
                name, fav_id = action.get("name"), action.get("id")
                if name and fav_id and not any(f["name"] == name for f in self.favorites):
                    self.favorites.append({"name": name, "id": fav_id})
                    self._save_favorites()
                    self._refresh_favorites_panel()
                    self._log(f"[Remote] Saved channel: '{name}'")
            elif action["type"] == "fav_remove":
                name = action.get("name")
                if name:
                    self._remove_favorite(name)
                    self._log(f"[Remote] Removed channel: '{name}'")
            elif action["type"] == "backup_set":
                self.backup_channel_id = action.get("id")
                self.backup_channel_name = action.get("name")
                self.backup_sel_label.configure(text=f"Backup: {self.backup_channel_name}", text_color="#3498db")
                self.backup_clear_btn.configure(state="normal")
                self._log(f"[Remote] Set backup channel: '{self.backup_channel_name}'")
            elif action["type"] == "backup_clear":
                self._clear_backup_channel()
                self._log("[Remote] Cleared backup channel")
            elif action["type"] == "set_recording_failover_secs":
                try:
                    secs = max(5, int(action.get("value")))
                    config.RECORDING_FAILOVER_SECS = secs
                    self._save_settings()
                    self._log(f"[Remote] Recording failover set to {secs}s")
                except (TypeError, ValueError):
                    self._log("[Remote] Invalid recording failover value ignored")

    def _web_schedule(self, action):
        try:
            now = datetime.datetime.now()
            parsed, kind = parse_schedule_start_time_raw(action.get("start_time"), now)
            start_time = normalize_schedule_start_time(parsed, now, kind)
            job = RecordingJob(
                action["channel_name"], action["channel_id"],
                start_time, int(action["duration_mins"]), self.output_dir,
                custom_name=action.get("custom_name"),
            )
            job.backup_channel_id   = self.backup_channel_id
            job.backup_channel_name = self.backup_channel_name
            self.recording_jobs.append(job)
            self._add_recording_card(job)
            self._persist_recording_jobs()
            backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
            if action.get("start_time") == "NOW":
                self._log(f"[Remote] Started recording '{job.channel_name}' for {job.duration_mins} min.{backup_info}")
                self._set_status(f"Recording: {job.channel_name}", "#e74c3c")
            else:
                self._log(f"[Remote] Scheduled '{job.channel_name}' at {start_time.strftime('%I:%M %p')} for {job.duration_mins} min.{backup_info}")
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
        except Exception as e:
            self._log(f"[Remote] Schedule error: {e}")

    # ── Channel Loading ───────────────────────────────────────────────────────

    def _start_fetching(self):
        self._status_text = "Fetching channel list…"
        self.global_status.configure(text=self._status_text, text_color="gray")
        self._fetch_start = datetime.datetime.now()
        self._fetch_result = None
        self._channels_loaded = False
        threading.Thread(target=self._fetch_channels, daemon=True).start()

    def _open_settings(self):
        CredentialsDialog(self, self._on_settings_saved)

    def _on_settings_saved(self):
        load_credentials()
        self.channel_map = {}
        self.all_channel_names = []
        self.m3u_text = ""
        self._fetch_start = datetime.datetime.now()
        self._channels_loaded = False
        self._refresh_startup_status()
        threading.Thread(target=self._fetch_channels, daemon=True).start()
        self.search_entry.delete(0, "end")
        self.search_entry.configure(state="disabled", placeholder_text="Loading channels — please wait…")
        self.backup_search_entry.configure(state="disabled", placeholder_text="Search for backup channel…")
        self.backup_channel_name = None
        self.backup_channel_id   = None
        self.backup_sel_label.configure(text="No backup selected", text_color="gray40")
        self.backup_clear_btn.configure(state="disabled")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()
        self.record_now_btn.configure(state="disabled")
        self.schedule_btn.configure(state="disabled")
        self.save_m3u_btn.configure(state="disabled")
        self._refresh_remote_links()

        if config.SERVER_URL and config.USERNAME and config.PASSWORD:
            self._start_fetching()
        else:
            self._set_status("Missing credentials. Please configure in Settings.", "#e74c3c")

    def _fetch_channels(self):
        try:
            trimmed_path = Path(getattr(config, "TRIMMED_M3U_PATH", "")).expanduser()
            if trimmed_path.exists() and trimmed_path.is_file() and trimmed_path.stat().st_size > 0:
                self.m3u_text = trimmed_path.read_text(encoding="utf-8", errors="replace")
                source_label = str(trimmed_path)
            else:
                url = f"{config.SERVER_URL}/get.php?username={config.USERNAME}&password={config.PASSWORD}&type=m3u_plus&output=ts"
                response = requests.get(url, timeout=60)
                self.m3u_text = response.text
                source_label = url

            lines = self.m3u_text.splitlines()
            current_name = ""
            for line in lines:
                if line.startswith("#EXTINF"):
                    current_name = line.split(",")[-1].strip()
                elif line.startswith("http") and current_name:
                    channel_id = line.split("/")[-1].replace(".ts", "").strip()
                    self.channel_map[current_name] = channel_id
                    current_name = ""
            self.all_channel_names = sorted(self.channel_map.keys())
            self._fetch_result = ("ok", len(self.all_channel_names))
            self._log(f"Loaded channels from {source_label}")
        except Exception as e:
            self._fetch_result = ("err", str(e))

    def _on_channels_loaded(self, count):
        self._channels_loaded = True
        self.search_entry.configure(state="normal", placeholder_text="Type to search channels…")
        self.backup_search_entry.configure(state="normal", placeholder_text="Search for backup channel…")
        self.record_now_btn.configure(state="normal")
        self.schedule_btn.configure(state="normal")
        self.save_m3u_btn.configure(state="normal")
        msg = f"Ready — {count:,} channels loaded"
        self._status_text = msg
        self.global_status.configure(text=msg, text_color="#2ecc71")
        self._log(f"Loaded {count:,} channels from provider.")

    def _on_channels_error(self, err):
        self._channels_loaded = True
        msg = "Failed to load channels. Check credentials/URL."
        self._status_text = msg
        self.global_status.configure(text=msg, text_color="red")
        self._log(f"Error fetching channels: {err}")

    # ── Channel Search / Selection ────────────────────────────────────────────

    def _on_search_key(self, event=None):
        query = self.search_entry.get().strip()
        for w in self.results_frame.winfo_children():
            w.destroy()
        if not query or not self.all_channel_names:
            self.results_frame.pack_forget()
            return
        matches = [n for n in self.all_channel_names if query.lower() in n.lower()][:20]
        if not matches:
            self.results_frame.pack(fill="x", padx=15, pady=(0, 4), before=self.sel_row)
            ctk.CTkLabel(self.results_frame, text="No matches.", text_color="gray").pack(pady=6)
            return
        self.results_frame.pack(fill="x", padx=15, pady=(0, 4), before=self.sel_row)
        for name in matches:
            ctk.CTkButton(
                self.results_frame, text=name, anchor="w",
                fg_color="transparent", hover_color="#484949", height=28,
                command=lambda n=name: self._select_channel(n),
            ).pack(fill="x", pady=1, padx=2)
        self._bind_scroll_tree(self.results_frame)

    def _select_channel(self, name):
        self.selected_channel_name = name
        self.selected_channel_id   = self.channel_map.get(name)
        self.selected_label.configure(text=f"Selected: {name}", text_color="white")
        self.preview_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self._update_save_btn_state()
        self.search_entry.delete(0, "end")
        for w in self.results_frame.winfo_children():
            w.destroy()
        self.results_frame.pack_forget()
        self._epg_channel_id = self.selected_channel_id
        self._epg_result = None
        self._show_epg_loading()
        if not self._epg_expanded:
            self._toggle_epg_section()
        threading.Thread(target=self._fetch_epg, args=(self.selected_channel_id,), daemon=True).start()

    # ── Backup Channel Search ─────────────────────────────────────────────────

    def _on_backup_search_key(self, event=None):
        query = self.backup_search_entry.get().strip()
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        if not query or not self.all_channel_names:
            self.backup_results_frame.pack_forget()
            return
        matches = [n for n in self.all_channel_names if query.lower() in n.lower()][:20]
        if not matches:
            self.backup_results_frame.pack(fill="x", pady=(0, 4), before=self._backup_results_anchor)
            ctk.CTkLabel(self.backup_results_frame, text="No matches.", text_color="gray").pack(pady=6)
            return
        self.backup_results_frame.pack(fill="x", pady=(0, 4), before=self._backup_results_anchor)
        for name in matches:
            ctk.CTkButton(
                self.backup_results_frame, text=name, anchor="w",
                fg_color="transparent", hover_color="#484949", height=28,
                command=lambda n=name: self._select_backup_channel(n),
            ).pack(fill="x", pady=1, padx=2)
        self._bind_scroll_tree(self.backup_results_frame)

    def _select_backup_channel(self, name):
        self.backup_channel_name = name
        self.backup_channel_id   = self.channel_map.get(name)
        self.backup_sel_label.configure(text=f"Backup: {name}", text_color="#3498db")
        self.backup_clear_btn.configure(state="normal")
        self.backup_search_entry.delete(0, "end")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()

    def _toggle_backup_section(self):
        self._backup_expanded = not self._backup_expanded
        if self._backup_expanded:
            self._backup_body.pack(fill="x")
            self._backup_toggle_btn.configure(text="▼  Backup Channel")
        else:
            self._backup_body.pack_forget()
            self._backup_toggle_btn.configure(text="▶  Backup Channel")

    def _clear_backup_channel(self):
        self.backup_channel_name = None
        self.backup_channel_id   = None
        self.backup_sel_label.configure(text="No backup selected", text_color="gray40")
        self.backup_clear_btn.configure(state="disabled")
        self.backup_search_entry.delete(0, "end")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()

    # ── Live Sports ───────────────────────────────────────────────────────────

    def _toggle_sports_section(self):
        self._sports_expanded = not self._sports_expanded
        if self._sports_expanded:
            self._sports_body.pack(fill="x")
            self._sports_toggle_btn.configure(text="▼  Live Sports Today")
            if not self.sports_scroll.winfo_children():
                self._fetch_sports()
        else:
            self._sports_body.pack_forget()
            self._sports_toggle_btn.configure(text="▶  Live Sports Today")

    def _fetch_sports(self, *args):
        league = self._sports_league.get()
        for w in self.sports_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.sports_scroll, text=f"Loading {league} schedule...", text_color="gray").pack(pady=10)

        def task():
            sport_map = {"NHL": "hockey/nhl", "NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb"}
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_map[league]}/scoreboard?dates={today_str}"
            try:
                r = requests.get(url, timeout=8)
                data = r.json()
                events = data.get("events", [])
                self.after(0, lambda: self._render_sports(events, league))
            except Exception as e:
                self.after(0, lambda: self._render_sports_error(str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _render_sports_error(self, err):
        for w in self.sports_scroll.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.sports_scroll, text=f"Error loading schedule:\n{err}", text_color="#e74c3c").pack(pady=10)

    def _render_sports(self, events, league):
        for w in self.sports_scroll.winfo_children():
            w.destroy()
        if not events:
            ctk.CTkLabel(self.sports_scroll, text="No games scheduled for today.", text_color="gray").pack(pady=10)
            return

        durations = {"NHL": 210, "NBA": 180, "NFL": 240, "MLB": 240}
        default_dur = durations.get(league, 210)
        today = datetime.date.today()
        todays_events = []

        for event in events:
            name = event.get("shortName", event.get("name", "Unknown Game"))
            date_str = event.get("date", "")
            local_dt = None
            local_time = ""
            try:
                ds = date_str.replace("Z", "+00:00")
                utc_dt = datetime.datetime.fromisoformat(ds)
                local_dt = utc_dt.astimezone()
                local_time = local_dt.strftime("%I:%M %p")
            except Exception:
                try:
                    utc_dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ")
                    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
                    local_dt = utc_dt.astimezone()
                    local_time = local_dt.strftime("%I:%M %p")
                except Exception:
                    local_time = "Unknown Time"
            if local_dt and local_dt.date() != today:
                continue
            todays_events.append((event, local_dt, local_time, name))

        if not todays_events:
            ctk.CTkLabel(self.sports_scroll, text="No games scheduled for today.", text_color="gray").pack(pady=10)
            return

        for event, local_dt, local_time, name in todays_events:
            status = event.get("status", {}).get("type", {}).get("description", "")
            if "In Progress" in status or "Halftime" in status:
                local_time = "LIVE NOW"
            elif "Final" in status:
                local_time = "FINAL"

            card = ctk.CTkFrame(self.sports_scroll, fg_color="#3a3b3b", corner_radius=6)
            card.pack(fill="x", pady=3, padx=4)
            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))
            ctk.CTkLabel(top, text=name, font=("Arial", 12, "bold"), anchor="w").pack(side="left")
            ctk.CTkLabel(top, text=local_time, font=("Arial", 11), text_color="#aaaaaa").pack(side="right")
            bot = ctk.CTkFrame(card, fg_color="transparent")
            bot.pack(fill="x", padx=8, pady=(0, 6))

            networks = []
            try:
                for b in event.get("competitions", [{}])[0].get("broadcasts", []):
                    for n in b.get("names", []):
                        networks.append(n)
            except Exception:
                pass
            networks = list(dict.fromkeys(networks))

            if networks:
                ctk.CTkLabel(bot, text="Find TV:", font=("Arial", 10), text_color="gray").pack(side="left", padx=(0, 6))
                for net in networks:
                    btn = ctk.CTkButton(bot, text=net, width=40, height=20, font=("Arial", 10),
                                        fg_color="#2563eb", hover_color="#1d4ed8",
                                        command=lambda n=net, dt=local_dt, d=default_dur: self._apply_sport_game(n, dt, d))
                    btn.pack(side="left", padx=2)

            full_team_names = []
            try:
                for comp in event.get("competitions", [{}])[0].get("competitors", []):
                    dn = comp.get("team", {}).get("displayName", "")
                    if dn:
                        full_team_names.append(dn)
            except Exception:
                pass
            search_str = " ".join(full_team_names) if full_team_names else name.replace("@", "").replace("VS", "").strip()
            t_btn = ctk.CTkButton(bot, text="Search Teams" if networks else "Find by Team",
                                  width=60, height=20, font=("Arial", 10),
                                  fg_color="#484949", hover_color="#575959",
                                  command=lambda s=search_str, dt=local_dt, d=default_dur: self._apply_sport_game(s, dt, d))
            t_btn.pack(side="right", padx=2)

        self._bind_scroll_tree(self.sports_scroll)

    def _apply_sport_game(self, query, start_dt, duration):
        if start_dt:
            self._set_epg_time(start_dt.strftime("%I:%M %p"), duration)
        self.search_entry.configure(state="normal")
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)
        self._on_search_key()
        self._log(f"Pre-filled schedule info for: {query}")

    # ── EPG ───────────────────────────────────────────────────────────────────

    def _toggle_epg_section(self):
        self._epg_expanded = not self._epg_expanded
        if self._epg_expanded:
            self._epg_wrapper.pack(fill="x", pady=(4, 0))
            self._epg_toggle_btn.configure(text="▼  Program Guide")
        else:
            self._epg_wrapper.pack_forget()
            has_data = bool(self.epg_frame.winfo_children())
            self._epg_toggle_btn.configure(
                text="▶  Program Guide  ✓" if has_data else "▶  Program Guide"
            )

    def _fetch_epg(self, channel_id):
        try:
            self._epg_result = (
                channel_id,
                fetch_epg(config.SERVER_URL, config.USERNAME, config.PASSWORD, channel_id, limit=16),
            )
        except Exception:
            self._epg_result = (channel_id, None)

    def _decode_epg(self, text):
        import base64
        try:
            return base64.b64decode(text).decode("utf-8").strip()
        except Exception:
            return str(text).strip()

    def _show_epg_loading(self):
        for w in self.epg_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.epg_frame, text="Fetching program guide…", text_color="gray").pack(pady=8, padx=10)

    @staticmethod
    def _parse_epg_ts(val):
        if val is None:
            return None
        s = str(val).strip()
        # Unix timestamp (plain digits, e.g. "1776265200")
        if s.isdigit() and len(s) > 8:
            return datetime.datetime.fromtimestamp(int(s))
        # XMLTV compact format "20260415190000 -0400"
        if len(s) >= 14 and s[:14].isdigit():
            digits = s[:14]
            dt = datetime.datetime(
                int(digits[0:4]), int(digits[4:6]),  int(digits[6:8]),
                int(digits[8:10]), int(digits[10:12]), int(digits[12:14]),
            )
            tz = s[14:].strip()
            if tz and tz[0] in ("+", "-"):
                sign = 1 if tz[0] == "+" else -1
                h, m = int(tz[1:3]), int(tz[3:5]) if len(tz) >= 5 else 0
                dt = dt - datetime.timedelta(hours=h * sign, minutes=m * sign)
                dt = dt + datetime.timedelta(seconds=-time.timezone if not time.daylight else -time.altzone)
            return dt
        # Xtream API datetime string "2026-04-15 07:00:00" or "2026-04-15T07:00:00"
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.datetime.strptime(s[:19], fmt)
            except ValueError:
                pass
        return None

    def _show_epg(self, channel_id, listings):
        if channel_id != self._epg_channel_id:
            return
        for w in self.epg_frame.winfo_children():
            w.destroy()
        if not listings:
            ctk.CTkLabel(self.epg_frame, text="No guide data available.", text_color="gray").pack(pady=8, padx=10)
            self._epg_toggle_btn.configure(text="▶  Program Guide")
            return
        self._epg_toggle_btn.configure(text="▶  Program Guide  ✓")
        now = datetime.datetime.now()
        first = True
        for listing in listings:
            try:
                raw_start = listing.get("start") or listing.get("start_timestamp")
                raw_stop  = listing.get("stop")  or listing.get("stop_timestamp")
                start = self._parse_epg_ts(raw_start)
                stop  = self._parse_epg_ts(raw_stop)
                if start is None or stop is None:
                    continue
            except Exception:
                continue
            title = self._decode_epg(listing.get("title", ""))
            desc  = self._decode_epg(listing.get("description", ""))
            is_now = start <= now < stop
            start_str = start.strftime("%I:%M %p")
            duration_mins = max(1, int((stop - start).total_seconds() / 60))
            row = ctk.CTkFrame(self.epg_frame, fg_color="#444545" if is_now else "transparent")
            row.pack(fill="x", padx=6, pady=(4 if first else 1, 1))
            first = False
            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x", padx=8, pady=(4, 0))
            if is_now:
                ctk.CTkLabel(hdr, text=" NOW ", font=("Arial", 10, "bold"),
                             fg_color="#e74c3c", corner_radius=4, text_color="white").pack(side="left", padx=(0, 6))
            ctk.CTkLabel(hdr, text=f"{start.strftime('%I:%M %p')} – {stop.strftime('%I:%M %p')}",
                         text_color="#aaaaaa", font=("Arial", 11)).pack(side="left")
            ctk.CTkButton(
                hdr, text="Set Time", width=66, height=22,
                fg_color="#575959", hover_color="#636666", font=("Arial", 10),
                command=lambda s=start_str, d=duration_mins: self._set_epg_time(s, d)
            ).pack(side="right")
            ctk.CTkLabel(row, text=title, anchor="w",
                         font=("Arial", 12, "bold" if is_now else "normal")).pack(fill="x", padx=8, pady=(0, 2))
            if desc:
                ctk.CTkLabel(row, text=desc[:100] + ("…" if len(desc) > 100 else ""),
                             anchor="w", text_color="gray", wraplength=440,
                             font=("Arial", 10)).pack(fill="x", padx=8, pady=(0, 4))
        self._bind_scroll_tree(self.epg_frame)

    # ── Stream Preview ────────────────────────────────────────────────────────

    def _preview_stream(self):
        if not self.selected_channel_id:
            return
        stream_url = (f"{config.SERVER_URL}/live/{config.USERNAME}"
                      f"/{config.PASSWORD}/{self.selected_channel_id}.ts")
        try:
            subprocess.Popen(
                ["ffplay", "-window_title", f"Preview: {self.selected_channel_name}", stream_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **config._SUBPROCESS_FLAGS,
            )
            self._log(f"Preview launched: '{self.selected_channel_name}'")
        except FileNotFoundError:
            self._log("Error: ffplay not found. It ships with FFmpeg — check your PATH.")

    # ── Folder & M3U ─────────────────────────────────────────────────────────

    def _pick_folder(self):
        folder = fd.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            self.folder_label.configure(text=folder)
            self._save_settings()

    def _open_output_folder(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.output_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self.output_dir])
        else:
            subprocess.Popen(["xdg-open", self.output_dir])

    def _save_m3u(self):
        if not self.m3u_text:
            return
        path = fd.asksaveasfilename(
            initialdir=self.output_dir, defaultextension=".m3u",
            filetypes=[("M3U Playlist", "*.m3u"), ("All files", "*.*")],
            initialfile="Playlist.m3u",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.m3u_text)
            self._log(f"M3U saved: {path}")
            self.global_status.configure(text="Playlist saved!", text_color="#2ecc71")

    # ── Scheduling ───────────────────────────────────────────────────────────

    def _record_now(self):
        if not self.selected_channel_id:
            self._set_status("Error: Search and select a channel first.", "red")
            return

        # Get default duration from the main input field
        try:
            default_duration = int(self.duration_input.get().strip())
        except ValueError:
            default_duration = 180

        # Show duration selection dialog with time helper
        def on_confirm_duration(duration_mins):
            self._start_recording_now(duration_mins)

        RecordNowDialog(self, self.selected_channel_name, on_confirm_duration, default_duration)

    def _start_recording_now(self, duration_mins):
        """Actually start the recording with the confirmed duration."""
        now = datetime.datetime.now()
        job = RecordingJob(self.selected_channel_name, self.selected_channel_id,
                           now, duration_mins, self.output_dir)
        job.backup_channel_id   = self.backup_channel_id
        job.backup_channel_name = self.backup_channel_name
        self.recording_jobs.append(job)
        self._add_recording_card(job)
        self._persist_recording_jobs()
        backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
        self._log(f"Started recording '{job.channel_name}' for {duration_mins} min.{backup_info}")
        self._set_status(f"Recording: {job.channel_name}", "#e74c3c")
        threading.Thread(target=run_job, args=(job,), daemon=True).start()

    def _schedule_recording(self):
        if not self.selected_channel_id:
            self._set_status("Error: Search and select a channel first.", "red")
            return
        start_time_str = self.time_input.get().strip()
        if not start_time_str:
            self._set_status("Error: Enter a start time.", "red")
            return
        try:
            duration_mins = int(self.duration_input.get().strip())
            if duration_mins <= 0:
                raise ValueError
        except ValueError:
            self._set_status("Error: Duration must be a positive number.", "red")
            return
        now = datetime.datetime.now()
        try:
            start_time = datetime.datetime.strptime(start_time_str, "%I:%M %p").replace(
                year=now.year, month=now.month, day=now.day
            )
        except ValueError:
            self._set_status("Error: Use format  07:00 PM", "red")
            return
        if start_time < now:
            start_time += datetime.timedelta(days=1)
        job = RecordingJob(self.selected_channel_name, self.selected_channel_id,
                           start_time, duration_mins, self.output_dir)
        job.backup_channel_id   = self.backup_channel_id
        job.backup_channel_name = self.backup_channel_name
        self.recording_jobs.append(job)
        self._add_recording_card(job)
        self._persist_recording_jobs()
        backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
        self._log(f"Scheduled '{job.channel_name}' at {start_time.strftime('%I:%M %p')} for {duration_mins} min.{backup_info}")
        self._set_status(f"Scheduled: {job.channel_name} at {start_time_str}", "#2ecc71")
        threading.Thread(target=run_job, args=(job,), daemon=True).start()

    # ── Recording Cards ───────────────────────────────────────────────────────

    def _add_recording_card(self, job):
        self.no_recordings_label.pack_forget()
        card = ctk.CTkFrame(self.recordings_frame, corner_radius=8)
        card.pack(fill="x", pady=4, padx=2)
        job.card_frame = card
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(top, text=job.channel_name, font=("Arial", 13, "bold"), anchor="w").pack(side="left")
        job.stop_btn = ctk.CTkButton(top, text="Stop", width=58, height=24,
                                     fg_color="#c0392b", hover_color="#e74c3c",
                                     command=lambda j=job: self._stop_job(j))
        job.stop_btn.pack(side="right")
        ctk.CTkLabel(card, anchor="w", text_color="gray",
                     text=f"Scheduled: {job.start_time.strftime('%I:%M %p')}  |  Duration: {job.duration_mins} min"
                     ).pack(fill="x", padx=10, pady=(0, 2))
        job.status_label = ctk.CTkLabel(card, text="Waiting to start…", text_color="#f39c12", anchor="w")
        job.status_label.pack(fill="x", padx=10, pady=(0, 8))
        self._bind_scroll_tree(self.recordings_frame)

    # ── Tick ─────────────────────────────────────────────────────────────────

    def _tick(self):
        now = datetime.datetime.now()

        if not self._channels_loaded:
            result = self._fetch_result
            if result is not None:
                if result[0] == "ok":
                    self._on_channels_loaded(result[1])
                else:
                    self._on_channels_error(result[1])
            else:
                elapsed = int((now - self._fetch_start).total_seconds())
                self.global_status.configure(text=f"Fetching channel list… ({elapsed}s)", text_color="gray")

        epg = self._epg_result
        if epg is not None:
            self._epg_result = None
            self._show_epg(epg[0], epg[1])

        # Drain tunnel output into log
        while self.tunnel_mgr.lines:
            self._log(f"[Tunnel] {self.tunnel_mgr.lines.pop(0)}")

        # Poll tunnel URL / errors
        tunnel_url = self.tunnel_mgr.url
        if tunnel_url is not None:
            self.tunnel_mgr.url = None
            self.current_remote_url = tunnel_url
            self.current_tunnel_url = tunnel_url
            self._refresh_remote_links()
            self._log(f"[Tunnel] URL active: {tunnel_url}")
        tunnel_log = self.tunnel_mgr.log
        if tunnel_log is not None:
            self.tunnel_mgr.log = None
            self._log(tunnel_log)

        self._process_web_actions()

        for job in self.recording_jobs:
            while job._pending_logs:
                self._log(job._pending_logs.pop(0))
            if job.status_label is None:
                continue
            if job.finish_msg is not None:
                msg, color = job.finish_msg
                job.finish_msg = None
                self._finalize_card(job, msg, color)
                self._log(f"{msg} '{job.channel_name}'")
                self._persist_recording_jobs()
                if self._status_text == f"Recording: {job.channel_name}":
                    self._set_status(f"Recording finished: {job.channel_name}", "#2ecc71")
                continue
            if job.status == "waiting":
                secs = max(0, int((job.start_time - now).total_seconds()))
                job.status_label.configure(
                    text=f"Starts in {str(datetime.timedelta(seconds=secs))}", text_color="#f39c12")
            elif job.status == "recording" and job.actual_start:
                elapsed   = int((now - job.actual_start).total_seconds())
                remaining = max(0, job_duration_secs(job) - elapsed)
                on_bkup      = job.active_channel_name != job.channel_name
                backup_str   = f"[BACKUP: {job.active_channel_name}]  " if on_bkup else ""
                reconnect_str = f"  |  Reconnects: {job.reconnect_count}" if job.reconnect_count > 0 else ""
                job.status_label.configure(
                    text=(f"{backup_str}RECORDING  |  Elapsed: {str(datetime.timedelta(seconds=elapsed))}"
                          f"  |  Remaining: {str(datetime.timedelta(seconds=remaining))}{reconnect_str}"),
                    text_color="#e74c3c")

        self.after(1000, self._tick)

    # ── Job Control ───────────────────────────────────────────────────────────

    def _stop_job(self, job):
        if job.status in ("complete", "stopped", "error"):
            return
        job.status = "stopped"
        if job.process and job.process.poll() is None:
            job.process.terminate()
        self._finalize_card(job, "Stopped by user.", "#e67e22")
        self._log(f"User stopped: '{job.channel_name}'")
        self._persist_recording_jobs()
        if self._status_text == f"Recording: {job.channel_name}":
            self._set_status(f"Stopped: {job.channel_name}", "#e67e22")

    def _finalize_card(self, job, message, color):
        if job.status_label:
            job.status_label.configure(text=message, text_color=color)
        if job.stop_btn:
            job.stop_btn.configure(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_closing(self):
        self.tunnel_mgr.stop()
        self.live_preview.stop_all()
        for job in self.recording_jobs:
            if job.status == "recording" and job.process:
                try:
                    job.process.terminate()
                except Exception:
                    pass
        self._persist_recording_jobs()
        self.destroy()
        sys.exit(0)

    def _log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", entry + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self._log_entries.append(entry)
        if len(self._log_entries) > 200:
            self._log_entries.pop(0)

    def _set_epg_time(self, time_str, duration_mins=None):
        self.time_input.delete(0, "end")
        self.time_input.insert(0, time_str)
        if duration_mins is not None:
            self.duration_input.delete(0, "end")
            self.duration_input.insert(0, str(duration_mins))
            self._update_hours_display()

    def _apply_preset_duration(self, duration_mins):
        """Apply a preset duration and update hours display."""
        self.duration_input.delete(0, "end")
        self.duration_input.insert(0, str(duration_mins))
        self._update_hours_display()
        self._set_status(f"Duration set to {duration_mins} minutes ({duration_mins/60:.1f} hours)", "#2ecc71")

    def _update_hours_display(self, event=None):
        """Update the hours display label based on current duration input."""
        try:
            mins = int(self.duration_input.get().strip())
            hours = mins / 60
            self.hours_display_label.configure(text=f"{hours:.1f} hrs")
        except (ValueError, AttributeError):
            self.hours_display_label.configure(text="-- hrs")

    def _calc_duration_from_end_time(self):
        """Calculate duration from start time and end time inputs."""
        try:
            start_str = self.time_input.get().strip()
            end_str = self.end_time_input.get().strip()

            if not start_str or not end_str:
                self._set_status("Enter both start and end times", "#e74c3c")
                return

            now = datetime.datetime.now()
            start_time = self._parse_time_string(start_str, now)
            end_time = self._parse_time_string(end_str, now)

            if end_time <= start_time:
                end_time += datetime.timedelta(days=1)

            duration_mins = int((end_time - start_time).total_seconds() / 60)

            self.duration_input.delete(0, "end")
            self.duration_input.insert(0, str(duration_mins))
            self._update_hours_display()

            self._set_status(f"Duration: {duration_mins} min ({duration_mins/60:.1f} hrs) from {start_time.strftime('%I:%M %p')} to {end_time.strftime('%I:%M %p')}", "#2ecc71")
        except ValueError as e:
            self._set_status(f"Invalid time format. Use format like '07:00 PM' or '19:00'", "#e74c3c")

    def _parse_time_string(self, time_str, base_date):
        """Parse a time string like '07:00 PM' or '19:00' into a datetime."""
        time_str = time_str.strip().upper()
        for fmt in ["%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%I%p"]:
            try:
                parsed = datetime.datetime.strptime(time_str, fmt)
                return base_date.replace(hour=parsed.hour, minute=parsed.minute, second=0, microsecond=0)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse time: {time_str}")

    def _set_status(self, message, color="gray"):
        self._status_text = message
        self.global_status.configure(text=message, text_color=color)

    def _configured_tunnel_url(self):
        provider = (config.TUNNEL_PROVIDER or "").strip()
        if provider == "cloudflare":
            domain = (config.CLOUDFLARE_DOMAIN or "").strip()
            return f"https://{domain}" if domain else ""
        elif provider == "instatunnel":
            subdomain = (config.INSTATUNNEL_SUBDOMAIN or "").strip()
            return f"https://{subdomain}.instatunnel.my" if subdomain else ""
        return ""

    def _refresh_remote_links(self):
        if self.current_remote_url:
            remote_text = (
                f"Remote (public): {self.current_remote_url}"
                if self.current_remote_url.startswith("https://")
                else f"Remote: {self.current_remote_url}"
            )
            self.remote_label.configure(text=remote_text, text_color="#3498db")
            self.remote_copy_btn.configure(state="normal")
        else:
            self.remote_label.configure(text="Remote: starting…", text_color="gray40")
            self.remote_copy_btn.configure(state="disabled")

        tunnel_url = self.current_tunnel_url or self._configured_tunnel_url()
        if tunnel_url:
            self.tunnel_label.configure(text=f"Tunnel: {tunnel_url}", text_color="#3498db")
            self.tunnel_copy_btn.configure(state="normal")
        else:
            self.tunnel_label.configure(text="Tunnel: not configured", text_color="gray40")
            self.tunnel_copy_btn.configure(state="disabled")

    def _refresh_startup_status(self):
        enabled = is_autostart_enabled()
        if enabled:
            self.startup_label.configure(text="Startup: enabled", text_color="#2ecc71")
        else:
            self.startup_label.configure(text="Startup: disabled", text_color="gray40")

    def _copy_remote_url(self):
        if self.current_remote_url:
            self.clipboard_clear()
            self.clipboard_append(self.current_remote_url)
            self.update()
            self._log("Remote URL copied to clipboard.")
            self.remote_copy_btn.configure(text="Copied!", fg_color="#1a6b3a")
            self.after(2000, lambda: self.remote_copy_btn.configure(text="Copy", fg_color="#575959"))

    def _open_tunnel_url(self):
        tunnel_url = self.current_tunnel_url or self._configured_tunnel_url()
        if tunnel_url:
            webbrowser.open(tunnel_url)

    def _copy_tunnel_url(self):
        tunnel_url = self.current_tunnel_url or self._configured_tunnel_url()
        if tunnel_url:
            self.clipboard_clear()
            self.clipboard_append(tunnel_url)
            self.update()
            self._log("Tunnel URL copied to clipboard.")
            self.tunnel_copy_btn.configure(text="Copied!", fg_color="#1a6b3a")
            self.after(2000, lambda: self.tunnel_copy_btn.configure(text="Copy", fg_color="#575959"))

    def _bind_scroll_tree(self, _scrollable_frame):
        pass

    def _install_window_scroll(self):
        def _find_scrollable_canvas(widget):
            while widget is not None:
                try:
                    if hasattr(widget, '_parent_canvas') and hasattr(widget, 'check_if_master_is_canvas'):
                        return widget._parent_canvas
                except Exception:
                    pass
                try:
                    parent = widget.master
                except Exception:
                    break
                if parent == widget:
                    break
                widget = parent
            return None

        def _on_mousewheel(event):
            try:
                w = event.widget.winfo_containing(event.x_root, event.y_root)
            except Exception:
                return
            if w is None:
                return
            canvas = _find_scrollable_canvas(w)
            if canvas is None:
                return
            if canvas.yview() == (0.0, 1.0):
                return
            if sys.platform == "darwin":
                canvas.yview_scroll(-event.delta, "units")
            elif sys.platform.startswith("win"):
                canvas.yview_scroll(-int(event.delta / 120), "units")
            else:
                canvas.yview_scroll(-event.delta, "units")

        self.bind_all("<MouseWheel>", _on_mousewheel)
        self.bind_all("<Button-4>", lambda e: _on_mousewheel(
            type('E', (), {'widget': e.widget, 'x_root': e.x_root, 'y_root': e.y_root, 'delta': 1})))
        self.bind_all("<Button-5>", lambda e: _on_mousewheel(
            type('E', (), {'widget': e.widget, 'x_root': e.x_root, 'y_root': e.y_root, 'delta': -1})))
