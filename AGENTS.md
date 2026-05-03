# AGENTS.md

## Cursor Cloud specific instructions

### Overview

ELITE IPTV DVR is a Python backend (HTTP API on port 8080) with a web remote UI. See `README.md` and `CLAUDE.md` for full docs.

### Running the server

- **Headless mode** (no GUI deps): `python3 server_headless.py`
  - Requires env vars or `credentials.json`: `SERVER_URL`, `USERNAME`, `PASSWORD`
  - Without real IPTV credentials the server starts fine but loads 0 channels. All API endpoints still work.
- **GUI mode**: `python3 main.py` — requires a display and `customtkinter`.

### Key endpoints

All served on port **8080**: `/api/status`, `/api/channels?q=`, `/api/favorites`, `/api/favorites/add` (POST), `/api/favorites/remove` (POST), `/api/schedule` (POST), `/` (web remote HTML).

### Lint

No project-specific linter is configured. Use `ruff check --select=E9,F63,F7,F82 .` for syntax-level checks. Two pre-existing F821 warnings exist in `iptv_recorder.py` and `ui/app.py` (late-binding lambda closures) — these are in existing code.

### Tests

No automated test suite exists in this repo. Verify changes by running the headless server and hitting API endpoints with `curl`.

### Gotchas

- FFmpeg is already installed in the VM (`/usr/bin/ffmpeg`). It is required for recording and DVR features but the server starts without it.
- `customtkinter` is only needed for GUI mode (`main.py`), not headless.
- The server exits immediately if `SERVER_URL`/`USERNAME`/`PASSWORD` are all empty. Provide dummy values to start the server without a real provider.
- State is stored in JSON flat files (`favorites.json`, `credentials.json`, `settings.json`, `scheduled_recordings.json`) in the app directory.
