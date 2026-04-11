# ELITE IPTV DVR — Implementation Plan

## Architecture Overview

**Two-repo system:**
- `iptv-recorder` (this repo) — PC "server brain": Python, tkinter, FFmpeg, REST API
- `elite-iptv-dvr` (Android) — Android TV client: Kotlin, Jetpack Compose for TV, ExoPlayer

The PC does all heavy lifting. Android TV is a thin player + remote control that talks to the PC's HTTP API on port 8080 (or via InstaTunnel for remote access).

---

## Phase 1 — PC: DVR Engine

### New module: `core/dvr_manager.py`

Handles the rolling live buffer. When Android TV tunes to a channel, the PC starts FFmpeg in **segment mode**:

```
ffmpeg -i <stream_url> -f segment -segment_time 1800 -reset_timestamps 1 dvr_buffer/seg_%03d.ts
```

- Segments are 30 minutes each
- Keep last 12 segments = 6-hour rolling window
- When segment 13 starts, delete segment 1
- `DVRJob` class, separate from existing `RecordingJob`

**Storage caps (both enforced, whichever hits first):**
- Max buffer hours: 6 (configurable)
- Max DVR storage: 50 GB (configurable)
- Protected recordings (scheduled/manual): never auto-deleted

### New API endpoints in `core/web_server.py`

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/dvr/start` | Android tunes to channel → PC starts rolling buffer |
| POST | `/dvr/stop` | Channel changed or app closed → stop buffer |
| GET | `/dvr/segments` | Returns JSON list of available segments + durations |
| GET | `/dvr/stream/<seg>` | Serves segment `.ts` bytes with HTTP range support |
| GET | `/dvr/status` | Buffer age, total size, storage remaining |
| GET | `/recordings` | List of all completed scheduled recordings |
| GET | `/recordings/<file>` | Serve a completed recording file |

### Settings additions
Add to the Settings dialog (PC):
- DVR buffer max hours (default: 6)
- DVR storage cap in GB (default: 50)
- DVR output folder (separate from recordings folder)

---

## Phase 2 — Android TV App

**Stack:** Kotlin + Jetpack Compose for TV + Retrofit + Media3/ExoPlayer

### Screens

1. **Pair Screen** — Enter PC's IP:8080 or InstaTunnel URL. Saved to local prefs.
2. **Channel Browser** — Grid of channels/favorites fetched from `/channels`. D-pad navigable.
3. **TV Guide** — EPG grid per channel. "Record" button calls existing `/schedule` endpoint.
4. **Player** — ExoPlayer fullscreen. Plays `dvr/stream/seg_XXX.ts` segments progressively.
5. **DVR Library** — Browse completed scheduled recordings from `/recordings`. Play them back.
6. **Settings** — Change PC URL, DVR preferences.

### Live DVR Playback Flow

1. User selects channel → `POST /dvr/start {channel_id, channel_name}`
2. Android fetches `/dvr/segments` → builds segment playlist
3. ExoPlayer plays segments sequentially as a `ConcatenatingMediaSource`
4. Live edge = last segment (currently being written) — ExoPlayer polls for new content
5. Seek bar shows total buffered duration; seeking past live edge is disabled
6. Channel change → `POST /dvr/stop` → new `POST /dvr/start`

### ExoPlayer notes
- Use `ProgressiveMediaSource` for each segment (handles growing files via HTTP range)
- Poll `/dvr/segments` every 30s to detect new segments added to playlist
- `LiveConfiguration` not needed — we manage the "live edge" manually via segment list

### D-pad / 10-foot UI rules
- All interactive elements must be focusable
- Minimum touch target: 48dp
- Large text (18sp minimum for body)
- High contrast — dark theme only
- No text input except for Pair screen (use system keyboard overlay)

---

## Phase 3 — Polish

- **Tray mode for PC:** Option to hide tkinter window, run as system tray icon (Windows)
- **Auto-discovery:** Android TV broadcasts UDP to find PC on local network (no manual IP entry)
- **Push notifications:** PC pushes recording-complete events to Android via long-poll or SSE
- **Storage dashboard:** Visual breakdown of DVR buffer vs saved recordings on Android

---

## File Structure (PC additions)

```
core/
  recorder.py       ← existing: RecordingJob (scheduled recordings)
  dvr_manager.py    ← NEW: DVRJob, segment cleanup, storage cap enforcement
  web_server.py     ← extend: add /dvr/* and /recordings endpoints
  channels.py       ← unchanged
  epg.py            ← unchanged
  tunnel.py         ← unchanged
  credentials.py    ← unchanged
  favorites.py      ← unchanged
config.py           ← add DVR_BUFFER_DIR, DVR_MAX_HOURS, DVR_MAX_GB
```

---

## Build Order

1. `core/dvr_manager.py` — DVRJob + segment rotation + storage cap
2. New `/dvr/*` endpoints in `web_server.py`
3. New `/recordings` endpoints in `web_server.py`
4. Android: Pair screen + API client (Retrofit)
5. Android: Channel browser
6. Android: Player with DVR seek
7. Android: TV Guide + schedule from guide
8. Android: DVR Library
9. PC: tray mode
10. Android: auto-discovery
