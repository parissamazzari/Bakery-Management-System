# --- Order-processing worker ------------------------------------------------
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev findutils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser . .
USER appuser

# Healthcheck: the worker has no HTTP port, so we check that the heartbeat
# file the main loop writes every 5s has been updated in the last 30s.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD find /tmp/worker_heartbeat -mmin -0.5 | grep -q worker_heartbeat || exit 1

CMD ["python", "worker.py"]
