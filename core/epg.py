import base64
import requests


def fetch_epg(server_url, username, password, channel_id, limit=16):
    """
    Fetch short EPG listings for a channel via Xtream API.
    Returns a list of listing dicts, empty list on error.
    """
    url = (
        f"{server_url}/player_api.php?username={username}&password={password}"
        f"&action=get_short_epg&stream_id={channel_id}&limit={limit}"
    )
    try:
        r = requests.get(url, timeout=8)
        return r.json().get("epg_listings", [])
    except Exception:
        return []


def decode_epg_text(text):
    """Decode a base64-encoded EPG title or description."""
    try:
        return base64.b64decode(text).decode("utf-8").strip()
    except Exception:
        return str(text).strip()
