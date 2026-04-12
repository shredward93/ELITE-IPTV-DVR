# ELITE IPTV DVR PVR Add-on

This is the native Kodi PVR client workstream for ELITE IPTV DVR.

## Goal

Make Kodi behave like a TiviMate-style frontend while your PC remains the backend brain:

- One guide inside Kodi
- Live TV via your PC proxy
- Pause / rewind through the DVR HLS buffer
- Record buttons and timers that save to the PC hard drive
- ELITE skin applied in Kodi's PVR windows

## What this add-on will do

- Expose channels to Kodi's Live TV section
- Provide EPG rows from your server's XMLTV cache
- Open live streams through the PC proxy endpoint
- Offer recording/timer actions that call your server's `/api/schedule`
- Surface recordings that already exist in your PC `recordings/` folder

## Server endpoints used

- `GET /kodi/playlist.m3u`
- `GET /kodi/guide.xml`
- `GET /api/stream/live?channel_id=X`
- `GET /dvr/playlist.m3u8`
- `POST /dvr/start`
- `POST /dvr/stop`
- `POST /api/schedule`
- `GET /api/recordings`

## Notes

- Kodi PVR clients are binary add-ons built against the Kodi PVR SDK.
- This folder is the Phase 2 source scaffold.
- No custom textures are required to continue; the existing ELITE skin can be styled later.

## Build reference

Kodi's PVR demo client uses the official Kodi add-on build system and the PVR client API.
The relevant SDK entry point is `#include <kodi/addon-instance/PVR.h>` for modern builds.

For now, this repository keeps the addon source organized and ready to complete in the next pass.
