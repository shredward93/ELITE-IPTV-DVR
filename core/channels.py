import requests


def parse_m3u_channels(m3u_text: str) -> dict[str, str]:
    """
    Parse channel names and IDs from M3U playlist text.
    Returns {channel_name: channel_id}.
    """
    channel_map = {}
    current_name = ""
    for line in m3u_text.splitlines():
        if line.startswith("#EXTINF"):
            current_name = line.split(",")[-1].strip()
        elif line.startswith("http") and current_name:
            channel_id = line.split("/")[-1].replace(".ts", "").strip()
            channel_map[current_name] = channel_id
            current_name = ""
    return channel_map


def fetch_channels(server_url, username, password):
    """
    Fetch M3U playlist from Xtream provider.
    Returns (channel_map, m3u_text) where channel_map = {name: channel_id}.
    Raises on network or parse error.
    """
    url = f"{server_url}/get.php?username={username}&password={password}&type=m3u_plus&output=ts"
    response = requests.get(url, timeout=60)
    m3u_text = response.text
    channel_map  = {}
    current_name = ""
    for line in m3u_text.splitlines():
        if line.startswith("#EXTINF"):
            current_name = line.split(",")[-1].strip()
        elif line.startswith("http") and current_name:
            channel_id = line.split("/")[-1].replace(".ts", "").strip()
            channel_map[current_name] = channel_id
            current_name = ""
    return channel_map, m3u_text
