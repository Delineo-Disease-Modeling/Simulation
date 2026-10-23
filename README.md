# Delineo Simulation

The Simulation service runs a disease through a convenience zone's synthetic
population. It moves people between homes and places hour by hour, works out
who infects whom using a Wells-Riley airborne transmission model, and uses the
**DMP** (Disease Modeling Platform) to track each infected person through their
disease states. It's a Flask server on port **1870**. The DMP also runs as a
separate FastAPI service on port **8000**.

> **New to Delineo?** Read
> [Start Here](https://github.com/Delineo-Disease-Modeling/.github/blob/main/docs/START_HERE.md)
> first, and keep the
> [Glossary](https://github.com/Delineo-Disease-Modeling/.github/blob/main/docs/GLOSSARY.md)
> handy.

## How a run works

1. The browser sends the run settings to `POST /simulation/`: zone, length,
   disease and variants, initial infections, and interventions.
2. The simulator downloads the zone's papdata and movement patterns from
   Fullstack (`GET {DELINEO_DB_URL}patterns/<czone_id>`).
3. `SimulationRunner` (`simulator/runner.py`) steps through time. At each step
   it moves people, applies interventions, runs transmission at every occupied
   location, and asks the DMP for the disease timeline of each new infection.
4. It uploads the results to Fullstack (`POST {DELINEO_DB_URL}simdata`).
5. Progress streams back to the browser as Server-Sent Events. The last event
   contains the new run ID.

## Running it

Do the full setup in
[Setup](https://github.com/Delineo-Disease-Modeling/.github/blob/main/docs/SETUP.md)
first (Python 3.13 and a `.venv` in this folder). Then, from this folder:

```bash
.venv/bin/python server.py
```

That serves the simulator on <http://localhost:1870>. `GET /` is a health
check. To start the DMP API as well:

```bash
.venv/bin/python -m uvicorn dmp.api.dmp_api_v2:app --port 8000 --reload
```

The simulator doesn't need the DMP service for normal runs. It imports the DMP
code directly, and only calls the HTTP service if that import fails.

In production, Docker runs the simulator under gunicorn (`server:app`) with
`WEB_CONCURRENCY` worker processes. Each simulation is CPU-bound, so separate
processes let several runs use separate cores.

> **Always start the server as `server.py` or `server:app`, never `app:app`.**
> A top-level module named `app` hides the `dmp/app` package. When that
> happens, the in-process DMP silently stops working, and every infection falls
> back to a slow HTTP call. `tests/test_deploy_entrypoints.py` guards against this.

### Environment variables

Everything is read in `simulator/config.py`, and that file explains each
setting. The ones you're most likely to need:

| Variable | Default | What it does |
| --- | --- | --- |
| `DELINEO_DB_URL` | `http://localhost:3000/api/` | Fullstack's API, for reading zones and writing results |
| `DMP_INPROCESS` | on | Run the DMP inside the simulator. Set to `0` to force HTTP. |
| `DMP_API_URL` | `http://localhost:8000` | The DMP service, used only as a fallback |
| `DMP_MODE` | `auto` | `auto`, `required` (fail if the DMP is unavailable), or `off` |
| `DELINEO_AGG_TRANSMISSION` | on | The faster aggregate Wells-Riley kernel. It's statistically equivalent to the pairwise kernel, but its output isn't byte-identical. |
| `DELINEO_AREA_VENTILATION` | on | Scale each place's ventilation by its floor area |
| `DELINEO_FRACTIONAL_DWELL` | on | Count partial-hour visits by their real minutes |
| `DELINEO_EXTERNAL_FOI` | off | Add infections from outside the zone |

## The simulation request

`POST /simulation/` takes JSON matching `simulation_schema` in `server.py`:

| Field | Required | Notes |
| --- | --- | --- |
| `czone_id` | yes | The zone to simulate |
| `length` | yes | Run length in **minutes** (Fullstack sends `hours * 60`) |
| `interventions` | yes | A list of `{time, mask, vaccine, capacity, lockdown, selfiso}`. Each value is a fraction from 0 to 1, starting at `time`, which is in **hours** (unlike `length`). |
| `initial_infected_count` / `initial_infected_ids` | no | How to seed the first infections |
| `disease_name`, `variants` | no | Which disease model and variants to use |
| `matrix_csv_by_variant`, `model_path_by_variant` | no | Custom DMP matrices or models per variant |
| `dmp_mode` | no | Overrides `DMP_MODE` for this run |
| `disabled_poi_ids` | no | Places to close. Visits to them become time at home. |
| `randseed` | no | `true` (the default) makes every run different. `false` uses a fixed seed, so runs repeat exactly. |
| `random_seed` | no | An explicit integer seed, for reproducible ensembles of runs |

## Tests

From this folder:

```bash
.venv/bin/python -m pytest
```

`pytest.ini` points pytest at `tests/`. The DMP API has its own tests in
`dmp/api/test_api_v2.py`.

> **Known issue:** two tests in `tests/test_state_machine_apptest.py` fail on a
> fresh install. The DMP's Streamlit UI imports `streamlit_javascript`, and
> neither `requirements.txt` nor `dmp/requirements.txt` lists it.

## Code map

```text
server.py                  # Flask app: POST /simulation/, GET /
waitress_app.py            # alternative production entry point
simulator/
├── jobs.py                # runs a simulation in a thread, streams SSE, uploads results
├── simulate.py            # run_simulator(), the entry point jobs.py calls
├── runner.py              # SimulationRunner: load data, main loop, write output
├── world.py, pap.py       # people, places, infection states
├── transmission.py        # Wells-Riley transmission kernels
├── interventions.py       # masks, capacity, lockdown, self-isolation
├── disabled_poi.py        # reroutes visits to closed places
├── membership.py          # fast struct-of-arrays engine for who is where
├── event_queue.py         # movement events over time
├── dmp_inprocess.py       # calls the DMP without HTTP
├── infectionmgr.py        # infection bookkeeping and DMP lookups
├── data_interface.py      # downloads papdata and patterns from Fullstack
├── patterns_codec.py      # binary DLNOPAT decoder
├── simdata.py, snapshots.py, io.py   # request normalization and output writing
├── config.py              # every setting and env var
├── config_data/           # default DMP matrices and demographic mapping
└── infection_models/      # Wells-Riley parameters and notes
dmp/                       # Disease Modeling Platform
├── api/dmp_api_v2.py      # FastAPI service (port 8000)
├── app/                   # Streamlit UI for building state machines
├── core/                  # DMP simulation logic
└── docs/API_DOCUMENTATION.md
dmp_functions.py, simulation_functions.py   # DMP helpers used by infectionmgr
scripts/                   # benchmarks, equivalence checks, pattern transcoding
tests/                     # pytest suite
```

## Things that trip people up

- **`app:app` vs `server:app`.** See the warning above.
- **Units of `length`.** A run's length is in minutes, but a zone's length is
  in hours.
- **Changing the transmission kernel or the random number streams.** This
  changes results even when the statistics don't change. Use
  `scripts/equivalence_ensemble.py` to compare ensembles of runs, not single
  runs.
- **Editing a DMP matrix.** Each row must sum to 1. `tests/test_default_matrix_csv.py`
  checks the bundled default.
- **Feature flags.** Several behaviors are on by default but can be turned off
  (see the env table above). To turn one off in production, set it in
  `Deploy/docker-compose.yml`.

## Further reading

- [`docs/SIMULATION_ENGINE.md`](docs/SIMULATION_ENGINE.md): **start here.** How
  a run works, step by step: the engine loop, the Wells-Riley transmission
  kernel, interventions, and the DMP
- [Model assumptions](https://github.com/Delineo-Disease-Modeling/.github/blob/main/docs/MODEL_ASSUMPTIONS.md):
  what the model assumes, what's calibrated, and what results can be used to
  claim
- [`dmp/README.md`](dmp/README.md) and
  [`dmp/docs/API_DOCUMENTATION.md`](dmp/docs/API_DOCUMENTATION.md): the DMP, its
  state machines, and its API
- [`simulator/infection_models/infection_model_parameters.md`](simulator/infection_models/infection_model_parameters.md):
  parameters for an **older**, virion-based version of the infection model. The
  current kernel's parameters are in `docs/SIMULATION_ENGINE.md`.
