#!/bin/sh
# ELITE IPTV DVR Docker Entrypoint

set -e

# Create necessary directories if they don't exist
mkdir -p /app/data /app/logs /recordings

# Ensure proper permissions
chown -R elite:elite /app/data /app/logs /recordings 2>/dev/null || true

# Check if credentials file exists, if not create from env vars
if [ ! -f /app/data/credentials.json ] && [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
    echo "Creating credentials.json from environment variables..."
    cat > /app/data/credentials.json <<EOF
{
    "server_url": "${SERVER_URL}",
    "username": "${USERNAME}",
    "password": "${PASSWORD}",
    "tunnel_provider": "${TUNNEL_PROVIDER}",
    "cloudflare_domain": "${CLOUDFLARE_DOMAIN}",
    "cloudflare_tunnel_token": "${CLOUDFLARE_TUNNEL_TOKEN}"
}
EOF
fi

# Verify FFmpeg is available
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Warning: FFmpeg not found! Recordings will not work."
fi

echo "Starting ELITE IPTV DVR..."
echo "Web UI will be available at: http://localhost:8080"

# Execute the main command
exec "$@"
