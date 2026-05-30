# Delineo Simulation
# Two services share this image (different CMD in docker-compose):
#   - simulation: Flask server on port 1870
#   - dmp:        FastAPI/uvicorn on port 8000

FROM python:3.13-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Default: run the simulation server (override in compose for DMP).
#
# Use gunicorn with multiple worker PROCESSES rather than the Flask dev server.
# A simulation is CPU-bound Python, so threads share one GIL and concurrent sims
# serialize onto a single core; separate worker processes run them on separate
# cores. WEB_CONCURRENCY sets the worker count (override per host/core count).
# --timeout 0 disables the worker timeout: each POST /simulation/ streams Server-
# Sent Events for the full run, so a non-zero timeout would kill long sims.
#
# The entry module is server.py, NOT app.py. gunicorn imports its target as a
# top-level module, and a module named `app` would shadow the dmp/app package,
# making `InProcessDMP()` raise and silently fall back to the slow per-infection
# HTTP path. `server:app` keeps the top-level name `app` free for dmp/app.
EXPOSE 1870
ENV WEB_CONCURRENCY=4
CMD ["gunicorn", "--worker-class", "sync", "--timeout", "0", "--bind", "0.0.0.0:1870", "server:app"]
