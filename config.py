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

WEB_PORT = 8080

# Mutable credential globals — populated by core.credentials.load_credentials()
SERVER_URL            = ""
USERNAME              = ""
PASSWORD              = ""
INSTATUNNEL_API_KEY   = ""
INSTATUNNEL_SUBDOMAIN = ""
