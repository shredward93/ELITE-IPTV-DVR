# IPTV Recorder — Roadmap & Architecture Plan

## Strategic Goals

1. **Backend Modularization** — Split `iptv_recorder.py` (~2100 lines) into clean, independently editable modules
2. **Frontend Modernization** — Expand the existing web remote into the primary UI; CTk becomes a background service
3. **Android TV Companion App** — Native Android TV player that uses the PC app as its backend brain (scheduling, FFmpeg, credentials)

---

## Recommended Module Structure

```
iptv-recorder/
├── main.py                    # Thin entrypoint only
├── config.py                  # AppConfig dataclass + credential I/O
├── core/
│   ├── __init__.py
│   ├── recorder.py            # RecordingJob, FFmpeg logic, segment/merge
│   ├── channels.py            # fetch_channels(), fetch_epg(), decode_epg()
│   ├── favorites.py           # load_favorites(), save_favorites()
│   ├── tunnel.py              # TunnelManager (InstaTunnel subprocess)
│   └── web_server.py          # HTTP server, all /api/* routing
├── ui/
│   ├── __init__.py
│   ├── app.py                 # IPTVRecorderApp(ctk.CTk)
│   └── dialogs.py             # SetupWizard, CredentialsDialog, SettingsDialog
└── static/
    └── remote.html            # Mobile web UI (extracted from embedded string)
```

**Hard boundary rules:**
- `core/` → zero tkinter/ctk imports, ever
- `ui/` → never calls FFmpeg directly; reads job state, never writes it
- `config.py` → no UI, no FFmpeg, no HTTP; just a dataclass + file I/O

---

## Frontend Path — Option A (Chosen)

**Expand the web remote into the primary UI. CTk becomes a tray icon / background service.**

The web remote already has 80% of the needed UI. The same REST API serves mobile browsers, desktop browsers, and the Android TV app natively. No new mandatory dependencies.

Transition steps (future, non-blocking):
1. Extract `static/remote.html` (Phase 2 of migration below — do immediately)
2. Keep CTk UI as-is; add `pystray` tray icon in a future pass
3. Expand `static/remote.html` into a full-featured SPA as a separate workstream
4. Once web UI is feature-complete, CTk window becomes optional/hidden by default

---

## Android TV — Stream Playback Decision

**PC proxies the stream. No direct URL exposure.**

XtreamCodes stream URLs contain credentials in plaintext (`/live/USERNAME/PASSWORD/id.ts`). If the Android TV receives the URL directly, credentials appear in ExoPlayer logs and Android system network logs.

With PC proxying via `GET /api/stream/live?channel_id=X`:
- Credentials never leave the PC
- TV only knows the local LAN IP:port
- Access is scoped to local network (or InstaTunnel session)
- Hop overhead on LAN is negligible — ExoPlayer fills its buffer in under 1 second

---

## API Contract

All responses JSON. All POST bodies JSON.

### Existing Endpoints (retain)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Mobile web UI |
| `GET` | `/api/status` | Recordings, status text, backup, log tail |
| `GET` | `/api/favorites` | `[{name, id}]` |
| `GET` | `/api/channels?q=` | Search, returns `[{name, id}]` max 25 |
| `GET` | `/api/epg?channel_id=` | `{listings: [...]}` |
| `GET` | `/api/log` | `{entries: [...]}` |
| `POST` | `/api/schedule` | `{channel_name, channel_id, start_time, duration_mins}` |
| `POST` | `/api/stop` | `{index: N}` |
| `POST` | `/api/favorites/add` | `{name, id}` |
| `POST` | `/api/favorites/remove` | `{name}` |
| `POST` | `/api/backup/set` | `{id, name}` |
| `POST` | `/api/backup/clear` | `{}` |

### New Endpoints (Android TV)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/info` | Version, capabilities, channel count |
| `GET` | `/api/channels/all` | Full channel list for TV guide |
| `GET` | `/api/recordings` | Active + recent jobs (cleaner than status blob) |
| `GET` | `/api/stream/url?channel_id=` | Returns proxy URL for ExoPlayer |
| `GET` | `/api/stream/live?channel_id=` | PC fetches `.ts` and pipes to client |
| `POST` | `/api/record` | Start recording immediately (alias for schedule NOW) |

#### `/api/info` shape
```json
{
  "version": "1.1.0",
  "server_reachable": true,
  "channel_count": 12483,
  "capabilities": ["recording", "epg", "favorites", "stream_proxy"]
}
```

#### `/api/stream/url` shape
```json
{
  "proxy_url": "http://192.168.1.10:8080/api/stream/live?channel_id=1234",
  "channel_name": "NHL Network HD"
}
```

#### `/api/recordings` shape
```json
{
  "active": [
    {
      "index": 0,
      "channel_name": "MSG Western NY",
      "status": "recording",
      "elapsed_secs": 1823,
      "remaining_secs": 9177,
      "output_file": "MSG_2026-04-10_16-30.ts"
    }
  ],
  "recent": [
    {"channel_name": "NHL Network", "status": "complete", "status_text": "Recording finished."}
  ]
}
```

---

## Migration Plan

Each phase leaves the app fully runnable. Commit after each phase. Never break the exe build.

| Phase | Target | Risk | Smoke Test |
|-------|--------|------|------------|
| 1 | `config.py` — replace 6 module globals with `AppConfig` dataclass | Low | App starts, credentials load |
| 2 | `static/remote.html` — extract embedded HTML string | Low | Web remote loads in browser |
| 3 | `core/favorites.py` — `load_favorites()`, `save_favorites()` | Trivial | Favorites persist across restart |
| 4 | `core/channels.py` — `fetch_channels()`, `fetch_epg()`, `decode_epg()` | Low | Channel search works |
| 5 | `core/recorder.py` — `RecordingJob`, `_run_recording_job`, FFmpeg/merge | Medium | Record 1 min, `.ts` file exists and plays |
| 6 | `core/tunnel.py` — `TunnelManager` class, subprocess lifecycle | Low–Med | InstaTunnel connects |
| 7 | `core/web_server.py` — `RemoteHandler`, `WebContext`, new TV endpoints | Medium | All `/api/*` endpoints respond |
| 8 | `ui/dialogs.py` — `SetupWizard`, `CredentialsDialog`, `SettingsDialog` | Low | Settings dialog opens and saves |
| 9 | `ui/app.py` + `main.py` — move `IPTVRecorderApp`, create entrypoint | Medium | Full app runs from `main.py` |
| 10 | Delete `iptv_recorder.py` | — | PyInstaller `.exe` runs end-to-end |

### `config.py` — Key design note

```python
@dataclass
class AppConfig:
    server_url:       str = ""
    username:         str = ""
    password:         str = ""
    tunnel_api_key:   str = ""
    tunnel_subdomain: str = ""
    output_dir:       str = ""
    app_dir:          str = ""
    bundle_dir:       str = ""

    def stream_url(self, channel_id: str) -> str:
        return f"{self.server_url.rstrip('/')}/live/{self.username}/{self.password}/{channel_id}.ts"

    def api_base(self) -> str:
        return f"{self.server_url.rstrip('/')}/player_api.php?username={self.username}&password={self.password}"

    @classmethod
    def load(cls, app_dir: str) -> "AppConfig": ...
    def save(self) -> None: ...
```

One `AppConfig` instance created in `main.py`, passed to every subsystem. No more module-level globals.

### `core/web_server.py` — Decoupling note

Replace `RemoteHandler.app = IPTVRecorderApp` class variable with a `WebContext` object:

```python
@dataclass
class WebContext:
    config:           AppConfig
    get_jobs:         Callable[[], list[RecordingJob]]
    get_channels:     Callable[[str], list[dict]]
    get_all_channels: Callable[[], list[dict]]
    get_favorites:    Callable[[], list[dict]]
    get_log:          Callable[[], list[str]]
    get_status:       Callable[[], str]
    get_backup:       Callable[[], dict | None]
    action_queue:     queue.Queue
```

`IPTVRecorderApp` constructs `WebContext` wiring its own methods as callables. Web server never imports from `ui/`.

---

## Android TV App (Future Repo)

Once the modular backend is in place and the `/api/*` contract above is stable:

- **Language:** Kotlin
- **Player:** ExoPlayer (points at `/api/stream/live?channel_id=X`)
- **UI:** Leanback library for TV-optimized channel guide and EPG grid
- **Scheduling:** Uses `POST /api/schedule` and `GET /api/recordings`
- **Discovery:** User enters PC's local IP (or InstaTunnel URL) in TV app settings
- **Auth:** Initially none (LAN-only trust); InstaTunnel provides the security boundary
