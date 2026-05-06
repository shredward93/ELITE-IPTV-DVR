# ELITE IPTV Recorder

A Python IPTV recording backend with a **mobile web remote**, an **Android TV app** (Kotlin, Jetpack Compose, Media3), and optional **Kodi** add-ons + skin for the living room.

The PC handles the heavy lifting: `FFmpeg` recording, scheduling, backups, favorites, EPG lookup, and remote access. TV clients are **thin**: they talk to the same HTTP API on port **8080**; no transcoding or file management on the device.

## Key Features

- **Live Guide & EPG Fetching:** Fetches and parses your provider's channel list and EPG data for scheduling reference.
- **Mobile Web Remote:** Built-in lightweight HTTP server on port 8080 for search, scheduling, favorites, and active job control (`static/remote.html` and related assets).
- **Android TV app (`android/`):**
  - **Pairing:** Connect to the PC URL (same LAN as the recorder); optional **recorder failover seconds** (5–300) saved on the server.
  - **Channels:** Search (debounced), favorites grid, record-now / schedule-later dialogs with clear selected-vs-unselected contrast.
  - **Guides:** Multi-channel **EPG grid** by category and single-channel **TV guide** with schedule/record actions.
  - **Live playback (parity with web):** Watch modes — **Live DVR** (preview HLS), **Original** (`/api/stream/live`), **Data saver** (mobile HLS profile) — same URLs/server behavior as the mobile webapp.
  - **DVR Library:** Lists **active** and **completed** recordings from `GET /api/recordings`; plays completed and in-progress `.ts` via **range‑seekable** URLs (`ts_url` / fallback HLS); inline **ExoPlayer** with full transport controls.
  - **Back / remote:** Back hides the player controls first; another Back returns to the **previous in-app screen** (guide, library, channels). Navigation uses a **stable NavHost start** so the stack is not reset after pairing.
  - **Seek / scrub (D-pad):** Progress bar uses **fixed small steps** (not “duration ÷ 20,” which caused multi‑minute jumps on long files); rewind / fast-forward buttons use shorter increments tuned for TV remotes.
  - **UI:** Dark ELITE palette (`EliteColors`), focus rings, and readable borders on lists and form fields.
- **Cloudflare Tunnel Remote Access:** Optional public tunnel for controlling recordings outside your local network. Supports both quick tunnels (temporary URL) and named tunnels with your own custom domain.
- **Resilient Recording & Backup Channels:** Uses FFmpeg reconnect flags and supports a backup channel if the primary stream fails.
- **Kodi workflow (optional):** Kodi PVR/video add-ons and the ELITE skin for guide browsing and recording alongside the same backend.
- **Setup Wizard & Settings:** First-run onboarding to save XtreamCodes credentials and tunnel configurations.
- **Auto-Dependency Check:** On Windows, the app can prompt to install FFmpeg via `winget` if needed.

### Planned

- **Multistream mode (toggle, off by default):** An opt-in switch at the top of the web UI that relaxes the one-video-at-a-time rule and lets the user open a second player pane so two channels — or a channel plus a recording — can play side by side (dual-screen layout, per-pane audio).

## Screenshots

![Desktop UI](Screenshots/Screenshot%202026-04-10%20134911.png)
![Mobile Web Remote](Screenshots/Screenshot%202026-04-10%20135741.png)

_Add Android TV captures under `Screenshots/` or `assets/` when available._

## Prerequisites

- **Python 3.8+** installed.
- **FFmpeg** installed and added to your PATH.
  - *Windows:* The app can offer to install this via `winget` on first launch.
  - *macOS:* `brew install ffmpeg`
  - *Linux:* `sudo apt install ffmpeg`
- **cloudflared (optional):** Only needed for Cloudflare Tunnel remote access. Download from [Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
- **Android TV (optional):** Android **5.0+ (API 21+)** on the TV or set-top box; JDK 17 + Android Studio to build the `android/` module.
- **Kodi (optional):** Install Kodi on your TV device to use the ELITE skin and add-on workflow.
- **Storage:** Make sure your output directory has enough free space.

## Installation & Setup

### Option 1: Windows Executable

For Windows users, you can download the packaged release directly from the Releases page. No Python installation is required.

> Important: download and extract the **entire folder**, not just the `.exe` file. The app requires the `internal` folder next to the executable.

### Option 2: Run from Source

1. Clone the repository:

   ```bash
   git clone https://github.com/shredward93/ELITE-IPTV-DVR.git
   cd ELITE-IPTV-DVR
   ```

2. Install the required Python dependencies:

   ```bash
   pip install -r requirements.txt customtkinter
   ```

   (`requirements.txt` covers shared server libs; `customtkinter` is required for the desktop UI entrypoints.)

3. Run the application:

   ```bash
   python iptv_recorder.py
   ```

4. On first run, the Setup Wizard saves your IPTV provider's XtreamCodes credentials to `credentials.json`.

### Android TV app

1. Install [Android Studio](https://developer.android.com/studio) (JDK **17**).
2. Open the `android/` folder (or import the repo and select the `android` Gradle project).
3. Build a debug or release APK: **Build → Build Bundle(s) / APK(s)** or `./gradlew assembleDebug` from `android/`.
4. On the TV, install the APK and enter the PC’s base URL (e.g. `http://192.168.1.100:8080`). The recorder must already be running and reachable on your LAN.

## Updating (NAS/Docker Deployment)

If running on a Synology NAS (or any Docker setup), follow this workflow for code updates:

### Quick Update Workflow

**On your PC:**

1. Make code changes or pull latest updates
2. Push to GitHub: `git push` (or run `1 - Push to GitHub.bat`)

**On your NAS:**

1. **Git Server app** → Pull latest code from GitHub
2. **Container Manager** → Select `elite-iptv-dvr` → **Stop**, then **Start**

That's it! The updated files are live immediately.

### Why This Works

- Code files are volume-mounted (live reload on restart)
- `PYTHONDONTWRITEBYTECODE=1` prevents Python caching issues
- Your `docker-compose.yml` with credentials is in `.gitignore` and stays untouched

### When to Rebuild

**Just restart** (10 seconds): Changes to `.py` files, `static/`, `core/`

**Full rebuild** (2-5 minutes): Changes to `requirements.txt`, `Dockerfile`, or base image updates

To rebuild: Container Manager → **Action** → **Reset and Rebuild**

## Usage

### Backend

1. Wait for the app to fetch the channel list from your provider.
2. Use the search bar to find a channel.
3. Optionally select a backup channel.
4. Choose a start time and duration.
5. Click **Schedule Recording**.

### Web Remote

1. Ensure the app is running on your desktop.
2. Use the status text at the bottom of the window to find your local remote URL or Cloudflare Tunnel public URL.
3. Open the URL on your phone or tablet.
4. Search channels, view EPG, schedule jobs, or stop active recordings.

### Kodi Frontend (optional)

1. Install the Kodi add-ons and skin from `kodi-addon/` and `kodi-skin/`.
2. Point Kodi at the PC backend using the Kodi setup guide.
3. Use Kodi as a living-room interface for browsing and recording (same API as the web and Android TV clients).

### Android TV app

1. Ensure the recorder is running and the TV can reach `http://<pc-ip>:8080`.
2. Pair once in the app; use **Channels** for search/favorites, **Guide grid** / per-channel **TV Guide** for EPG, and **DVR Library** for recordings.
3. During playback, **Back** hides on-screen controls first, then exits to the screen you came from.

## Roadmap

- **Android TV:** Keep parity with `static/remote.html` for URLs and watch modes; refine UX from feedback.
- **Kodi TV experience:** Continue the PVR addon and ELITE skin integration for users who prefer Kodi.
- **NAS/Docker support:** Containerized deployment for Synology, TrueNAS, and similar.
- **Web remote:** Stay API-compatible with backend changes.
- **Backend cleanup:** Prune unused legacy code and keep docs aligned with shipped clients.

## Remote Access Setup (Cloudflare Tunnel)

For access outside your home network, the app supports **Cloudflare Tunnel** (free, no account required for quick tunnels; custom domains need a free Cloudflare account).

### Quick Tunnel (Easiest — No Domain Required)

1. Download `cloudflared` for your OS from [Cloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
2. Place `cloudflared.exe` (Windows) next to the app, or put it in your PATH
3. Open the app → **⚙ Settings** → **Remote Access**
4. Set **Provider** to **"Cloudflare Tunnel"**
5. Leave **Domain** and **Token** blank
6. Click **Save & Relaunch**
7. The app will launch a quick tunnel — a random `*.trycloudflare.com` URL will appear in the status bar

Each restart gets a new random URL. Good for testing.

### Named Tunnel with Custom Domain

If you own a domain (purchased via Cloudflare or elsewhere), you can have a **persistent URL** that never changes.

#### Step 1: Add Domain to Cloudflare (if not purchased there)

If your domain is elsewhere (Wix, GoDaddy, etc.), point it to Cloudflare:

1. Sign up at [Cloudflare](https://dash.cloudflare.com)
2. Click **"Add Site"** → enter your domain
3. Choose the **Free** plan
4. Cloudflare scans your DNS — approve or add records as needed
5. **Important:** Cloudflare gives you **two nameservers**
6. Go to your domain registrar (Wix, GoDaddy, etc.) → change nameservers to Cloudflare's
7. Wait for DNS propagation (usually minutes, up to 24 hours)

#### Step 2: Create the Tunnel

1. Go to [Cloudflare Zero Trust](https://one.dash.cloudflare.com) (Zero Trust dashboard)
2. Navigate to **Networks** → **Tunnels**
3. Click **"Create a tunnel"** → Select **"Cloudflare tunnel"**
4. Name it: `elite-dvr` (or anything)
5. Select **Windows** as environment
6. Copy the command shown (contains a token starting with `eyJh...`)

#### Step 3: Connect the Tunnel

**Option A — Let the app manage it (recommended):**

- Don't run the command yourself
- Just copy the **token** part (`eyJh...`)
- Proceed to Step 4

**Option B — Install as Windows service:**

- Open **Command Prompt as Administrator**
- `cd` to where you put `cloudflared.exe`
- Paste and run the full command from Step 2
- This runs cloudflared as a background service

#### Step 4: Configure Public Hostname

On the tunnel page in Cloudflare dashboard:

1. Click **"Add a public hostname"**
2. **Subdomain:** `iptv` (or `dvr`, `live`, etc.)
3. **Domain:** Select your domain from dropdown
4. **Type:** `HTTP`
5. **URL:** `localhost:8080` (or whatever port your app uses)
6. Click **"Save hostname"**

#### Step 5: Configure the App

1. Open **ELITE IPTV DVR**
2. Click **⚙ Settings**
3. Under **"Remote Access (Tunnel)"**:
   - **Provider:** `Cloudflare Tunnel`
   - **Domain:** Your full domain (e.g., `iptv.yourdomain.com`)
   - **Tunnel Token:** The `eyJh...` token from Step 2 (if using Option A above)
4. Click **"Save & Relaunch App"**

After restart, the status bar shows your tunnel URL in blue. Click **Copy** → open on your phone to test.

### Troubleshooting

| Issue | Solution |
|----------|----------|
| "cloudflared not found" | Place `cloudflared.exe` next to the app, or add to PATH |
| "Tunnel: not configured" | Check domain and token are saved correctly |
| Can't connect from outside | Check Windows Firewall isn't blocking port 8080; verify hostname is saved in Cloudflare dashboard |
| Domain doesn't resolve | Wait for DNS propagation; check at [DNS Checker](https://dnschecker.org/) |

## Disclaimer

This application is a recording utility. It does not provide, host, or distribute any IPTV content, playlists, or streams. Users must provide their own access to legal IPTV services. The developers are not responsible for how this software is used.