# ELITE IPTV DVR - Docker Image
# Multi-stage build for smaller final image

FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 elite && mkdir -p /app /recordings && chown -R elite:elite /app /recordings

# Copy Python packages from builder
COPY --from=builder /root/.local /home/elite/.local
ENV PATH=/home/elite/.local/bin:$PATH

# Copy application code
WORKDIR /app
COPY --chown=elite:elite . .

# Create necessary directories
RUN mkdir -p /app/data /app/logs && chown -R elite:elite /app

# Switch to non-root user
USER elite

# Expose web port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Entry point
ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "-m", "main"]
