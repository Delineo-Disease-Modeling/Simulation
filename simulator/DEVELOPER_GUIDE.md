# Simulator Developer Guide

Welcome to the Delineo Simulator codebase. This guide is for new developers working in the `simulator/` component. It explains the architecture, key modules, data flow, configuration, debugging/profiling practices, and common workflows.

---

## High-level Architecture

The simulator is a Flask-backed service (root `app.py`) that orchestrates simulation runs with core logic in `simulator/`. It optionally consults the Disease Modeling Platform (DMP) API for disease progression timelines.

- Simulator entrypoint (Flask): `app.py`
- Simulator engine and logic: `simulator/`
- Optional DMP service (FastAPI): `dmp/api/dmp_api.py`

Key design:
- `simulate.run_simulator(...)` drives full runs and returns results for the HTTP endpoints in `app.py`.
- `InfectionManager` (`infectionmgr.py`) manages infection progression and integrates with DMP for timelines.
- Configuration is centralized in `simulator/config.py`.

---

## Key Modules

- `simulator/simulate.py`
  - `DiseaseSimulator`: owns collections of people, households, facilities, and logging.
  - `run_simulator(...)`: main function executed by Flask endpoints; builds the world, seeds infections, steps simulation, and aggregates outputs.
  - `SimulationLogger`: efficient, buffered logging to CSV and text summary reports.
  - Intervention-aware movement and risk utilities: `move_people(...)`, `calculate_*_risk`.

- `simulator/infectionmgr.py`
  - `InfectionManager`: manages infection state, batching, and DMP timeline lookups.
  - Integrates with Wells-Riley model via `infection_models/v5_wells_riley.py::CAT`.
  - Caches DMP timelines, performs concurrent API calls, and applies fallback when DMP is unavailable.

- `simulator/config.py`
  - Central config for simulator defaults, DMP base URL/paths, server host/port, intervention defaults and variants, and fallback timelines.

- `simulator/data_interface.py`
  - Streaming loader that pulls people/places/homes/patterns from a remote endpoint.

- `simulator/pap.py`
  - Domain models: `Person`, `Household`, `Facility`, infection state enums, etc.

- `simulator/infection_models/`
  - Infection probability model(s) used when evaluating transmissions.

---

## Data Flow

1. `app.py` receives a request at `/` or `/simulation/` and calls `simulate.run_simulator(...)`.
2. `run_simulator(...)` in `simulator/simulate.py`:
   - Loads streamed data via `StreamDataLoader.stream_data(...)`.
   - Builds `Household` and `Facility` objects, then creates `Person` objects and assigns initial infections and interventions.
   - Initializes `DiseaseSimulator` (optional logging via `SimulationLogger`).
   - Steps through patterns and movements, evaluating transmission risks and updating states.
3. For newly infected individuals, `InfectionManager` may:
   - Batch requests to DMP at `POST {DMP_API.base_url}/simulate` using demographics, or
   - Apply fallback timelines from `INFECTION_MODEL.fallback_timeline` if DMP is down or not initialized.
4. Final results and logs are returned to Flask to form the HTTP response.

---

## Configuration

See `simulator/config.py`:
- `DMP_API.base_url`: e.g., `http://localhost:8000` (FastAPI/uvicorn default).
- `DMP_API.paths`: default files used to initialize the DMP (`combined_matrices.csv`, `demographic_mapping.csv`, `custom_states.txt`).
- `DMP_API.state_mapping`: maps DMP state labels to simulator `InfectionState` values.
- `INFECTION_MODEL`: fallback timelines, timestep, multi-disease setting.
- `SIMULATION`: default timestep, length, location, intervention defaults, variants, and logging parameters.
- `SERVER`: host/port for the Flask simulator (`0.0.0.0:1880`).

Tip: Prefer repo-relative or environment-based paths. The repo currently includes absolute defaults; adjust for your environment or pass explicit files to the DMP `/initialize` endpoint.

---

## Local Setup

- Python 3.10+ recommended.
- From repo root (`Simulation/`):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# If you plan to run the DMP locally:
pip install -r dmp/requirements.txt  # includes uvicorn
```

Run services:
- DMP (in `Simulation/dmp/`):
```bash
uvicorn api.dmp_api:app --reload
```
- Simulator (in `Simulation/`):
```bash
python app.py
```

---

## Typical Development Workflows

- Modify simulation behavior (movements/interventions):
  - Edit `simulator/simulate.py` (`move_people`, `DiseaseSimulator`, intervention effects).
  - Adjust defaults in `simulator/config.py` under `SIMULATION`.

- Change infection progression or DMP integration:
  - Edit `simulator/infectionmgr.py` for batching, caching, and API payloads.
  - Update mappings in `config.py` (`DMP_API.state_mapping`, `time_conversion_factor`).
  - Update infection probability logic in `infection_models/`.

- Add logging or metrics:
  - Extend `SimulationLogger` in `simulate.py` (person, movement, infection, intervention, location, contact logs; CSV export and summary report).

- Test API end-to-end:
  - Start DMP with `uvicorn`.
  - `curl` simulator endpoints:
    - GET `http://localhost:1880/`
    - POST `http://localhost:1880/simulation/` with a JSON body containing interventions.

---

## Debugging Tips

- Enable logs: `run_simulator(..., enable_logging=True, log_dir="simulation_logs_<timestamp>")`.
- Inspect `simulation_logs_*/simulation.log`, `*_logs.csv`, and `summary_report.txt`.
- DMP initialization:
  - The Flask app calls `initialize_dmp_api()` on startup and on incoming requests if needed.
  - Check console output for messages like "DMP API successfully initialized!" or failure warnings.
- If DMP is unavailable, fallback timelines are used (see `INFECTION_MODEL.fallback_timeline`).
- Use smaller datasets or filter patterns for faster iteration.

---

## Profiling

- Use built-in CSV logs to understand movement and infection hotspots.
- Consider Python profilers (e.g., `cProfile`, `py-spy`) around `run_simulator(...)` when diagnosing slowdowns.
- Batch sizes and concurrency in `InfectionManager` can be tweaked (`max_workers`, batch thresholds) to evaluate performance.

---

## Testing

- API-level tests for DMP live in `dmp/api/test_api.py`.
- Add unit tests for simulator components under `simulator/tests/` (create this folder) or extend `simulator/test_loading_data.py`.
- For deterministic runs, set `"randseed": false` in the simulator POST body to seed randomness.

---

## Extending the Simulator

- Add a new intervention:
  1. Add a default in `SIMULATION["default_interventions"]`.
  2. Handle its effects in `move_people(...)`, logging via `SimulationLogger.log_intervention_effect`.
  3. Optionally surface it in the Flask API request handling (`app.py`).

- Add a new infection variant:
  1. Append to `SIMULATION["variants"]`.
  2. Ensure seeding logic in `simulate.py` assigns initial infections per variant.

- Customize DMP demographics:
  1. Ensure `infectionmgr._make_api_request` payload matches DMP’s expected schema (Age, Sex, Vaccination Status, Variant).
  2. Update `dmp/cli/user_input.py` and mapping files if you add demographics categories.

---

## Code Style & Conventions

- Keep imports at top of files and avoid circular imports.
- Prefer dependency injection of config values where feasible; otherwise use `simulator/config.py`.
- Add docstrings and type hints where possible.
- Use buffered logging and batch operations for performance-critical paths.

---

## Common Pitfalls

- Forgetting to start DMP before running the simulator → simulator falls back to internal timelines and results may differ.
- Absolute paths in `simulator/config.py` not matching your local environment → use absolute paths or update config to point at repo-relative files.
- Port conflicts on `8000` (DMP) or `1880` (simulator) → configure `uvicorn --port` and/or `SERVER["port"]` accordingly.

---

## Reference: Important Symbols

- Entrypoints:
  - Flask: `app.py`, endpoints `/` and `/simulation/`
  - Runner: `simulator/simulate.py::run_simulator(...)`
- Infection manager: `simulator/infectionmgr.py::InfectionManager`
- Data streaming: `simulator/data_interface.py::StreamDataLoader`
- Config: `simulator/config.py`
- Domain models: `simulator/pap.py`

---

## Example: Minimal Run with Defaults

1) Start DMP (optional but recommended):
```bash
cd dmp
uvicorn api.dmp_api:app --reload
```
2) Start simulator:
```bash
python app.py
```
3) Trigger a run (defaults):
```bash
curl http://localhost:1880/
```
4) Trigger a custom run with interventions:
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

Welcome aboard! If you have questions, start by examining `run_simulator(...)`, `InfectionManager.run_model(...)`, and `simulator/config.py`. They define most of the core logic and default behaviors.
