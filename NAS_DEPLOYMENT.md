# ELITE IPTV DVR — Synology NAS Deployment Guide

## Quick Start

### Critical: Proper Folder Structure

**The #1 cause of build failures is incorrect folder structure.** Follow this exactly:

1. **Create project folder** on NAS: `/docker/eliteiptvdvr/`

2. **Upload root files first** (flat in the folder):
   - `Dockerfile`
   - `requirements.txt`
   - `server_headless.py`
   - `config.py`
   - `.dockerignore` (optional)
   - **NOT** `docker-compose.yml` (create this manually with your credentials)

3. **Create and upload subfolders** (files go INSIDE these):
   - Create `core/` folder → upload all files from PC's `core/` folder
   - Create `static/` folder → upload `remote.html` from PC's `static/`
   - Create `data/` folder (empty, for persistence)
   - Create `recordings/` folder (empty, for recordings)

4. **Verify structure** in File Station:
   ```
   eliteiptvdvr/
   ├── core/          ← folder with 10 .py files
   ├── static/        ← folder with remote.html
   ├── data/          ← empty folder
   ├── recordings/    ← empty folder
   ├── docker-compose.yml      ← Create this manually from docker-compose.yml.example
   ├── Dockerfile
   └── ...other root files
   ```

### Option 1: Docker Compose (Recommended)

1. **Set up files** as described above (git pull or manual copy)

2. **Create `docker-compose.yml` manually** (copy from `docker-compose.yml.example` and fill in your credentials):
   ```bash
   cp docker-compose.yml.example docker-compose.yml
   # Edit docker-compose.yml with your credentials
   ```

   Or create it directly with your credentials filled in.

   **IMPORTANT:** `docker-compose.yml` is in `.gitignore` and will NOT be pulled from GitHub. This protects your credentials.

3. **Run the container** in Container Manager or via SSH:
   ```bash
   cd /volume1/docker/eliteiptvdvr
   docker-compose up -d
   ```

4. **Verify** it's running:
   ```bash
   docker-compose logs -f
   ```

### Option 2: Synology Container Manager UI

1. Open **Container Manager** → **Project** → **Create**
2. Set path to where you copied the files
3. It will use `docker-compose.yml` automatically
4. Click **Build and Run**

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVER_URL` | Yes | Your IPTV provider URL |
| `USERNAME` | Yes | Provider username |
| `PASSWORD` | Yes | Provider password |
| `TUNNEL_PROVIDER` | No | `cloudflare` or `instatunnel` |
| `INSTATUNNEL_API_KEY` | No | InstaTunnel API key |
| `INSTATUNNEL_SUBDOMAIN` | No | Your InstaTunnel subdomain |
| `CLOUDFLARE_TUNNEL_TOKEN` | No | Cloudflare tunnel token (see below for setup) |
| `CLOUDFLARE_DOMAIN` | No | Your Cloudflare domain |

### Cloudflare Tunnel Setup (for Remote Access)

To access your DVR remotely (e.g., from a different location):

1. **In Cloudflare Zero Trust Dashboard**:
   - Go to https://one.dash.cloudflare.com/ → **Networks** → **Tunnels**
   - Create a tunnel or use existing
   - **Add a connector** (this generates a new token)

2. **Copy the NEW token**:
   - Look for the Docker command: `docker run ... --token eyJ...`
   - Copy the long `eyJ...` string (not the Connector ID)
   - **Important**: Tokens are one-time use per connector. Each new deployment needs a fresh token.

3. **Paste into docker-compose.yml**:
   ```yaml
   CLOUDFLARE_TUNNEL_TOKEN: "eyJhIjoi..."
   CLOUDFLARE_DOMAIN: "your-subdomain.yourdomain.com"
   ```

4. **Access your DVR remotely**:
   ```
   https://your-subdomain.yourdomain.com/api/info
   ```
| `RECORDINGS_DIR` | No | Where to save recordings (default: `/app/recordings`) |

### Volumes

| Container Path | Description |
|---------------|-------------|
| `/app/recordings` | Completed recordings |
| `/app/data` | Scheduled recordings persistence |
| `/app/credentials.json` | Alternative to env vars |

## Multi-User Setup

With the NAS deployment, all users share the same server:

1. **Edward's Kodi** → connects to NAS IP:8080
2. **Kurt's Kodi** → connects to NAS IP:8080
3. **Dad's Kodi** → connects to NAS IP:8080

**Stream Multiplexer**: When all 3 users watch the same hockey game, only 1 provider connection is used instead of 3.

## Kodi Configuration

1. Go to **Settings** → **PVR & Live TV** → **General**
2. Set **M3U playlist URL** to:
   ```
   http://YOUR-NAS-IP:8080/kodi/playlist.m3u
   ```
3. Set **XMLTV URL** to:
   ```
   http://YOUR-NAS-IP:8080/kodi/guide.xml
   ```
4. Enable **Recordings** path:
   ```
   http://YOUR-NAS-IP:8080/recordings
   ```

## Maintenance

### View logs
```bash
docker-compose logs -f
```

### Restart
```bash
docker-compose restart
```

### Update
```bash
docker-compose down
docker-compose pull  # if using registry
docker-compose up -d
```

### Backup recordings
Recordings are stored in the `./recordings` folder on your NAS. Back this up via Synology's normal backup tools.

## Troubleshooting

### Build Errors

**"COPY failed: file not found" or "no such file or directory"**
- **Cause**: `core/` or `static/` folders missing or uploaded as flat files
- **Fix**: Delete all files on NAS. Re-upload: root files first, then create `core/` and `static/` folders and upload files into them.

**"Bind mount failed: '/volume1/docker/eliteiptvdvr/data' does not exist"**
- **Cause**: `data/` and `recordings/` folders weren't created
- **Fix**: Create empty `data/` and `recordings/` folders in File Station before building

### Runtime Errors

**"cloudflared not found" in logs**
- **Cause**: Old Dockerfile without cloudflared
- **Fix**: Update Dockerfile to include cloudflared installation (see repo for latest)

**"Provided Tunnel token is not valid"**
- **Cause**: Reusing old token or using Connector ID instead of token
- **Fix**: In Cloudflare dashboard, click **Add connector** and copy the NEW `eyJ...` token (not the Connector ID)

**Container won't start**
- Check credentials are set correctly
- Verify port 8080 isn't already in use

**Can't connect from Kodi**
- Check NAS firewall allows port 8080
- Verify Container Manager port mapping

**Bad Gateway when accessing tunnel URL**
- Wait 30-60 seconds for tunnel to fully connect
- Check container logs for `[Tunnel] URL active:` message
- If token errors appear, refresh token in Cloudflare dashboard

**Recordings not saving**
- Check `./recordings` folder has write permissions
- Verify `RECORDINGS_DIR` env var

**Stream multiplexing not working**
- Verify all Kodis are using same channel_id
- Check logs for `StreamMuxer` messages
