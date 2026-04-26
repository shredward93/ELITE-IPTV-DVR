# ELITE IPTV DVR — Kodi Setup Guide

### 1. PVR IPTV Simple Client

Add-ons → Install from repository → **PVR IPTV Simple Client** → Install → Configure

**General tab:**
- Location: `Remote path (Internet address)`
- M3U URL: `https://server.eliteiptvdvr.uk/kodi/playlist.m3u`

**EPG tab:**
- Location: `Remote path (Internet address)`
- XMLTV URL: `https://server.eliteiptvdvr.uk/kodi/guide.xml`
- Ignore Case for EPG Channel IDs: **On**

**Timeshift tab:**
- Enable timeshift: **On**
- Enable timeshift for all streams: **On**
- Click **Modify inputstream.ffmpegdirect settings…**
  - Timeshift buffer path: `special://../../../timeshift`
  - Enable timeshift limit: **On**
  - Maximum timeshift buffer length: `1.00 hours`

OK → Enable when prompted.

---

### 2. Recordings Folder

Videos → Files → **Add videos…** → Browse → **Network location**

- Protocol: **HTTP**
- Server: `server.eliteiptvdvr.uk`
- Port: `80`
- Path: `/recordings/`

Name it **DVR Recordings** → Set content to **None** → OK

---

### 3. Timeshift (advanced — only if live TV crashes)

Create/edit `advancedsettings.xml` in Kodi's userdata folder:

```xml
<advancedsettings>
  <pvr>
    <timeshiftenabled>true</timeshiftenabled>
    <timeshiftpath>special://temp/</timeshiftpath>
    <timeshiftMaxSize>1073741824</timeshiftMaxSize>
    <cacheMemSize>20971520</cacheMemSize>
  </pvr>
</advancedsettings>
```
