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

# Default: run the simulation server (override in compose for DMP)
EXPOSE 1870
CMD ["python", "app.py"]
