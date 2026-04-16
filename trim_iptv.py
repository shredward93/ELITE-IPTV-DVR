#!/usr/bin/env python3
"""Trim an IPTV M3U + XMLTV pair down to a curated keep list.

This script is designed for the ELITE IPTV DVR workflow:
- Keep a small set of category groups.
- Keep a few standalone must-have channels.
- Write a smaller M3U and a matching XMLTV file.

Usage examples:
    python trim_iptv.py
    python trim_iptv.py --m3u Playlist.m3u --xmltv xmltv_cache.xml
    python trim_iptv.py --m3u-url http://YOUR-PROVIDER/get.php?... --xmltv-url http://YOUR-PROVIDER/xmltv.php?... \
        --out-m3u trimmed.m3u --out-xmltv trimmed.xml

Notes:
- If your source M3U does not include group-title values, category filtering cannot be applied.
  In that case the script still keeps the standalone must-have channels.
- For best results, use the provider's full m3u_plus playlist, not the Kodi proxy playlist.
"""

from __future__ import annotations

import argparse
import html
import gzip
import re
import sys
import urllib.parse
from copy import deepcopy
from pathlib import Path
from typing import Iterable

import requests
import xml.etree.ElementTree as ET

import config
from core.credentials import load_credentials


KEEP_CATEGORIES = [
    "USA | NHL TEAMS",
    "USA | NHL BACKUP",
    "USA | NHL",
    "USA | NFL TEAMS",
    "USA | NFL TEAMS BACKUP",
    "USA | NFL BACKUP",
]

KEEP_CHANNELS = [
    "NY | BUFFALO | CBS 4 WIVB",
    "US : ABC",
    "US : TNT",
    "US : NBC",
    "NHL Network HD",
    "CA: TSN 4K WEST",
    "CA: SPORTSNET 4K",
    "CA: SPORTSNET ONE 4K",
]

DEFAULT_M3U = Path("Playlist.m3u")
DEFAULT_XMLTV = Path("xmltv_cache.xml")
DEFAULT_OUT_M3U = Path("Playlist.trimmed.m3u")
DEFAULT_OUT_XMLTV = Path("xmltv_cache.trimmed.xml")

ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')


def normalize_text(value: object) -> str:
    """Lowercase and strip non-alphanumeric characters for fuzzy comparisons."""
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


# Recompute the derived sets after normalize_text exists.
KEEP_CATEGORY_KEYS = {normalize_text(v) for v in KEEP_CATEGORIES}
KEEP_CHANNEL_KEYS = {normalize_text(v) for v in KEEP_CHANNELS}


def local_name(tag: str) -> str:
    if not tag:
        return ""
    return tag.rsplit("}", 1)[-1]


def is_remote_source(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"}


def load_text_source(source: str) -> str:
    """Load text from a local file path or a remote URL."""
    if not source:
        return ""

    if is_remote_source(source):
        response = requests.get(source, timeout=60)
        response.raise_for_status()
        raw = response.content
    else:
        raw = Path(source).expanduser().read_bytes()

    if raw.startswith(b"\x1f\x8b"):
        raw = gzip.decompress(raw)

    return raw.decode("utf-8", errors="replace")


def fetch_provider_categories(server_url: str, username: str, password: str) -> list[dict]:
    url = (
        f"{server_url.rstrip('/')}" 
        f"/player_api.php?username={username}&password={password}&action=get_live_categories"
    )
    response = requests.get(url, timeout=12)
    response.raise_for_status()
    result = []
    for cat in response.json() or []:
        cat_id = str(cat.get("category_id", "") or "").strip()
        cat_name = str(cat.get("category_name", "") or "").strip()
        if cat_id and cat_name:
            result.append({"category_id": cat_id, "category_name": cat_name})
    return result


def fetch_provider_streams(server_url: str, username: str, password: str) -> list[dict]:
    url = (
        f"{server_url.rstrip('/')}"
        f"/player_api.php?username={username}&password={password}&action=get_live_streams"
    )
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    result = []
    for s in response.json() or []:
        stream_id = str(s.get("stream_id", "") or "").strip()
        if not stream_id:
            continue
        result.append({
            "id": stream_id,
            "name": str(s.get("name", "") or "").strip(),
            "category_id": str(s.get("category_id", "") or "").strip(),
            "category_name": str(s.get("category_name", "") or "").strip(),
            "epg_channel_id": str(s.get("epg_channel_id", "") or "").strip(),
            "stream_icon": str(s.get("stream_icon", "") or "").strip(),
        })
    return result


def source_has_useful_group_titles(m3u_text: str) -> bool:
    for entry in iter_m3u_entries(m3u_text):
        group_title = normalize_text(entry.get("attrs", {}).get("group-title", ""))
        if group_title and group_title not in {"livetv"}:
            return True
    return False


def build_provider_entry(server_url: str, username: str, password: str, stream: dict) -> dict:
    tvg_id = stream.get("epg_channel_id") or stream.get("id")
    name = stream.get("name", "")
    category_name = stream.get("category_name", "") or "Live TV"
    icon = stream.get("stream_icon", "")
    extinf = (
        f'#EXTINF:-1 tvg-id="{html.escape(str(tvg_id), quote=True)}" '
        f'tvg-name="{html.escape(name, quote=True)}" '
        f'group-title="{html.escape(category_name, quote=True)}"'
    )
    if icon:
        extinf += f' tvg-logo="{html.escape(icon, quote=True)}"'
    extinf += f',{name}'
    url = f"{server_url.rstrip('/')}/live/{username}/{password}/{stream['id']}.ts"
    return {
        "extinf": extinf,
        "url": url,
        "attrs": {
            "tvg-id": str(tvg_id),
            "tvg-name": name,
            "group-title": category_name,
            "tvg-logo": icon,
        },
        "name": name,
        "stream": stream,
    }


def entry_signature(entry: dict) -> tuple[str, str, str]:
    attrs = entry.get("attrs", {})
    tvg_id = normalize_text(attrs.get("tvg-id", ""))
    url = normalize_text(entry.get("url", ""))
    name = normalize_text(attrs.get("tvg-name", "") or entry.get("name", ""))
    return tvg_id, url, name


def trim_provider_streams(server_url: str, username: str, password: str):
    categories = fetch_provider_categories(server_url, username, password)
    category_ids = [c["category_id"] for c in categories if name_matches_keep(c["category_name"], KEEP_CATEGORY_KEYS)]
    category_name_by_id = {c["category_id"]: c["category_name"] for c in categories}
    streams = fetch_provider_streams(server_url, username, password)

    kept_entries = []
    seen_categories = []
    seen_signatures: set[tuple[str, str, str]] = set()
    selected_count = 0
    duplicate_count = 0

    for stream in streams:
        category_id = stream.get("category_id", "")
        category_name = stream.get("category_name", "") or category_name_by_id.get(category_id, "")
        name = stream.get("name", "")
        tvg_id = stream.get("epg_channel_id", "") or stream.get("id", "")
        keep = category_id in category_ids or any(
            name_matches_keep(label, KEEP_CHANNEL_KEYS)
            for label in (name, tvg_id, stream.get("epg_channel_id", ""))
        )
        if not keep:
            continue

        selected_count += 1
        entry = build_provider_entry(server_url, username, password, stream)
        signature = entry_signature(entry)
        if signature in seen_signatures:
            duplicate_count += 1
            continue
        seen_signatures.add(signature)
        kept_entries.append(entry)
        if category_name and category_name not in seen_categories:
            seen_categories.append(category_name)

    return {
        "total_entries": len(streams),
        "total_urls": len(streams),
        "kept_entries": kept_entries,
        "seen_categories": seen_categories,
        "provider_mode": True,
        "selected_count": selected_count,
        "duplicate_count": duplicate_count,
        "matched_category_count": len(category_ids),
    }


def iter_m3u_entries(text: str):
    """Yield playlist entries as dictionaries with extinf/url/metadata."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("#EXTINF"):
            attrs = {m.group(1).lower(): m.group(2) for m in ATTR_RE.finditer(line)}
            channel_name = line.split(",", 1)[1].strip() if "," in line else attrs.get("tvg-name", "")
            url = ""
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if not candidate:
                    j += 1
                    continue
                if candidate.startswith("#"):
                    j += 1
                    continue
                url = candidate
                break
            yield {
                "extinf": line,
                "url": url,
                "attrs": attrs,
                "name": channel_name,
            }
            i = j + 1 if url else i + 1
            continue
        i += 1


def name_matches_keep(name: str, keep_keys: set[str]) -> bool:
    normalized = normalize_text(name)
    if not normalized:
        return False
    if normalized in keep_keys:
        return True
    # Allow a limited fuzzy match for longer labels like "NHL Network HD - East".
    for key in keep_keys:
        if len(key) < 5 or len(normalized) < 5:
            continue
        if key in normalized or normalized in key:
            return True
    return False


def entry_should_keep(entry: dict) -> tuple[bool, str]:
    attrs = entry.get("attrs", {})
    name = entry.get("name", "")
    group_title = attrs.get("group-title", "")
    tvg_name = attrs.get("tvg-name", "")
    tvg_id = attrs.get("tvg-id", "")

    if name_matches_keep(group_title, KEEP_CATEGORY_KEYS):
        return True, f"category:{group_title}"

    for label in (name, tvg_name, tvg_id):
        if name_matches_keep(label, KEEP_CHANNEL_KEYS):
            return True, f"channel:{label}"

    return False, ""


def trim_m3u(source_text: str):
    entries = []
    kept = []
    seen_categories = []
    seen_urls = 0
    seen_signatures: set[tuple[str, str, str]] = set()
    duplicate_count = 0

    for entry in iter_m3u_entries(source_text):
        entries.append(entry)
        if entry.get("url"):
            seen_urls += 1
        keep, reason = entry_should_keep(entry)
        if keep:
            entry["keep_reason"] = reason
            signature = entry_signature(entry)
            if signature in seen_signatures:
                duplicate_count += 1
                continue
            seen_signatures.add(signature)
            kept.append(entry)
            group_title = entry.get("attrs", {}).get("group-title", "")
            if group_title and group_title not in seen_categories:
                seen_categories.append(group_title)

    return {
        "total_entries": len(entries),
        "total_urls": seen_urls,
        "kept_entries": kept,
        "seen_categories": seen_categories,
        "duplicate_count": duplicate_count,
    }


def extract_keep_keys_from_entries(entries: Iterable[dict]) -> tuple[set[str], set[str]]:
    """Return kept XMLTV channel IDs and fallback name keys."""
    kept_ids: set[str] = set()
    kept_name_keys: set[str] = set()

    for entry in entries:
        attrs = entry.get("attrs", {})
        tvg_id = str(attrs.get("tvg-id", "")).strip()
        tvg_name = str(attrs.get("tvg-name", "")).strip()
        name = str(entry.get("name", "")).strip()
        group_title = str(attrs.get("group-title", "")).strip()

        if tvg_id:
            kept_ids.add(tvg_id.lower())
        if tvg_name:
            kept_name_keys.add(normalize_text(tvg_name))
        if name:
            kept_name_keys.add(normalize_text(name))
        if group_title:
            kept_name_keys.add(normalize_text(group_title))

    return kept_ids, kept_name_keys


def trim_xmltv(source_text: str, keep_ids: set[str], keep_name_keys: set[str]):
    tree = ET.ElementTree(ET.fromstring(source_text))
    root = tree.getroot()

    all_channels = 0
    all_programmes = 0
    kept_channels = 0
    kept_programmes = 0

    channel_id_to_name_key: dict[str, str] = {}
    keep_channel_ids: set[str] = set()

    # First pass: identify which channels to keep.
    for child in root:
        if local_name(child.tag) != "channel":
            continue
        all_channels += 1
        channel_id = (child.attrib.get("id", "") or "").strip().lower()
        display_name = ""
        for disp in child.findall(".//display-name"):
            if disp.text and disp.text.strip():
                display_name = disp.text.strip()
                break
        display_key = normalize_text(display_name)
        channel_id_to_name_key[channel_id] = display_key

        if channel_id and channel_id in keep_ids:
            keep_channel_ids.add(channel_id)
            kept_channels += 1
        elif display_key and display_key in keep_name_keys:
            keep_channel_ids.add(channel_id)
            kept_channels += 1

    # Second pass: keep programmes that match retained channels.
    new_root = ET.Element(root.tag, root.attrib)
    for child in root:
        tag = local_name(child.tag)
        if tag == "channel":
            channel_id = (child.attrib.get("id", "") or "").strip().lower()
            display_name = ""
            for disp in child.findall(".//display-name"):
                if disp.text and disp.text.strip():
                    display_name = disp.text.strip()
                    break
            display_key = normalize_text(display_name)
            if channel_id in keep_channel_ids or display_key in keep_name_keys:
                new_root.append(deepcopy(child))
        elif tag == "programme":
            all_programmes += 1
            programme_channel = (child.attrib.get("channel", "") or "").strip().lower()
            if programme_channel in keep_channel_ids:
                kept_programmes += 1
                new_root.append(deepcopy(child))
        else:
            # Preserve any other metadata nodes if present.
            new_root.append(deepcopy(child))

    return {
        "xml_tree": ET.ElementTree(new_root),
        "all_channels": all_channels,
        "all_programmes": all_programmes,
        "kept_channels": kept_channels,
        "kept_programmes": kept_programmes,
    }


def write_m3u(entries: Iterable[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("#EXTM3U\n")
        for entry in entries:
            extinf = entry.get("extinf", "").rstrip()
            url = entry.get("url", "").strip()
            if not extinf or not url:
                continue
            fh.write(extinf + "\n")
            fh.write(url + "\n")


def write_xmltv(tree: ET.ElementTree, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Trim IPTV M3U and XMLTV files to a curated keep list."
    )
    parser.add_argument("--m3u", default=str(DEFAULT_M3U), help="Input M3U file path")
    parser.add_argument("--xmltv", default=str(DEFAULT_XMLTV), help="Input XMLTV file path")
    parser.add_argument("--m3u-url", default="", help="Optional remote M3U URL override")
    parser.add_argument("--xmltv-url", default="", help="Optional remote XMLTV URL override")
    parser.add_argument("--server-url", default="", help="Xtream server URL for provider-category lookup")
    parser.add_argument("--username", default="", help="Xtream username for provider-category lookup")
    parser.add_argument("--password", default="", help="Xtream password for provider-category lookup")
    parser.add_argument("--out-m3u", default=str(DEFAULT_OUT_M3U), help="Output trimmed M3U path")
    parser.add_argument("--out-xmltv", default=str(DEFAULT_OUT_XMLTV), help="Output trimmed XMLTV path")
    parser.add_argument(
        "--m3u-only",
        action="store_true",
        help="Only write the trimmed M3U and skip XMLTV output",
    )
    parser.add_argument(
        "--xmltv-only",
        action="store_true",
        help="Only write the trimmed XMLTV and skip M3U output",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    load_credentials()

    if args.m3u_only and args.xmltv_only:
        print("Choose only one of --m3u-only or --xmltv-only.", file=sys.stderr)
        return 2

    m3u_source = args.m3u_url or args.m3u
    xmltv_source = args.xmltv_url or args.xmltv
    server_url = (args.server_url or config.SERVER_URL).strip()
    username = (args.username or config.USERNAME).strip()
    password = (args.password or config.PASSWORD).strip()

    print(f"[trim] Loading M3U from: {m3u_source}")
    m3u_text = load_text_source(m3u_source)

    use_provider_mode = not source_has_useful_group_titles(m3u_text)
    if use_provider_mode and server_url and username and password:
        print("[trim] Source M3U has no useful category groups; using provider category lookup instead.")
        m3u_result = trim_provider_streams(server_url, username, password)
    else:
        m3u_result = trim_m3u(m3u_text)

    kept_entries = m3u_result["kept_entries"]
    keep_ids, keep_name_keys = extract_keep_keys_from_entries(kept_entries)

    out_m3u = Path(args.out_m3u)
    out_xmltv = Path(args.out_xmltv)

    if not args.xmltv_only:
        write_m3u(kept_entries, out_m3u)
        print(f"[trim] Wrote trimmed M3U: {out_m3u.resolve()}")

    xmltv_result = None
    if not args.m3u_only:
        print(f"[trim] Loading XMLTV from: {xmltv_source}")
        xmltv_text = load_text_source(xmltv_source)
        xmltv_result = trim_xmltv(xmltv_text, keep_ids, keep_name_keys)
        write_xmltv(xmltv_result["xml_tree"], out_xmltv)
        print(f"[trim] Wrote trimmed XMLTV: {out_xmltv.resolve()}")

    print()
    print("[trim] Summary")
    print(f"  Keep categories: {len(KEEP_CATEGORIES)}")
    print(f"  Keep channels:   {len(KEEP_CHANNELS)}")
    print(f"  M3U entries in:   {m3u_result['total_entries']}")
    print(f"  M3U entries out:  {len(kept_entries)}")
    print(f"  Duplicate entries skipped: {m3u_result.get('duplicate_count', 0)}")
    print(f"  Unique categories seen in source: {len(m3u_result['seen_categories'])}")

    if m3u_result["seen_categories"]:
        print("  Matched categories:")
        for cat in m3u_result["seen_categories"]:
            print(f"    - {cat}")
    else:
        print("  Matched categories: none found in the source M3U.")
        print("  (That usually means the source M3U does not carry group-title data.)")

    if m3u_result.get("provider_mode"):
        print(f"  Provider categories matched: {m3u_result.get('matched_category_count', 0)}")
        print(f"  Provider streams selected:    {m3u_result.get('selected_count', 0)}")

    if xmltv_result is not None:
        print(f"  XMLTV channels in: {xmltv_result['all_channels']}")
        print(f"  XMLTV channels out:{xmltv_result['kept_channels']}")
        print(f"  XMLTV programmes in: {xmltv_result['all_programmes']}")
        print(f"  XMLTV programmes out:{xmltv_result['kept_programmes']}")

    if not kept_entries:
        print()
        print("[trim] WARNING: nothing matched your keep list.")
        print("[trim] If you used the Kodi proxy playlist, category filtering will not work well there.")
        print("[trim] Use your provider's full m3u_plus playlist for best results.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
