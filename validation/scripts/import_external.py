#!/usr/bin/env python3
import argparse
import os
import json
import pandas as pd
from typing import Optional

# Reuse the incidence extractor logic compatible with API output
# We inline a small version here to avoid cross-imports.

def extract_incidence_from_result(final_result: dict, step_minutes: int = 60) -> pd.DataFrame:
    result = final_result.get("result", {})
    steps = sorted(int(k) for k in result.keys())
    records = []
    prev_total_infected = 0
    for idx, t in enumerate(steps):
        frame = result[str(t)]
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
    return pd.DataFrame.from_records(records)


def extract_incidence_from_infection_logs(csv_path: str, step_minutes: int = 60) -> pd.DataFrame:
    """
    Build a standardized series from an infection logs CSV that has a 'timestep' column.
    We count infection events per timestep as new_cases.
    """
    df = pd.read_csv(csv_path)
    if 'timestep' not in df.columns:
        raise ValueError("infection_logs.csv must contain a 'timestep' column")
    grp = df.groupby('timestep').size().reset_index(name='new_cases')
    grp = grp.sort_values('timestep').reset_index(drop=True)
    grp['step_index'] = range(len(grp))
    grp['minutes_per_step'] = step_minutes
    grp['days_since_start'] = grp['step_index'] * step_minutes / (60.0 * 24.0)
    grp['cum_cases'] = grp['new_cases'].cumsum()
    # Reorder columns
    grp = grp[['step_index','timestep','minutes_per_step','days_since_start','new_cases','cum_cases']]
    return grp


def load_json_file(path: str) -> dict:
    with open(path, 'r') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='Import external simulator outputs and standardize to sim_timeseries.csv')
    parser.add_argument('--source_path', required=True, help='Path to JSON results file or to a directory containing infection_logs.csv')
    parser.add_argument('--step_minutes', type=int, default=60)
    parser.add_argument('--artifacts', default=os.path.join(os.path.dirname(__file__), '..', 'artifacts'))
    parser.add_argument('--outfile', default='sim_timeseries_external.csv', help='Output CSV filename inside artifacts/')
    args = parser.parse_args()

    os.makedirs(args.artifacts, exist_ok=True)

    src = args.source_path
    if os.path.isdir(src):
        # Look for infection_logs.csv first
        log_csv = os.path.join(src, 'infection_logs.csv')
        if not os.path.exists(log_csv):
            # try nested common layouts
            candidates = []
            for root, _, files in os.walk(src):
                if 'infection_logs.csv' in files:
                    candidates.append(os.path.join(root, 'infection_logs.csv'))
            if not candidates:
                raise FileNotFoundError('infection_logs.csv not found under the provided directory')
            log_csv = sorted(candidates)[0]
        df = extract_incidence_from_infection_logs(log_csv, step_minutes=args.step_minutes)
    else:
        # Assume JSON file shaped like API output
        data = load_json_file(src)
        # Some pipelines may save the dict directly without the top-level keys; handle both
        if 'result' in data and isinstance(data['result'], dict):
            final_result = data
        else:
            final_result = {'result': data, 'movement': {}}
        df = extract_incidence_from_result(final_result, step_minutes=args.step_minutes)

    out_path = os.path.join(args.artifacts, args.outfile)
    df.to_csv(out_path, index=False)
    print(f'Saved standardized external series: {out_path} ({len(df)} rows)')


if __name__ == '__main__':
    main()
