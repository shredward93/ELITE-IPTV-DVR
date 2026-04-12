"""
Kodi Addon for ELITE IPTV DVR

Integrates with the PC-based ELITE IPTV DVR server to provide:
- Live TV with pause/rewind (via DVR buffer)
- Direct live streaming
- EPG guide support

Settings required:
- Server IP (e.g., 192.168.1.100)
- Server Port (default: 8080)
"""

import sys
import json
import urllib.request
import urllib.parse
import urllib.error
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

# Addon constants
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

# Settings
SETTING_SERVER_IP = ADDON.getSettingString('server_ip') or '192.168.1.100'
SETTING_SERVER_PORT = ADDON.getSettingInt('server_port') or 8080


def get_server_url():
    """Build the server base URL from settings."""
    return f"http://{SETTING_SERVER_IP}:{SETTING_SERVER_PORT}"


def make_request(url, method='GET', data=None):
    """Make HTTP request to server with error handling."""
    try:
        req = urllib.request.Request(url, method=method)
        if data and method == 'POST':
            req.add_header('Content-Type', 'application/json')
            req.data = json.dumps(data).encode('utf-8')

        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode('utf-8')
    except urllib.error.URLError as e:
        xbmcgui.Dialog().notification(ADDON_NAME, f'Connection error: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        return None
    except Exception as e:
        xbmcgui.Dialog().notification(ADDON_NAME, f'Error: {str(e)}', xbmcgui.NOTIFICATION_ERROR)
        return None


def parse_m3u(content):
    """Parse M3U playlist content into channel list."""
    channels = []
    lines = content.strip().split('\n')
    current_ch = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('#EXTINF'):
            # Parse EXTINF line: #EXTINF:-1 tvg-id="X" tvg-name="Name" ...
            current_ch = {}

            # Extract tvg-name
            if 'tvg-name="' in line:
                start = line.find('tvg-name="') + 10
                end = line.find('"', start)
                current_ch['name'] = line[start:end]
            else:
                # Fallback: get name after last comma
                if ',' in line:
                    current_ch['name'] = line.rsplit(',', 1)[-1]
                else:
                    current_ch['name'] = 'Unknown'

            # Extract tvg-id
            if 'tvg-id="' in line:
                start = line.find('tvg-id="') + 8
                end = line.find('"', start)
                current_ch['tvg_id'] = line[start:end]

            # Extract tvg-logo
            if 'tvg-logo="' in line:
                start = line.find('tvg-logo="') + 10
                end = line.find('"', start)
                current_ch['icon'] = line[start:end]
            else:
                current_ch['icon'] = ''

        elif line.startswith('http') and current_ch:
            current_ch['url'] = line
            # Extract channel_id from URL if proxy mode
            if 'channel_id=' in line:
                current_ch['channel_id'] = line.split('channel_id=')[1].split('&')[0]
            else:
                current_ch['channel_id'] = ''
            channels.append(current_ch)
            current_ch = None

    return channels


def build_url(mode, **kwargs):
    """Build addon URL with parameters."""
    params = urllib.parse.urlencode(kwargs)
    return f"{BASE_URL}?mode={mode}&{params}"


def list_channels():
    """Show main menu with channel list."""
    server_url = get_server_url()
    m3u_url = f"{server_url}/kodi/playlist.m3u"

    xbmcplugin.setPluginCategory(HANDLE, 'Channels')
    xbmcplugin.setContent(HANDLE, 'videos')

    # Fetch playlist
    content = make_request(m3u_url)
    if not content:
        xbmcplugin.endOfDirectory(HANDLE)
        return

    channels = parse_m3u(content)

    if not channels:
        xbmcgui.Dialog().notification(ADDON_NAME, 'No channels found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(HANDLE)
        return

    # Add "Watch Live (No DVR)" mode toggle info
    list_item = xbmcgui.ListItem(label='[ Live Mode: Direct Stream ]')
    list_item.setInfo('video', {'title': 'Direct streaming mode - instant channel change'})
    list_item.setArt({'icon': 'DefaultAddonPVRClient.png'})
    xbmcplugin.addDirectoryItem(
        handle=HANDLE,
        url=build_url('toggle_mode'),
        listitem=list_item,
        isFolder=True
    )

    # Add separator
    list_item = xbmcgui.ListItem(label='─' * 30)
    list_item.setProperty('IsPlayable', 'false')
    xbmcplugin.addDirectoryItem(handle=HANDLE, url='', listitem=list_item, isFolder=False)

    # Add channels
    for ch in channels:
        channel_id = ch.get('channel_id', '')
        channel_name = ch.get('name', 'Unknown')
        icon = ch.get('icon', '')

        list_item = xbmcgui.ListItem(label=channel_name)
        list_item.setInfo('video', {
            'title': channel_name,
            'mediatype': 'video'
        })

        if icon:
            list_item.setArt({
                'thumb': icon,
                'icon': icon,
                'poster': icon
            })

        # Context menu: Watch with DVR vs Watch Live
        context_menu = [
            ('Watch with DVR (Pause/Rewind)', f'RunPlugin({build_url("play_dvr", channel_id=channel_id, name=channel_name)})'),
            ('Watch Live (Direct)', f'RunPlugin({build_url("play_live", channel_id=channel_id)})')
        ]
        list_item.addContextMenuItems(context_menu)

        # Default action: Play Live
        play_url = build_url('play_live', channel_id=channel_id)

        xbmcplugin.addDirectoryItem(
            handle=HANDLE,
            url=play_url,
            listitem=list_item,
            isFolder=False
        )

    xbmcplugin.endOfDirectory(HANDLE)


def play_live(channel_id):
    """Play channel directly via proxy (fast, no pause/rewind)."""
    server_url = get_server_url()
    stream_url = f"{server_url}/api/stream/live?channel_id={channel_id}"

    play_item = xbmcgui.ListItem(path=stream_url)
    play_item.setProperty('IsPlayable', 'true')
    play_item.setMimeType('video/mp2t')
    play_item.setContentLookup(False)

    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)


def play_dvr(channel_id, channel_name):
    """Start DVR buffer and play with pause/rewind capability."""
    server_url = get_server_url()

    # Show progress dialog
    dialog = xbmcgui.DialogProgress()
    dialog.create(ADDON_NAME, f'Starting DVR buffer for {channel_name}...')
    dialog.update(25)

    # Start DVR buffer on server
    start_url = f"{server_url}/dvr/start"
    result = make_request(start_url, method='POST', data={
        'channel_id': channel_id,
        'channel_name': channel_name
    })

    if not result:
        dialog.close()
        xbmcgui.Dialog().notification(ADDON_NAME, 'Failed to start DVR', xbmcgui.NOTIFICATION_ERROR)
        return

    dialog.update(75, 'Buffering... Please wait')

    # Wait a moment for buffer to initialize
    import time
    time.sleep(2)

    dialog.update(100, 'Starting playback...')
    dialog.close()

    # Play the DVR HLS stream
    dvr_url = f"{server_url}/dvr/playlist.m3u8"

    play_item = xbmcgui.ListItem(path=dvr_url)
    play_item.setProperty('IsPlayable', 'true')
    play_item.setMimeType('application/vnd.apple.mpegurl')
    play_item.setContentLookup(False)

    # Set stream info for Kodi player
    play_item.setProperty('inputstream', 'inputstream.hls')
    play_item.setProperty('inputstream.hls.manifest_type', 'hls')

    xbmcplugin.setResolvedUrl(HANDLE, True, listitem=play_item)


def stop_dvr():
    """Stop the DVR buffer. Can be called from context menu or on playback stop."""
    server_url = get_server_url()
    stop_url = f"{server_url}/dvr/stop"

    result = make_request(stop_url, method='POST')
    if result:
        xbmcgui.Dialog().notification(ADDON_NAME, 'DVR stopped', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification(ADDON_NAME, 'DVR stop failed', xbmcgui.NOTIFICATION_ERROR)


def show_settings():
    """Open addon settings."""
    ADDON.openSettings()


def router(params):
    """Route to appropriate handler based on mode parameter."""
    mode = params.get('mode', [''])[0]

    if mode == '':
        list_channels()
    elif mode == 'play_live':
        play_live(params.get('channel_id', [''])[0])
    elif mode == 'play_dvr':
        play_dvr(
            params.get('channel_id', [''])[0],
            params.get('name', ['Unknown'])[0]
        )
    elif mode == 'stop_dvr':
        stop_dvr()
    elif mode == 'settings':
        show_settings()
    elif mode == 'toggle_mode':
        # Just refresh to show same menu (placeholder for future enhancement)
        xbmc.executebuiltin('Container.Refresh')
    else:
        list_channels()


if __name__ == '__main__':
    params = urllib.parse.parse_qs(sys.argv[2][1:])
    router(params)
