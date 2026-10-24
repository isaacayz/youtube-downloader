FROM python:3.11-slim

# Create unprivileged user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/sh -m appuser

WORKDIR /app

ENV PYTHONPATH=/app

# Install system dependencies including FFmpeg, ffprobe, and Node.js runtime for yt-dlp EJS
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY apps/worker/pyproject.toml /app/pyproject.toml
COPY apps/worker/README.md /app/README.md
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY apps/worker /app
RUN chmod +x /app/entrypoint.sh

# Create staging and downloads directories with appuser ownership
RUN mkdir -p /staging /downloads && \
    chown -R appuser:appuser /staging /downloads /app

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
