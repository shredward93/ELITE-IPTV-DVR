import customtkinter as ctk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import subprocess
import threading
import datetime
import time
import requests
import os
import sys
import re
import json
import queue
import shutil
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from core.epg import fetch_epg

APP_VERSION = "1.0.0"

# On Windows, prevent FFmpeg / npx from flashing a console window.
_SUBPROCESS_FLAGS = {}
if sys.platform == "win32":
    _SUBPROCESS_FLAGS["creationflags"] = subprocess.CREATE_NO_WINDOW


def _build_instatunnel_env():
    # GUI apps on macOS don't inherit the shell PATH, so Homebrew/npm binaries
    # aren't found. Prepend common install locations.
    env = os.environ.copy()
    extra = [
        "/opt/homebrew/bin",
        "/usr/local/bin",
        os.path.expanduser("~/.local/bin"),
        os.path.expanduser("~/bin"),
    ]
    env["PATH"] = ":".join(extra) + ":" + env.get("PATH", "")
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    return env, npx


def _resolve_instatunnel_cli(npx):
    cli = "instatunnel.cmd" if sys.platform == "win32" else "instatunnel"
    if shutil.which(cli):
        return [cli]
    return [npx, "--yes", "instatunnel@latest"]

# --- XSTREAM CREDENTIALS ---
# Leave these blank — configure via the ⚙ Settings dialog (saved to credentials.json)
SERVER_URL = ""
USERNAME   = ""
PASSWORD   = ""
# ---------------------------

# --- INSTATUNNEL ---
INSTATUNNEL_API_KEY   = ""   # configured in ⚙ Settings
INSTATUNNEL_SUBDOMAIN = ""   # configured in ⚙ Settings
# -------------------

WEB_PORT = 8080

# When packaged with PyInstaller (--onefile/--onedir), __file__ points to a temp
# extraction dir that changes every run.  Use the directory of the real executable
# instead so favorites.json persists next to the .exe.
if getattr(sys, "frozen", False):
    _APP_DIR    = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS          # bundled assets (theme, etc.) live here
else:
    _APP_DIR    = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = _APP_DIR

FAVORITES_FILE    = os.path.join(_APP_DIR, "favorites.json")
CREDENTIALS_FILE  = os.path.join(_APP_DIR, "credentials.json")
SETTINGS_FILE     = os.path.join(_APP_DIR, "settings.json")


def _load_saved_credentials():
    """Override hardcoded credentials with anything saved by the user."""
    global SERVER_URL, USERNAME, PASSWORD, INSTATUNNEL_API_KEY, INSTATUNNEL_SUBDOMAIN
    try:
        with open(CREDENTIALS_FILE) as f:
            data = json.load(f)
        SERVER_URL            = data.get("server_url",       SERVER_URL)            or SERVER_URL
        USERNAME              = data.get("username",         USERNAME)              or USERNAME
        PASSWORD              = data.get("password",         PASSWORD)              or PASSWORD
        INSTATUNNEL_API_KEY   = data.get("tunnel_api_key",   INSTATUNNEL_API_KEY)   or INSTATUNNEL_API_KEY
        INSTATUNNEL_SUBDOMAIN = data.get("tunnel_subdomain", INSTATUNNEL_SUBDOMAIN) or INSTATUNNEL_SUBDOMAIN
    except Exception:
        pass  # file doesn't exist yet — use the hardcoded defaults


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme(os.path.join(_BUNDLE_DIR, "ember.json"))


# ── Startup dependency check ──────────────────────────────────────────────────

def _check_ffmpeg():
    """
    Verify FFmpeg is available before the main window opens.
    On Windows, offer to auto-install via winget if it's missing.
    Returns True if the app should proceed, False if it should exit.
    """
    if shutil.which("ffmpeg"):
        return True  # already on PATH — nothing to do

    if sys.platform != "win32":
        # macOS / Linux: just warn; user installs via brew/apt
        mb.showwarning(
            "FFmpeg Not Found",
            "FFmpeg was not found on your system.\n\n"
            "Install it with:\n"
            "  Mac:   brew install ffmpeg\n"
            "  Linux: sudo apt install ffmpeg\n\n"
            "The app will open, but recording and preview won't work until FFmpeg is installed."
        )
        return True  # open the app anyway so they can browse channels / EPG

    # ── Windows: offer winget auto-install ───────────────────────────────────
    install = mb.askyesno(
        "FFmpeg Not Found",
        "FFmpeg is required for recording and previewing streams, "
        "but it wasn't found on this PC.\n\n"
        "Install it automatically now?\n"
        "(Uses winget — built into Windows 10/11. Requires internet.)\n\n"
        "The app will close after installing. Reopen it to start recording."
    )

    if not install:
        # Let them open the app anyway — they might install FFmpeg themselves
        return True

    try:
        result = subprocess.run(
            [
                "winget", "install", "Gyan.FFmpeg",
                "--silent",
                "--accept-package-agreements",
                "--accept-source-agreements",
            ],
            timeout=300,          # 5 min max
        )
        if result.returncode == 0:
            mb.showinfo(
                "FFmpeg Installed",
                "FFmpeg was installed successfully.\n\n"
                "Reopen the app to start recording."
            )
        else:
            mb.showerror(
                "Install Failed",
                "winget couldn't install FFmpeg automatically.\n\n"
                "Please install it manually:\n"
                "  1. Open Microsoft Store and install 'App Installer' (for winget)\n"
                "  2. Or download from: https://ffmpeg.org/download.html"
            )
    except FileNotFoundError:
        mb.showerror(
            "winget Not Found",
            "winget is not available on this PC.\n\n"
            "Please install FFmpeg manually from:\n"
            "https://ffmpeg.org/download.html\n\n"
            "Then reopen the app."
        )
    except subprocess.TimeoutExpired:
        mb.showerror(
            "Timeout",
            "The installation timed out. Please check your internet connection and try again,\n"
            "or install FFmpeg manually from https://ffmpeg.org/download.html"
        )

    return False  # exit after install attempt so PATH updates take effect


# ── Embedded mobile web UI ────────────────────────────────────────────────────

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>IPTV Remote</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#111827;color:#e5e7eb;font-family:system-ui,sans-serif;padding:16px;max-width:480px;margin:auto}
h1{font-size:20px;font-weight:700;margin-bottom:2px}
.sub{font-size:12px;color:#6b7280;margin-bottom:16px}
.section{background:#1f2937;border-radius:12px;padding:14px;margin-bottom:14px}
.sec-title{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;margin-bottom:10px;font-weight:600;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.card{background:#111827;border-radius:8px;padding:12px;margin-bottom:8px}
.card-name{font-weight:600;font-size:15px;margin-bottom:4px}
.card-status{font-size:12px;color:#9ca3af;margin-bottom:8px}
.rec-status{color:#ef4444}
.btn{display:inline-flex;align-items:center;justify-content:center;padding:8px 14px;border-radius:8px;border:none;font-size:13px;font-weight:500;cursor:pointer;transition:opacity .15s;white-space:nowrap}
.btn:active{opacity:.7}
.btn-sm{padding:5px 10px;font-size:12px}
.btn-red{background:#dc2626;color:#fff}
.btn-blue{background:#2563eb;color:#fff}
.btn-green{background:#16a34a;color:#fff}
.btn-gray{background:#374151;color:#e5e7eb}
.fav-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid #374151}
.fav-row:last-child{border-bottom:none}
.fav-name{flex:1;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
input{width:100%;background:#111827;color:#e5e7eb;border:1px solid #374151;border-radius:8px;padding:10px 12px;font-size:14px;margin-bottom:8px;outline:none}
input:focus{border-color:#2563eb}
.empty{color:#6b7280;font-size:13px;text-align:center;padding:12px 0}
.badge{display:inline-block;background:#dc2626;color:#fff;font-size:10px;font-weight:700;padding:2px 5px;border-radius:4px;margin-right:4px}
.overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:10;padding:20px;overflow-y:auto}
.modal{background:#1f2937;border-radius:16px;padding:20px;max-width:440px;margin:60px auto}
.modal h2{font-size:16px;margin-bottom:14px}
.modal-btns{display:flex;gap:8px;margin-top:4px}
.result-item{padding:10px 6px;border-bottom:1px solid #374151;cursor:pointer;font-size:14px}
.result-item:active{background:#374151;border-radius:6px}
.result-item:last-child{border-bottom:none}
.sel-card{background:#111827;border-radius:8px;padding:12px;margin-top:8px}
.sel-name{font-weight:600;font-size:15px;margin-bottom:8px}
.sel-btns{display:flex;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.epg-row{padding:7px 0;border-bottom:1px solid #374151}
.epg-row:last-child{border-bottom:none}
.epg-now{background:#1e293b;border-radius:6px;padding:8px;margin:2px 0}
.epg-hdr{display:flex;align-items:center;gap:6px;margin-bottom:3px}
.epg-time{font-size:11px;color:#9ca3af;flex:1}
.epg-title{font-size:13px;font-weight:500}
.epg-desc{font-size:11px;color:#6b7280;margin-top:2px}
.log-line{font-size:11px;color:#9ca3af;padding:2px 0;font-family:monospace;word-break:break-all}
</style>
</head>
<body>
<h1>IPTV Recorder</h1>
<div class="sub" id="srv-status">Connecting…</div>

<div class="section">
  <div class="sec-title" style="cursor:default">Find Channel</div>
  <div id="backup-status" style="font-size:12px; color:#3b82f6; margin-bottom:8px; display:none;">
    Backup: <span id="backup-name-disp" style="font-weight:600"></span>
    <span onclick="clearBackup()" style="cursor:pointer; text-decoration:underline; margin-left:8px; color:#9ca3af;">Clear</span>
  </div>
  <input type="search" id="search-input" placeholder="Search 300k+ channels…" oninput="onSearch()" autocomplete="off">
  <div id="search-results"></div>
  <div id="sel-card" style="display:none">
    <div class="sel-card">
      <div class="sel-name" id="sel-name"></div>
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div class="sel-name" id="sel-name" style="margin-bottom:0"></div>
        <div onclick="closeChannel()" style="cursor:pointer; padding:4px; color:#6b7280; font-size:24px; line-height:1; font-weight:bold;" title="Close">✕</div>
      </div>
      <div class="sel-btns">
        <button class="btn btn-red btn-sm" onclick="openModal(true)">Record Now</button>
        <button class="btn btn-blue btn-sm" onclick="openModal(false)">Schedule</button>
        <button class="btn btn-sm btn-gray" id="fav-btn" onclick="toggleFav()">Save</button>
        <button class="btn btn-gray btn-sm" onclick="setBackup()">Set Backup</button>
      </div>
      <div id="epg-panel"><div class="empty">Loading guide…</div></div>
    </div>
  </div>
</div>

<div class="section">
  <div class="sec-title" style="cursor:default">Active Recordings</div>
  <div id="recordings"><div class="empty">No active recordings</div></div>
</div>

<div class="section">
  <div class="sec-title" style="cursor:default">Saved Channels</div>
  <div id="favorites"><div class="empty">No saved channels yet</div></div>
</div>

<div class="section">
  <div class="sec-title" onclick="toggleLog()">Recording Log <span id="log-arrow">▶</span></div>
  <div id="log-panel" style="display:none;max-height:220px;overflow-y:auto;margin-top:6px"></div>
</div>

<div class="overlay" id="overlay">
  <div class="modal">
    <h2 id="modal-title">Schedule Recording</h2>
    <input type="text" id="m-time" placeholder="Start time (07:00 PM)">
    <input type="number" id="m-dur" placeholder="Duration (minutes)" value="180">
    <div class="modal-btns">
      <button class="btn btn-green" style="flex:1" onclick="confirmSchedule()">Schedule</button>
      <button class="btn btn-gray" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>

<script>
let selId=null,selName=null,allFavs=[],searchTimer=null,logOpen=false,isRecordNow=false;

function d64(s){try{return atob(s)}catch(e){return s||''}}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmt12(ts){const d=new Date(ts*1000);let h=d.getHours(),m=d.getMinutes();const p=h>=12?'PM':'AM';h=h%12||12;return h+':'+(m<10?'0'+m:m)+' '+p}

// ── Status / Recordings ───────────────────────────────────────────────────────
function refreshStatus(){
  fetch('/api/status').then(r=>r.json()).then(d=>{
    document.getElementById('srv-status').textContent=d.status;
    const bDisp=document.getElementById('backup-status');
    if(d.backup_name){
      document.getElementById('backup-name-disp').textContent=d.backup_name;
      bDisp.style.display='block';
    }else{
      bDisp.style.display='none';
    }
    const el=document.getElementById('recordings');
    if(!d.recordings.length){el.innerHTML='<div class="empty">No active recordings</div>';return}
    el.innerHTML=d.recordings.map((r,i)=>`
      <div class="card">
        <div class="card-name">${esc(r.name)}</div>
        <div class="card-status${r.status==='recording'?' rec-status':''}">${esc(r.status_text)}</div>
        ${r.stoppable?`<button class="btn btn-red btn-sm" onclick="stopJob(${i})">Stop</button>`:''}
      </div>`).join('');
  }).catch(()=>{});
}

// ── Favorites ─────────────────────────────────────────────────────────────────
function refreshFavs(){
  fetch('/api/favorites').then(r=>r.json()).then(favs=>{
    allFavs=favs;
    const el=document.getElementById('favorites');
    if(!favs.length){el.innerHTML='<div class="empty">No saved channels yet</div>';return}
    el.innerHTML=favs.map(f=>`
      <div class="fav-row">
        <span class="fav-name" onclick="selectFav('${esc(f.id)}','${esc(f.name)}')">${esc(f.name)}</span>
        <button class="btn btn-blue btn-sm" onclick="selectFav('${esc(f.id)}','${esc(f.name)}')">Select</button>
        <button class="btn btn-gray btn-sm" onclick="removeFav('${esc(f.name)}')">✕</button>
      </div>`).join('');
    updateFavBtn();
  }).catch(()=>{});
}

function selectFav(id,name){document.getElementById('search-input').value='';selectChannel(id,name);window.scrollTo({top:0,behavior:'smooth'});}

function updateFavBtn(){
  if(!selId)return;
  const saved=allFavs.some(f=>f.id===selId);
  const btn=document.getElementById('fav-btn');
  btn.textContent=saved?'Saved ✓':'Save';
  btn.className='btn btn-sm '+(saved?'btn-green':'btn-gray');
}

function toggleFav(){
  if(!selId)return;
  const saved=allFavs.some(f=>f.id===selId);
  const url=saved?'/api/favorites/remove':'/api/favorites/add';
  const body=saved?{name:selName}:{name:selName,id:selId};
  fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(()=>refreshFavs());
}

function removeFav(name){
  fetch('/api/favorites/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})})
    .then(()=>refreshFavs());
}

// ── Channel Search ────────────────────────────────────────────────────────────
function onSearch(){
  clearTimeout(searchTimer);
  const q=document.getElementById('search-input').value.trim();
  if(!q){document.getElementById('search-results').innerHTML='';return}
  searchTimer=setTimeout(()=>{
    fetch('/api/channels?q='+encodeURIComponent(q))
      .then(r=>r.json()).then(renderResults).catch(()=>{});
  },350);
}

function renderResults(channels){
  const el=document.getElementById('search-results');
  if(!channels.length){el.innerHTML='<div class="empty">No matches</div>';return}
  el.innerHTML=channels.map(c=>`<div class="result-item" onclick="selectChannel('${esc(c.id)}','${esc(c.name)}')">${esc(c.name)}</div>`).join('');
}

function selectChannel(id,name){
  selId=id;selName=name;
  document.getElementById('search-input').value=name;
  document.getElementById('search-results').innerHTML='';
  document.getElementById('sel-name').textContent=name;
  document.getElementById('sel-card').style.display='block';
  document.getElementById('epg-panel').innerHTML='<div class="empty">Loading guide…</div>';
  updateFavBtn();
  fetch('/api/epg?channel_id='+id).then(r=>r.json()).then(d=>renderEpg(d.listings))
    .catch(()=>{document.getElementById('epg-panel').innerHTML='<div class="empty">No guide data</div>';});
}

function closeChannel(){
  selId=null; selName=null;
  document.getElementById('sel-card').style.display='none';
  document.getElementById('search-input').value='';
}

// ── EPG ───────────────────────────────────────────────────────────────────────
function renderEpg(listings){
  const el=document.getElementById('epg-panel');
  if(!listings||!listings.length){el.innerHTML='<div class="empty">No guide data</div>';return}
  const now=Date.now()/1000;
  el.innerHTML=listings.map(l=>{
    const title=d64(l.title||'');
    const desc=l.description?d64(l.description):'';
    const isNow=l.start_timestamp<=now&&now<l.stop_timestamp;
    const t=fmt12(l.start_timestamp);
    const d=Math.max(1, Math.round((l.stop_timestamp - l.start_timestamp) / 60));
    return `<div class="epg-row${isNow?' epg-now':''}">
      <div class="epg-hdr">
        ${isNow?'<span class="badge">NOW</span>':''}
        <span class="epg-time">${fmt12(l.start_timestamp)} – ${fmt12(l.stop_timestamp)}</span>
        <button class="btn btn-gray btn-sm" onclick="setEpgTime('${esc(t)}', ${d})">Set</button>
      </div>
      <div class="epg-title">${esc(title)}</div>
      ${desc?`<div class="epg-desc">${esc(desc.substring(0,120))}</div>`:''}
    </div>`;
  }).join('');
}

function setEpgTime(t, d){document.getElementById('m-time').value=t;if(d)document.getElementById('m-dur').value=d;openModal(false)}

// ── Schedule modal ────────────────────────────────────────────────────────────
function openModal(now=false){
  if(!selId){alert('Select a channel first');return}
  isRecordNow=now;
  document.getElementById('modal-title').textContent=now?'Record Now: '+selName:'Schedule: '+selName;
  document.getElementById('m-time').style.display=now?'none':'block';
  document.getElementById('overlay').style.display='block';
}
function closeModal(){document.getElementById('overlay').style.display='none'}
function confirmSchedule(){
  const dur=parseInt(document.getElementById('m-dur').value);
  if(!dur){alert('Enter duration');return}
  let time='NOW';
  if(!isRecordNow){
    time=document.getElementById('m-time').value.trim();
    if(!time){alert('Enter a start time');return}
  }
  fetch('/api/schedule',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({channel_id:selId,channel_name:selName,start_time:time,duration_mins:dur})
  }).then(r=>r.json()).then(d=>{closeModal();alert(d.message)}).catch(()=>alert('Error'));
}
function setBackup(){
  if(!selId)return;
  fetch('/api/backup/set',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:selId,name:selName})
  }).then(r=>r.json()).then(d=>{refreshStatus();alert(d.message);}).catch(()=>alert('Error'));
}
function clearBackup(){
  fetch('/api/backup/clear',{method:'POST'}).then(()=>refreshStatus());
}
function stopJob(i){
  if(!confirm('Stop this recording?'))return;
  fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i})})
    .then(r=>r.json()).then(d=>alert(d.message));
}

// ── Log ───────────────────────────────────────────────────────────────────────
function toggleLog(){
  logOpen=!logOpen;
  document.getElementById('log-panel').style.display=logOpen?'block':'none';
  document.getElementById('log-arrow').textContent=logOpen?'▼':'▶';
  if(logOpen)refreshLog();
}
function refreshLog(){
  fetch('/api/log').then(r=>r.json()).then(d=>{
    document.getElementById('log-panel').innerHTML=
      d.entries.slice().reverse().map(e=>`<div class="log-line">${esc(e)}</div>`).join('');
  }).catch(()=>{});
}

document.getElementById('overlay').addEventListener('click',e=>{
  if(e.target===document.getElementById('overlay'))closeModal();
});

refreshStatus();refreshFavs();
setInterval(refreshStatus,2000);
setInterval(refreshFavs,20000);
setInterval(()=>{if(logOpen)refreshLog()},5000);
</script>
</body>
</html>"""


# ── HTTP request handler ──────────────────────────────────────────────────────

class RemoteHandler(BaseHTTPRequestHandler):
    app = None  # set to IPTVRecorderApp instance before server starts

    def do_GET(self):
        parsed = urlparse(self.path)
        qs     = parse_qs(parsed.query)
        path   = parsed.path

        if path == "/":
            self._html(HTML_PAGE)
        elif path == "/api/status":
            self._json(self.app._web_get_status())
        elif path == "/api/favorites":
            self._json(self.app.favorites)
        elif path == "/api/channels":
            q = qs.get("q", [""])[0].lower().strip()
            if not q or not self.app.all_channel_names:
                self._json([])
            else:
                results = [
                    {"name": n, "id": self.app.channel_map[n]}
                    for n in self.app.all_channel_names if q in n.lower()
                ][:25]
                self._json(results)
        elif path == "/api/epg":
            channel_id = qs.get("channel_id", [""])[0]
            if not channel_id:
                self._json({"listings": []})
            else:
                try:
                    url = (f"{SERVER_URL}/player_api.php?username={USERNAME}&password={PASSWORD}"
                           f"&action=get_short_epg&stream_id={channel_id}&limit=12")
                    r = requests.get(url, timeout=8)
                    self._json({"listings": r.json().get("epg_listings", [])})
                except Exception:
                    self._json({"listings": []})
        elif path == "/api/log":
            self._json({"entries": list(self.app._log_entries[-80:])})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = json.loads(self.rfile.read(length)) if length else {}
        path   = urlparse(self.path).path

        if path == "/api/schedule":
            self.app._web_actions.put({"type": "schedule", **body})
            msg = f"Started: {body.get('channel_name','')}" if body.get("start_time") == "NOW" else f"Scheduled: {body.get('channel_name','')} at {body.get('start_time','')}"
            self._json({"message": msg})
        elif path == "/api/stop":
            self.app._web_actions.put({"type": "stop", "index": body.get("index", 0)})
            self._json({"message": "Stop requested."})
        elif path == "/api/favorites/add":
            self.app._web_actions.put({"type": "fav_add", "name": body.get("name"), "id": body.get("id")})
            self._json({"ok": True})
        elif path == "/api/favorites/remove":
            self.app._web_actions.put({"type": "fav_remove", "name": body.get("name")})
            self._json({"ok": True})
        elif path == "/api/backup/set":
            self.app._web_actions.put({"type": "backup_set", "id": body.get("id"), "name": body.get("name")})
            self._json({"message": f"Backup channel set to: {body.get('name')}"})
        elif path == "/api/backup/clear":
            self.app._web_actions.put({"type": "backup_clear"})
            self._json({"message": "Backup channel cleared"})
        else:
            self.send_response(404); self.end_headers()

    def _html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode())

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass  # silence access logs


# ── Recording job ─────────────────────────────────────────────────────────────

class RecordingJob:
    def __init__(self, channel_name, channel_id, start_time, duration_mins, output_dir):
        self.channel_name  = channel_name
        self.channel_id    = channel_id
        self.start_time    = start_time
        self.duration_mins = duration_mins
        self.output_dir    = output_dir
        self.status          = "waiting"
        self.process         = None
        self.actual_start    = None
        self.output_file     = None
        self.card_frame      = None
        self.status_label    = None
        self.stop_btn        = None
        self.finish_msg          = None   # set by bg thread, consumed by _tick
        self.reconnect_count     = 0      # incremented on each FFmpeg restart
        self.backup_channel_id   = None
        self.backup_channel_name = None
        self.active_channel_name = channel_name  # updated when switched to backup
        self._pending_logs       = []            # log messages queued by bg thread; drained by _tick


# ── First-run setup wizard ────────────────────────────────────────────────────

class SetupWizard(ctk.CTkToplevel):
    """
    Multi-step onboarding shown the first time the app launches (no credentials.json).
    Walks the user through IPTV provider credentials and optional tunnel setup.
    """

    _PAGES = ["welcome", "iptv", "tunnel"]
    _HEADERS = ["Welcome to IPTV Recorder", "IPTV Provider", "Remote Access  (optional)"]
    _STEPS   = ["", "Step 1 of 2", "Step 2 of 2"]

    def __init__(self, parent, on_complete):
        super().__init__(parent)
        self._on_complete = on_complete
        self._page = 0

        self.title("Setup")
        self.geometry("500x560")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._finish)   # closing = skip remaining steps

        # ── Header ──
        self._header_lbl = ctk.CTkLabel(self, text="", font=("Arial", 20, "bold"))
        self._header_lbl.pack(pady=(28, 2), padx=32)
        self._step_lbl = ctk.CTkLabel(self, text="", text_color="gray50", font=("Arial", 11))
        self._step_lbl.pack(pady=(0, 16))

        # ── Page container ──
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=32)

        # ── Nav buttons ──
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=32, pady=(12, 28))

        self._back_btn = ctk.CTkButton(nav, text="← Back", width=90,
                                       fg_color="#575959", hover_color="#636666",
                                       command=self._prev)
        self._back_btn.pack(side="left")
        self._skip_btn = ctk.CTkButton(nav, text="Skip", width=72,
                                       fg_color="#333434", hover_color="#484949",
                                       text_color="gray55",
                                       command=self._skip)
        self._skip_btn.pack(side="left", padx=(8, 0))
        self._next_btn = ctk.CTkButton(nav, text="Get Started →", width=150,
                                       command=self._next)
        self._next_btn.pack(side="right")

        # ── Build all pages ──
        self._pages = {}
        self._build_welcome()
        self._build_iptv()
        self._build_tunnel()
        self._show_page(0)

    # ── Page builders ─────────────────────────────────────────────────────────

    def _build_welcome(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")

        ctk.CTkLabel(f,
                     text="This app records live IPTV streams on a schedule.\nHere's what you'll need to get started:",
                     text_color="gray70", font=("Arial", 12), justify="left", anchor="w"
                     ).pack(fill="x", pady=(0, 14))

        items = [
            ("📺  IPTV Subscription",
             "Any provider that uses the XtreamCodes format.\n"
             "They'll give you a Server URL, Username, and Password."),
            ("📡  Node.js  (optional — for remote control)",
             "Required to control recordings from your phone.\n"
             "Free download at nodejs.org if you want this feature."),
            ("🔑  InstaTunnel account  (optional — for remote control)",
             "Gives your app a public URL for phone access.\n"
             "Free account at instatunnel.my — takes 30 seconds."),
        ]
        for title, desc in items:
            card = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
            card.pack(fill="x", pady=4)
            ctk.CTkLabel(card, text=title, font=("Arial", 12, "bold"), anchor="w"
                         ).pack(fill="x", padx=14, pady=(10, 2))
            ctk.CTkLabel(card, text=desc, text_color="gray55", font=("Arial", 11),
                         anchor="w", justify="left"
                         ).pack(fill="x", padx=14, pady=(0, 10))

        self._pages["welcome"] = f

    def _build_iptv(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")

        ctk.CTkLabel(f,
                     text="Enter the credentials from your IPTV provider.\n"
                          "Check your welcome email or your provider's dashboard.",
                     text_color="gray70", font=("Arial", 12), justify="left", anchor="w"
                     ).pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(f, text="Server URL", anchor="w").pack(fill="x")
        self._url = ctk.CTkEntry(f, placeholder_text="http://provider.example.com:8080")
        self._url.pack(fill="x", pady=(0, 10))
        self._url.insert(0, SERVER_URL)

        ctk.CTkLabel(f, text="Username", anchor="w").pack(fill="x")
        self._user = ctk.CTkEntry(f)
        self._user.pack(fill="x", pady=(0, 10))
        self._user.insert(0, USERNAME)

        ctk.CTkLabel(f, text="Password", anchor="w").pack(fill="x")
        self._pass = ctk.CTkEntry(f, show="•")
        self._pass.pack(fill="x", pady=(0, 6))
        self._pass.insert(0, PASSWORD)

        self._iptv_err = ctk.CTkLabel(f, text="", text_color="#e74c3c",
                                       font=("Arial", 11), anchor="w")
        self._iptv_err.pack(fill="x")

        self._pages["iptv"] = f

    def _build_tunnel(self):
        f = ctk.CTkFrame(self._content, fg_color="transparent")

        info = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
        info.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(info,
                     text="InstaTunnel gives your app a public HTTPS URL so you can\n"
                          "browse channels, save favourites, and schedule recordings\n"
                          "from your phone — even away from home.",
                     text_color="gray55", font=("Arial", 11), justify="left", anchor="w"
                     ).pack(fill="x", padx=14, pady=10)

        ctk.CTkButton(f, text="1.  Go to instatunnel.my and create a free account →",
                      fg_color="#484949", hover_color="#575959",
                      command=lambda: webbrowser.open("https://instatunnel.my")
                      ).pack(fill="x", pady=(0, 6))

        steps = ctk.CTkFrame(f, fg_color="#2E2F2F", corner_radius=8)
        steps.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(steps,
                     text="2.  Log in and open the Dashboard\n"
                          "3.  Copy your API Key from the dashboard\n"
                          f"4.  If asked for a port, use {WEB_PORT}\n"
                          "5.  Paste your API Key below and choose a subdomain",
                     text_color="gray55", font=("Arial", 11), justify="left", anchor="w"
                     ).pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(f, text="API Key", anchor="w").pack(fill="x")
        self._tunnel_key = ctk.CTkEntry(f, placeholder_text="it_…")
        self._tunnel_key.pack(fill="x", pady=(0, 10))
        self._tunnel_key.insert(0, INSTATUNNEL_API_KEY)

        ctk.CTkLabel(f, text="Subdomain  (becomes https://<subdomain>.instatunnel.my)",
                     anchor="w").pack(fill="x")
        self._tunnel_sub = ctk.CTkEntry(f, placeholder_text="e.g. johns-iptv")
        self._tunnel_sub.pack(fill="x", pady=(0, 6))
        self._tunnel_sub.insert(0, INSTATUNNEL_SUBDOMAIN)

        ctk.CTkLabel(f, text="You can always add this later via ⚙ Settings.",
                     text_color="gray40", font=("Arial", 10), anchor="w").pack(fill="x")

        self._pages["tunnel"] = f

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _show_page(self, idx):
        self._page = idx
        for frame in self._pages.values():
            frame.pack_forget()
        self._pages[self._PAGES[idx]].pack(fill="both", expand=True)

        self._header_lbl.configure(text=self._HEADERS[idx])
        self._step_lbl.configure(text=self._STEPS[idx])
        self._back_btn.configure(state="normal" if idx > 0 else "disabled")
        self._skip_btn.configure(state="normal" if idx > 0 else "disabled")

        last = idx == len(self._PAGES) - 1
        self._next_btn.configure(text="Finish" if last else ("Get Started →" if idx == 0 else "Next →"))

    def _prev(self):
        if self._page > 0:
            self._show_page(self._page - 1)

    def _next(self):
        if self._page == 1:   # IPTV page — require all three fields
            if not all([self._url.get().strip(),
                        self._user.get().strip(),
                        self._pass.get().strip()]):
                self._iptv_err.configure(text="All three fields are required.")
                return
            self._iptv_err.configure(text="")

        if self._page < len(self._PAGES) - 1:
            self._show_page(self._page + 1)
        else:
            self._finish()

    def _skip(self):
        """Skip the current optional page."""
        if self._page < len(self._PAGES) - 1:
            self._show_page(self._page + 1)
        else:
            self._finish()

    def _finish(self):
        self._save()
        self.destroy()
        self._on_complete()

    def _save(self):
        global SERVER_URL, USERNAME, PASSWORD, INSTATUNNEL_API_KEY, INSTATUNNEL_SUBDOMAIN
        SERVER_URL            = self._url.get().strip().rstrip("/")
        USERNAME              = self._user.get().strip()
        PASSWORD              = self._pass.get().strip()
        INSTATUNNEL_API_KEY   = self._tunnel_key.get().strip()
        INSTATUNNEL_SUBDOMAIN = self._tunnel_sub.get().strip()
        try:
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump({
                    "server_url":       SERVER_URL,
                    "username":         USERNAME,
                    "password":         PASSWORD,
                    "tunnel_api_key":   INSTATUNNEL_API_KEY,
                    "tunnel_subdomain": INSTATUNNEL_SUBDOMAIN,
                }, f, indent=2)
        except Exception as e:
            print(f"Could not save credentials: {e}")


# ── Credentials dialog ────────────────────────────────────────────────────────

class CredentialsDialog(ctk.CTkToplevel):
    def __init__(self, parent, on_save):
        super().__init__(parent)
        self._on_save = on_save
        self.title("Account Settings")
        self.geometry("440x640")
        self.resizable(False, True)
        self.grab_set()   # modal — blocks the main window
        self.lift()
        self.focus_force()

        ctk.CTkLabel(self, text="XtreamCodes Account",
                     font=("Arial", 16, "bold")).pack(pady=(20, 12))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=28)

        ctk.CTkLabel(form, text="Server URL", anchor="w").pack(fill="x")
        self._url = ctk.CTkEntry(form, placeholder_text="http://yourserver.com:8080")
        self._url.pack(fill="x", pady=(0, 10))
        self._url.insert(0, SERVER_URL)

        ctk.CTkLabel(form, text="Username", anchor="w").pack(fill="x")
        self._user = ctk.CTkEntry(form)
        self._user.pack(fill="x", pady=(0, 10))
        self._user.insert(0, USERNAME)

        ctk.CTkLabel(form, text="Password", anchor="w").pack(fill="x")
        self._pass = ctk.CTkEntry(form, show="•")
        self._pass.pack(fill="x", pady=(0, 10))
        self._pass.insert(0, PASSWORD)

        ctk.CTkButton(form, text="Save & Reload Channels",
                      command=self._save_xtream).pack(fill="x", pady=(5, 10))

        ctk.CTkFrame(self, height=1, fg_color="#484949").pack(fill="x", padx=28, pady=(8, 12))

        ctk.CTkLabel(self, text="InstaTunnel  (Remote Access)",
                     font=("Arial", 14, "bold"), anchor="w").pack(fill="x", padx=28, pady=(0, 6))

        tunnel_form = ctk.CTkFrame(self, fg_color="transparent")
        tunnel_form.pack(fill="x", padx=28)

        ctk.CTkButton(tunnel_form, text="instatunnel.my  — create a free account →",
                      fg_color="#484949", hover_color="#575959", height=28,
                      command=lambda: webbrowser.open("https://instatunnel.my")
                      ).pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(tunnel_form,
                     text=f"Log in → Dashboard → copy your API Key  (app uses port {WEB_PORT})",
                     text_color="gray50", font=("Arial", 10), anchor="w"
                     ).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(tunnel_form, text="API Key", anchor="w").pack(fill="x")
        self._tunnel_key = ctk.CTkEntry(tunnel_form, placeholder_text="it_…")
        self._tunnel_key.pack(fill="x", pady=(0, 10))
        self._tunnel_key.insert(0, INSTATUNNEL_API_KEY)

        ctk.CTkLabel(tunnel_form, text="Subdomain  (becomes https://<subdomain>.instatunnel.my)",
                     anchor="w").pack(fill="x")
        self._tunnel_sub = ctk.CTkEntry(tunnel_form, placeholder_text="e.g. johns-iptv")
        self._tunnel_sub.pack(fill="x", pady=(0, 6))
        self._tunnel_sub.insert(0, INSTATUNNEL_SUBDOMAIN)

        ctk.CTkLabel(tunnel_form, text="Tunnel changes take effect on next app launch.",
                     text_color="gray40", font=("Arial", 10), anchor="w").pack(fill="x", pady=(0, 12))

        ctk.CTkButton(tunnel_form, text="Save & Relaunch App",
                      fg_color="#c0392b", hover_color="#e74c3c",
                      command=self._save_tunnel).pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=28, pady=(0, 20))
        ctk.CTkButton(btns, text="Close",
                      fg_color="#575959", hover_color="#484949",
                      command=self.destroy).pack(fill="x", expand=True)

    def _save_to_file(self):
        global SERVER_URL, USERNAME, PASSWORD, INSTATUNNEL_API_KEY, INSTATUNNEL_SUBDOMAIN
        SERVER_URL            = self._url.get().strip().rstrip("/")
        USERNAME              = self._user.get().strip()
        PASSWORD              = self._pass.get().strip()
        INSTATUNNEL_API_KEY   = self._tunnel_key.get().strip()
        INSTATUNNEL_SUBDOMAIN = self._tunnel_sub.get().strip()
        try:
            with open(CREDENTIALS_FILE, "w") as f:
                json.dump({
                    "server_url":       SERVER_URL,
                    "username":         USERNAME,
                    "password":         PASSWORD,
                    "tunnel_api_key":   INSTATUNNEL_API_KEY,
                    "tunnel_subdomain": INSTATUNNEL_SUBDOMAIN,
                }, f, indent=2)
        except Exception as e:
            print(f"Could not save credentials: {e}")

    def _save_xtream(self):
        self._save_to_file()
        self.destroy()
        self._on_save()

    def _save_tunnel(self):
        self._save_to_file()
        self.destroy()
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable] + sys.argv[1:])
        else:
            subprocess.Popen([sys.executable] + sys.argv)
        self.master._on_closing()


# ── Main application ──────────────────────────────────────────────────────────

class IPTVRecorderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"ELITE IPTV Recorder  v{APP_VERSION}")
        self.geometry("1050x760")
        self.minsize(950, 700)

        if sys.platform == "win32":
            import ctypes
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"elite.iptv.recorder.{APP_VERSION}")
                icon_path = os.path.join(_BUNDLE_DIR, "icon.ico")
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
                elif getattr(sys, "frozen", False):
                    self.iconbitmap(sys.executable)  # Automatically pull the .exe icon
            except Exception:
                pass

        self.channel_map           = {}
        self.all_channel_names     = []
        self.recording_jobs        = []
        self.output_dir            = os.path.expanduser("~")
        self._load_settings()
        self.m3u_text              = ""
        self._fetch_start          = datetime.datetime.now()
        self._channels_loaded      = False
        self._fetch_result         = None
        self.selected_channel_name = None
        self.selected_channel_id   = None
        self._epg_result           = None
        self._epg_channel_id       = None
        self._status_text          = "Fetching channel list…"
        self._web_actions          = queue.Queue()
        self.favorites             = []
        self._log_entries          = []     # kept in sync with log_box; served to web remote
        self.tunnel_process        = None
        self._tunnel_url           = None   # set by bg thread, polled by _tick
        self._tunnel_log           = None   # error/notice from bg thread, polled by _tick
        self._tunnel_lines         = []     # every raw line from tunnel, drained by _tick for logging
        self.backup_channel_name   = None
        self.backup_channel_id     = None
        self.current_remote_url    = None

        self._load_favorites()
        self._build_ui()
        self._tick()
        self._start_web_server()

        # First run — no saved credentials yet: open setup wizard before fetching
        if not os.path.exists(CREDENTIALS_FILE):
            self.after(300, lambda: SetupWizard(self, self._on_settings_saved))
        else:
            threading.Thread(target=self._fetch_channels, daemon=True).start()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Base container (replaces outer scrollable frame)
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Left Pane (Configuration)
        left_pane = ctk.CTkFrame(main_container, fg_color="transparent")
        left_pane.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # Right Pane (Monitoring)
        right_pane = ctk.CTkFrame(main_container, fg_color="transparent", width=400)
        right_pane.pack_propagate(False)
        right_pane.pack(side="right", fill="y", expand=False, padx=(10, 0))

        title_row = ctk.CTkFrame(left_pane, fg_color="transparent")
        title_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(title_row, text="ELITE IPTV Recorder",
                     font=("Arial", 22, "bold")).pack(side="left")
        ctk.CTkButton(title_row, text="⚙ Settings", width=100, height=34,
                      fg_color="#484949", hover_color="#575959",
                      command=self._open_settings).pack(side="right")

        panel = ctk.CTkFrame(left_pane)
        panel.pack(fill="both", expand=True)

        # ── Saved Channels / Favorites ──
        self.fav_section = ctk.CTkFrame(panel, fg_color="transparent")
        self.fav_section.pack(fill="x", padx=15, pady=(10, 4))
        fav_header = ctk.CTkFrame(self.fav_section, fg_color="transparent")
        fav_header.pack(fill="x")
        ctk.CTkLabel(fav_header, text="Saved Channels", font=("Arial", 12, "bold"), anchor="w").pack(side="left")
        _fav_wrapper = ctk.CTkFrame(self.fav_section, height=55, fg_color="transparent")
        _fav_wrapper.pack(fill="x", pady=(4, 0))
        _fav_wrapper.pack_propagate(False)
        self.fav_scroll = ctk.CTkScrollableFrame(_fav_wrapper, fg_color="#2E2F2F")
        self.fav_scroll.pack(fill="both", expand=True)
        self._refresh_favorites_panel()

        ctk.CTkFrame(panel, height=1, fg_color="#484949").pack(fill="x", padx=15, pady=(8, 8))

        # ── Live Sports Today (collapsible) ──
        self.sports_frame = ctk.CTkFrame(panel, fg_color="transparent")
        _spt_hdr = ctk.CTkFrame(self.sports_frame, fg_color="transparent")
        _spt_hdr.pack(fill="x", pady=(0, 2))
        self._sports_toggle_btn = ctk.CTkButton(
            _spt_hdr, text="▶  Live Sports Today", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_sports_section)
        self._sports_toggle_btn.pack(side="left", fill="x", expand=True)

        self._sports_body = ctk.CTkFrame(self.sports_frame, fg_color="transparent")
        self._sports_expanded = False

        _spt_controls = ctk.CTkFrame(self._sports_body, fg_color="transparent")
        _spt_controls.pack(fill="x", pady=(0, 4))

        self._sports_league = ctk.StringVar(value="NHL")
        self.sports_combo = ctk.CTkComboBox(
            _spt_controls, variable=self._sports_league,
            values=["NHL", "NBA", "NFL", "MLB"],
            width=80, command=self._fetch_sports
        )
        self.sports_combo.pack(side="left", padx=(0, 6))

        self.sports_refresh_btn = ctk.CTkButton(
            _spt_controls, text="Refresh", width=60,
            fg_color="#575959", hover_color="#484949",
            command=self._fetch_sports
        )
        self.sports_refresh_btn.pack(side="left")

        _spt_wrapper = ctk.CTkFrame(self._sports_body, height=150, fg_color="transparent")
        _spt_wrapper.pack(fill="x", pady=(4, 0))
        _spt_wrapper.pack_propagate(False)
        self.sports_scroll = ctk.CTkScrollableFrame(_spt_wrapper, fg_color="#2E2F2F")
        self.sports_scroll.pack(fill="both", expand=True)

        self.sports_frame.pack(fill="x", padx=15, pady=(0, 4))

        ctk.CTkFrame(panel, height=1, fg_color="#484949").pack(fill="x", padx=15, pady=(8, 8))

        # ── Channel search ──
        ctk.CTkLabel(panel, text="Search Channel", anchor="w").pack(fill="x", padx=15, pady=(0, 2))
        self.search_entry = ctk.CTkEntry(panel, placeholder_text="Loading channels — please wait…", state="disabled")
        self.search_entry.pack(fill="x", padx=15, pady=(0, 4))
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        self.results_frame = ctk.CTkScrollableFrame(panel, height=130, fg_color="#2E2F2F")
        self._results_anchor = ctk.CTkFrame(panel, height=0, fg_color="transparent")
        self._results_anchor.pack(fill="x", padx=15)

        # Selected row
        sel_row = ctk.CTkFrame(panel, fg_color="transparent")
        sel_row.pack(fill="x", padx=15, pady=(0, 4))
        self.sel_row = sel_row
        self.selected_label = ctk.CTkLabel(sel_row, text="No channel selected", text_color="gray", anchor="w")
        self.selected_label.pack(side="left", fill="x", expand=True)
        self.save_btn = ctk.CTkButton(
            sel_row, text="Save", width=60,
            fg_color="#575959", hover_color="#484949",
            command=self._toggle_save_channel, state="disabled"
        )
        self.save_btn.pack(side="right", padx=(4, 0))
        self.preview_btn = ctk.CTkButton(
            sel_row, text="Preview", width=72,
            fg_color="#575959", hover_color="#484949",
            command=self._preview_stream, state="disabled"
        )
        self.preview_btn.pack(side="right", padx=(4, 0))

        # EPG panel — collapsible, hidden by default
        _epg_hdr = ctk.CTkFrame(panel, fg_color="transparent")
        _epg_hdr.pack(fill="x", padx=15, pady=(0, 2))
        self._epg_toggle_btn = ctk.CTkButton(
            _epg_hdr, text="▶  Program Guide", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_epg_section)
        self._epg_toggle_btn.pack(side="left", fill="x", expand=True)
        self._epg_expanded = False

        _epg_wrapper = ctk.CTkFrame(panel, height=150, fg_color="transparent")
        _epg_wrapper.pack_propagate(False)
        self.epg_frame = ctk.CTkScrollableFrame(_epg_wrapper, fg_color="#2E2F2F")
        self.epg_frame.pack(fill="both", expand=True)
        self._epg_wrapper = _epg_wrapper  # keep ref for show/hide

        # ── Backup Channel (optional, collapsible) ────────────────────────────
        self.backup_frame = ctk.CTkFrame(panel, fg_color="transparent")
        ctk.CTkFrame(self.backup_frame, height=1, fg_color="#484949").pack(fill="x", pady=(4, 6))
        _bkp_hdr = ctk.CTkFrame(self.backup_frame, fg_color="transparent")
        _bkp_hdr.pack(fill="x", pady=(0, 2))
        self._backup_toggle_btn = ctk.CTkButton(
            _bkp_hdr, text="▶  Backup Channel", font=("Arial", 11, "bold"),
            fg_color="transparent", hover_color="#3a3b3b", anchor="w",
            command=self._toggle_backup_section)
        self._backup_toggle_btn.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(_bkp_hdr, text="optional", text_color="gray40",
                     font=("Arial", 10), anchor="e").pack(side="right")

        # Collapsible body — hidden by default
        self._backup_body = ctk.CTkFrame(self.backup_frame, fg_color="transparent")
        self._backup_expanded = False
        self.backup_search_entry = ctk.CTkEntry(
            self._backup_body, placeholder_text="Search for backup channel…", state="disabled")
        self.backup_search_entry.pack(fill="x", pady=(0, 4))
        self.backup_search_entry.bind("<KeyRelease>", self._on_backup_search_key)
        self.backup_results_frame = ctk.CTkScrollableFrame(self._backup_body, height=100, fg_color="#2E2F2F")
        self._backup_results_anchor = ctk.CTkFrame(self._backup_body, height=0, fg_color="transparent")
        self._backup_results_anchor.pack(fill="x")
        _bkp_sel_row = ctk.CTkFrame(self._backup_body, fg_color="transparent")
        _bkp_sel_row.pack(fill="x", pady=(0, 4))
        self.backup_sel_label = ctk.CTkLabel(
            _bkp_sel_row, text="No backup selected", text_color="gray40", anchor="w")
        self.backup_sel_label.pack(side="left", fill="x", expand=True)
        self.backup_clear_btn = ctk.CTkButton(
            _bkp_sel_row, text="Clear", width=54,
            fg_color="#575959", hover_color="#484949",
            command=self._clear_backup_channel, state="disabled")
        self.backup_clear_btn.pack(side="right", padx=(4, 0))
        self.backup_frame.pack(fill="x", padx=15, pady=(0, 4))

        self.td_frame = ctk.CTkFrame(panel, fg_color="transparent")

        # Time + Duration
        self.td_frame.pack(fill="x", padx=15, pady=(4, 10))
        left = ctk.CTkFrame(self.td_frame, fg_color="transparent")
        left.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(left, text="Start Time", anchor="w").pack(fill="x")
        self.time_input = ctk.CTkEntry(left, placeholder_text="07:00 PM")
        self.time_input.pack(fill="x")
        right = ctk.CTkFrame(self.td_frame, fg_color="transparent")
        right.pack(side="right", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(right, text="Duration (minutes)", anchor="w").pack(fill="x")
        self.duration_input = ctk.CTkEntry(right, placeholder_text="180")
        self.duration_input.pack(fill="x")
        self.duration_input.insert(0, "180")

        # Output folder
        ctk.CTkLabel(panel, text="Output Folder", anchor="w").pack(fill="x", padx=15, pady=(4, 2))
        folder_row = ctk.CTkFrame(panel, fg_color="transparent")
        folder_row.pack(fill="x", padx=15, pady=(0, 10))
        self.folder_label = ctk.CTkLabel(folder_row, text=self.output_dir, anchor="w", text_color="gray")
        self.folder_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(folder_row, text="Open", width=60, fg_color="#575959", hover_color="#484949", command=self._open_output_folder).pack(side="right", padx=(6, 0))
        ctk.CTkButton(folder_row, text="Browse…", width=90, command=self._pick_folder).pack(side="right")

        # Action buttons
        btn_row = ctk.CTkFrame(panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(4, 14))
        self.record_now_btn = ctk.CTkButton(
            btn_row, text="Record Now", command=self._record_now, state="disabled",
            fg_color="#c0392b", hover_color="#e74c3c"
        )
        self.record_now_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.schedule_btn = ctk.CTkButton(
            btn_row, text="Schedule Recording", command=self._schedule_recording, state="disabled"
        )
        self.schedule_btn.pack(side="left", expand=True, fill="x", padx=(0, 6))
        self.save_m3u_btn = ctk.CTkButton(
            btn_row, text="Save M3U", width=90,
            fg_color="#575959", hover_color="#484949",
            command=self._save_m3u, state="disabled"
        )
        self.save_m3u_btn.pack(side="right")

        # ── Right Pane Monitoring Items ──
        status_panel = ctk.CTkFrame(right_pane)
        status_panel.pack(fill="x", pady=(0, 12))
        self.global_status = ctk.CTkLabel(status_panel, text="Fetching channel list…", text_color="gray")
        self.global_status.pack(pady=(8, 2))
        self.remote_label = ctk.CTkLabel(status_panel, text="Remote: starting…", text_color="gray40", font=("Arial", 10))
        self.remote_label.pack(pady=(0, 8))
        
        remote_frame = ctk.CTkFrame(status_panel, fg_color="transparent")
        remote_frame.pack(pady=(0, 8))
        self.remote_label = ctk.CTkLabel(remote_frame, text="Remote: starting…", text_color="gray40", font=("Arial", 10), cursor="hand2")
        self.remote_label.pack(side="left")
        self.remote_label.bind("<Button-1>", lambda e: webbrowser.open(self.current_remote_url) if self.current_remote_url else None)
        self.remote_copy_btn = ctk.CTkButton(
            remote_frame, text="Copy", width=40, height=20, font=("Arial", 10),
            fg_color="#575959", hover_color="#484949",
            command=self._copy_remote_url, state="disabled"
        )
        self.remote_copy_btn.pack(side="left", padx=(8, 0))

        # Active Recordings
        ctk.CTkLabel(right_pane, text="Active Recordings", font=("Arial", 14, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.recordings_frame = ctk.CTkScrollableFrame(right_pane)
        self.recordings_frame.pack(fill="both", expand=True, pady=(0, 12))
        self.no_recordings_label = ctk.CTkLabel(self.recordings_frame, text="No recordings scheduled.", text_color="gray")
        self.no_recordings_label.pack(pady=10)

        # Recording Log
        ctk.CTkLabel(right_pane, text="Recording Log", font=("Arial", 14, "bold"), anchor="w").pack(fill="x", pady=(0, 2))
        self.log_box = ctk.CTkTextbox(right_pane, height=200, state="disabled")
        self.log_box.pack(fill="x", pady=(0, 0))

        # Bind mousewheel
        self.after(200, self._install_window_scroll)

    # ── Favorites ─────────────────────────────────────────────────────────────

    def _load_favorites(self):
        try:
            with open(FAVORITES_FILE, "r") as f:
                self.favorites = json.load(f)
        except Exception:
            self.favorites = []

    def _save_favorites(self):
        with open(FAVORITES_FILE, "w") as f:
            json.dump(self.favorites, f, indent=2)

    def _load_settings(self):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            if "output_dir" in data and os.path.isdir(data["output_dir"]):
                self.output_dir = data["output_dir"]
        except Exception:
            pass

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump({"output_dir": self.output_dir}, f, indent=2)
        except Exception:
            pass

    def _refresh_favorites_panel(self):
        for w in self.fav_scroll.winfo_children():
            w.destroy()
        if not self.favorites:
            ctk.CTkLabel(self.fav_scroll, text="No saved channels yet.", text_color="gray").pack(pady=8)
            self._bind_scroll_tree(self.fav_scroll)
            return
        for fav in self.favorites:
            row = ctk.CTkFrame(self.fav_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkButton(
                row, text=fav["name"], anchor="w",
                fg_color="#484949", hover_color="#575959", height=28,
                command=lambda f=fav: self._select_channel(f["name"]),
            ).pack(side="left", fill="x", expand=True, padx=(0, 4))
            ctk.CTkButton(
                row, text="✕", width=28, height=28,
                fg_color="#333434", hover_color="#c0392b", text_color="gray",
                command=lambda n=fav["name"]: self._remove_favorite(n),
            ).pack(side="right")
        self._bind_scroll_tree(self.fav_scroll)

    def _toggle_save_channel(self):
        if not self.selected_channel_name:
            return
        names = [f["name"] for f in self.favorites]
        if self.selected_channel_name in names:
            self._remove_favorite(self.selected_channel_name)
        else:
            self.favorites.append({"name": self.selected_channel_name, "id": self.selected_channel_id})
            self._save_favorites()
            self._refresh_favorites_panel()
            self.save_btn.configure(text="Saved", fg_color="#1a6b3a")
            self._log(f"Saved: '{self.selected_channel_name}'")

    def _remove_favorite(self, name):
        self.favorites = [f for f in self.favorites if f["name"] != name]
        self._save_favorites()
        self._refresh_favorites_panel()
        if self.selected_channel_name == name:
            self.save_btn.configure(text="Save", fg_color="#F89344")
        self._log(f"Removed from favorites: '{name}'")

    def _update_save_btn_state(self):
        if not self.selected_channel_name:
            return
        already = any(f["name"] == self.selected_channel_name for f in self.favorites)
        self.save_btn.configure(
            text="Saved" if already else "Save",
            fg_color="#1a6b3a" if already else "#F89344"
        )

    # ── Web server ────────────────────────────────────────────────────────────

    def _start_web_server(self):
        RemoteHandler.app = self
        try:
            server = ThreadingHTTPServer(("0.0.0.0", WEB_PORT), RemoteHandler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                ip = ([
                    s.getsockname()[0] for s in [
                        socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    ] if not s.connect_ex(("192.168.1.1", 80))
                ] or ["localhost"])[0]
            except Exception:
                ip = "localhost"
            url = f"http://{ip}:{WEB_PORT}"
            self.remote_label.configure(text=f"Remote: {url}", text_color="gray")
            self.current_remote_url = url
            self.remote_label.configure(text=f"Remote: {url}", text_color="#3498db")
            self.remote_copy_btn.configure(state="normal")
            self._log(f"Remote control active: {url}")
            self._start_instatunnel()
        except OSError:
            self.remote_label.configure(text=f"Remote: port {WEB_PORT} in use", text_color="#e74c3c")

    def _start_instatunnel(self):
        if not INSTATUNNEL_SUBDOMAIN:
            self.remote_label.configure(
                text="Remote: tunnel not configured — open ⚙ Settings",
                text_color="gray40")
            return

        _ansi = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]|\r')

        def run_tunnel():
            env, npx = _build_instatunnel_env()

            # Kill any stale session holding our subdomain before claiming it again.
            kill_cmd = _resolve_instatunnel_cli(npx) + ["--kill", INSTATUNNEL_SUBDOMAIN]
            if INSTATUNNEL_API_KEY:
                kill_cmd += ["--api-key", INSTATUNNEL_API_KEY]
            try:
                subprocess.run(kill_cmd, env=env, timeout=10,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               **_SUBPROCESS_FLAGS)
            except Exception:
                pass  # kill is best-effort; proceed regardless
            time.sleep(1)

            cmd = _resolve_instatunnel_cli(npx) + ["connect", str(WEB_PORT), "--subdomain", INSTATUNNEL_SUBDOMAIN]
            if INSTATUNNEL_API_KEY:
                cmd += ["--api-key", INSTATUNNEL_API_KEY]
            try:
                self.tunnel_process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    env=env, **_SUBPROCESS_FLAGS,
                )
                stdout = self.tunnel_process.stdout
                if stdout is None:
                    return
                for raw in stdout:
                    line = _ansi.sub("", raw).strip()
                    if not line:
                        continue
                    self._tunnel_lines.append(line)
                    if self._tunnel_url is None:
                        m = re.search(r'https?://\S+', line)
                        if m:
                            url = m.group(0).rstrip('.,;)"\'>]')
                            # Skip the API server URL that appears in help/error text
                            if "api.instatunnel" not in url:
                                self._tunnel_url = url
            except FileNotFoundError:
                self._tunnel_log = "InstaTunnel: npx not found — check Node.js is installed."
            except Exception as e:
                self._tunnel_log = f"InstaTunnel error: {e}"

        threading.Thread(target=run_tunnel, daemon=True).start()

    def _web_get_status(self):
        now = datetime.datetime.now()
        recordings = []
        for i, job in enumerate(self.recording_jobs):
            if job.status == "complete":
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": "Recording finished.", "stoppable": False})
            elif job.status == "error":
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": "Error encountered.", "stoppable": False})
            elif job.status == "stopped":
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": "Stopped by user.", "stoppable": False})
            elif job.status == "waiting":
                secs = max(0, int((job.start_time - now).total_seconds()))
                txt = f"Starts in {str(datetime.timedelta(seconds=secs))}"
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": txt, "stoppable": True})
            elif job.status == "recording" and job.actual_start:
                elapsed   = int((now - job.actual_start).total_seconds())
                remaining = max(0, job.duration_mins * 60 - elapsed)
                txt = f"RECORDING  •  {str(datetime.timedelta(seconds=elapsed))} elapsed  •  {str(datetime.timedelta(seconds=remaining))} remaining"
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": txt, "stoppable": True})
            else:
                secs = max(0, int((job.start_time - now).total_seconds()))
                txt = f"Starts in {str(datetime.timedelta(seconds=secs))}"
                recordings.append({"name": job.channel_name, "status": job.status, "status_text": txt, "stoppable": True})
        return {
            "status": self._status_text,
            "backup_name": self.backup_channel_name,
            "recordings": recordings
        }

    def _process_web_actions(self):
        while not self._web_actions.empty():
            action = self._web_actions.get_nowait()
            if action["type"] == "schedule":
                self._web_schedule(action)
            elif action["type"] == "stop":
                active = [j for j in self.recording_jobs if j.status in ("waiting", "recording")]
                idx = action.get("index", 0)
                if 0 <= idx < len(active):
                    self._stop_job(active[idx])
            elif action["type"] == "fav_add":
                name, fav_id = action.get("name"), action.get("id")
                if name and fav_id and not any(f["name"] == name for f in self.favorites):
                    self.favorites.append({"name": name, "id": fav_id})
                    self._save_favorites()
                    self._refresh_favorites_panel()
                    self._log(f"[Remote] Saved channel: '{name}'")
            elif action["type"] == "fav_remove":
                name = action.get("name")
                if name:
                    self._remove_favorite(name)
                    self._log(f"[Remote] Removed channel: '{name}'")
            elif action["type"] == "backup_set":
                self.backup_channel_id = action.get("id")
                self.backup_channel_name = action.get("name")
                self.backup_sel_label.configure(text=f"Backup: {self.backup_channel_name}", text_color="#3498db")
                self.backup_clear_btn.configure(state="normal")
                self._log(f"[Remote] Set backup channel: '{self.backup_channel_name}'")
            elif action["type"] == "backup_clear":
                self._clear_backup_channel()
                self._log("[Remote] Cleared backup channel")

    def _web_schedule(self, action):
        try:
            now = datetime.datetime.now()
            if action.get("start_time") == "NOW":
                start_time = now
            else:
                start_time = datetime.datetime.strptime(action["start_time"].strip(), "%I:%M %p").replace(
                    year=now.year, month=now.month, day=now.day
                )
                if start_time < now:
                    start_time += datetime.timedelta(days=1)
            job = RecordingJob(
                action["channel_name"], action["channel_id"],
                start_time, int(action["duration_mins"]), self.output_dir
            )
            job.backup_channel_id   = self.backup_channel_id
            job.backup_channel_name = self.backup_channel_name
            self.recording_jobs.append(job)
            self._add_recording_card(job)
            backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
            if action.get("start_time") == "NOW":
                self._log(f"[Remote] Started recording '{job.channel_name}' for {job.duration_mins} min.{backup_info}")
                self._set_status(f"Recording: {job.channel_name}", "#e74c3c")
            else:
                self._log(f"[Remote] Scheduled '{job.channel_name}' at {start_time.strftime('%I:%M %p')} for {job.duration_mins} min.{backup_info}")
            threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        except Exception as e:
            self._log(f"[Remote] Schedule error: {e}")

    # ── Channel Loading ───────────────────────────────────────────────────────

    def _start_fetching(self):
        self._status_text = "Fetching channel list…"
        self.global_status.configure(text=self._status_text, text_color="gray")
        self._fetch_start = datetime.datetime.now()
        self._fetch_result = None
        self._channels_loaded = False
        threading.Thread(target=self._fetch_channels, daemon=True).start()

    def _open_settings(self):
        CredentialsDialog(self, self._on_settings_saved)

    def _on_settings_saved(self):
        self.channel_map = {}
        self.all_channel_names = []
        for w in self.results_frame.winfo_children(): w.destroy()
        self.results_frame.pack_forget()
        self.search_entry.delete(0, "end")
        self.search_entry.configure(state="disabled", placeholder_text="Loading channels — please wait…")
        self.backup_search_entry.configure(state="disabled", placeholder_text="Search for backup channel…")
        self.backup_channel_name = None
        self.backup_channel_id   = None
        self.backup_sel_label.configure(text="No backup selected", text_color="gray40")
        self.backup_clear_btn.configure(state="disabled")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()
        self.record_now_btn.configure(state="disabled")
        self.schedule_btn.configure(state="disabled")
        self.save_m3u_btn.configure(state="disabled")
        
        if SERVER_URL and USERNAME and PASSWORD:
            self._start_fetching()
        else:
            self._set_status("Missing credentials. Please configure in Settings.", "#e74c3c")

    def _fetch_channels(self):
        url = f"{SERVER_URL}/get.php?username={USERNAME}&password={PASSWORD}&type=m3u_plus&output=ts"
        try:
            response = requests.get(url, timeout=60)
            self.m3u_text = response.text
            lines = response.text.splitlines()
            current_name = ""
            for line in lines:
                if line.startswith("#EXTINF"):
                    current_name = line.split(",")[-1].strip()
                elif line.startswith("http") and current_name:
                    channel_id = line.split("/")[-1].replace(".ts", "").strip()
                    self.channel_map[current_name] = channel_id
                    current_name = ""
            self.all_channel_names = sorted(self.channel_map.keys())
            self._fetch_result = ("ok", len(self.all_channel_names))
        except Exception as e:
            self._fetch_result = ("err", str(e))

    def _on_channels_loaded(self, count):
        self._channels_loaded = True
        self.search_entry.configure(state="normal", placeholder_text="Type to search channels…")
        self.backup_search_entry.configure(state="normal", placeholder_text="Search for backup channel…")
        self.record_now_btn.configure(state="normal")
        self.schedule_btn.configure(state="normal")
        self.save_m3u_btn.configure(state="normal")
        msg = f"Ready — {count:,} channels loaded"
        self._status_text = msg
        self.global_status.configure(text=msg, text_color="#2ecc71")
        self._log(f"Loaded {count:,} channels from provider.")

    def _on_channels_error(self, err):
        self._channels_loaded = True
        msg = "Failed to load channels. Check credentials/URL."
        self._status_text = msg
        self.global_status.configure(text=msg, text_color="red")
        self._log(f"Error fetching channels: {err}")

    # ── Channel Search / Selection ────────────────────────────────────────────

    def _on_search_key(self, event=None):
        query = self.search_entry.get().strip()
        for w in self.results_frame.winfo_children():
            w.destroy()
        if not query or not self.all_channel_names:
            self.results_frame.pack_forget()
            return
        matches = [n for n in self.all_channel_names if query.lower() in n.lower()][:20]
        if not matches:
            self.results_frame.pack(fill="x", padx=15, pady=(0, 4), before=self.sel_row)
            ctk.CTkLabel(self.results_frame, text="No matches.", text_color="gray").pack(pady=6)
            return
        self.results_frame.pack(fill="x", padx=15, pady=(0, 4), before=self.sel_row)
        for name in matches:
            ctk.CTkButton(
                self.results_frame, text=name, anchor="w",
                fg_color="transparent", hover_color="#484949", height=28,
                command=lambda n=name: self._select_channel(n),
            ).pack(fill="x", pady=1, padx=2)
        self._bind_scroll_tree(self.results_frame)

    def _select_channel(self, name):
        self.selected_channel_name = name
        self.selected_channel_id   = self.channel_map.get(name)
        self.selected_label.configure(text=f"Selected: {name}", text_color="white")
        self.preview_btn.configure(state="normal")
        self.save_btn.configure(state="normal")
        self._update_save_btn_state()
        self.search_entry.delete(0, "end")
        for w in self.results_frame.winfo_children():
            w.destroy()
        self.results_frame.pack_forget()
        self._epg_channel_id = self.selected_channel_id
        self._epg_result = None
        self._show_epg_loading()
        threading.Thread(target=self._fetch_epg, args=(self.selected_channel_id,), daemon=True).start()

    # ── Backup Channel Search ─────────────────────────────────────────────────

    def _on_backup_search_key(self, event=None):
        query = self.backup_search_entry.get().strip()
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        if not query or not self.all_channel_names:
            self.backup_results_frame.pack_forget()
            return
        matches = [n for n in self.all_channel_names if query.lower() in n.lower()][:20]
        if not matches:
            self.backup_results_frame.pack(fill="x", pady=(0, 4), before=self._backup_results_anchor)
            ctk.CTkLabel(self.backup_results_frame, text="No matches.", text_color="gray").pack(pady=6)
            return
        self.backup_results_frame.pack(fill="x", pady=(0, 4), before=self._backup_results_anchor)
        for name in matches:
            ctk.CTkButton(
                self.backup_results_frame, text=name, anchor="w",
                fg_color="transparent", hover_color="#484949", height=28,
                command=lambda n=name: self._select_backup_channel(n),
            ).pack(fill="x", pady=1, padx=2)
        self._bind_scroll_tree(self.backup_results_frame)

    def _select_backup_channel(self, name):
        self.backup_channel_name = name
        self.backup_channel_id   = self.channel_map.get(name)
        self.backup_sel_label.configure(text=f"Backup: {name}", text_color="#3498db")
        self.backup_clear_btn.configure(state="normal")
        self.backup_search_entry.delete(0, "end")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()

    def _toggle_backup_section(self):
        self._backup_expanded = not self._backup_expanded
        if self._backup_expanded:
            self._backup_body.pack(fill="x")
            self._backup_toggle_btn.configure(text="▼  Backup Channel")
        else:
            self._backup_body.pack_forget()
            self._backup_toggle_btn.configure(text="▶  Backup Channel")

    def _clear_backup_channel(self):
        self.backup_channel_name = None
        self.backup_channel_id   = None
        self.backup_sel_label.configure(text="No backup selected", text_color="gray40")
        self.backup_clear_btn.configure(state="disabled")
        self.backup_search_entry.delete(0, "end")
        for w in self.backup_results_frame.winfo_children():
            w.destroy()
        self.backup_results_frame.pack_forget()

    # ── Live Sports ───────────────────────────────────────────────────────────

    def _toggle_sports_section(self):
        self._sports_expanded = not self._sports_expanded
        if self._sports_expanded:
            self._sports_body.pack(fill="x")
            self._sports_toggle_btn.configure(text="▼  Live Sports Today")
            if not self.sports_scroll.winfo_children():
                self._fetch_sports()
        else:
            self._sports_body.pack_forget()
            self._sports_toggle_btn.configure(text="▶  Live Sports Today")

    def _fetch_sports(self, *args):
        league = self._sports_league.get()
        for w in self.sports_scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.sports_scroll, text=f"Loading {league} schedule...", text_color="gray").pack(pady=10)

        def task():
            sport_map = {"NHL": "hockey/nhl", "NBA": "basketball/nba", "NFL": "football/nfl", "MLB": "baseball/mlb"}
            # Explicitly request today's date to prevent ESPN from automatically rolling forward to tomorrow's games
            today_str = datetime.datetime.now().strftime("%Y%m%d")
            url = f"https://site.api.espn.com/apis/site/v2/sports/{sport_map[league]}/scoreboard?dates={today_str}"
            try:
                r = requests.get(url, timeout=8)
                data = r.json()
                events = data.get("events", [])
                self.after(0, lambda: self._render_sports(events, league))
            except Exception as e:
                self.after(0, lambda: self._render_sports_error(str(e)))
        threading.Thread(target=task, daemon=True).start()

    def _render_sports_error(self, err):
        for w in self.sports_scroll.winfo_children(): w.destroy()
        ctk.CTkLabel(self.sports_scroll, text=f"Error loading schedule:\n{err}", text_color="#e74c3c").pack(pady=10)

    def _render_sports(self, events, league):
        for w in self.sports_scroll.winfo_children(): w.destroy()
        if not events:
            ctk.CTkLabel(self.sports_scroll, text="No games scheduled for today.", text_color="gray").pack(pady=10)
            return

        durations = {"NHL": 210, "NBA": 180, "NFL": 240, "MLB": 240}
        default_dur = durations.get(league, 210)

        today = datetime.date.today()
        todays_events = []

        for event in events:
            name = event.get("shortName", event.get("name", "Unknown Game"))
            date_str = event.get("date", "")
            local_time = ""
            local_dt = None
            try:
                ds = date_str.replace("Z", "+00:00")
                utc_dt = datetime.datetime.fromisoformat(ds)
                local_dt = utc_dt.astimezone()
                local_time = local_dt.strftime("%I:%M %p")
            except Exception:
                try:
                    utc_dt = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%MZ")
                    utc_dt = utc_dt.replace(tzinfo=datetime.timezone.utc)
                    local_dt = utc_dt.astimezone()
                    local_time = local_dt.strftime("%I:%M %p")
                except Exception:
                    local_time = "Unknown Time"

            # Filter out games that don't match today's local date
            if local_dt and local_dt.date() != today:
                continue

            todays_events.append((event, local_dt, local_time, name))

        if not todays_events:
            ctk.CTkLabel(self.sports_scroll, text="No games scheduled for today.", text_color="gray").pack(pady=10)
            return

        for event, local_dt, local_time, name in todays_events:
            status = event.get("status", {}).get("type", {}).get("description", "")
            if "In Progress" in status or "Halftime" in status:
                local_time = "LIVE NOW"
            elif "Final" in status:
                local_time = "FINAL"

            card = ctk.CTkFrame(self.sports_scroll, fg_color="#3a3b3b", corner_radius=6)
            card.pack(fill="x", pady=3, padx=4)

            top = ctk.CTkFrame(card, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkLabel(top, text=name, font=("Arial", 12, "bold"), anchor="w").pack(side="left")
            ctk.CTkLabel(top, text=local_time, font=("Arial", 11), text_color="#aaaaaa").pack(side="right")

            bot = ctk.CTkFrame(card, fg_color="transparent")
            bot.pack(fill="x", padx=8, pady=(0, 6))

            networks = []
            try:
                for b in event.get("competitions", [{}])[0].get("broadcasts", []):
                    for n in b.get("names", []):
                        networks.append(n)
            except Exception:
                pass

            networks = list(dict.fromkeys(networks))

            if networks:
                ctk.CTkLabel(bot, text="Find TV:", font=("Arial", 10), text_color="gray").pack(side="left", padx=(0, 6))
                for net in networks:
                    btn = ctk.CTkButton(bot, text=net, width=40, height=20, font=("Arial", 10),
                                        fg_color="#2563eb", hover_color="#1d4ed8",
                                        command=lambda n=net, dt=local_dt, d=default_dur: self._apply_sport_game(n, dt, d))
                    btn.pack(side="left", padx=2)

            # Team search fallback/addition
            search_str = name.replace("@", "").replace("VS", "").strip()
            t_btn = ctk.CTkButton(bot, text="Search Teams" if networks else "Find by Team", width=60, height=20, font=("Arial", 10),
                                  fg_color="#484949", hover_color="#575959",
                                  command=lambda s=search_str, dt=local_dt, d=default_dur: self._apply_sport_game(s, dt, d))
            t_btn.pack(side="right", padx=2)
        
        self._bind_scroll_tree(self.sports_scroll)

    def _apply_sport_game(self, query, start_dt, duration):
        if start_dt:
            self._set_epg_time(start_dt.strftime("%I:%M %p"), duration)
        self.search_entry.configure(state="normal")
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, query)
        self._on_search_key()
        self._log(f"Pre-filled schedule info for: {query}")

    # ── EPG ───────────────────────────────────────────────────────────────────

    def _toggle_epg_section(self):
        self._epg_expanded = not self._epg_expanded
        if self._epg_expanded:
            self._epg_wrapper.pack(fill="x", padx=15, pady=(0, 6))
            self._epg_toggle_btn.configure(text="▼  Program Guide")
        else:
            self._epg_wrapper.pack_forget()
            # Restore ✓ if there's guide data loaded
            has_data = bool(self.epg_frame.winfo_children())
            self._epg_toggle_btn.configure(
                text="▶  Program Guide  ✓" if has_data else "▶  Program Guide"
            )

    def _fetch_epg(self, channel_id):
        try:
            self._epg_result = (
                channel_id,
                fetch_epg(SERVER_URL, USERNAME, PASSWORD, channel_id, limit=16),
            )
        except Exception:
            self._epg_result = (channel_id, None)

    def _decode_epg(self, text):
        import base64
        try:
            return base64.b64decode(text).decode("utf-8").strip()
        except Exception:
            return str(text).strip()

    def _show_epg_loading(self):
        for w in self.epg_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self.epg_frame, text="Fetching program guide…", text_color="gray").pack(pady=8, padx=10)

    def _show_epg(self, channel_id, listings):
        if channel_id != self._epg_channel_id:
            return
        for w in self.epg_frame.winfo_children():
            w.destroy()
        if not listings:
            ctk.CTkLabel(self.epg_frame, text="No guide data available.", text_color="gray").pack(pady=8, padx=10)
            self._epg_toggle_btn.configure(text="▶  Program Guide")
            return
        self._epg_toggle_btn.configure(text="▶  Program Guide  ✓")
        now = datetime.datetime.now()
        first = True
        for listing in listings:
            try:
                start = datetime.datetime.fromtimestamp(int(listing["start_timestamp"]))
                stop  = datetime.datetime.fromtimestamp(int(listing["stop_timestamp"]))
            except Exception:
                continue
            title     = self._decode_epg(listing.get("title", ""))
            desc      = self._decode_epg(listing.get("description", ""))
            is_now    = start <= now < stop
            start_str = start.strftime("%I:%M %p")
            duration_mins = max(1, int((stop - start).total_seconds() / 60))
            row = ctk.CTkFrame(self.epg_frame, fg_color="#444545" if is_now else "transparent")
            row.pack(fill="x", padx=6, pady=(4 if first else 1, 1))
            first = False
            hdr = ctk.CTkFrame(row, fg_color="transparent")
            hdr.pack(fill="x", padx=8, pady=(4, 0))
            if is_now:
                ctk.CTkLabel(hdr, text=" NOW ", font=("Arial", 10, "bold"),
                             fg_color="#e74c3c", corner_radius=4, text_color="white").pack(side="left", padx=(0, 6))
            ctk.CTkLabel(hdr, text=f"{start.strftime('%I:%M %p')} – {stop.strftime('%I:%M %p')}",
                         text_color="#aaaaaa", font=("Arial", 11)).pack(side="left")
            ctk.CTkButton(
                hdr, text="Set Time", width=66, height=22,
                fg_color="#575959", hover_color="#636666", font=("Arial", 10),
                command=lambda s=start_str, d=duration_mins: self._set_epg_time(s, d)
            ).pack(side="right")
            ctk.CTkLabel(row, text=title, anchor="w",
                         font=("Arial", 12, "bold" if is_now else "normal")).pack(fill="x", padx=8, pady=(0, 2))
            if desc:
                ctk.CTkLabel(row, text=desc[:100] + ("…" if len(desc) > 100 else ""),
                             anchor="w", text_color="gray", wraplength=440,
                             font=("Arial", 10)).pack(fill="x", padx=8, pady=(0, 4))
        self._bind_scroll_tree(self.epg_frame)

    # ── Stream Preview ────────────────────────────────────────────────────────

    def _preview_stream(self):
        if not self.selected_channel_id:
            return
        stream_url = f"{SERVER_URL}/live/{USERNAME}/{PASSWORD}/{self.selected_channel_id}.ts"
        try:
            subprocess.Popen(
                ["ffplay", "-window_title", f"Preview: {self.selected_channel_name}", stream_url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **_SUBPROCESS_FLAGS,
            )
            self._log(f"Preview launched: '{self.selected_channel_name}'")
        except FileNotFoundError:
            self._log("Error: ffplay not found. It ships with FFmpeg — check your PATH.")

    # ── Folder & M3U ─────────────────────────────────────────────────────────

    def _pick_folder(self):
        folder = fd.askdirectory(initialdir=self.output_dir)
        if folder:
            self.output_dir = folder
            self.folder_label.configure(text=folder)
            self._save_settings()

    def _open_output_folder(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(self.output_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self.output_dir])
        else:
            subprocess.Popen(["xdg-open", self.output_dir])

    def _save_m3u(self):
        if not self.m3u_text:
            return
        path = fd.asksaveasfilename(
            initialdir=self.output_dir, defaultextension=".m3u",
            filetypes=[("M3U Playlist", "*.m3u"), ("All files", "*.*")],
            initialfile="Playlist.m3u",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.m3u_text)
            self._log(f"M3U saved: {path}")
            self.global_status.configure(text="Playlist saved!", text_color="#2ecc71")

    # ── Scheduling ───────────────────────────────────────────────────────────

    def _record_now(self):
        if not self.selected_channel_id:
            self._set_status("Error: Search and select a channel first.", "red"); return
        try:
            duration_mins = int(self.duration_input.get().strip())
            if duration_mins <= 0: raise ValueError
        except ValueError:
            self._set_status("Error: Duration must be a positive number.", "red"); return
        now = datetime.datetime.now()
        job = RecordingJob(self.selected_channel_name, self.selected_channel_id,
                           now, duration_mins, self.output_dir)
        job.backup_channel_id   = self.backup_channel_id
        job.backup_channel_name = self.backup_channel_name
        self.recording_jobs.append(job)
        self._add_recording_card(job)
        backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
        self._log(f"Started recording '{job.channel_name}' for {duration_mins} min.{backup_info}")
        self._set_status(f"Recording: {job.channel_name}", "#e74c3c")
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()

    def _schedule_recording(self):
        if not self.selected_channel_id:
            self._set_status("Error: Search and select a channel first.", "red"); return
        start_time_str = self.time_input.get().strip()
        if not start_time_str:
            self._set_status("Error: Enter a start time.", "red"); return
        try:
            duration_mins = int(self.duration_input.get().strip())
            if duration_mins <= 0: raise ValueError
        except ValueError:
            self._set_status("Error: Duration must be a positive number.", "red"); return
        now = datetime.datetime.now()
        try:
            start_time = datetime.datetime.strptime(start_time_str, "%I:%M %p").replace(
                year=now.year, month=now.month, day=now.day
            )
        except ValueError:
            self._set_status("Error: Use format  07:00 PM", "red"); return
        if start_time < now:
            start_time += datetime.timedelta(days=1)
        job = RecordingJob(self.selected_channel_name, self.selected_channel_id,
                           start_time, duration_mins, self.output_dir)
        job.backup_channel_id   = self.backup_channel_id
        job.backup_channel_name = self.backup_channel_name
        self.recording_jobs.append(job)
        self._add_recording_card(job)
        backup_info = f"  Backup: '{self.backup_channel_name}'" if self.backup_channel_name else ""
        self._log(f"Scheduled '{job.channel_name}' at {start_time.strftime('%I:%M %p')} for {duration_mins} min.{backup_info}")
        self._set_status(f"Scheduled: {job.channel_name} at {start_time_str}", "#2ecc71")
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()

    # ── Recording Cards ───────────────────────────────────────────────────────

    def _add_recording_card(self, job):
        self.no_recordings_label.pack_forget()
        card = ctk.CTkFrame(self.recordings_frame, corner_radius=8)
        card.pack(fill="x", pady=4, padx=2)
        job.card_frame = card
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(top, text=job.channel_name, font=("Arial", 13, "bold"), anchor="w").pack(side="left")
        job.stop_btn = ctk.CTkButton(top, text="Stop", width=58, height=24,
                                     fg_color="#c0392b", hover_color="#e74c3c",
                                     command=lambda j=job: self._stop_job(j))
        job.stop_btn.pack(side="right")
        ctk.CTkLabel(card, anchor="w", text_color="gray",
                     text=f"Scheduled: {job.start_time.strftime('%I:%M %p')}  |  Duration: {job.duration_mins} min"
                     ).pack(fill="x", padx=10, pady=(0, 2))
        job.status_label = ctk.CTkLabel(card, text="Waiting to start…", text_color="#f39c12", anchor="w")
        job.status_label.pack(fill="x", padx=10, pady=(0, 8))
        self._bind_scroll_tree(self.recordings_frame)

    # ── Tick ─────────────────────────────────────────────────────────────────

    def _tick(self):
        now = datetime.datetime.now()

        # Poll channel fetch
        if not self._channels_loaded:
            result = self._fetch_result
            if result is not None:
                if result[0] == "ok": self._on_channels_loaded(result[1])
                else:                 self._on_channels_error(result[1])
            else:
                elapsed = int((now - self._fetch_start).total_seconds())
                self.global_status.configure(text=f"Fetching channel list… ({elapsed}s)", text_color="gray")

        # Poll EPG
        epg = self._epg_result
        if epg is not None:
            self._epg_result = None
            self._show_epg(epg[0], epg[1])

        # Drain tunnel output lines into the log (lets us see exactly what instatunnel prints)
        while self._tunnel_lines:
            self._log(f"[Tunnel] {self._tunnel_lines.pop(0)}")

        # Poll tunnel URL / errors from background thread
        tunnel_url = self._tunnel_url
        if tunnel_url is not None:
            self._tunnel_url = None
            self.current_remote_url = tunnel_url
            self.remote_label.configure(text=f"Remote (public): {tunnel_url}", text_color="#3498db")
            self._log(f"[Tunnel] URL active: {tunnel_url}")
        tunnel_log = self._tunnel_log
        if tunnel_log is not None:
            self._tunnel_log = None
            self._log(tunnel_log)

        # Process web actions
        self._process_web_actions()

        # Update recording cards
        for job in self.recording_jobs:
            while job._pending_logs:
                self._log(job._pending_logs.pop(0))
            if job.status_label is None:
                continue
            if job.finish_msg is not None:
                msg, color = job.finish_msg
                job.finish_msg = None
                self._finalize_card(job, msg, color)
                self._log(f"{msg} '{job.channel_name}'")
                if self._status_text == f"Recording: {job.channel_name}":
                    self._set_status(f"Recording finished: {job.channel_name}", "#2ecc71")
                continue
            if job.status == "waiting":
                secs = max(0, int((job.start_time - now).total_seconds()))
                job.status_label.configure(
                    text=f"Starts in {str(datetime.timedelta(seconds=secs))}", text_color="#f39c12")
            elif job.status == "recording" and job.actual_start:
                elapsed   = int((now - job.actual_start).total_seconds())
                remaining = max(0, job.duration_mins * 60 - elapsed)
                on_bkup      = job.active_channel_name != job.channel_name
                backup_str   = f"[BACKUP: {job.active_channel_name}]  " if on_bkup else ""
                reconnect_str = f"  |  Reconnects: {job.reconnect_count}" if job.reconnect_count > 0 else ""
                job.status_label.configure(
                    text=f"{backup_str}RECORDING  |  Elapsed: {str(datetime.timedelta(seconds=elapsed))}  |  Remaining: {str(datetime.timedelta(seconds=remaining))}{reconnect_str}",
                    text_color="#e74c3c")

        self.after(1000, self._tick)

    # ── Job Execution ─────────────────────────────────────────────────────────

    def _run_job(self, job):
        wait_secs = (job.start_time - datetime.datetime.now()).total_seconds()
        if wait_secs > 0:
            time.sleep(wait_secs)
        if job.status == "stopped":
            return

        job.status       = "recording"
        job.actual_start = datetime.datetime.now()
        date_str   = job.actual_start.strftime("%Y-%m-%d_%H-%M")
        safe_name  = "".join(c if c.isalnum() or c in " -_" else "_" for c in job.channel_name)[:60].strip()
        base_path  = os.path.join(job.output_dir, f"{safe_name}_{date_str}")

        active_id         = job.channel_id
        on_backup         = False
        fail_streak_start = None
        segment           = 0

        while job.status == "recording":
            elapsed   = (datetime.datetime.now() - job.actual_start).total_seconds()
            remaining = job.duration_mins * 60 - elapsed
            if remaining <= 3:
                break  # close enough to the end — done

            stream_url = f"{SERVER_URL.rstrip('/')}/live/{USERNAME}/{PASSWORD}/{active_id}.ts"
            out = f"{base_path}.ts" if segment == 0 else f"{base_path}_part{segment}.ts"
            job.output_file = out

            cmd = [
                "ffmpeg", "-y",
                # FFmpeg-level reconnect (handles transient packet loss mid-stream)
                "-reconnect", "1",
                "-reconnect_at_eof", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",    # seconds between retries (was 2000 — wrong!)
                "-timeout", "15000000",          # 15s socket read timeout (microseconds)
                "-i", stream_url,
                "-t", str(int(remaining)),
                "-c", "copy",
                out,
            ]

            try:
                job.process = subprocess.Popen(
                    cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    **_SUBPROCESS_FLAGS,
                )
                _, stderr_bytes = job.process.communicate()
                retcode = job.process.returncode
                if retcode != 0 and stderr_bytes:
                    err_text = stderr_bytes[-8192:].decode("utf-8", errors="replace")
                    lines = err_text.splitlines()
                    # Prefer lines that look like real errors over the banner
                    _ERR_KW = ("error", "invalid", "refused", "failed",
                               "forbidden", "unauthorized", "404", "403",
                               "401", "no such", "timeout", "unable")
                    err_lines = [l.strip() for l in lines
                                 if l.strip() and any(k in l.lower() for k in _ERR_KW)]
                    if err_lines:
                        job._pending_logs.append(f"ffmpeg error: {err_lines[-1]}")
                    else:
                        # Fallback: last non-empty non-banner line
                        non_banner = [l.strip() for l in lines
                                      if l.strip() and not l.startswith("  lib")]
                        if non_banner:
                            job._pending_logs.append(f"ffmpeg: {non_banner[-1]}")
            except FileNotFoundError:
                job.status     = "error"
                job.finish_msg = ("Error: ffmpeg not found in PATH.", "red")
                return
            except Exception as e:
                job.status     = "error"
                job.finish_msg = (f"Error: {e}", "red")
                return

            if job.status == "stopped":
                return

            elapsed   = (datetime.datetime.now() - job.actual_start).total_seconds()
            remaining = job.duration_mins * 60 - elapsed

            if remaining <= 3:
                break  # finished on schedule

            if retcode != 0:
                # FFmpeg exited with an error before the recording was done.
                segment             += 1
                job.reconnect_count += 1

                if fail_streak_start is None:
                    fail_streak_start = time.time()
                elif (not on_backup and job.backup_channel_id
                      and time.time() - fail_streak_start >= 120):
                    # Primary has been down >2 min — switch to backup channel
                    on_backup              = True
                    active_id              = job.backup_channel_id
                    job.active_channel_name = job.backup_channel_name
                    fail_streak_start      = None
                    job._pending_logs.append(
                        f"Primary '{job.channel_name}' down >2 min — switching to backup '{job.backup_channel_name}'"
                    )

                time.sleep(4)
                # loop continues — ffmpeg restarts with updated remaining time and channel
            else:
                fail_streak_start = None
                break  # clean exit, recording complete

        if job.status == "recording":
            # ── Merge parts if FFmpeg restarted during the recording ──────────────
            if segment > 0:
                parts = (
                    [f"{base_path}.ts"] +
                    [f"{base_path}_part{i}.ts" for i in range(1, segment + 1)]
                )
                parts = [p for p in parts if os.path.exists(p) and os.path.getsize(p) > 0]

                if len(parts) > 1:
                    concat_txt = base_path + "_concat.txt"
                    merged_tmp = base_path + "_merged.ts"
                    merged_ok  = False
                    try:
                        with open(concat_txt, "w") as f:
                            for p in parts:
                                # FFmpeg concat requires single-quotes escaped
                                escaped = p.replace("'", "'\\''")
                                f.write(f"file '{escaped}'\n")
                        merge_cmd = [
                            "ffmpeg", "-y",
                            "-f", "concat", "-safe", "0",
                            "-i", concat_txt,
                            "-c", "copy",
                            merged_tmp,
                        ]
                        subprocess.run(merge_cmd,
                                       stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL,
                                       **_SUBPROCESS_FLAGS)
                        if os.path.exists(merged_tmp) and os.path.getsize(merged_tmp) > 0:
                            final = f"{base_path}.ts"
                            os.replace(merged_tmp, final)
                            for p in parts[1:]:   # delete _part files; parts[0] was overwritten
                                try: os.remove(p)
                                except OSError: pass
                            job.output_file = final
                            merged_ok = True
                    except Exception:
                        pass
                    finally:
                        try: os.remove(concat_txt)
                        except OSError: pass
                        try: os.remove(merged_tmp)   # clean up temp if merge failed
                        except OSError: pass

                    if merged_ok:
                        n = len(parts)
                        job.finish_msg = (f"Recording finished ({n} parts merged).", "#2ecc71")
                    else:
                        job.finish_msg = (
                            f"Recording finished — {len(parts)} parts (merge failed, kept separately).",
                            "#e67e22",
                        )
                else:
                    job.finish_msg = ("Recording finished.", "#2ecc71")
            else:
                job.finish_msg = ("Recording finished.", "#2ecc71")

            job.status = "complete"

    def _stop_job(self, job):
        if job.status in ("complete", "stopped", "error"):
            return
        job.status = "stopped"
        if job.process and job.process.poll() is None:
            job.process.terminate()
        self._finalize_card(job, "Stopped by user.", "#e67e22")
        self._log(f"User stopped: '{job.channel_name}'")
        if self._status_text == f"Recording: {job.channel_name}":
            self._set_status(f"Stopped: {job.channel_name}", "#e67e22")

    def _finalize_card(self, job, message, color):
        if job.status_label: job.status_label.configure(text=message, text_color=color)
        if job.stop_btn:     job.stop_btn.configure(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _on_closing(self):
        if self.tunnel_process:
            try:
                self.tunnel_process.terminate()
            except Exception:
                pass
        for job in self.recording_jobs:
            if job.status == "recording" and job.process:
                try:
                    job.process.terminate()
                except Exception:
                    pass
        self.destroy()
        sys.exit(0)

    def _log(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self.log_box.configure(state="normal")
        self.log_box.insert("end", entry + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        self._log_entries.append(entry)
        if len(self._log_entries) > 200:
            self._log_entries.pop(0)

    def _set_epg_time(self, time_str, duration_mins=None):
        self.time_input.delete(0, "end")
        self.time_input.insert(0, time_str)
        if duration_mins is not None:
            self.duration_input.delete(0, "end")
            self.duration_input.insert(0, str(duration_mins))

    def _set_status(self, message, color="gray"):
        self._status_text = message
        self.global_status.configure(text=message, text_color=color)

    def _copy_remote_url(self):
        if self.current_remote_url:
            self.clipboard_clear()
            self.clipboard_append(self.current_remote_url)
            self.update()
            self._log("Remote URL copied to clipboard.")
            self.remote_copy_btn.configure(text="Copied!", fg_color="#1a6b3a")
            self.after(2000, lambda: self.remote_copy_btn.configure(text="Copy", fg_color="#575959"))

    def _bind_scroll_tree(self, _scrollable_frame):
        """No-op — scrolling handled by _install_window_scroll."""
        pass

    def _install_window_scroll(self):
        """Bind MouseWheel on the root window. Walk up from the widget under
        the cursor to find the nearest CTkScrollableFrame canvas and scroll it."""

        def _find_scrollable_canvas(widget):
            """Walk up the widget tree until we find a CTkScrollableFrame's canvas."""
            while widget is not None:
                try:
                    if hasattr(widget, '_parent_canvas') and hasattr(widget, 'check_if_master_is_canvas'):
                        return widget._parent_canvas
                except Exception:
                    pass
                try:
                    parent = widget.master
                except Exception:
                    break
                if parent == widget:
                    break
                widget = parent
            return None

        def _on_mousewheel(event):
            # Find the widget directly under the cursor
            try:
                w = event.widget.winfo_containing(event.x_root, event.y_root)
            except Exception:
                return
            if w is None:
                return

            canvas = _find_scrollable_canvas(w)
            if canvas is None:
                return

            # Already fully visible — nothing to scroll
            if canvas.yview() == (0.0, 1.0):
                return

            if sys.platform == "darwin":
                canvas.yview_scroll(-event.delta, "units")
            elif sys.platform.startswith("win"):
                canvas.yview_scroll(-int(event.delta / 120), "units")
            else:
                # Linux Button-4/5 handled separately
                canvas.yview_scroll(-event.delta, "units")

        self.bind_all("<MouseWheel>", _on_mousewheel)
        # Linux
        self.bind_all("<Button-4>", lambda e: _on_mousewheel(type('E', (), {'widget': e.widget, 'x_root': e.x_root, 'y_root': e.y_root, 'delta': 1})))
        self.bind_all("<Button-5>", lambda e: _on_mousewheel(type('E', (), {'widget': e.widget, 'x_root': e.x_root, 'y_root': e.y_root, 'delta': -1})))


if __name__ == "__main__":
    _load_saved_credentials()   # override hardcoded defaults with saved credentials
    if not _check_ffmpeg():
        sys.exit(0)
    app = IPTVRecorderApp()
    app.mainloop()
