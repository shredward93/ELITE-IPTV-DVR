# IPTV Recorder — Roadmap & Architecture Plan

## Strategic Goals

1. **Backend Modularization** — Split `iptv_recorder.py` (~2100 lines) into clean, independently editable modules ✅ Complete
2. **Frontend Modernization** — Expand the existing web remote into the primary UI; CTk becomes a background service ✅ Complete
3. **Kodi PVR Integration** — Native Kodi PVR addon + custom ELITE skin for TiviMate-like experience with PC-based recording
   - PVR addon with full grid guide
   - Pause/rewind live TV via DVR buffer
   - One-click recording to PC hard drive
   - Custom ELITE skin for consistent branding
4. **NAS Deployment** — Headless Docker deployment for always-on server (Synology DS1621xs+)
   - Stream multiplexing for multi-user efficiency
   - Headless launcher (no GUI)
   - Docker container support
   - Environment variable configuration

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

## NAS Deployment (Synology DS1621xs+)

**Target:** Synology DS1621xs+ NAS (quad-core Intel Xeon D-1527, 32GB DDR4 ECC, 10GbE, Docker/Container Manager support)

**Goal:** Run the server headlessly on NAS for always-on operation, accessible remotely by all users (Edward, Kurt/Emmett, Dad). All recordings land on NAS storage and are accessible to all users simultaneously.

### Components to Build

| Component | Priority | Status |
|-----------|----------|--------|
| `StreamMuxer` — Multi-user stream sharing | High | Not built |
| `server_headless.py` — GUI-less entrypoint | High | Not built |
| `Dockerfile` — Linux container recipe | High | Not built |
| Environment variable credentials | Medium | Not built |
| HTTP recordings browser for Kodi | Medium | Not built |
| First-run web setup page | Medium | Not built |

### Headless Launcher (`server_headless.py`)

Replacement entrypoint for `main.py` that skips the `customtkinter` GUI and starts web server, DVR manager, channel fetching, and tunnel directly. Core modules (`web_server.py`, `dvr_manager.py`, `recorder.py`, `channels.py`, `epg.py`, `tunnel.py`) are already GUI-agnostic.

### Credentials via Environment Variables

Headless launcher reads credentials from environment variables as primary source, falling back to `credentials.json` if present:

- `SERVER_URL`
- `USERNAME`
- `PASSWORD`
- `INSTATUNNEL_API_KEY`
- `INSTATUNNEL_SUBDOMAIN`
- `RECORDINGS_DIR`

### Remote Access

**Cloudflare** is already fully implemented in `core/tunnel.py` and is the preferred remote access method for NAS deployment. Requires no client-side login.

---

## Feature: Stream Multiplexing (Priority — Build Now)

**Problem:** Current `_proxy_live_stream` opens a fresh provider connection for every Kodi client request. Three users watching the same hockey game = 3 provider connections consumed unnecessarily.

**Solution: `StreamMuxer` class in `web_server.py`**
- Maintains dictionary keyed by `channel_id` of active provider streams
- First client request opens provider connection
- Subsequent clients tap into existing feed (no new provider connection)
- Clients removed from feed on disconnect
- Last client disconnect closes provider connection automatically
- Completely transparent to Kodi — same `/api/stream/live?channel_id=XXX` endpoint

**Multi-User Setup:**
- Three primary users in different locations
- Each user has their own Kodi device
- All point at the same NAS server URL
- Independent live TV, scheduling, DVR pause/rewind
- Shared recordings library on NAS

---

## Frontend Path — Option A (Chosen)

**Expand the web remote into the primary UI. CTk becomes a tray icon / background service.**

The web remote already has most of the needed UI. The same REST API serves mobile browsers, desktop browsers, and Kodi-aware workflows without adding new mandatory dependencies.

Transition steps (future, non-blocking):
1. Keep `static/remote.html` as the lightweight scheduling/control surface.
2. Keep CTk UI as-is; add `pystray` tray icon in a future pass.
3. Expand `static/remote.html` into a full-featured SPA as a separate workstream.
4. Once the web UI is feature-complete, CTk window becomes optional/hidden by default.

---

## Kodi PVR — Stream & Recording Architecture

**PC proxies the stream. No direct URL exposure.**

XtreamCodes stream URLs contain credentials in plaintext (`/live/USERNAME/PASSWORD/id.ts`). Kodi never sees the raw URL — only your server's proxy endpoints.

With PC proxying via `GET /api/stream/live?channel_id=X`:
- Credentials never leave the PC
- Kodi only knows the local LAN IP:port
- Access is scoped to local network (or InstaTunnel session)
- Hop overhead on LAN is negligible — Kodi fills its buffer in under 1 second

### Recording Flow

```
Kodi PVR Guide → User clicks "Record"
               ↓
         PVR Addon calls POST /api/schedule
               ↓
         Server starts FFmpeg recording
               ↓
         Recording saved to PC: recordings/ folder
```

Kodi's native "Record" button is wired to your server's API — recordings land on the PC, not the Android TV.

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

### New Endpoints (Kodi Integration)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/info` | Version, capabilities, channel count |
| `GET` | `/api/channels/all` | Full channel list for TV guide |
| `GET` | `/api/recordings` | Active + recent jobs (cleaner than status blob) |
| `GET` | `/api/stream/url?channel_id=` | Returns proxy URL for Kodi player |
| `GET` | `/api/stream/live?channel_id=` | PC fetches `.ts` and pipes to Kodi |
| `POST` | `/api/record` | Start recording immediately (alias for schedule NOW) |
| `GET` | `/kodi/playlist.m3u` | M3U playlist with proxy URLs for PVR |
| `GET` | `/kodi/guide.xml` | XMLTV EPG data for PVR guide |
| `GET` | `/dvr/playlist.m3u8` | HLS playlist for pause/rewind live TV |
| `POST` | `/dvr/start` | Start DVR buffer for a channel |
| `POST` | `/dvr/stop` | Stop DVR buffer |
| `GET` | `/dvr/status` | DVR buffer status |

### PVR Addon (Kodi) Architecture

The PVR addon (`pvr.eliteiptv`) provides:
- **Channel list** — Populates Kodi's TV section with all channels
- **EPG guide** — Grid timeline with show titles, times, descriptions
- **Live playback** — Proxy stream or DVR HLS (user choice)
- **Recording** — Kodi's record button calls your server's API

**Files:**
- `kodi-addon/pvr.eliteiptv/` — Native PVR addon source scaffold
- `kodi-addon/pvr.eliteiptv/` — PVR addon source tree (native Kodi PVR client)
- `kodi-skin/skin.elite.dvr/` — Custom skin with gold/orange ELITE branding

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

## Kodi PVR Integration (Active Development)

### Phase 1: Core PVR Addon ✅ Complete
- [x] `/kodi/playlist.m3u` endpoint — M3U with proxy URLs
- [x] `/kodi/guide.xml` endpoint — XMLTV EPG data
- [x] Basic video addon (`plugin.video.eliteiptv`) — Channel browser + DVR play

### Phase 2: Full PVR Backend Addon ⏳ Current
- [x] PVR addon project scaffold (`pvr.eliteiptv`) — Native Kodi PVR client source layout
- [ ] Implement `GetChannels()`, `GetEPGForChannel()`, `Record()` callbacks
- [ ] Wire Kodi's "Record" button to `POST /api/schedule`
- [ ] Support pause/rewind via DVR HLS option

### Phase 3: Custom Skin Polish ⏳ Pending
- [ ] Finish `skin.elite.dvr` textures (panel_rounded.png, etc.)
- [ ] Test PVR guide rendering with custom skin
- [ ] Ensure focused states are visible from couch distance

### Phase 4: TiviMate Parity ⏳ Future
- [ ] Auto-start DVR buffer on channel tune (configurable)
- [ ] Record series/season passes via Kodi timer interface
- [ ] Thumbnail/poster art in guide grid
- [ ] Channel groups/favorites synced with server

### Setup Instructions (Future)

1. Install Kodi on Android TV (ONN 4K Pro or any Android TV)
2. Install ELITE IPTV DVR PVR addon
3. Configure addon with PC server IP:port
4. Activate ELITE skin (optional but recommended)
5. Go to TV → Guide — full TiviMate-like experience
