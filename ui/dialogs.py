"""
ui/dialogs.py — Setup wizard and credentials/settings dialog.

All dialogs read current values from config globals and write back
via core.credentials.save_credentials() so both disk and in-memory
globals stay in sync.
"""

import json
import os
import sys
import webbrowser

import customtkinter as ctk
import tkinter.filedialog as fd

import config
from core.credentials import save_credentials


# ── First-run setup wizard ─────────────────────────────────────────────────────

class SetupWizard(ctk.CTkToplevel):
    """
    Multi-step onboarding shown on first launch (no credentials.json yet).
    Walks the user through IPTV credentials and optional tunnel setup.
    """

    _PAGES   = ["welcome", "iptv", "tunnel"]
    _HEADERS = ["Welcome to IPTV Recorder", "IPTV Provider", "Remote Access  (optional)"]
    _STEPS   = ["", "Step 1 of 2", "Step 2 of 2"]

    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self._on_complete = on_complete
        self._page = 0

        self.title("Setup")
        self.geometry("500x560")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._finish)

        self._header_lbl = ctk.CTkLabel(self, text="", font=("Arial", 20, "bold"))
        self._header_lbl.pack(pady=(28, 2), padx=32)
        self._step_lbl = ctk.CTkLabel(self, text="", text_color="gray50", font=("Arial", 11))
        self._step_lbl.pack(pady=(0, 16))

        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=32)

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=32, pady=(8, 24))
        self._back_btn = ctk.CTkButton(nav, text="← Back", width=90,
                                       fg_color="#484949", hover_color="#575959",
                                       command=self._prev)
        self._back_btn.pack(side="left")
        self._skip_btn = ctk.CTkButton(nav, text="Skip", width=70,
                                       fg_color="#484949", hover_color="#575959",
                                       command=self._skip)
        self._skip_btn.pack(side="left", padx=(8, 0))
        self._next_btn = ctk.CTkButton(nav, text="Get Started →", command=self._next)
        self._next_btn.pack(side="right")

        self._pages = {}
        self._build_welcome()
        self._build_iptv()
        self._build_tunnel()
        self._show_page(0)

    def _build_welcome(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        ctk.CTkLabel(
            f,
            text="This app records live IPTV streams on a schedule.\nHere's what you'll need to get started:",
            text_color="gray70", font=("Arial", 12), justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 14))

        for title, desc in [
            ("📺  IPTV Subscription",
             "Any provider that uses the XtreamCodes format.\n"
             "They'll give you a Server URL, Username, and Password."),
            ("📡  Node.js  (optional — for remote control)",
             "Required to control recordings from your phone.\n"
             "Free download at nodejs.org if you want this feature."),
            ("🔑  InstaTunnel account  (optional — for remote control)",
             "Gives your app a public URL for phone access.\n"
             "Free account at instatunnel.my — takes 30 seconds."),
        ]:
            card = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=title, font=("Arial", 12, "bold"), anchor="w").pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(card, text=desc, text_color="gray55", font=("Arial", 11),
                         anchor="w", justify="left").pack(fill="x", padx=14, pady=(0, 10))
        self._pages["welcome"] = f

    def _build_iptv(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        ctk.CTkLabel(
            f,
            text="Enter the credentials from your IPTV provider.\n"
                 "Check your welcome email or your provider's dashboard.",
            text_color="gray70", font=("Arial", 12), justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(f, text="Server URL", anchor="w").pack(fill="x")
        self._url = ctk.CTkEntry(f, placeholder_text="http://provider.example.com:8080")
        self._url.pack(fill="x", pady=(0, 10))
        self._url.insert(0, config.SERVER_URL)

        ctk.CTkLabel(f, text="Username", anchor="w").pack(fill="x")
        self._user = ctk.CTkEntry(f)
        self._user.pack(fill="x", pady=(0, 10))
        self._user.insert(0, config.USERNAME)

        ctk.CTkLabel(f, text="Password", anchor="w").pack(fill="x")
        self._pass = ctk.CTkEntry(f, show="•")
        self._pass.pack(fill="x", pady=(0, 6))
        self._pass.insert(0, config.PASSWORD)

        self._iptv_err = ctk.CTkLabel(f, text="", text_color="#e74c3c", font=("Arial", 11), anchor="w")
        self._iptv_err.pack(fill="x")
        self._pages["iptv"] = f

    def _build_tunnel(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")
        info = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
        info.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(
            info,
            text="InstaTunnel gives your app a public HTTPS URL so you can\n"
                 "browse channels, save favourites, and schedule recordings\n"
                 "from your phone — even away from home.",
            text_color="gray55", font=("Arial", 11), justify="left", anchor="w",
        ).pack(fill="x", padx=14, pady=10)

        ctk.CTkButton(f, text="1.  Go to instatunnel.my and create a free account →",
                      fg_color="#484949", hover_color="#575959",
                      command=lambda: webbrowser.open("https://instatunnel.my")
                      ).pack(fill="x", pady=(0, 6))

        steps = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
        steps.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(
            steps,
            text=f"2.  Log in and open the Dashboard\n"
                 f"3.  Copy your API Key from the dashboard\n"
                 f"4.  If asked for a port, use {config.WEB_PORT}\n"
                 f"5.  Paste your API Key below and choose a subdomain",
            text_color="gray55", font=("Arial", 11), justify="left", anchor="w",
        ).pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(f, text="API Key", anchor="w").pack(fill="x")
        self._tunnel_key = ctk.CTkEntry(f, placeholder_text="it_…")
        self._tunnel_key.pack(fill="x", pady=(0, 10))
        self._tunnel_key.insert(0, config.INSTATUNNEL_API_KEY)

        ctk.CTkLabel(f, text="Subdomain  (becomes https://<subdomain>.instatunnel.my)", anchor="w").pack(fill="x")
        self._tunnel_sub = ctk.CTkEntry(f, placeholder_text="e.g. johns-iptv")
        self._tunnel_sub.pack(fill="x", pady=(0, 6))
        self._tunnel_sub.insert(0, config.INSTATUNNEL_SUBDOMAIN)

        ctk.CTkLabel(f, text="You can always add this later via ⚙ Settings.",
                     text_color="gray40", font=("Arial", 10), anchor="w").pack(fill="x")
        self._pages["tunnel"] = f

    def _show_page(self, idx):
        self._page = idx
        for frame in self._pages.values():
            frame.pack_forget()
        self._pages[self._PAGES[idx]].pack(fill="both", expand=True)
        self._header_lbl.configure(text=self._HEADERS[idx])
        self._step_lbl.configure(text=self._STEPS[idx])
        self._back_btn.configure(state="normal" if idx > 0 else "disabled")
        self._skip_btn.configure(state="normal" if idx > 0 else "disabled")
        last = idx == len(self._PAGES) - 1
        self._next_btn.configure(text="Finish" if last else ("Get Started →" if idx == 0 else "Next →"))

    def _prev(self):
        if self._page > 0:
            self._show_page(self._page - 1)

    def _next(self):
        if self._page == 1:
            if not all([self._url.get().strip(), self._user.get().strip(), self._pass.get().strip()]):
                self._iptv_err.configure(text="All three fields are required.")
                return
            self._iptv_err.configure(text="")
        if self._page < len(self._PAGES) - 1:
            self._show_page(self._page + 1)
        else:
            self._finish()

    def _skip(self):
        if self._page < len(self._PAGES) - 1:
            self._show_page(self._page + 1)
        else:
            self._finish()

    def _finish(self):
        self._save()
        self.destroy()
        self._on_complete()

    def _save(self):
        save_credentials(
            server_url=self._url.get().strip().rstrip("/"),
            username=self._user.get().strip(),
            password=self._pass.get().strip(),
            api_key=self._tunnel_key.get().strip(),
            subdomain=self._tunnel_sub.get().strip(),
        )


# ── Settings / credentials dialog ─────────────────────────────────────────────

class CredentialsDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Account Settings")
        self.geometry("440x880")
        self.resizable(False, True)
        self.grab_set()
        self.lift()
        self.focus_force()

        ctk.CTkLabel(self, text="XtreamCodes Account",
                     font=("Arial", 16, "bold")).pack(pady=(20, 12))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28)

        ctk.CTkLabel(form, text="Server URL", anchor="w").pack(fill="x")
        self._url = ctk.CTkEntry(form, placeholder_text="http://yourserver.com:8080")
        self._url.pack(fill="x", pady=(0, 10))
        self._url.insert(0, config.SERVER_URL)

        ctk.CTkLabel(form, text="Username", anchor="w").pack(fill="x")
        self._user = ctk.CTkEntry(form)
        self._user.pack(fill="x", pady=(0, 10))
        self._user.insert(0, config.USERNAME)

        ctk.CTkLabel(form, text="Password", anchor="w").pack(fill="x")
        self._pass = ctk.CTkEntry(form, show="•")
        self._pass.pack(fill="x", pady=(0, 10))
        self._pass.insert(0, config.PASSWORD)

        ctk.CTkButton(form, text="Save & Reload Channels",
                      command=self._save_xtream).pack(fill="x", pady=(5, 10))

        ctk.CTkFrame(self, height=1, fg_color="#484949").pack(fill="x", padx=28, pady=(8, 12))

        ctk.CTkLabel(self, text="InstaTunnel  (Remote Access)",
                     font=("Arial", 14, "bold"), anchor="w").pack(fill="x", padx=28, pady=(0, 6))

        tf = ctk.CTkFrame(self, fg_color="transparent")
        tf.pack(fill="x", padx=28)

        ctk.CTkButton(tf, text="instatunnel.my  — create a free account →",
                      fg_color="#484949", hover_color="#575959", height=28,
                      command=lambda: webbrowser.open("https://instatunnel.my")
                      ).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(tf,
                     text=f"Log in → Dashboard → copy your API Key  (app uses port {config.WEB_PORT})",
                     text_color="gray50", font=("Arial", 10), anchor="w"
                     ).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(tf, text="API Key", anchor="w").pack(fill="x")
        self._tunnel_key = ctk.CTkEntry(tf, placeholder_text="it_…")
        self._tunnel_key.pack(fill="x", pady=(0, 10))
        self._tunnel_key.insert(0, config.INSTATUNNEL_API_KEY)

        ctk.CTkLabel(tf, text="Subdomain  (becomes https://<subdomain>.instatunnel.my)", anchor="w").pack(fill="x")
        self._tunnel_sub = ctk.CTkEntry(tf, placeholder_text="e.g. johns-iptv")
        self._tunnel_sub.pack(fill="x", pady=(0, 6))
        self._tunnel_sub.insert(0, config.INSTATUNNEL_SUBDOMAIN)

        ctk.CTkLabel(tf, text="Tunnel changes take effect on next app launch.",
                     text_color="gray40", font=("Arial", 10), anchor="w").pack(fill="x", pady=(0, 12))

        ctk.CTkButton(tf, text="Save & Relaunch App",
                      fg_color="#c0392b", hover_color="#e74c3c",
                      command=self._save_tunnel).pack(fill="x", pady=(0, 10))

        ctk.CTkFrame(self, height=1, fg_color="#484949").pack(fill="x", padx=28, pady=(8, 12))

        ctk.CTkLabel(self, text="DVR Settings",
                     font=("Arial", 14, "bold"), anchor="w").pack(fill="x", padx=28, pady=(0, 6))

        df = ctk.CTkFrame(self, fg_color="transparent")
        df.pack(fill="x", padx=28)

        ctk.CTkLabel(df, text="Buffer Folder  (rolling live segments — separate from recordings)",
                     anchor="w", text_color="gray60", font=("Arial", 10)).pack(fill="x", pady=(0, 2))
        dir_row = ctk.CTkFrame(df, fg_color="transparent")
        dir_row.pack(fill="x", pady=(0, 10))
        self._dvr_dir = ctk.CTkEntry(dir_row, placeholder_text=config.DVR_BUFFER_DIR)
        self._dvr_dir.pack(side="left", fill="x", expand=True)
        self._dvr_dir.insert(0, config.DVR_BUFFER_DIR)
        ctk.CTkButton(dir_row, text="Browse…", width=90,
                      command=self._pick_dvr_dir).pack(side="right", padx=(6, 0))

        caps_row = ctk.CTkFrame(df, fg_color="transparent")
        caps_row.pack(fill="x", pady=(0, 6))

        left_cap = ctk.CTkFrame(caps_row, fg_color="transparent")
        left_cap.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(left_cap, text="Max buffer hours", anchor="w").pack(fill="x")
        self._dvr_hours = ctk.CTkEntry(left_cap, placeholder_text="6")
        self._dvr_hours.pack(fill="x")
        self._dvr_hours.insert(0, str(config.DVR_MAX_HOURS))

        right_cap = ctk.CTkFrame(caps_row, fg_color="transparent")
        right_cap.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(right_cap, text="Max storage (GB)", anchor="w").pack(fill="x")
        self._dvr_gb = ctk.CTkEntry(right_cap, placeholder_text="50")
        self._dvr_gb.pack(fill="x")
        self._dvr_gb.insert(0, str(config.DVR_MAX_GB))

        ctk.CTkLabel(df, text="Both caps are enforced — the first limit reached triggers cleanup.",
                     text_color="gray40", font=("Arial", 10), anchor="w").pack(fill="x", pady=(4, 6))

        self._dvr_msg = ctk.CTkLabel(df, text="", font=("Arial", 11), anchor="w")
        self._dvr_msg.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(df, text="Save DVR Settings",
                      fg_color="#484949", hover_color="#575959",
                      command=self._save_dvr).pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=28, pady=(0, 20))
        ctk.CTkButton(btns, text="Close",
                      fg_color="#575959", hover_color="#484949",
                      command=self.destroy).pack(fill="x", expand=True)

    def _save_xtream(self):
        save_credentials(
            server_url=self._url.get().strip().rstrip("/"),
            username=self._user.get().strip(),
            password=self._pass.get().strip(),
            api_key=self._tunnel_key.get().strip(),
            subdomain=self._tunnel_sub.get().strip(),
        )
        self.destroy()
        self._on_save()

    def _save_tunnel(self):
        save_credentials(
            server_url=self._url.get().strip().rstrip("/"),
            username=self._user.get().strip(),
            password=self._pass.get().strip(),
            api_key=self._tunnel_key.get().strip(),
            subdomain=self._tunnel_sub.get().strip(),
        )
        self.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _pick_dvr_dir(self):
        path = fd.askdirectory(initialdir=self._dvr_dir.get() or config.DVR_BUFFER_DIR)
        if path:
            self._dvr_dir.delete(0, "end")
            self._dvr_dir.insert(0, path)

    def _save_dvr(self):
        buf_dir = self._dvr_dir.get().strip()
        try:
            max_hours = int(self._dvr_hours.get().strip())
            max_gb    = int(self._dvr_gb.get().strip())
            if max_hours < 1 or max_gb < 1:
                raise ValueError
        except (ValueError, TypeError):
            self._dvr_msg.configure(text="Hours and GB must be whole numbers ≥ 1.", text_color="#e74c3c")
            return

        config.DVR_BUFFER_DIR = buf_dir if buf_dir else config.DVR_BUFFER_DIR
        config.DVR_MAX_HOURS  = max_hours
        config.DVR_MAX_GB     = max_gb

        # Merge with existing settings.json so output_dir is preserved.
        data = {}
        try:
            with open(config.SETTINGS_FILE) as f:
                data = json.load(f)
        except Exception:
            pass
        data["dvr_buffer_dir"] = config.DVR_BUFFER_DIR
        data["dvr_max_hours"]  = config.DVR_MAX_HOURS
        data["dvr_max_gb"]     = config.DVR_MAX_GB
        try:
            with open(config.SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self._dvr_msg.configure(text="DVR settings saved.", text_color="#2ecc71")
        except Exception as e:
            self._dvr_msg.configure(text=f"Could not save: {e}", text_color="#e74c3c")
