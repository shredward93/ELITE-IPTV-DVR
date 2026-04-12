import base64
import gzip
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests

import config


_GUIDE_KEY_RE = re.compile(r"[^a-z0-9]+", re.IGNORECASE)


def decode_epg_text(text):
    """Decode a base64-encoded EPG title or description."""
    try:
        return base64.b64decode(text).decode("utf-8").strip()
    except Exception:
        return str(text).strip()


def normalize_guide_key(value):
    if value is None:
        return ""
    return _GUIDE_KEY_RE.sub("", str(value).strip().lower())


def _extract_listing_items(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("epg_listings", "listings", "epg", "items", "data", "programs", "response"):
            items = payload.get(key)
            if isinstance(items, list):
                return items
            if isinstance(items, dict):
                nested = _extract_listing_items(items)
                if nested:
                    return nested

    return []


def _first_value(entry, *keys):
    for key in keys:
        value = entry.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_channel(channel):
    if not isinstance(channel, dict):
        return None

    channel_id = str(_first_value(channel, "id", "stream_id", "channel_id", "category_id") or "").strip()
    name = str(_first_value(channel, "name", "channel_name", "title") or "").strip()
    if not channel_id and not name:
        return None

    normalized = dict(channel)
    normalized["id"] = channel_id
    normalized["name"] = name
    normalized["guide_key"] = normalize_guide_key(channel.get("guide_key") or channel_id or name)
    return normalized


def _normalize_category(category):
    if not isinstance(category, dict):
        return None

    category_id = str(_first_value(category, "category_id", "id") or "").strip()
    name = str(_first_value(category, "category_name", "name") or "").strip()
    if not name:
        return None

    return {
        "category_id": category_id,
        "category_name": name,
    }


def _normalize_listing(entry):
    if not isinstance(entry, dict):
        return None

    normalized = dict(entry)
    normalized["title"] = decode_epg_text(
        _first_value(entry, "title", "name", "program_name", "program", "event_name") or ""
    )
    description = decode_epg_text(
        _first_value(entry, "description", "desc", "plot", "summary", "overview") or ""
    )
    normalized["description"] = description if description else None
    normalized["start"] = _first_value(entry, "start", "start_time", "from", "begin", "startDate")
    normalized["stop"] = _first_value(entry, "stop", "end", "end_time", "to", "finish", "endDate")
    normalized["channel_key"] = normalize_guide_key(
        _first_value(entry, "channel_id", "stream_id", "tvg_id", "tvg-id", "channel", "name")
    )
    return normalized


def _normalize_xmltv_listing(channel_key, entry):
    if not isinstance(entry, dict):
        return None

    start = _first_value(entry, "start", "start_time")
    stop = _first_value(entry, "stop", "end", "end_time")
    normalized = {
        "title": decode_epg_text(_first_value(entry, "title", "name") or ""),
        "description": decode_epg_text(_first_value(entry, "desc", "description") or ""),
        "start": str(start).strip() if start else None,
        "stop": str(stop).strip() if stop else None,
        "channel_key": normalize_guide_key(channel_key),
        "source": "xmltv",
    }
    return normalized


def _provider_get(url, timeout=10):
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _fetch_categories(server_url, username, password):
    url = (
        f"{server_url}/player_api.php"
        f"?username={username}&password={password}"
        f"&action=get_live_categories"
    )
    try:
        payload = _provider_get(url, timeout=8)
        categories = [_normalize_category(item) for item in payload if isinstance(item, dict)]
        return [item for item in categories if item]
    except Exception as exc:
        print(f"[EPG] Failed to fetch categories: {exc}")
        return []


def _fetch_channels_by_category(server_url, username, password, category_id):
    if not category_id:
        return []

    url = (
        f"{server_url}/player_api.php"
        f"?username={username}&password={password}"
        f"&action=get_live_streams&category_id={category_id}"
    )
    try:
        payload = _provider_get(url, timeout=10)
        channels = [_normalize_channel(item) for item in payload if isinstance(item, dict)]
        return [item for item in channels if item]
    except Exception as exc:
        print(f"[EPG] Failed to fetch channels for category {category_id}: {exc}")
        return []


def _load_xmltv_source():
    source_url = config.XMLTV_SOURCE_URL
    source_path = config.XMLTV_SOURCE_PATH

    if not source_url and not source_path:
        return None, None

    try:
        if source_url:
            response = requests.get(source_url, timeout=20)
            response.raise_for_status()
            raw_bytes = response.content
            source_name = source_url
        else:
            with open(source_path, "rb") as handle:
                raw_bytes = handle.read()
            source_name = source_path

        if source_name.endswith(".gz"):
            raw_bytes = gzip.decompress(raw_bytes)

        return raw_bytes, source_name
    except Exception as exc:
        print(f"[EPG] Failed to load XMLTV source: {exc}")
        return None, None


def _parse_xmltv_source():
    raw_bytes, source_name = _load_xmltv_source()
    if not raw_bytes:
        return {}, source_name

    try:
        root = ET.fromstring(raw_bytes)
    except Exception as exc:
        print(f"[EPG] Failed to parse XMLTV source: {exc}")
        return {}, source_name

    xmltv_map = {}
    for programme in root.findall("programme"):
        channel_key = normalize_guide_key(programme.get("channel"))
        if not channel_key:
            continue

        title = programme.findtext("title", default="") or ""
        desc = programme.findtext("desc", default="") or ""
        start = programme.get("start", "")
        stop = programme.get("stop", "")

        listing = _normalize_xmltv_listing(
            channel_key,
            {
                "title": title,
                "description": desc,
                "start": start[:14] if start else None,
                "stop": stop[:14] if stop else None,
            },
        )
        if listing is None:
            continue

        xmltv_map.setdefault(channel_key, []).append(listing)

    for channel_key, listings in xmltv_map.items():
        xmltv_map[channel_key] = listings[:50]

    print(f"[EPG] Loaded XMLTV guide source '{source_name}' with {len(xmltv_map)} channel keys")
    return xmltv_map, source_name


def _fetch_epg_uncached(server_url, username, password, channel_id, limit=16):
    url = (
        f"{server_url}/player_api.php?username={username}&password={password}"
        f"&action=get_short_epg&stream_id={channel_id}&limit={limit}"
    )
    print(f"[EPG FETCH] Fetching EPG for channel {channel_id} with limit {limit}")
    try:
        payload = _provider_get(url, timeout=8)
        raw_listings = _extract_listing_items(payload)
        listings = [listing for listing in (_normalize_listing(item) for item in raw_listings) if listing]
        print(f"[EPG FETCH] Channel {channel_id}: got {len(listings)} listings from API")
        return listings
    except Exception as exc:
        print(f"[EPG FETCH] Error fetching EPG for channel {channel_id}: {exc}")
        return []


class GuideCache:
    def __init__(self, ttl_seconds=None, max_workers=10):
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else config.GUIDE_CACHE_TTL_SECONDS
        self._max_workers = max_workers
        self._channel_cache = {}
        self._bundle_cache = {}
        self._lock = threading.RLock()

    def _get_cached(self, cache, cache_key):
        with self._lock:
            entry = cache.get(cache_key)
            if not entry:
                return None
            if entry["expires_at"] <= time.time():
                cache.pop(cache_key, None)
                return None
            return entry["value"]

    def _set_cached(self, cache, cache_key, value):
        with self._lock:
            cache[cache_key] = {
                "expires_at": time.time() + self._ttl_seconds,
                "value": value,
            }

    def get_channel_epg(self, server_url, username, password, channel_id, limit=16, refresh=False):
        cache_key = (str(channel_id), int(limit))
        if not refresh:
            cached = self._get_cached(self._channel_cache, cache_key)
            if cached is not None:
                return cached

        listings = _fetch_epg_uncached(server_url, username, password, channel_id, limit=limit)
        self._set_cached(self._channel_cache, cache_key, listings)
        return listings

    def get_multi_epg(self, server_url, username, password, channel_ids, limit=6, refresh=False):
        normalized_ids = [str(cid).strip() for cid in channel_ids if str(cid).strip()]
        if not normalized_ids:
            return []

        results = []

        def _fetch(cid):
            listings = self.get_channel_epg(server_url, username, password, cid, limit=limit, refresh=refresh)
            print(f"[EPG MULTI] Channel {cid}: {len(listings)} listings")
            return {"channel_id": cid, "listings": listings}

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            for item in pool.map(_fetch, normalized_ids[:30]):
                results.append(item)

        print(f"[EPG MULTI] Total listings returned: {sum(len(r['listings']) for r in results)}")
        return results

    def get_guide_bundle(self, server_url, username, password, category_id=None, limit=24, refresh=False):
        resolved_category_id = str(category_id or "").strip() or "__default__"
        cache_key = (resolved_category_id, int(limit))
        if not refresh:
            cached = self._get_cached(self._bundle_cache, cache_key)
            if cached is not None:
                return cached

        categories = _fetch_categories(server_url, username, password)
        active_category_id = str(category_id or "").strip()
        if not active_category_id and categories:
            active_category_id = categories[0]["category_id"]

        channels = _fetch_channels_by_category(server_url, username, password, active_category_id)

        guide_source = "xtream"
        guide_epg = {}
        source_url = config.XMLTV_SOURCE_URL.strip()
        source_path = config.XMLTV_SOURCE_PATH.strip()
        if source_url or source_path:
            xmltv_map, source_name = _parse_xmltv_source()
            if xmltv_map:
                guide_source = "xmltv"
                for channel in channels:
                    channel_id = str(channel.get("id", "")).strip()
                    channel_name = str(channel.get("name", "")).strip()
                    candidates = [
                        normalize_guide_key(channel_id),
                        normalize_guide_key(channel_name),
                        normalize_guide_key(channel.get("guide_key")),
                    ]
                    matched = []
                    for candidate in candidates:
                        if candidate and candidate in xmltv_map:
                            matched = xmltv_map[candidate]
                            break
                    guide_epg[channel_id] = matched[:limit]
                print(f"[EPG BUNDLE] Using XMLTV source {source_name} for {len(channels)} channels")
            else:
                print("[EPG BUNDLE] XMLTV source configured but no guide entries were parsed; falling back to Xtream")

        if guide_source != "xmltv":
            channel_ids = [channel["id"] for channel in channels if channel.get("id")]
            epg_rows = self.get_multi_epg(server_url, username, password, channel_ids, limit=limit, refresh=refresh)
            guide_epg = {row["channel_id"]: row["listings"] for row in epg_rows}

        bundle = {
            "source": guide_source,
            "category_id": active_category_id,
            "categories": categories,
            "channels": channels,
            "guide_epg": guide_epg,
            "generated_at": int(time.time() * 1000),
            "refresh_after_ms": int(self._ttl_seconds * 1000),
        }

        self._set_cached(self._bundle_cache, cache_key, bundle)
        return bundle

    def clear(self):
        with self._lock:
            self._channel_cache.clear()
            self._bundle_cache.clear()


guide_cache = GuideCache()


def fetch_epg(server_url, username, password, channel_id, limit=16, refresh=False):
    return guide_cache.get_channel_epg(server_url, username, password, channel_id, limit=limit, refresh=refresh)


def fetch_multi_epg(server_url, username, password, channel_ids, limit=6, refresh=False):
    return guide_cache.get_multi_epg(server_url, username, password, channel_ids, limit=limit, refresh=refresh)


def build_guide_bundle(server_url, username, password, category_id=None, limit=24, refresh=False):
    return guide_cache.get_guide_bundle(server_url, username, password, category_id=category_id, limit=limit, refresh=refresh)


def fetch_categories(server_url, username, password):
    return _fetch_categories(server_url, username, password)


def fetch_channels_by_category(server_url, username, password, category_id):
    return _fetch_channels_by_category(server_url, username, password, category_id)
