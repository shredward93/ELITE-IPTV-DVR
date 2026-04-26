# Android TV app — roadmap

This is the focused plan for the native **Android TV** client. Server contract, DVR rules, and HTTP range semantics live in `docs/ROADMAP.md` and `docs/ARCHITECTURE_CODEMAP.md`; this file tracks **TV-only** delivery.

## Principles

- **Thin client:** no FFmpeg, no local file management, no full EPG dataset on device.
- **Same APIs as the webapp:** Retrofit against the PC server; windowed guide requests to keep payloads small.
- **Playback:** Media3 ExoPlayer + server-side DVR HLS (`/dvr/playlist.m3u8`); reuse the warm-buffer + live-offset pattern from `PlayerScreen`.

## Phase 1 — Performance and guide (current)

- [x] Optional `window_start_ms` / `window_end_ms` on `/api/epg` and `/api/epg/multi` (server filters listings).
- [x] Android: shared `GuideConstants` window aligned with the grid timeline.
- [x] Android: batched `getMultiEpg` loads (e.g. 8 channels per request) instead of one large `channel_ids` blob.
- [x] Android: cancel-stale single-channel EPG when switching channels quickly.

## Phase 2 — Parity with webapp

- [ ] Recordings library: completed files + range playback where the server exposes it.
- [ ] Scheduling: same validation and error surfacing as web (`/api/schedule`).
- [ ] Favorites and search: match `/api/favorites`, `/api/channels?q=`.
- [ ] Optional: leanback-style channel zapping without rebuilding the whole guide state.

## Phase 3 — TV polish

- [ ] Loading / empty / error states on every screen; retry with backoff.
- [ ] Banner, content rating metadata, and focus restoration after player exit.
- [ ] Accessibility: readable fonts, focus order, reduced motion option if needed.

## Phase 4 — Release

- [ ] Release signing, ProGuard rules for Retrofit/Gson/Media3.
- [ ] Versioning aligned with `config.APP_VERSION` / server `api/info`.
- [ ] Sideload or Play distribution — pick one and document install steps in `docs/NAS_DEPLOYMENT.md` or a short TV install note.

## Out of scope

- Running provider M3U/XMLTV import on the TV (always on the PC server).
- Replacing the server with on-TV logic.
