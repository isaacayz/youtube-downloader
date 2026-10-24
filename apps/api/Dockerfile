FROM python:3.11-slim

# Create unprivileged user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/sh -m appuser

WORKDIR /app

ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy healthcheck script from infra
COPY infra/scripts/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

# Install python dependencies
COPY apps/api/pyproject.toml /app/pyproject.toml
COPY apps/api/README.md /app/README.md
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application source code
COPY apps/api /app
RUN chmod +x /app/entrypoint.sh

# Create staging and downloads directories with appuser ownership
RUN mkdir -p /staging /downloads && \
    chown -R appuser:appuser /staging /downloads /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
