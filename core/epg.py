"""
core/epg.py — EPG / guide data pipeline.

Strategy
--------
1. On first guide request the provider's xmltv.php is downloaded in a
   background thread and saved to disk (XMLTV_CACHE_PATH).
2. The XML is parsed once into an in-memory dict keyed by lower-cased
   XMLTV channel-id.  Subsequent requests are served purely from memory.
3. Channels are matched to XMLTV entries via `epg_channel_id` (the field
   the provider sets).  A normalised-name fallback covers gaps.
4. The XMLTV cache is refreshed once every GUIDE_CACHE_TTL_SECONDS
   (default 12 h).  A background thread handles the refresh so guide
   requests are never blocked by a network download.
"""

import base64
import gzip
import os
import re
import threading
import time
import xml.etree.ElementTree as ET

import requests

import config


# ── helpers ───────────────────────────────────────────────────────────────────

_NORM_RE = re.compile(r"[^a-z0-9]")


def _norm(value: str) -> str:
    """Lower-case, strip non-alphanumeric — used for fuzzy name matching."""
    return _NORM_RE.sub("", str(value).lower())


def _decode(text) -> str:
    """Try base64 decode; fall back to plain string."""
    try:
        return base64.b64decode(text).decode("utf-8").strip()
    except Exception:
        return str(text).strip()


# ── XMLTV in-memory store ─────────────────────────────────────────────────────

class _XmltvStore:
    """
    Thread-safe store that holds the parsed XMLTV programme map.

    _by_id  : {lower(channel_id) -> [listing, ...]}
    _by_name: {norm(display_name) -> lower(channel_id)}  (for fallback)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._by_id: dict = {}
        self._by_name: dict = {}
        self._loaded_at: float = 0.0
        self._loading: bool = False

    # ── public ────────────────────────────────────────────────────────────────

    def get_listings(self, epg_channel_id: str, channel_name: str = "") -> list:
        with self._lock:
            key = epg_channel_id.lower() if epg_channel_id else ""
            listings = self._by_id.get(key)
            if listings is not None:
                return listings
            # fallback: normalised name
            if channel_name:
                fallback_key = self._by_name.get(_norm(channel_name))
                if fallback_key:
                    return self._by_id.get(fallback_key, [])
            return []

    def needs_refresh(self) -> bool:
        with self._lock:
            if self._loading:
                return False
            age = time.time() - self._loaded_at
            return age > config.GUIDE_CACHE_TTL_SECONDS

    def is_empty(self) -> bool:
        with self._lock:
            return not self._by_id

    def load_async(self, server_url: str, username: str, password: str):
        """Kick off a background refresh if one is not already running."""
        with self._lock:
            if self._loading:
                return
            self._loading = True
        t = threading.Thread(
            target=self._load,
            args=(server_url, username, password),
            daemon=True,
        )
        t.start()

    # ── private ───────────────────────────────────────────────────────────────

    def _load(self, server_url: str, username: str, password: str):
        try:
            raw = self._fetch_raw(server_url, username, password)
            if raw:
                by_id, by_name = self._parse(raw)
                with self._lock:
                    self._by_id = by_id
                    self._by_name = by_name
                    self._loaded_at = time.time()
                    self._loading = False
                print(f"[EPG] XMLTV loaded: {len(by_id)} channels, "
                      f"{sum(len(v) for v in by_id.values())} programmes")
            else:
                with self._lock:
                    self._loading = False
        except Exception as exc:
            print(f"[EPG] XMLTV load failed: {exc}")
            with self._lock:
                self._loading = False

    def _fetch_raw(self, server_url: str, username: str, password: str) -> bytes:
        cache_path = config.XMLTV_CACHE_PATH
        url = (
            config.XMLTV_SOURCE_URL.strip()
            or f"{server_url}/xmltv.php?username={username}&password={password}"
        )

        print(f"[EPG] Downloading XMLTV from {url[:60]}…")
        try:
            r = requests.get(url, timeout=60, stream=True)
            r.raise_for_status()
            raw = r.content
        except Exception as exc:
            print(f"[EPG] XMLTV download failed ({exc}); trying disk cache")
            raw = None

        if raw:
            # decompress if needed
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            # persist to disk
            try:
                os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                with open(cache_path, "wb") as fh:
                    fh.write(raw)
            except Exception as exc:
                print(f"[EPG] Could not write XMLTV cache: {exc}")
            return raw

        # fall back to cached file
        if os.path.exists(cache_path):
            print("[EPG] Using cached XMLTV file from disk")
            with open(cache_path, "rb") as fh:
                raw = fh.read()
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            return raw

        return b""

    @staticmethod
    def _parse(raw: bytes) -> tuple:
        try:
            root = ET.fromstring(raw)
        except Exception as exc:
            print(f"[EPG] XMLTV parse error: {exc}")
            return {}, {}

        # Build display-name → id mapping
        by_name: dict = {}
        for ch in root.findall("channel"):
            ch_id = ch.get("id", "").lower()
            display = ch.findtext("display-name") or ""
            if ch_id and display:
                by_name[_norm(display)] = ch_id

        # Build id → programmes mapping
        by_id: dict = {}
        now_ts = time.time()
        cutoff = now_ts - 2 * 3600  # keep anything ending in last 2 h

        for prog in root.findall("programme"):
            ch_id = prog.get("channel", "").lower()
            if not ch_id:
                continue

            start_raw = prog.get("start", "")
            stop_raw  = prog.get("stop", "")

            # Quick time filter — skip very old programmes
            stop_ts = _xmltv_ts(stop_raw)
            if stop_ts and stop_ts < cutoff:
                continue

            title = prog.findtext("title") or ""
            desc  = prog.findtext("desc")  or ""
            listing = {
                "title":       title,
                "description": desc or None,
                "start":       start_raw[:14] if start_raw else None,
                "stop":        stop_raw[:14]  if stop_raw  else None,
            }
            by_id.setdefault(ch_id, []).append(listing)

        # Cap per-channel
        for ch_id in by_id:
            by_id[ch_id] = by_id[ch_id][:48]

        return by_id, by_name


def _xmltv_ts(raw: str) -> float:
    """Parse XMLTV timestamp (20260411043000 -0400) to unix float, or 0."""
    if not raw or len(raw) < 14:
        return 0.0
    try:
        digits = raw[:14]
        import datetime as _dt
        dt = _dt.datetime(
            int(digits[0:4]), int(digits[4:6]),  int(digits[6:8]),
            int(digits[8:10]), int(digits[10:12]), int(digits[12:14]),
            tzinfo=_dt.timezone.utc,
        )
        # handle timezone offset in raw string e.g. " -0400"
        tz_part = raw[14:].strip()
        if tz_part and (tz_part[0] in ("+", "-")):
            sign  = 1 if tz_part[0] == "+" else -1
            h, m  = int(tz_part[1:3]), int(tz_part[3:5]) if len(tz_part) >= 5 else 0
            offset = _dt.timedelta(hours=h, minutes=m) * sign
            dt    = dt - offset
        return dt.timestamp()
    except Exception:
        return 0.0


# ── module-level singleton ────────────────────────────────────────────────────

_store = _XmltvStore()


# ── provider fetch helpers ────────────────────────────────────────────────────

def _fetch_categories(server_url, username, password):
    url = (f"{server_url}/player_api.php"
           f"?username={username}&password={password}&action=get_live_categories")
    try:
        cats = requests.get(url, timeout=8).json()
        return [
            {"category_id": str(c.get("category_id", "")),
             "category_name": c.get("category_name", "")}
            for c in cats if c.get("category_name")
        ]
    except Exception as exc:
        print(f"[EPG] fetch_categories failed: {exc}")
        return []


def _fetch_channels_by_category(server_url, username, password, category_id):
    if not category_id:
        return []
    url = (f"{server_url}/player_api.php"
           f"?username={username}&password={password}"
           f"&action=get_live_streams&category_id={category_id}")
    try:
        streams = requests.get(url, timeout=10).json()
        result = []
        for s in streams:
            if not s.get("stream_id"):
                continue
            result.append({
                "id":             str(s["stream_id"]),
                "name":           s.get("name", ""),
                "epg_channel_id": s.get("epg_channel_id", "") or "",
                "stream_icon":    s.get("stream_icon", "") or "",
            })
        return result
    except Exception as exc:
        print(f"[EPG] fetch_channels failed for cat {category_id}: {exc}")
        return []


def _fetch_all_channels(server_url, username, password):
    """Fetch every live stream once, then group by category on the backend."""
    url = (f"{server_url}/player_api.php"
           f"?username={username}&password={password}&action=get_live_streams")
    try:
        streams = requests.get(url, timeout=15).json()
        result = []
        for s in streams:
            if not s.get("stream_id"):
                continue
            result.append({
                "id":             str(s["stream_id"]),
                "name":           s.get("name", ""),
                "category_id":    str(s.get("category_id", "") or ""),
                "category_name":  s.get("category_name", "") or "",
                "epg_channel_id": s.get("epg_channel_id", "") or "",
                "stream_icon":    s.get("stream_icon", "") or "",
            })
        return result
    except Exception as exc:
        print(f"[EPG] fetch_all_channels failed: {exc}")
        return []


# ── guide bundle builder ──────────────────────────────────────────────────────

class _BundleCache:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: dict = {}

    def get(self, key):
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None
            if entry["expires_at"] <= time.time():
                self._cache.pop(key, None)
                return None
            return entry["value"]

    def set(self, key, value, ttl):
        with self._lock:
            self._cache[key] = {"expires_at": time.time() + ttl, "value": value}

    def clear(self):
        with self._lock:
            self._cache.clear()


_bundle_cache = _BundleCache()


def _ensure_xmltv(server_url, username, password):
    """Trigger background load if store is empty or stale."""
    if _store.is_empty() or _store.needs_refresh():
        _store.load_async(server_url, username, password)


def build_guide_bundle(server_url, username, password,
                       category_id=None, limit=24, refresh=False):
    # Ensure XMLTV is loading / fresh (non-blocking)
    _ensure_xmltv(server_url, username, password)

    resolved_cat = str(category_id or "").strip()
    cache_key = (resolved_cat or "__default__", int(limit))

    if not refresh:
        cached = _bundle_cache.get(cache_key)
        if cached is not None:
            return cached

    categories = _fetch_categories(server_url, username, password)
    active_cat = resolved_cat or (categories[0]["category_id"] if categories else "")

    store_empty = _store.is_empty()
    full_bundle = not resolved_cat

    if full_bundle:
        all_channels = _fetch_all_channels(server_url, username, password)
        channels_by_category = {}
        for ch in all_channels:
            category_key = str(ch.get("category_id", "") or "").strip()
            channels_by_category.setdefault(category_key, []).append(ch)

        channels = channels_by_category.get(active_cat, [])
    else:
        channels = _fetch_channels_by_category(server_url, username, password, active_cat)
        channels_by_category = {active_cat: channels}

    guide_epg = {}
    for ch in (all_channels if full_bundle else channels):
        cid  = ch["id"]
        eid  = ch.get("epg_channel_id", "")
        name = ch.get("name", "")
        if store_empty:
            guide_epg[cid] = []
        else:
            listings = _store.get_listings(eid, name)
            guide_epg[cid] = listings[:limit]

    if full_bundle:
        # Ensure channels from inactive categories still get guide rows in the payload.
        # Android uses this to switch categories instantly without reloading.
        for cat_id, cat_channels in channels_by_category.items():
            for ch in cat_channels:
                cid = ch["id"]
                if cid not in guide_epg:
                    eid = ch.get("epg_channel_id", "")
                    name = ch.get("name", "")
                    guide_epg[cid] = [] if store_empty else _store.get_listings(eid, name)[:limit]

    matched = sum(1 for v in guide_epg.values() if v)
    print(f"[EPG] Bundle cat={active_cat}: {len(channels)} channels, "
          f"{matched} with EPG, store_empty={store_empty}")

    bundle = {
        "source":           "xmltv" if not store_empty else "loading",
        "category_id":      active_cat,
        "categories":       categories,
        "channels":         channels,
        "channels_by_category": channels_by_category if full_bundle else {active_cat: channels},
        "guide_epg":        guide_epg,
        "generated_at":     int(time.time() * 1000),
        "refresh_after_ms": int(config.GUIDE_CACHE_TTL_SECONDS * 1000),
        "full_bundle":      full_bundle,
    }

    # Only cache if we actually have EPG data
    if not store_empty:
        _bundle_cache.set(cache_key, bundle, config.GUIDE_CACHE_TTL_SECONDS)

    return bundle


# ── legacy single-channel EPG (still used by PC UI) ──────────────────────────

def fetch_epg(server_url, username, password, channel_id, limit=16, refresh=False):
    """Return listings for a single channel_id from XMLTV store or Xtream fallback."""
    _ensure_xmltv(server_url, username, password)

    if not _store.is_empty():
        # We need the epg_channel_id for this stream_id — do a quick lookup
        # by fetching channel info; for speed, try store by raw channel_id first
        listings = _store.get_listings(channel_id)
        if listings:
            return listings[:limit]
        # No match — fall through to Xtream
    return _fetch_xtream_epg(server_url, username, password, channel_id, limit)


def _fetch_xtream_epg(server_url, username, password, channel_id, limit=16):
    url = (f"{server_url}/player_api.php?username={username}&password={password}"
           f"&action=get_short_epg&stream_id={channel_id}&limit={limit}")
    try:
        data = requests.get(url, timeout=8).json()
        raw  = data.get("epg_listings", [])
        return [
            {
                "title":       _decode(e.get("title", "")),
                "description": _decode(e.get("description", "")) or None,
                "start":       e.get("start") or e.get("start_timestamp"),
                "stop":        e.get("stop")  or e.get("stop_timestamp"),
            }
            for e in raw
        ]
    except Exception as exc:
        print(f"[EPG] Xtream EPG fetch failed for {channel_id}: {exc}")
        return []


def fetch_multi_epg(server_url, username, password, channel_ids, limit=6, refresh=False):
    """Legacy multi-channel EPG — used by /api/epg/multi."""
    _ensure_xmltv(server_url, username, password)
    results = []
    for cid in channel_ids[:30]:
        listings = fetch_epg(server_url, username, password, cid, limit=limit)
        results.append({"channel_id": cid, "listings": listings})
    return results


def fetch_categories(server_url, username, password):
    return _fetch_categories(server_url, username, password)


def fetch_channels_by_category(server_url, username, password, category_id):
    return _fetch_channels_by_category(server_url, username, password, category_id)
