#!/usr/bin/env python3
"""
ELITE IPTV DVR Kodi Addon
Connects to your PC server backend
"""

import sys
import json
import urllib.request
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Addon configuration
ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

# Server URL - change this to your PC's IP (configured in addon settings)
SERVER_URL = ADDON.getSetting('server_url') or "http://192.168.2.81:8080"

# Kodi routing
HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]


def log(msg):
    """Log to Kodi debug log"""
    xbmc.log(f"[{ADDON_ID}] {msg}", level=xbmc.LOGINFO)


def build_url(action, **params):
    """Build plugin URL with parameters"""
    param_str = f"action={action}"
    for key, value in params.items():
        param_str += f"&{key}={urllib.parse.quote(str(value))}"
    return f"{BASE_URL}?{param_str}"


def fetch_json(endpoint):
    """Fetch JSON from server"""
    url = f"{SERVER_URL}{endpoint}"
    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        log(f"Error fetching {url}: {e}")
        return None


def list_categories():
    """Show category list from /api/guide"""
    log("Fetching guide bundle...")
    
    bundle = fetch_json("/api/guide")
    if not bundle:
        xbmcgui.Dialog().notification(ADDON_NAME, "Failed to fetch guide", xbmcgui.NOTIFICATION_ERROR)
        return
    
    categories = bundle.get('categories', [])
    
    if not categories:
        # Fallback menu if no categories
        items = [
            ("Live TV", "livetv", "All live channels"),
            ("TV Guide", "guide", "Browse EPG guide"),
            ("Recordings", "recordings", "Your DVR recordings"),
        ]
        for name, action, desc in items:
            li = xbmcgui.ListItem(label=name)
            li.setInfo('video', {'title': name, 'plot': desc})
            url = build_url(action)
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
    else:
        # Intentional filtered view: the backend already narrows guide categories to the
        # curated USA / Sports / US Networks / English-style set. If you ever need to
        # revert to the prior behavior, remove that backend filter and this label will
        # still make the list read as a subset rather than a missing-data state.
        header = xbmcgui.ListItem(label="Filtered Guide Categories")
        header.setInfo('video', {
            'title': 'Filtered Guide Categories',
            'plot': 'Showing the curated guide category set from the backend filter.'
        })
        header.setArt({'icon': 'DefaultFolder.png', 'fanart': ADDON.getAddonInfo('fanart')})
        header.setProperty('IsPlayable', 'false')
        xbmcplugin.addDirectoryItem(HANDLE, build_url('guide'), header, isFolder=True)

        # Show actual categories from server
        for cat in categories:
            cat_id = cat.get('category_id', '')
            cat_name = cat.get('category_name', 'Unknown')
            
            li = xbmcgui.ListItem(label=cat_name)
            li.setInfo('video', {
                'title': cat_name,
                'plot': f"Browse {cat_name} channels"
            })
            li.setArt({'icon': 'DefaultVideo.png', 'fanart': ADDON.getAddonInfo('fanart')})
            url = build_url("category", category_id=cat_id, category_name=cat_name)
            xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=True)
        
        # Add utility items
        xbmcplugin.addDirectoryItem(HANDLE, build_url("recordings"), 
            xbmcgui.ListItem(label="DVR Recordings"), isFolder=True)
    
    xbmcplugin.endOfDirectory(HANDLE)


def list_channels_by_category(category_id, category_name):
    """List channels in a category with EPG info"""
    log(f"Fetching channels for category: {category_id}")
    
    bundle = fetch_json(f"/api/guide?category_id={category_id}")
    if not bundle:
        xbmcgui.Dialog().notification(ADDON_NAME, "Failed to fetch channels", xbmcgui.NOTIFICATION_ERROR)
        return
    
    channels = bundle.get('channels', [])
    guide_epg = bundle.get('guide_epg', {})
    
    if not channels:
        xbmcgui.Dialog().notification(ADDON_NAME, "No channels found", xbmcgui.NOTIFICATION_INFO)
        return
    
    for ch in channels:
        ch_id = ch.get('id', '')
        ch_name = ch.get('name', 'Unknown')
        icon = ch.get('stream_icon', '')
        
        # Get current program from EPG
        listings = guide_epg.get(ch_id, [])
        current_program = listings[0] if listings else {}
        program_title = current_program.get('title', 'No EPG data')
        program_desc = current_program.get('description', '')
        
        li = xbmcgui.ListItem(label=f"{ch_name} - {program_title}")
        li.setInfo('video', {
            'title': ch_name,
            'plot': f"{program_title}\n{program_desc}" if program_desc else program_title,
            'genre': category_name
        })
        li.setArt({
            'icon': icon or 'DefaultVideo.png',
            'thumb': icon or 'DefaultVideo.png',
            'fanart': ADDON.getAddonInfo('fanart')
        })
        li.setProperty('IsPlayable', 'true')
        
        # Play URL via proxy
        play_url = f"{SERVER_URL}/api/stream/live?channel_id={ch_id}"
        url = build_url("play", url=play_url, channel_id=ch_id, channel_name=ch_name)
        
        # Add context menu for recording
        li.addContextMenuItems([
            ("Record This Channel", f"RunPlugin({build_url('record', channel_id=ch_id, channel_name=ch_name)})")
        ])
        
        xbmcplugin.addDirectoryItem(HANDLE, url, li, isFolder=False)
    
    xbmcplugin.endOfDirectory(HANDLE)


def play_stream(url):
    """Play a video stream"""
    log(f"Playing: {url}")
    
    li = xbmcgui.ListItem(path=url)
    li.setProperty('IsPlayable', 'true')
    li.setMimeType('application/vnd.apple.mpegurl')
    li.setContentLookup(False)
    
    xbmcplugin.setResolvedUrl(HANDLE, True, li)


def list_recordings():
    """List completed DVR recordings"""
    log("Fetching recordings...")
    
    recordings = fetch_json("/api/recordings")
    if not recordings:
        xbmcgui.Dialog().notification(ADDON_NAME, "Failed to fetch recordings", xbmcgui.NOTIFICATION_ERROR)
        return
    
    recent = recordings.get('recent', [])
    
    if not recent:
        xbmcgui.Dialog().notification(ADDON_NAME, "No recordings found", xbmcgui.NOTIFICATION_INFO)
        return
    
    for rec in recent:
        ch_name = rec.get('channel_name', 'Unknown')
        status = rec.get('status', 'unknown')
        
        li = xbmcgui.ListItem(label=f"{ch_name} ({status})")
        li.setInfo('video', {
            'title': ch_name,
            'plot': f"Status: {status}"
        })
        li.setArt({'icon': 'DefaultVideo.png'})
        # Recordings would need file URLs - placeholder for now
        xbmcplugin.addDirectoryItem(HANDLE, '', li, isFolder=False)
    
    xbmcplugin.endOfDirectory(HANDLE)


def start_recording(channel_id, channel_name):
    """Start recording a channel via API"""
    log(f"Starting recording: {channel_name} ({channel_id})")
    
    try:
        url = f"{SERVER_URL}/api/record"
        data = json.dumps({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "start_time": "NOW"
        }).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode('utf-8'))
            msg = result.get('message', 'Recording started')
            xbmcgui.Dialog().notification(ADDON_NAME, msg, xbmcgui.NOTIFICATION_INFO)
    except Exception as e:
        log(f"Recording failed: {e}")
        xbmcgui.Dialog().notification(ADDON_NAME, "Failed to start recording", xbmcgui.NOTIFICATION_ERROR)


def router():
    """Route to appropriate handler based on action parameter"""
    params = urllib.parse.parse_qs(sys.argv[2][1:])
    action = params.get('action', [''])[0]
    
    log(f"Action: {action}")
    
    if not action:
        list_categories()
    elif action == 'category':
        cat_id = params.get('category_id', [''])[0]
        cat_name = params.get('category_name', [''])[0]
        list_channels_by_category(cat_id, cat_name)
    elif action == 'livetv':
        # Default to first category
        list_categories()
    elif action == 'guide':
        # Future: Full EPG grid view
        xbmcgui.Dialog().notification(ADDON_NAME, "TV Guide grid coming soon", xbmcgui.NOTIFICATION_INFO)
        list_categories()
    elif action == 'recordings':
        list_recordings()
    elif action == 'record':
        ch_id = params.get('channel_id', [''])[0]
        ch_name = urllib.parse.unquote(params.get('channel_name', [''])[0])
        start_recording(ch_id, ch_name)
    elif action == 'play':
        url = urllib.parse.unquote(params.get('url', [''])[0])
        play_stream(url)
    else:
        list_categories()


if __name__ == '__main__':
    router()
