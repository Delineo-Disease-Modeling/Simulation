#!/usr/bin/env python3
import argparse
import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta

DEFAULT_URL = "http://localhost:1880/simulation/"


def call_simulator(url: str, length: int, location: str, interventions: dict | None) -> dict:
    payload = {"length": length, "location": location}
    if interventions:
        payload.update(interventions)
    r = requests.post(url, json=payload, timeout=180)
    r.raise_for_status()
    # Flask returns JSON already; ensure dict
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def extract_incidence(final_result: dict, step_minutes: int = 60) -> pd.DataFrame:
    """
    Convert simulator 'result' into a per-step new-infections time series by
    differencing the infected-set sizes across steps (proxy incidence).
    final_result structure (from simulate.run_simulator):
      {
        'result': {
          timestep_int: { variant: { person_id: state_value, ... }, ... }, ...
        },
        'movement': {...}
      }
    """
    result = final_result.get("result", {})
    # Sort timesteps numerically
    steps = sorted(int(k) for k in result.keys())

    records = []
    prev_total_infected = 0
    for idx, t in enumerate(steps):
        frame = result[str(t)]
        # Count unique infected persons across variants
        infected_ids = set()
        for variant, mapping in frame.items():
            infected_ids.update(mapping.keys())
        total_infected = len(infected_ids)
        new_cases = max(total_infected - prev_total_infected, 0)
        prev_total_infected = total_infected
        records.append({
            "step_index": idx,
            "timestep": t,
            "minutes_per_step": step_minutes,
            "days_since_start": (idx * step_minutes) / (60.0 * 24.0),
            "new_cases": new_cases,
            "cum_cases": total_infected
        })

    df = pd.DataFrame.from_records(records)
    return df


def main():
    parser = argparse.ArgumentParser(description="Run the simulator via HTTP and standardize outputs")
    parser.add_argument("--url", default=DEFAULT_URL, help="Simulator POST endpoint")
    parser.add_argument("--length", type=int, default=56*24*60, help="Max simulation length in minutes (default: 56 days)")
    parser.add_argument("--location", default="barnsdall", help="Simulator location argument")
    parser.add_argument("--step_minutes", type=int, default=60, help="Minutes per simulation step (SIMULATION.default_timestep)")
    parser.add_argument("--artifacts", default=os.path.join(os.path.dirname(__file__), "..", "artifacts"))
    parser.add_argument("--interventions", default=None, help='JSON string of interventions to pass through')
    args = parser.parse_args()

    os.makedirs(args.artifacts, exist_ok=True)

    interventions = None
    if args.interventions:
        interventions = json.loads(args.interventions)

    final_result = call_simulator(args.url, args.length, args.location, interventions)

    # Save raw JSON
    raw_path = os.path.join(args.artifacts, "sim_raw_result.json")
    with open(raw_path, "w") as f:
        json.dump(final_result, f)
    print(f"Saved raw simulator output: {raw_path}")

    # Standardize timeseries
    df = extract_incidence(final_result, step_minutes=args.step_minutes)
    ts_path = os.path.join(args.artifacts, "sim_timeseries.csv")
    df.to_csv(ts_path, index=False)
    print(f"Saved standardized series: {ts_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
