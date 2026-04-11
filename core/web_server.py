"""
core/web_server.py — HTTP server and all /api/* endpoint routing.

RemoteHandler never imports from ui/ — it talks to the app only
through a WebContext object set before the server starts.
"""

import json
import os
import socket
import threading

import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import config


class WebContext:
    """
    Thin bridge between the HTTP handler and the application.
    IPTVRecorderApp constructs one of these and passes it to start_web_server().
    """
    def __init__(
        self,
        get_status_fn,     # () -> dict  (recordings, status text, backup name)
        get_channels_fn,   # (q: str) -> list[{name, id}]  max 25
        get_favorites_fn,  # () -> list[{name, id}]
        get_log_fn,        # () -> list[str]
        action_queue,      # queue.Queue — web actions dispatched to UI thread
    ):
        self.get_status    = get_status_fn
        self.get_channels  = get_channels_fn
        self.get_favorites = get_favorites_fn
        self.get_log       = get_log_fn
        self.action_queue  = action_queue


class RemoteHandler(BaseHTTPRequestHandler):
    ctx: WebContext = None  # set by start_web_server() before server starts

    # ── Read static HTML once ────────────────────────────────────────────────
    _html_page: str = None

    @classmethod
    def _get_html(cls) -> str:
        if cls._html_page is None:
            html_path = os.path.join(config._BUNDLE_DIR, "static", "remote.html")
            try:
                with open(html_path, encoding="utf-8") as f:
                    cls._html_page = f.read()
            except Exception:
                cls._html_page = "<h1>Web UI not found</h1>"
        return cls._html_page

    # ── Request handlers ─────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path

        if path == "/":
            self._html(self._get_html())

        elif path == "/api/status":
            self._json(self.ctx.get_status())

        elif path == "/api/favorites":
            self._json(self.ctx.get_favorites())

        elif path == "/api/channels":
            q = qs.get("q", [""])[0].lower().strip()
            self._json(self.ctx.get_channels(q))

        elif path == "/api/epg":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._json({"listings": []})
            else:
                try:
                    url = (
                        f"{config.SERVER_URL}/player_api.php"
                        f"?username={config.USERNAME}&password={config.PASSWORD}"
                        f"&action=get_short_epg&stream_id={channel_id}&limit=12"
                    )
                    r = requests.get(url, timeout=8)
                    self._json({"listings": r.json().get("epg_listings", [])})
                except Exception:
                    self._json({"listings": []})

        elif path == "/api/log":
            self._json({"entries": self.ctx.get_log()})

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}
        path   = urlparse(self.path).path

        if path == "/api/schedule":
            self.ctx.action_queue.put({"type": "schedule", **body})
            ch   = body.get("channel_name", "")
            st   = body.get("start_time", "")
            msg  = f"Started: {ch}" if st == "NOW" else f"Scheduled: {ch} at {st}"
            self._json({"message": msg})

        elif path == "/api/stop":
            self.ctx.action_queue.put({"type": "stop", "index": body.get("index", 0)})
            self._json({"message": "Stop requested."})

        elif path == "/api/favorites/add":
            self.ctx.action_queue.put({"type": "fav_add", "name": body.get("name"), "id": body.get("id")})
            self._json({"ok": True})

        elif path == "/api/favorites/remove":
            self.ctx.action_queue.put({"type": "fav_remove", "name": body.get("name")})
            self._json({"ok": True})

        elif path == "/api/backup/set":
            self.ctx.action_queue.put({"type": "backup_set", "id": body.get("id"), "name": body.get("name")})
            self._json({"message": f"Backup channel set to: {body.get('name')}"})

        elif path == "/api/backup/clear":
            self.ctx.action_queue.put({"type": "backup_clear"})
            self._json({"message": "Backup channel cleared"})

        else:
            self.send_response(404)
            self.end_headers()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _html(self, content: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass  # suppress per-request console spam


def start_web_server(ctx: WebContext) -> str:
    """
    Start the HTTP server on config.WEB_PORT.
    Returns the local LAN URL (http://192.168.x.x:PORT).
    Raises OSError if the port is already in use.
    """
    RemoteHandler.ctx = ctx
    server = ThreadingHTTPServer(("0.0.0.0", config.WEB_PORT), RemoteHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect_ex(("192.168.1.1", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "localhost"

    return f"http://{ip}:{config.WEB_PORT}"
