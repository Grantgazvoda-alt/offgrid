# OffGrid — self-hosted batch AI engine. Small, no DB server.
FROM python:3.12-slim-bookworm

# Install tini for proper PID 1 signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

# Copy app code
COPY . .

# Create non-root user and data dirs
RUN groupadd -r offgrid && useradd -r -g offgrid -d /app -s /sbin/nologin offgrid \
    && mkdir -p /app/data /app/batches \
    && chown -R offgrid:offgrid /app

USER offgrid

ENV OFFGRID_DATA=/app/data \
    OFFGRID_BATCH_DIR=/app/batches \
    PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "app.py"]
