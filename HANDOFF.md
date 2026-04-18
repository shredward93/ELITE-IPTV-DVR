# ELITE IPTV DVR — Session Handoff

## Project Overview

**Repo:** `shredward93/ELITE-IPTV-DVR` (GitHub, private)  
**NAS:** Synology DS1621xs+ — Intel Xeon D-1527 (4C/8T @ 2.2GHz, NO iGPU)  
**Deployment:** Docker via Synology Container Manager, Cloudflare tunnel at `server.eliteiptvdvr.uk`  
**Active branch:** `mobile-webapp` (do NOT merge to `main` yet — still testing)  
**NAS pull script:** Task Scheduler runs:
```bash
cd /volume1/docker/eliteiptvdvr
git config --global --add safe.directory /volume1/docker/eliteiptvdvr
git fetch origin
git checkout mobile-webapp
git reset --hard origin/mobile-webapp
docker-compose up -d
```

---

## What Was Built This Session

### 1. `core/mobile_transcode.py` (new file)

A singleton transcode manager that spins up on-demand ffmpeg HLS sessions per channel+quality.

**Profiles:**
| Button | Profile key | Resolution | FPS cap | Video bitrate |
|--------|-------------|------------|---------|---------------|
| Auto   | `auto`      | → mobile on phones, original on desktop | — | — |
| Low    | `low`       | 640×360 | 30 | 700k |
| Mobile | `mobile`    | 854×480 | 60 | 1600k |
| HD     | `hd`        | 1280×720 | 60 | 3000k |
| Orig   | `original`  | passthrough | source | no transcode |

**Key design decisions:**
- Hardware encoder detection with **3-stage validation**: (1) compiled in, (2) `/dev/dri` device present, (3) 1-frame smoke-test. Without this, Debian's ffmpeg reports `h264_qsv` compiled-in even on iGPU-less machines and silently dies — this was bug #1.
- `libx264 -preset ultrafast -tune zerolatency` software fallback — the Xeon handles it at ~12% CPU for HD (confirmed working).
- `-hls_flags +temp_file` — atomic segment writes. ffmpeg writes to `.ts.tmp`, renames to `.ts` only when fully closed. Without this, mobile browsers fetched half-written HD segments and the decoder crashed — this was bug #2.
- `MAX_TRANSCODES` env var (docker-compose) controls concurrent session cap (default 3).
- Sessions idle-killed after 25s; ffmpeg stderr captured to `<session>/ffmpeg.log` and tailed into container logs on unexpected exit.

**New API endpoints (in `core/web_server.py`):**
- `GET /api/stream/mobile.m3u8?channel_id=X&profile=Y` — serves HLS playlist, waits up to 15s for first segment
- `GET /api/stream/mobile/<channel_id>/<profile>/seg_NNNNN.ts` — serves individual HLS segments, touches session to reset idle timer
- `GET /api/stream/info?channel_id=X` — returns detected encoder info (debug)
- `GET /api/recordings` — **enhanced** to return `{active: [...], recent: [...], completed: [...]}` with file URLs, metadata, sizes

### 2. `static/remote.html` — major updates

**Live player upgrades:**
- Replaced old `/api/stream/url` (returned LAN IP, useless over Cloudflare tunnel) with same-origin relative `/api/stream/mobile.m3u8` URLs — this was the original root cause of mobile playback being completely broken.
- hls.js loaded via CDN for desktop browsers; native HLS on iOS Safari.
- Quality toggle bar (Auto / Low / Mobile / HD / Orig) in the player, persisted to `localStorage`.
- `tearDownPlayer()` fully destroys hls.js instance before switching quality to avoid memory leaks.

**Recordings tab rebuilt:**
- Split into **Active** (with 🔴 LIVE badge, elapsed/remaining time, Stop button, Watch Live button) and **Completed** (Play, Open in VLC, Download) sections.
- Inline video player drops into the card itself.
- VLC deep links: `vlc-x-callback://` on iOS, `vlc://` on Android/desktop.
- Auto-refreshes every 5s; also refreshes immediately on schedule/stop actions.

---

## Current Status — What Works ✅

- Live channel playback on mobile in all quality modes (Auto / Low / Mobile / HD / Orig) — **confirmed working on Galaxy Fold 5**
- Quality switching mid-stream
- Quality preference persisted in localStorage
- HD 720p60 transcoding at ~12% CPU on Xeon D-1527
- Recordings tab shows active and completed recordings with metadata
- Download button works (confirmed)
- Banner + LED for active recording status
- Recording start / stop from webapp

---

## What Still Needs to Be Done ❌

### Recordings inline playback (next task)

**Problem:** The "Play" button in the Recordings → Completed section currently does:
```js
playRecordingInline('ts', r.ts_url, id)
// which sets: video.src = '/recordings/SomeFile.ts'
```

Raw MPEG-TS in a `<video>` tag is **not supported on iOS Safari** and unreliable on Android Chrome. So the Play button silently does nothing on most phones.

**Solution to implement:**

**Backend — add a new endpoint in `core/web_server.py`:**

`GET /api/recordings/hls/<filename>/index.m3u8`

This should:
1. Look up the `.ts` file in the recordings dir
2. Run: `ffmpeg -i <file.ts> -c copy -f hls -hls_time 10 -hls_flags independent_segments+temp_file -hls_segment_filename <tmpdir>/seg_%05d.ts <tmpdir>/index.m3u8`
   - `-c copy` = zero re-encoding (pure remux), very fast, ~5 seconds per hour of content
   - `hls_time 10` = bigger segments ok for VOD (reduces segment count)
3. Wait for all segments to be written (ffmpeg exits when done — it's a static file, not live)
4. Cache the tmpdir by filename (so repeat plays don't re-remux)
5. Serve `index.m3u8`

Also add: `GET /api/recordings/hls/<filename>/seg_NNNNN.ts` to serve the segments.

**Frontend — in `renderCompletedRec()` in `static/remote.html`:**

Change the Play button to use hls:
```js
// Current:
`<button ... onclick="playRecordingInline('ts','${r.ts_url}','${id}')">▶  Play</button>`

// Change to:
`<button ... onclick="playRecordingInline('hls','/api/recordings/hls/${encodeURIComponent(r.filename)}/index.m3u8','${id}')">▶  Play</button>`
```

The `playRecordingInline('hls', ...)` path already handles hls.js vs native HLS correctly (same code path as live stream inline player in the Active section).

**Key considerations:**
- Cache cleanup: remuxed HLS dirs live in `/tmp/elite_rec_hls/<filename>/`. Clean up on container restart (they're in `/tmp` so this is automatic). Can also add a simple TTL reaper if memory/disk becomes a concern.
- The remux blocks the request thread for a few seconds on first play. Consider either: (a) doing it async + poll endpoint, or (b) just accepting the delay (files are typically 1-4GB, remux is IO-bound at ~50MB/s → 20-80s for large files). **Probably want async + 202 polling or a loading state in the UI.**
- Alternatively: a simpler approach is to just increase the `hls_time` to a large value (e.g., 60s) and only wait for the first segment before responding, then serve segments progressively — but this is more complex to implement than full-file-then-serve.

**Simplest viable implementation (recommended starting point):**
- Run ffmpeg synchronously on first request, respond 200 when done.
- Show "Converting…" spinner in the UI while waiting (the fetch will just take a few seconds).
- Cache result so second play is instant.

---

## File Map

```
ELITE IPTV DVR/
├── core/
│   ├── mobile_transcode.py   ← NEW — transcode manager
│   ├── web_server.py         ← modified — new stream + recordings endpoints
│   ├── recorder.py           ← existing — recording logic
│   └── ...
├── static/
│   └── remote.html           ← modified — full mobile UI overhaul
├── docker-compose.yml        ← gitignored (has credentials) — has MAX_TRANSCODES: "3"
├── Dockerfile                ← unchanged — python:3.11-slim-bookworm + ffmpeg + cloudflared
└── HANDOFF.md                ← this file
```

---

## Branch / Credential Notes

- `docker-compose.yml` is in `.gitignore` (contains IPTV credentials + Cloudflare token).
- `docker-compose.backup*.yml` also gitignored (added this session after accidental leak).
- Cloudflare token and IPTV password were briefly exposed in commit `94d4b13` (now scrubbed via force-push). **User should rotate both as a precaution.**
- The NAS gets updates by running the Task Scheduler task above — it pulls `mobile-webapp` and does `docker-compose up -d` (NOT restart — restart won't re-read env vars).
