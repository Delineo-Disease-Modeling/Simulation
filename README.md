# Delineo Simulation

Simulation runs an airborne-outbreak scenario using synthetic people, homes,
places, and movement from a Delineo convenience zone. Its Flask API downloads
inputs from Fullstack, streams progress to the caller, and uploads results for
the web application's maps and charts. The repository also contains the Disease
Modeling Platform (DMP).

Start with the shared [project overview](https://github.com/Delineo-Disease-Modeling/Fullstack/blob/main/docs/overview.md)
and [local walkthrough](https://github.com/Delineo-Disease-Modeling/Fullstack/blob/main/docs/getting-started.md).
The walkthrough includes a synthetic run and explains which real-data inputs
must be supplied separately.

## Install and start this service

Use Python 3.12 for the native setup. From this repository's root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
DELINEO_DB_URL=http://localhost:3000/api/ .venv/bin/python server.py
```

The server listens on port **1870**. `DELINEO_DB_URL` points to Fullstack's API
and must end in `/api/`. Its default is `http://localhost:3000/api/`.

```bash
curl --fail http://localhost:1870/
```

Expect `{"service":"delineo-simulation","status":"ok"}` (key order may differ).
`GET /` checks the service; **`POST /simulation/`** runs a scenario and returns
server-sent events. Its request `length` and intervention `time` values are in
minutes. The [synthetic example](https://github.com/Delineo-Disease-Modeling/Fullstack/blob/main/docs/examples/smoke.py)
demonstrates a complete request and output checks.

The entry module is **`server.py`**. For a WSGI process use `server:app`, as the
Dockerfile does. A top-level `app.py` conflicts with the DMP package's import
path and is not a valid current startup instruction.

## Disease progression

The root `requirements.txt` includes the DMP dependencies. Simulation normally
loads the bundled model database in-process (`DMP_INPROCESS=1`). It can fall back
to the HTTP DMP service at `DMP_API_BASE_URL`, or its alias `DMP_API_URL`, defaulting
to `http://localhost:8000`.

Run requests support `dmp_mode` values `auto`, `required`, and `off`. `auto` permits
fallback timelines; `required` surfaces unavailable progression models; `off`
uses default simulator timelines. A separate DMP server is not necessary for the
normal in-process path.

To expose the optional API, from the Simulation root:

```bash
.venv/bin/python -m uvicorn dmp.api.dmp_api_v2:app --host 127.0.0.1 --port 8000
```

Its interactive reference is at `http://localhost:8000/docs`. See the
[DMP README](dmp/README.md) for the editor and model database.

## Code map

| Location | Responsibility |
| --- | --- |
| `server.py` | Flask routes, simulation request validation, and SSE response |
| `simulator/jobs.py` | Background jobs, progress messages, and result upload |
| `simulator/runner.py` | Load inputs, build the world, advance simulation, write output |
| `simulator/config.py` | Runtime defaults and environment variables |
| `simulator/data_interface.py` | Fullstack input loading and movement-format decoding |
| `simulator/infection_models/v6_wells_riley.py` | Transmission model |
| `simulator/infectionmgr.py` | Disease timelines and infection-state management |
| `dmp/` | Progression models, FastAPI API, Streamlit editor, SQLite database |
| `tests/` | Runtime, progression, transmission, format, and entry-point checks |
| `scripts/` | Performance and equivalence utilities |

Older integration examples under `simulator/api_testing/` and `README_v0.md` files
are historical material, not the current installation guide. Install the pinned
root requirements instead of resolving missing imports one package at a time.
No special network connection is assumed; diagnose access to the specific
database, service, or data provider if a request fails.

`main` is deployed to production. Use a short-lived branch for changes and link
companion Algorithms/Fullstack pull requests when their interfaces change.
