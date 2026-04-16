"""
core/tunnel.py — Tunnel management for InstaTunnel and Cloudflare.

TunnelManager owns the cloudflared or instatunnel process.
The UI polls tunnel_mgr.url, tunnel_mgr.log, and tunnel_mgr.lines
from the main thread (safe because assignment is atomic in CPython).
"""

import os
import re
import shutil
import subprocess
import sys
import threading
import time

import config


class TunnelManager:
    def __init__(self):
        self._process = None
        self._starting = False
        self.provider = None  # "cloudflare" | "instatunnel" | None
        self.url   = None       # set by bg thread when tunnel URL is confirmed
        self.log   = None       # error/notice string from bg thread (one-shot)
        self.lines = []         # raw output lines queued by bg thread; drain in UI tick

    # ── Public API ────────────────────────────────────────────────────────────

    def is_configured(self):
        """Return True if any tunnel provider is configured."""
        if config.TUNNEL_PROVIDER == "cloudflare" and config.CLOUDFLARE_DOMAIN:
            return True
        if config.TUNNEL_PROVIDER == "instatunnel" and config.INSTATUNNEL_SUBDOMAIN:
            return True
        return False

    def start(self):
        """Spawn tunnel in background thread. No-op if not configured."""
        if not self.is_configured():
            return
        if self._process and self._process.poll() is None:
            return
        if self._starting:
            return
        self._starting = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._terminate_process()
        if config.TUNNEL_PROVIDER == "instatunnel" and config.INSTATUNNEL_SUBDOMAIN:
            env, npx = self._build_env()
            self._cleanup_instatunnel_session(env, npx)

    # ── Cloudflare Tunnel ─────────────────────────────────────────────────────

    def _spawn_cloudflare(self):
        """Spawn cloudflared quick tunnel. Returns True on success."""
        _ansi = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\r')
        
        # Try to find cloudflared binary
        cloudflared = self._find_cloudflared()
        if not cloudflared:
            self.log = "cloudflared not found. Download from https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
            return False

        self.provider = "cloudflare"
        
        # Build command: cloudflared tunnel --url http://localhost:PORT
        # Or if domain is configured and token available, use named tunnel
        if config.CLOUDFLARE_TUNNEL_TOKEN and config.CLOUDFLARE_DOMAIN:
            # Named tunnel with token
            cmd = [
                cloudflared,
                "tunnel",
                "run",
                "--token", config.CLOUDFLARE_TUNNEL_TOKEN,
            ]
            expected_url = f"https://{config.CLOUDFLARE_DOMAIN}"
        else:
            # Quick tunnel (random subdomain each time, but no expiry)
            cmd = [
                cloudflared,
                "tunnel",
                "--url", f"http://127.0.0.1:{config.WEB_PORT}",
            ]
            expected_url = None  # Will be parsed from output

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **config._SUBPROCESS_FLAGS,
            )
            stdout = self._process.stdout
            if stdout is None:
                return False

            for raw in stdout:
                line = _ansi.sub("", raw).strip()
                if not line:
                    continue
                self.lines.append(f"[CF] {line}")
                
                # Parse URL from quick tunnel output
                # Format: "Your quick tunnel is ready at: https://something.trycloudflare.com"
                if expected_url:
                    self.url = expected_url
                else:
                    m = re.search(r'https://[a-zA-Z0-9_-]+\.trycloudflare\.com', line)
                    if m:
                        self.url = m.group(0)
                        
        except FileNotFoundError:
            self.log = "cloudflared not found in PATH"
            return False
        except Exception as e:
            self.log = f"Cloudflare tunnel error: {e}"
            return False

        return True

    def _find_cloudflared(self):
        """Find cloudflared binary in PATH or common locations."""
        binary = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
        
        # Check PATH
        if shutil.which(binary):
            return shutil.which(binary)
        
        # Check common locations
        common_paths = [
            os.path.expanduser("~/bin/cloudflared"),
            os.path.expanduser("~/.local/bin/cloudflared"),
            "/usr/local/bin/cloudflared",
            "/opt/homebrew/bin/cloudflared",
            "C:\\Program Files\\Cloudflare\\cloudflared.exe",
        ]
        for path in common_paths:
            if os.path.isfile(path):
                return path
        return None

    # ── InstaTunnel ───────────────────────────────────────────────────────────

    def _build_env(self):
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
        return env, npx

    def _resolve_instatunnel_cli(self, npx):
        cli = "instatunnel.cmd" if sys.platform == "win32" else "instatunnel"
        if shutil.which(cli):
            return [cli]
        return [npx, "--yes", "instatunnel@latest"]

    def _cleanup_instatunnel_session(self, env, npx, pause=True):
        """Best-effort removal of any prior reservation for our subdomain."""
        kill_cmd = self._resolve_instatunnel_cli(npx) + ["--kill", config.INSTATUNNEL_SUBDOMAIN]
        if config.INSTATUNNEL_API_KEY:
            kill_cmd += ["--api-key", config.INSTATUNNEL_API_KEY]
        try:
            subprocess.run(
                kill_cmd, env=env, timeout=15,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **config._SUBPROCESS_FLAGS,
            )
        except Exception:
            pass
        if pause:
            time.sleep(2)

    def _spawn_instatunnel(self, env, npx, allow_retry=True):
        _ansi = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\r')
        cmd = self._resolve_instatunnel_cli(npx) + ["connect", str(config.WEB_PORT), "--subdomain", config.INSTATUNNEL_SUBDOMAIN]
        if config.INSTATUNNEL_API_KEY:
            cmd += ["--api-key", config.INSTATUNNEL_API_KEY]

        duplicate_seen = False
        self.provider = "instatunnel"

        try:
            self._process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env, **config._SUBPROCESS_FLAGS,
            )
            stdout = self._process.stdout
            if stdout is None:
                return False

            for raw in stdout:
                line = _ansi.sub("", raw).strip()
                if not line:
                    continue
                self.lines.append(f"[IT] {line}")
                lowered = line.lower()
                if "duplicate key value violates unique constraint" in lowered or "already reserved" in lowered:
                    duplicate_seen = True
                    break
                if self.url is None:
                    m = re.search(r'https?://\S+', line)
                    if m:
                        candidate = m.group(0).rstrip('.,;)"\'\u003e]')
                        if "api.instatunnel" not in candidate:
                            self.url = candidate
        except FileNotFoundError:
            self.log = "InstaTunnel CLI not found — install it with npm install -g instatunnel@latest."
            return False
        except Exception as e:
            self.log = f"InstaTunnel error: {e}"
            return False

        if duplicate_seen:
            self._terminate_process()
            if allow_retry:
                self.lines.append(f"InstaTunnel: subdomain '{config.INSTATUNNEL_SUBDOMAIN}' was reserved; retrying after cleanup.")
                self._cleanup_instatunnel_session(env, npx)
                return self._spawn_instatunnel(env, npx, allow_retry=False)
            self.log = f"InstaTunnel: subdomain '{config.INSTATUNNEL_SUBDOMAIN}' is already reserved."
            return False

        return True

    # ── Common ─────────────────────────────────────────────────────────────────

    def _terminate_process(self):
        proc = self._process
        if not proc:
            return
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        self._process = None

    def _run(self):
        try:
            if config.TUNNEL_PROVIDER == "cloudflare":
                self._spawn_cloudflare()
            elif config.TUNNEL_PROVIDER == "instatunnel":
                env, npx = self._build_env()
                self._cleanup_instatunnel_session(env, npx)
                self._spawn_instatunnel(env, npx, allow_retry=True)
        finally:
            self._starting = False
