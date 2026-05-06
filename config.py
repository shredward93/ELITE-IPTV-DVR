import os
import sys
import subprocess

APP_VERSION = "1.0.0"

# Suppress console windows on Windows for all subprocesses
_SUBPROCESS_FLAGS = {}
if sys.platform == "win32":
    _SUBPROCESS_FLAGS["creationflags"] = subprocess.CREATE_NO_WINDOW

# PyInstaller path resolution:
#   _APP_DIR    = next to the .exe (user-writable: favorites, credentials)
#   _BUNDLE_DIR = _MEIPASS when frozen (read-only bundled assets: theme)
if getattr(sys, "frozen", False):
    _APP_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
else:
    _APP_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = _APP_DIR

FAVORITES_FILE   = os.path.join(_APP_DIR, "favorites.json")
CREDENTIALS_FILE = os.path.join(_APP_DIR, "credentials.json")
SETTINGS_FILE    = os.path.join(_APP_DIR, "settings.json")
SCHEDULES_FILE   = os.path.join(_APP_DIR, "scheduled_recordings.json")

WEB_PORT = 8080

# Guide / EPG refresh cadence. Default to twice per day so the backend can
# keep guide data fresh without reloading it on every screen visit.
GUIDE_CACHE_TTL_SECONDS = int(os.getenv("GUIDE_CACHE_TTL_SECONDS", str(12 * 60 * 60)))

# Optional XMLTV hooks for future backend guide sources.
XMLTV_SOURCE_URL  = os.getenv("XMLTV_SOURCE_URL", "").strip()
XMLTV_SOURCE_PATH = os.getenv("XMLTV_SOURCE_PATH", "").strip()
XMLTV_CACHE_PATH  = os.path.join(_APP_DIR, "xmltv_cache.xml")

# Optional trimmed IPTV inputs. When present, the desktop app can prefer these
# files instead of reusing the full provider playlist / guide.
TRIMMED_M3U_PATH   = os.getenv("TRIMMED_M3U_PATH", os.path.join(_APP_DIR, "Playlist.trimmed.m3u")).strip()
TRIMMED_XMLTV_PATH = os.getenv("TRIMMED_XMLTV_PATH", os.path.join(_APP_DIR, "xmltv_cache.trimmed.xml")).strip()

# DVR settings — overridden by core.dvr_settings.load_dvr_settings()
DVR_BUFFER_DIR = os.path.join(_APP_DIR, "dvr_buffer")
DVR_MAX_HOURS  = 6
DVR_MAX_GB     = 50
RECORDING_FAILOVER_SECS = int(os.getenv("RECORDING_FAILOVER_SECS", "30"))

# Mutable credential globals — populated by core.credentials.load_credentials()
SERVER_URL            = ""
USERNAME              = ""
PASSWORD              = ""

# Tunnel provider: "instatunnel" | "cloudflare"
TUNNEL_PROVIDER       = ""

# InstaTunnel settings
INSTATUNNEL_API_KEY   = ""
INSTATUNNEL_SUBDOMAIN = ""

# Cloudflare Tunnel settings
CLOUDFLARE_TUNNEL_TOKEN = ""   # Optional: for named tunnel auth
CLOUDFLARE_DOMAIN       = ""   # e.g. iptv.yourdomain.com
