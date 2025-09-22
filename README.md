# Delineo Infection Simulator

End-to-end infection spread simulation with an external Disease Modeling Platform (DMP) for disease progression timelines. This repository contains:

- Flask-based simulator service (`app.py`) that runs simulations using logic in `simulator/`.
- FastAPI-based DMP service (`dmp/api/dmp_api.py`) that generates disease progression timelines from matrices and demographic mappings.
- Utilities for profiling, data management, and visualization.

---

## Repository Structure

- `dmp/`
  - `api/dmp_api.py`: FastAPI app exposing `/initialize` and `/simulate`.
  - `core/`, `cli/`, `app/`, `data/`: DMP core logic, CLI, optional Streamlit UI, and sample data.
  - `README.md`, `requirements.txt`

- `simulator/`
  - Core simulation engine and configuration.
  - `config.py`: Central configuration for server port, DMP base URL, default inputs, interventions.
  - Additional data under `simulator/config_data/`.

- Root files
  - `app.py`: Flask entrypoint that exposes `/simulation/` and `/`.
  - `requirements.txt`: Top-level dependency pins used by both services.
  - Profiling artifacts and various helper scripts.

---

## Dependencies

- Python 3.10+ (recommended)
- pip or another package manager

Install dependencies (root):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

Note on `uvicorn`:

- The root `requirements.txt` pins FastAPI but does not include `uvicorn`.
- You can either:
  - Install `uvicorn` directly: `pip install uvicorn`, or
  - Install DMP extras: `pip install -r dmp/requirements.txt`

Key packages (root `requirements.txt`): FastAPI, Flask, Flask-Cors, numpy, pandas, scipy, matplotlib, streamlit, pydantic, PyYAML, requests, werkzeug.

---

## Quick Start

1) Start the DMP API (FastAPI/uvicorn) in one terminal:

```bash
cd dmp
uvicorn api.dmp_api:app --reload
```

This starts the API at `http://localhost:8000`.

2) Start the Simulator server (Flask) in another terminal from the repository root:

```bash
python app.py
```

This starts the simulator at `http://0.0.0.0:1880` (see `simulator/config.py`).

---

## Running the DMP API

The DMP provides two endpoints:

- POST `/initialize` — Load matrices, mapping, and states
- POST `/simulate` — Run simulation given demographics

Example initialization (after starting uvicorn):

```bash
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{
        "matrices_path": "<absolute-or-repo-path>/Simulation/simulator/config_data/combined_matrices.csv",
        "mapping_path":  "<absolute-or-repo-path>/Simulation/simulator/config_data/demographic_mapping.csv",
        "states_path":   "<absolute-or-repo-path>/Simulation/simulator/config_data/custom_states.txt"
      }'
```

Notes:

- Default `states_path` is optional; if omitted, DMP uses `dmp/data/default_states.txt`.
- In `simulator/config.py` the paths are currently absolute and point to `simulator/config_data/*` under this repo. You can keep those or pass your own in `/initialize`.

Run a DMP-only simulation:

```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
        "demographics": {
          "Age": "25",
          "Vaccination Status": "Vaccinated",
          "Sex": "F",
          "Variant": "Omicron"
        }
      }'
```

---

## Running the Simulator

Start the Flask server from repo root:

```bash
python app.py
```

The simulator exposes:

- GET `/` — Basic simulation using defaults
- POST `/simulation/` — Simulation with body-provided interventions

The simulator will lazily initialize the DMP API using the base URL from `simulator/config.py` (`DMP_API["base_url"] = http://localhost:8000`). If the DMP is not reachable, the simulator falls back to internal timelines.

Example request to `/simulation/`:

```bash
curl -X POST http://localhost:1880/simulation/ \
  -H "Content-Type: application/json" \
  -d '{
        "length": 72000,
        "location": "barnsdall",
        "mask": 0.2,
        "vaccine": 0.5,
        "capacity": 0.8,
        "lockdown": 0,
        "selfiso": 0.1,
        "randseed": true
      }'
```

See defaults in `simulator/config.py` under `SIMULATION["default_interventions"]` and `SIMULATION["default_max_length"]`.

---

## Configuration

All key simulator settings live in `simulator/config.py`:

- `DMP_API.base_url` — DMP API URL (default `http://localhost:8000`)
- `DMP_API.paths.*` — Default files used to initialize DMP
- `DMP_API.state_mapping` — Maps DMP states to simulator internal states
- `SERVER.host` / `SERVER.port` — Simulator server binding (default `0.0.0.0:1880`)
- `SIMULATION.*` — Default timestep, length, location, intervention defaults, variants
- `INFECTION_MODEL.*` — Internal infection model fallback and time conversion

You can override `DMP_API.paths` at runtime by calling the DMP `/initialize` endpoint with your own files, or by editing `simulator/config.py`.

---

## Development

- Create and activate a virtual environment
- Install root requirements: `pip install -r requirements.txt`
- Optionally install DMP extras: `pip install -r dmp/requirements.txt`
- Start services as in Quick Start

Useful paths:

- DMP API app: `dmp/api/dmp_api.py`
- Simulator app: `app.py`
- Simulator logic: `simulator/`

---

## Testing

Run DMP API tests from `dmp/`:

```bash
cd dmp
python -m api.test_api
```

---

## Troubleshooting

- DMP API not reachable at `http://localhost:8000`:
  - Ensure uvicorn is running: `uvicorn api.dmp_api:app --reload` in `dmp/`.
  - Verify `uvicorn` is installed (`pip install uvicorn`) or install `dmp/requirements.txt`.

- File not found during DMP `/initialize`:
  - Use absolute paths or ensure repo-relative paths are correct.
  - Sample files are under `simulator/config_data/`.

- Simulator starts but returns fallback timelines:
  - This happens when DMP is not initialized or not reachable.
  - Start DMP first, then (re)start the simulator or trigger initialization by calling a simulator endpoint again.

- Port conflicts:
  - Change simulator port in `simulator/config.py` (`SERVER["port"]`).
  - Change DMP port by running uvicorn with `--port` (e.g., `uvicorn api.dmp_api:app --reload --port 8001`) and update `DMP_API.base_url`.

---

## License

See `LICENSE` in the repository root.
