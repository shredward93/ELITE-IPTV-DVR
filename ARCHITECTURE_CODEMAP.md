# ELITE IPTV DVR Architecture Codemap

This document maps the current backend and Android integration points so future UI/UX work can stay focused and safe.

## System view

- **PC app (`main.py`, `iptv_recorder.py`)**
  - Desktop control surface for scheduling, recording, favorites, and configuration.
  - Loads credentials, checks FFmpeg, and starts the Tkinter app.
- **Shared backend modules (`core/`)**
  - `core/web_server.py` exposes the HTTP API used by the Android client and web remote.
  - `core/dvr_manager.py` manages the rolling live DVR buffer on the PC.
  - `core/channels.py` fetches and parses the provider M3U channel list.
  - `core/epg.py` fetches and normalizes EPG listings.
  - `core/credentials.py`, `core/favorites.py`, `core/tunnel.py` support app state and remote access.
- **Android client (`android/app/`)**
  - Compose UI for channel browser, guide, recordings, and live playback.
  - Talks to the PC only through HTTP endpoints on port 8080.

## Backend request flow

1. `main.py` starts the desktop app.
2. The desktop app loads IPTV credentials and channel data.
3. `core/web_server.py` serves:
   - `/api/channels`
   - `/api/channels/all`
   - `/api/categories`
   - `/api/channels/by-category`
   - `/api/epg`
   - `/api/epg/multi`
   - `/api/stream/url`
   - `/api/stream/live`
   - `/dvr/start`
   - `/dvr/stop`
   - `/dvr/status`
   - `/dvr/segments`
   - `/dvr/playlist.m3u8`
   - `/recordings`
4. The Android app consumes those endpoints through Retrofit / helper URL builders.

## Live playback architecture

- **Current stable path**
  - Android live playback uses the direct proxy stream endpoint: `/api/stream/live?channel_id=...`
  - The proxy fetches the provider stream and pipes bytes through to the client.
- **DVR buffer path**
  - `core/dvr_manager.py` maintains a rolling HLS buffer for recording / DVR-related work.
  - The HLS playlist and segments remain part of the backend, but they are not the current live playback path.

## TV guide / EPG flow

- `core/epg.py` is the shared helper for short EPG lookups.
- `core/web_server.py` reuses that helper for both `/api/epg` and `/api/epg/multi`.
- The desktop UI still has its own guide-rendering logic in `ui/app.py` and `iptv_recorder.py`, but both now use the shared EPG fetch helper.

### Android guide screens

- **`TVGuideScreen`**
  - Single-channel guide view.
  - Loads one channel’s EPG through `MainViewModel.loadEpg(channelId)`.
  - Shows a vertical list of listings and lets the user schedule a recording from the selected item.
  - Also exposes a direct "Watch Live" action back to the player screen.
- **`EpgGuideScreen`**
  - Category-first grid guide.
  - Loads categories with `MainViewModel.loadCategories()`.
  - Selecting a category loads channel lists via `loadChannelsByCategory(categoryId)`.
  - When channels are available, it loads multi-channel guide data via `loadGuideEpg(ids, limit)`.
  - Renders a horizontal timeline grid of channels + programme blocks and allows play-live / record actions from each row.

### Android guide data flow

- `ApiService.getEpg()` → `/api/epg`
- `ApiService.getCategories()` → `/api/categories`
- `ApiService.getChannelsByCategory()` → `/api/channels/by-category`
- `ApiService.getMultiEpg()` → `/api/epg/multi`
- `MainViewModel` stores the latest results in:
  - `epgListings`
  - `categories`
  - `categoryChannels`
  - `guideEpg`
- `Navigation.kt` wires the guide screens into the app routes:
  - `guide/{channelId}/{channelName}` → `TVGuideScreen`
  - `guide_grid` → `EpgGuideScreen`

## Small backend cleanup completed

- **EPG helper reuse**
  - Centralized EPG fetch + decode behavior in `core/epg.py`.
  - Removed duplicated EPG request/decode logic from `core/web_server.py`.
- **Result**
  - Backend guide code is a little easier to maintain.
  - No live player behavior was changed.

## Good next places to work

- **Guide UX**
  - TV guide layout, loading state, and channel metadata presentation.
- **Live controls**
  - Only if you want to refine on-screen controls, not the playback engine itself.
- **Backend follow-up**
  - If needed, align the remaining desktop-side EPG helpers with `core/epg.py` later.
