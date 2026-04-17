# ELITE IPTV DVR - Docker/NAS Deployment

Docker configuration for running ELITE IPTV DVR on NAS systems (Synology, TrueNAS, QNAP, etc.) or any Docker-capable server.

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/yourusername/ELITE-IPTV-DVR.git
cd ELITE-IPTV-DVR/docker

# Copy and edit the environment file
cp .env.example .env
nano .env  # or use any text editor
```

Edit `.env` with your:
- **Recordings path** (where your NAS stores videos)
- **IPTV provider credentials** (XtreamCodes)
- **Cloudflare Tunnel token** (optional, for remote access)

### 2. Build and Run

**Option A: Local Network Only** (simplest)
```bash
docker-compose -f docker-compose.simple.yml up -d
```

**Option B: With Cloudflare Tunnel** (public access)
```bash
# Named tunnel (persistent URL with your domain)
docker-compose --profile tunnel up -d
```

**Option C: Quick Tunnel** (temporary URL, good for testing)
```bash
docker-compose --profile quick-tunnel up -d
```

### 3. Access the Web UI

- **Local:** `http://your-nas-ip:8080`
- **Public (if using tunnel):** Check logs for the assigned URL

## NAS-Specific Instructions

### Synology DSM

1. Install **Container Manager** from Package Center
2. Enable SSH and connect to your NAS
3. Clone this repo and follow Quick Start above
4. For recordings path, use: `/volume1/video/recordings` (adjust volume number)
5. Consider using Synology's **Reverse Proxy** instead of Cloudflare Tunnel for local-only access

### TrueNAS Scale

1. Use the **Custom App** deployment in Apps catalog
2. Point to this Docker Compose configuration
3. Set up host path mounts for recordings storage pool

### QNAP Container Station

1. Create application from docker-compose.yml
2. Map shared folders for persistent data and recordings

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WEB_PORT` | No | Web UI port (default: 8080) |
| `RECORDINGS_PATH` | Yes | Where recordings are stored |
| `SERVER_URL` | Yes* | XtreamCodes provider URL |
| `USERNAME` | Yes* | Provider username |
| `PASSWORD` | Yes* | Provider password |
| `TUNNEL_PROVIDER` | No | Set to `cloudflare` to enable tunnel |
| `CLOUDFLARE_DOMAIN` | No | Your custom domain |
| `CLOUDFLARE_TUNNEL_TOKEN` | No | Token from Cloudflare dashboard |

*Required unless using `credentials.json` mount

### Volume Mounts

| Container Path | Description |
|----------------|-------------|
| `/recordings` | All DVR recordings saved here |
| `/app/data` | Persistent app data (credentials, favorites, schedules) |
| `/app/logs` | Application logs |

## Cloudflare Tunnel Setup

Same process as Windows setup:

1. Go to https://one.dash.cloudflare.com → Networks → Tunnels
2. Create a tunnel named `elite-dvr-nas`
3. Select **Docker** as environment, copy the token
4. Add public hostname pointing to `http://elite-dvr:8080`
5. Set `CLOUDFLARE_TUNNEL_TOKEN` in `.env` to the copied token
6. Run `docker-compose --profile tunnel up -d`

The cloudflared container runs as a sidecar — no host network mode needed.

## Updates

```bash
cd ELITE-IPTV-DVR/docker

# Pull latest code
git pull

# Rebuild and restart
docker-compose down
docker-compose --profile tunnel up -d --build
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Container won't start | Check `docker logs elite-dvr` for errors |
| Recordings not saving | Verify `RECORDINGS_PATH` exists and has correct permissions |
| Can't access web UI | Check firewall rules on NAS; verify port 8080 isn't blocked |
| Tunnel not connecting | Verify `CLOUDFLARE_TUNNEL_TOKEN` is correct and not expired |
| FFmpeg not found | Included in image; if missing, rebuild with `docker-compose build --no-cache` |

## File Structure

```
docker/
├── Dockerfile                    # Multi-stage build definition
├── docker-compose.yml            # Full setup with tunnel profiles
├── docker-compose.simple.yml     # Local network only
├── entrypoint.sh                 # Container startup script
├── .env.example                  # Template environment file
└── README.md                     # This file
```
