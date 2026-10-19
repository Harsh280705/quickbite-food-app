# QuickBite backend image — shared by the API and every worker entry point.
FROM python:3.11.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# procps provides pgrep for container health checks.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r /app/requirements.lock.txt

COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY app /app/app
COPY scripts /app/scripts
COPY workers /app/workers
COPY static /app/static
COPY data/image_manifest.json /app/data/image_manifest.json

# Runs as a non-root user.
RUN useradd --create-home --uid 10001 quickbite \
    && chown -R quickbite:quickbite /app
USER quickbite

EXPOSE 8000

# Default command is overridden per compose service (workers use python -m).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
