# ELITE IPTV DVR Kodi Addon

Live TV and DVR client for ELITE IPTV DVR server. Works on Kodi 19+ (Matrix/Omega) including Android TV.

## Features

- **Live TV streaming** - Direct proxy streaming for instant channel changes
- **DVR mode** - Pause and rewind live TV using the PC-based DVR buffer
- **EPG support** - Guide data from your IPTV provider (via server)
- **Channel icons** - Automatic channel logo support
- **Context menu** - Choose DVR or Live mode per channel

## Installation

### 1. Enable Unknown Sources in Kodi

Settings → System → Add-ons → Enable "Unknown Sources"

### 2. Install the Addon

**Method A - Direct Install:**
1. Copy the `plugin.video.eliteiptv` folder to your Kodi addons directory:
   - Windows: `%APPDATA%\Kodi\addons\`
   - Android: `/Android/data/org.xbmc.kodi/files/.kodi/addons/`
   - Linux: `~/.kodi/addons/`
2. Restart Kodi

**Method B - Zip Install:**
1. Zip this folder (rename to `plugin.video.eliteiptv.zip`)
2. Kodi → Add-ons → Install from zip file
3. Select the zip file

### 3. Configure the Addon

1. Kodi → Add-ons → My add-ons → Video add-ons → ELITE IPTV DVR
2. Click Configure
3. Set:
   - **Server IP**: Your PC's IP address (e.g., 192.168.1.100)
   - **Server Port**: 8080 (default)
4. Make sure your ELITE IPTV DVR server is running on the PC

## Usage

### Watching Live TV (Fast)

- Select any channel to play directly
- Fast channel switching, minimal delay
- No pause/rewind capability

### Watching with DVR (Pause/Rewind)

- Long-press on channel → "Watch with DVR (Pause/Rewind)"
- Wait 2-3 seconds for buffer to start
- You can now:
  - **Pause** live TV
  - **Rewind** up to the buffer limit (default 5 minutes)
  - **Fast-forward** back to live

### EPG Guide (Kodi PVR)

For full TV guide integration:

1. Enable Kodi's PVR IPTV Simple Client:
   - Kodi → Add-ons → Install from repository → PVR clients → PVR IPTV Simple Client
2. Configure PVR IPTV Simple Client:
   - Location: Remote path (Internet address)
   - M3U playlist URL: `http://YOUR-PC-IP:8080/kodi/playlist.m3u`
   - XMLTV URL: `http://YOUR-PC-IP:8080/kodi/guide.xml`
3. Restart Kodi
4. Access TV guide via TV → Guide

## Troubleshooting

### "Connection error"
- Verify the PC server is running
- Check the IP address in addon settings
- Ensure both devices are on the same network

### DVR doesn't start
- Check `/dvr/status` endpoint in browser
- Verify FFmpeg is installed on the PC

### No EPG data
- Wait for first XMLTV download (can take 30-60 seconds)
- Check `/kodi/guide.xml` loads in browser

## URLs Reference

These endpoints work directly in Kodi or browser:

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Playlist | `http://PC-IP:8080/kodi/playlist.m3u` | Channel list for PVR |
| EPG Guide | `http://PC-IP:8080/kodi/guide.xml` | TV guide data |
| Live Stream | `http://PC-IP:8080/api/stream/live?channel_id=XXX` | Direct proxy |
| DVR HLS | `http://PC-IP:8080/dvr/playlist.m3u8` | Pause/rewind stream |
