# ELITE IPTV Recorder

A Python IPTV recording backend with a mobile web remote and a Kodi-first living-room workflow.

The PC handles the heavy lifting: `FFmpeg` recording, scheduling, backups, favorites, EPG lookup, and remote access. The TV side now centers on Kodi add-ons and the ELITE Kodi skin.

## Key Features

- **Live Guide & EPG Fetching:** Fetches and parses your provider's channel list and EPG data for scheduling reference.
- **Mobile Web Remote:** Built-in lightweight HTTP server on port 8080 for search, scheduling, favorites, and active job control.
- **InstaTunnel Remote Access:** Optional public tunnel for controlling recordings outside your local network.
- **Resilient Recording & Backup Channels:** Uses FFmpeg reconnect flags and supports a backup channel if the primary stream fails.
- **Kodi-first TV workflow:** Native Kodi add-ons and the ELITE skin are the primary couch interface for guide browsing and recording.
- **Setup Wizard & Settings:** First-run onboarding to save XtreamCodes credentials and tunnel configurations.
- **Auto-Dependency Check:** On Windows, the app can prompt to install FFmpeg via `winget` if needed.

## Screenshots

![Desktop UI](Screenshots/Screenshot%202026-04-10%20134911.png)
![Mobile Web Remote](Screenshots/Screenshot%202026-04-10%20135741.png)

## Prerequisites

- **Python 3.8+** installed.
- **FFmpeg** installed and added to your PATH.
  - *Windows:* The app can offer to install this via `winget` on first launch.
  - *macOS:* `brew install ffmpeg`
  - *Linux:* `sudo apt install ffmpeg`
- **Node.js (optional):** Only needed for InstaTunnel remote access.
- **Kodi:** Install Kodi on your TV device to use the ELITE skin and addon workflow.
- **Storage:** Make sure your output directory has enough free space.

## Installation & Setup

### Option 1: Windows Executable

For Windows users, you can download the packaged release directly from the Releases page. No Python installation is required.

> Important: download and extract the **entire folder**, not just the `.exe` file. The app requires the `internal` folder next to the executable.

### Option 2: Run from Source

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/iptv-recorder.git
   cd iptv-recorder
   ```

2. Install the required Python dependencies:

   ```bash
   pip install customtkinter requests
   ```

3. Run the application:

   ```bash
   python iptv_recorder.py
   ```

4. On first run, the Setup Wizard saves your IPTV provider's XtreamCodes credentials to `credentials.json`.

## Usage

### Backend

1. Wait for the app to fetch the channel list from your provider.
2. Use the search bar to find a channel.
3. Optionally select a backup channel.
4. Choose a start time and duration.
5. Click **Schedule Recording**.

### Web Remote

1. Ensure the app is running on your desktop.
2. Use the status text at the bottom of the window to find your local remote URL or InstaTunnel public URL.
3. Open the URL on your phone or tablet.
4. Search channels, view EPG, schedule jobs, or stop active recordings.

### Kodi Frontend

1. Install the Kodi add-ons and skin from `kodi-addon/` and `kodi-skin/`.
2. Point Kodi at the PC backend using the Kodi setup guide.
3. Use Kodi as the main living-room interface for browsing and recording.

## Roadmap

- **Kodi-first TV experience:** Finish the Kodi addon and ELITE skin integration so the TV UI becomes the primary couch workflow.
- **Tunnel hardening:** Stabilize InstaTunnel startup, shutdown, and duplicate-subdomain recovery.
- **Kodi setup polish:** Document SMB setup and the install flow for the Kodi skin/addon path.
- **Web remote maintenance:** Keep the mobile remote API-compatible with backend changes.
- **Backend cleanup:** Continue pruning unused legacy code and docs as the Kodi-first path matures.

## Disclaimer

This application is a recording utility. It does not provide, host, or distribute any IPTV content, playlists, or streams. Users must provide their own access to legal IPTV services. The developers are not responsible for how this software is used.