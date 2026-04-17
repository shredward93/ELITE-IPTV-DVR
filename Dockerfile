# Dockerfile for ELITE IPTV DVR — Headless server for NAS deployment
# Synology Container Manager compatible

FROM python:3.11-slim-bookworm

# Install FFmpeg, curl, and cloudflared (for Cloudflare tunnel)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install cloudflared for Cloudflare tunnel
RUN curl -L --output /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
    && chmod +x /usr/local/bin/cloudflared

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY server_headless.py .
COPY core/ ./core/
COPY static/ ./static/

# Create directories for data and recordings
RUN mkdir -p /app/data /app/recordings

# Environment variables (can be overridden at runtime)
ENV SERVER_URL=""
ENV USERNAME=""
ENV PASSWORD=""
ENV TUNNEL_PROVIDER=""
ENV INSTATUNNEL_API_KEY=""
ENV INSTATUNNEL_SUBDOMAIN=""
ENV CLOUDFLARE_TUNNEL_TOKEN=""
ENV CLOUDFLARE_DOMAIN=""
ENV RECORDINGS_DIR="/app/recordings"
ENV PYTHONUNBUFFERED=1

# Expose web server port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/info || exit 1

# Run the headless server
CMD ["python", "server_headless.py"]
