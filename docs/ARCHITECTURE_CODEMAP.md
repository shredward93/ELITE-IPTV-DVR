# ELITE IPTV DVR Architecture Codemap

This document maps the current backend, Android TV app, and Kodi PVR integration points so TV UX work stays focused and safe.

## System view

- **PC Server (`main.py`, `core/`)**
  - Desktop control surface for scheduling, recording, favorites, and configuration.
  - HTTP API server (`core/web_server.py`) serves the web remote, Android TV client, and Kodi PVR addon.
  - DVR buffer manager (`core/dvr_manager.py`) enables pause/rewind live TV.
  - FFmpeg recording pipeline saves completed recordings to `recordings/` folder.

- **Shared backend modules (`core/`)**
  - `core/web_server.py` — HTTP API for JSON `/api/*` clients (Android, web), Kodi endpoints, and DVR control.
  - `core/dvr_manager.py` — Rolling HLS buffer for live TV pause/rewind.
  - `core/recorder.py` — Scheduled recording jobs with FFmpeg.
  - `core/channels.py` — Provider channel list fetching.
  - `core/epg.py` — XMLTV EPG fetch and cache.
  - `core/credentials.py`, `core/favorites.py`, `core/tunnel.py` — App state.

- **Android TV client (`android/`)**
  - Kotlin, Jetpack Compose, Navigation Compose, Media3 ExoPlayer.
  - Uses the same **REST + HLS URLs** as `static/remote.html` (no per-channel format forks).
  - DVR library uses `GET /api/recordings`; playback uses **HTTP range** on completed/in-progress `.ts` where exposed by the API.

- **Kodi client (any Kodi device)**
  - **PVR addon** (`kodi-addon/pvr.eliteiptv/`) — Native Kodi PVR client.
  - **Video addon** (`kodi-addon/plugin.video.eliteiptv/`) — Channel browser fallback.
  - **Custom skin** (`kodi-skin/skin.elite.dvr/`) — ELITE branding, gold/orange theme.
  - Talks to PC server only through HTTP endpoints on port 8080.

## Backend request flow

1. `main.py` starts the desktop app + HTTP server.
2. The desktop app loads IPTV credentials and channel data.
3. `core/web_server.py` serves JSON APIs and Kodi PVR endpoints, including:
   - `/api/channels`, `/api/epg/*`, `/api/categories`, `/api/schedule`, `/api/recordings`, preview/stream URLs — used by **Android TV** and **web remote**
   - `/kodi/playlist.m3u` — M3U playlist with proxy URLs
   - `/kodi/guide.xml` — XMLTV EPG for PVR guide
   - `/api/stream/live?channel_id=X` — Proxy stream for live TV
   - `/dvr/playlist.m3u8` — HLS playlist for pause/rewind
   - `/dvr/start`, `/dvr/stop` — DVR buffer control
   - `/api/schedule` — Start scheduled/recording
   - `/api/recordings` — Active + completed recordings
4. Android TV and Kodi PVR addon consume these endpoints via HTTP.
5. Recordings are saved to PC's `recordings/` folder, not the TV.

## Live playback architecture

- **Direct proxy path (fast)**
  - Kodi requests: `GET /api/stream/live?channel_id=123`
  - PC fetches provider stream and pipes TS bytes to Kodi.
  - Fast channel switching, minimal delay.
  - Used when DVR pause/rewind is not needed.

- **DVR buffer path (pause/rewind)**
  - User selects "Watch with DVR" or enables auto-DVR mode.
  - Addon calls `POST /dvr/start` to begin FFmpeg HLS buffer.
  - Kodi plays: `GET /dvr/playlist.m3u8` (rolling HLS manifest).
  - Kodi's native player handles pause, rewind, fast-forward through the buffer.
  - Buffer maintains ~5 minutes of segments on PC disk.

## TV guide / EPG flow

- `core/epg.py` fetches and caches XMLTV from provider.
- `core/web_server.py` serves:
  - `/kodi/guide.xml` — Full XMLTV for Kodi PVR.
  - `/api/epg/*` — JSON EPG for web remote.
- Desktop UI (`ui/app.py`) uses shared EPG helpers.

### Kodi PVR guide flow

1. **PVR addon startup**
   - Addon fetches `/kodi/playlist.m3u` for channel list.
   - Addon fetches `/kodi/guide.xml` for EPG data.
   - Populates Kodi's native TV database.

2. **User opens TV → Guide**
   - Kodi renders grid timeline using its native PVR UI.
   - Custom skin (`skin.elite.dvr`) applies gold/orange ELITE theming.
   - Channel logos, show titles, times, descriptions visible.

3. **User selects a show**
   - Context menu: "Watch", "Record", "Record series".
   - Clicking "Record" → addon calls `POST /api/schedule`.
   - Server starts FFmpeg recording to PC disk.

### PVR addon data flow

| Kodi Action | Addon Call | Server Endpoint |
|-------------|------------|-----------------|
| Load channels | `GetChannels()` | `GET /kodi/playlist.m3u` |
| Load EPG | `GetEPGForChannel()` | `GET /kodi/guide.xml` |
| Play live | `OpenLiveStream()` | `GET /api/stream/live` or `/dvr/playlist.m3u8` |
| Record now | `Record()` | `POST /api/schedule` |
| Timer schedule | `AddTimer()` | `POST /api/schedule` with future time |

## File structure

```
ELITE-IPTV-DVR/
├── core/                      # Backend server modules
│   ├── web_server.py          # HTTP API (JSON + Kodi endpoints)
│   ├── dvr_manager.py         # Rolling HLS buffer
│   ├── recorder.py            # Scheduled recording jobs
│   ├── epg.py                 # XMLTV fetch/cache
│   ├── channels.py            # Provider channel list
│   └── ...
├── android/                   # Android TV app (Kotlin, Compose, Media3)
│   └── app/...
├── static/                    # Mobile web remote (reference for client parity)
├── kodi-addon/                # Kodi client addons
│   ├── pvr.eliteiptv/         # (Future) Native PVR addon
│   └── plugin.video.eliteiptv/ # Video addon (current)
├── kodi-skin/                 # Custom ELITE skin
│   └── skin.elite.dvr/
│       ├── xml/Home.xml       # Main menu
│       ├── xml/Startup.xml    # Boot animation
│       ├── colors/defaults.xml
│       └── media/             # Textures (TODO)
└── ui/                        # Desktop control UI
```

## Small backend cleanup completed

- **EPG helper reuse**
  - Centralized EPG fetch + decode behavior in `core/epg.py`.
  - Removed duplicated EPG request/decode logic from `core/web_server.py`.
- **Kodi endpoints added**
  - `/kodi/playlist.m3u` — M3U with proxy URLs.
  - `/kodi/guide.xml` — XMLTV EPG data.
- **Result**
  - Backend supports the web remote, Android TV client, and Kodi PVR from the same codebase.

## Good next places to work

- **PVR addon (Phase 2)**
  - Build `pvr.eliteiptv` native PVR addon with `Record()` callback.
  - Wire Kodi's guide "Record" button to `POST /api/schedule`.
- **Skin polish (Phase 3)**
  - Create texture assets for `skin.elite.dvr`.
  - Test PVR guide rendering with gold/orange theme.
- **DVR auto-start**
  - Option to auto-start DVR buffer on channel tune for seamless pause/rewind.
