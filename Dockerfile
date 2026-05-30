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
# A simulation is CPU-bound Python, so threads share one GIL and concurrent
# sims serialize onto a single core (each ~2x slower under load). Separate
# worker processes let concurrent sims run on separate cores.
#
#   - WEB_CONCURRENCY sets the number of workers (override per host/core count
#     in compose; defaults to 4 here).
#   - --timeout 0 disables the worker timeout. Each POST /simulation/ streams
#     Server-Sent Events for the full run duration, so a non-zero timeout would
#     kill long-running sims mid-stream.
EXPOSE 1870
ENV WEB_CONCURRENCY=4
CMD ["gunicorn", "--worker-class", "sync", "--timeout", "0", "--bind", "0.0.0.0:1870", "app:app"]
