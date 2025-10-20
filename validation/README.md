# Simulator Validation Suite

This folder hosts a standalone, non-invasive validation harness for the Delineo simulator.
It relies on the existing Dockerized services and HTTP API and does not change simulator code.

## Overview
- Fetch reliable public data (CDC/JHU) into `data/raw/` and prepare clean time series in `data/processed/`.
- Start simulator via Docker Compose and call `POST http://localhost:1880/simulation/` to generate results.
- Compare simulator outputs against ground truth and compute metrics.
- Produce a compact HTML/PNG report in `reports/`.

## Quickstart
1) Start services (DMP + Simulator) from `Simulation/` root:
   ```bash
   make up
   # or
   docker compose up -d
   ```
   The simulator should be available at `http://localhost:1880/`.

2) (Optional) Run simulator locally via Flask for development:
   ```bash
   python app.py
   ```

3) Create a Python venv and install validation deps:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4) Fetch and prepare data:
   ```bash
   make data
   # or
   python scripts/fetch_data.py --source cdc --geo us --start 2020-06-01 --end 2021-06-01
   python scripts/prepare_data.py --geo us --agg weekly
   ```

5) Run simulator and collect outputs (example length 56 days):
   ```bash
   python scripts/run_simulation.py --length 56 --location us
   ```

6) Compare and generate metrics/report:
   ```bash
   python scripts/compare.py --geo us --horizon 1,2,3,4 --agg weekly
   ```

Outputs go to `artifacts/` (JSON/CSV) and `reports/`.

## Folder Structure
- scripts/
  - fetch_data.py: Download ground-truth data (CDC/JHU) into `data/raw/`.
  - prepare_data.py: Clean and aggregate to match simulator outputs.
  - run_simulation.py: Call simulator API and write standardized results.
  - metrics.py: Metric functions (MAE, RMSE, sMAPE, coverage, CRPS stub).
  - compare.py: Align, compute metrics, and write reports.
- data/
  - raw/: Source datasets.
  - processed/: Cleaned and standardized datasets.
- artifacts/: Simulator outputs serialized as CSV/JSON and alignment tables.
- reports/: HTML/PNG summaries.

## County-Level Validation (Hagerstown, MD)

For detailed validation using real 2021 data from Hagerstown, MD (Washington County), see **[HAGERSTOWN_VALIDATION.md](HAGERSTOWN_VALIDATION.md)**.

**Quick start for Hagerstown validation**:
```bash
# Run complete validation for March 2021
python scripts/run_hagerstown_validation.py --month 2021-03
```

This will:
1. Fetch real COVID-19 data for Washington County, MD from the NYT dataset
2. Prepare and aggregate the data to weekly totals
3. Run the simulator with Hagerstown location and appropriate interventions
4. Compare results and generate validation metrics

**New scripts for county-level validation**:
- `scripts/fetch_county_data.py`: Download county-level COVID data from NYT dataset
- `scripts/prepare_county_data.py`: Aggregate county data for validation
- `scripts/run_hagerstown_validation.py`: Complete orchestration script
- `configs/hagerstown_2021_config.json`: Pre-configured validation parameters

## Notes
- No changes to the simulator are required. We target `POST /simulation/` from `Simulation/app.py`.
- DMP is initialized automatically by `app.py` and through Docker health checks per `docker-compose.yml`.
- If the simulator returns different field names or frequencies, adjust mapping in `scripts/prepare_data.py` and `scripts/run_simulation.py`.
