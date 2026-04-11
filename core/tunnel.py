"""
core/tunnel.py — InstaTunnel subprocess management.

TunnelManager owns the npx/instatunnel process.
The UI polls tunnel_mgr.url, tunnel_mgr.log, and tunnel_mgr.lines
from the main thread (safe because assignment is atomic in CPython).
"""

import os
import re
import subprocess
import sys
import threading
import time

import config


class TunnelManager:
    def __init__(self):
        self._process = None
        self.url   = None   # set by bg thread when tunnel URL is confirmed
        self.log   = None   # error/notice string from bg thread (one-shot)
        self.lines = []     # raw output lines queued by bg thread; drain in UI tick

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self):
        """Spawn tunnel in background thread. No-op if subdomain not configured."""
        if not config.INSTATUNNEL_SUBDOMAIN:
            return
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    # ── Private ───────────────────────────────────────────────────────────────

    def _run(self):
        _ansi = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\r')

        # GUI apps on macOS don't inherit shell PATH — prepend common locations.
        env = os.environ.copy()
        extra = [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            os.path.expanduser("~/.local/bin"),
            os.path.expanduser("~/bin"),
        ]
        env["PATH"] = ":".join(extra) + ":" + env.get("PATH", "")

        npx = "npx.cmd" if sys.platform == "win32" else "npx"

        # Kill any stale session holding our subdomain before claiming it.
        kill_cmd = [npx, "--yes", "instatunnel", "--kill", config.INSTATUNNEL_SUBDOMAIN]
        if config.INSTATUNNEL_API_KEY:
            kill_cmd += ["--api-key", config.INSTATUNNEL_API_KEY]
        try:
            subprocess.run(
                kill_cmd, env=env, timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **config._SUBPROCESS_FLAGS,
            )
        except Exception:
            pass
        time.sleep(1)

        cmd = [npx, "--yes", "instatunnel", str(config.WEB_PORT), "-s", config.INSTATUNNEL_SUBDOMAIN]
        if config.INSTATUNNEL_API_KEY:
            cmd += ["--api-key", config.INSTATUNNEL_API_KEY]

        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env, **config._SUBPROCESS_FLAGS,
            )
            stdout = self._process.stdout
            if stdout is None:
                return
            for raw in stdout:
                line = _ansi.sub("", raw).strip()
                if not line:
                    continue
                self.lines.append(line)
                if self.url is None:
                    m = re.search(r'https?://\S+', line)
                    if m:
                        candidate = m.group(0).rstrip('.,;)"\'>]')
                        if "api.instatunnel" not in candidate:
                            self.url = candidate
        except FileNotFoundError:
            self.log = "InstaTunnel: npx not found — check Node.js is installed."
        except Exception as e:
            self.log = f"InstaTunnel error: {e}"
