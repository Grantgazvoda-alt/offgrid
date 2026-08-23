# OffGrid — self-hosted batch AI engine. Small, no DB server.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt || \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# data and batches mountable volumes
VOLUME ["/app/data", "/app/batches"]

ENV OFFGRID_DATA=/app/data \
    OFFGRID_BATCH_DIR=/app/batches \
    PORT=8000

EXPOSE 8000

CMD ["python", "app.py"]