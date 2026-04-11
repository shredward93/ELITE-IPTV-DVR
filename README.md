# ELITE IPTV Recorder

A fully functional, feature-rich Python desktop application for scheduling and recording IPTV streams directly to disk. 

Built specifically to bypass fragile desktop players, this app uses `FFmpeg` to capture live `.ts` streams and saves them as `.mp4` files. It features advanced auto-reconnect capabilities to survive stream hiccups, an embedded mobile web remote, and a clean dark-mode interface built with `customtkinter`.

## ✨ Key Features

* **Live Guide & EPG Fetching:** Silently fetches and parses your provider's M3U playlist on launch to populate a searchable channel list. Also pulls Electronic Program Guide (EPG) data for scheduling reference.
* **📱 Mobile Web Remote:** Features a built-in lightweight HTTP server (port 8080) that serves a slick mobile single-page app. Search channels, schedule recordings, manage favorites, and view active jobs directly from your phone's browser.
* **🌍 InstaTunnel Remote Access:** Configure a free InstaTunnel API key to securely control your recordings from outside your local network.
* **🛡️ Resilient Recording & Backup Channels:** Uses specific FFmpeg flags (`-reconnect`) to automatically resume writing to the file if the server drops packets. You can also specify a **Backup Channel** that the app will automatically switch to if the primary stream goes down for more than 2 minutes!
* **⭐ Favorites System:** Save frequently recorded channels to a persistent favorites list for quick access.
* **🪄 Setup Wizard & Settings:** Easy first-run onboarding to securely save your XtreamCodes credentials and tunnel configurations.
* **🤖 Auto-Dependency Check:** On Windows, the app will automatically prompt and install FFmpeg via `winget` if it is missing from your system.

## 💻 Screenshots

![Desktop UI](Screenshots/Screenshot%202026-04-10%20134911.png)
![Mobile Web Remote](Screenshots/Screenshot%202026-04-10%20135741.png)

## 📋 Prerequisites

1. **Python 3.8+** installed.
2. **FFmpeg** installed and added to the system's PATH. 
   * *Windows:* The app will offer to auto-install this via `winget` on first launch!
   * *Mac:* `brew install ffmpeg`
   * *Linux:* `sudo apt install ffmpeg`
3. **Node.js (Optional):** Only required if you plan to use the InstaTunnel remote access feature.
4. **Storage:** Ensure your output directory has plenty of space. Uncompressed live streams can result in massive files.

## 🚀 Installation & Setup

### Option 1: Windows Executable (.exe)
For Windows users, you can download the pre-packaged release directly from the Releases page. No Python installation is required!

⚠️ **Important:** Make sure to download and extract the **entire folder** (not just the `.exe` file). The application requires the `internal` folder that sits right next to the executable to function properly.

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

4. **First Run:** The app will launch a Setup Wizard. Enter your IPTV provider's XtreamCodes credentials (Server URL, Username, Password). These will be saved securely to a local `credentials.json` file.

## 🎮 Usage

### Desktop App
1. Wait for the app to fetch the channel list from your provider.
2. Use the search bar to find a channel.
3. Optionally, search and select a **Backup Channel**.
4. Select your Start Time (e.g., `07:00 PM`) and Duration (in minutes).
5. Click **Schedule Recording**.

### Web Remote
1. Ensure the app is running on your desktop.
2. Look at the status text at the bottom of the window to find your Local Remote URL (e.g., `http://192.168.1.X:8080`) or your InstaTunnel Public URL.
3. Open the URL on your mobile device.
4. Use the bottom navigation to Search Channels, view the EPG, Schedule Jobs, or Stop active recordings.

## 🗺️ Roadmap

- [ ] **Standalone Windows Executable:** Bundle the application into a single `.exe` using PyInstaller for easy distribution without needing Python installed.
- [x] **Standalone Windows Executable:** Bundle the application into a single `.exe` using PyInstaller for easy distribution without needing Python installed.
- [ ] **Backend Modularization:** Split the monolithic `iptv_recorder.py` into scalable core modules (`recorder.py`, `channels.py`, `web_server.py`, etc.).
- [ ] **Frontend Modernization:** Potentially wrap the sleek Web UI inside a native desktop window using PyWebView, phasing out Tkinter entirely.
- [ ] **Android TV Client:** Develop a companion Android TV player app with a rich channel guide and DVR interface, utilizing this PC application as the backend "brain" to handle the heavy lifting (stream capturing, FFmpeg processing, and scheduling).

## ⚠️ Disclaimer

This application is a recording utility. It does not provide, host, or distribute any IPTV content, playlists, or streams. Users must provide their own access to legal IPTV services. The developers are not responsible for how this software is used.