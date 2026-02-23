#!/usr/bin/env python3
"""
Comprehensive simulation runner for the Barnsdall, OK disease simulation.

Covers:
  - Calibration sweep (find DMP params for ~250 infections)
  - Scenario A: same params + same 12 seeds, multiple runs  (variability)
  - Scenario B: same params + different seed identities
  - Scenario C: 2 and 50 seeded persons
  - Scenario D: same params + 25 seeds + interventions (vaccine, mask, social-distancing)

All results are written to experiment_outputs/<run_name>_summary.json and CSV files.
"""

import importlib
import json
import os
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SIX_WEEKS = 6 * 7 * 24 * 60  # minutes
BASE_SEED_IDS = "160,43,47,4,36,9,14,19,27,22,3,5"
TARGET_INFECTIONS = 250
OUT_DIR = Path("experiment_outputs")
OUT_DIR.mkdir(exist_ok=True)


# ── helpers ──────────────────────────────────────────────────────────────────

def set_env(rate: float = None, infectious_min: int = None):
    """Set env vars read by simulator/config.py before (re)importing."""
    if rate is not None:
        os.environ["INFECTION_TRANSMISSION_RATE"] = str(rate)
    if infectious_min is not None:
        # Fallback infected_duration controls how long someone stays infectious
        os.environ["FALLBACK_INFECTED_DURATION"] = str(infectious_min)
    # Force config reload
    import importlib
    mods_to_reload = [k for k in sys.modules if k.startswith('simulator')]
    for m in mods_to_reload:
        try:
            importlib.reload(sys.modules[m])
        except Exception:
            pass


def run_sim(interventions: dict, log_dir: str, length: int = SIX_WEEKS) -> dict:
    from simulator import simulate
    simulate.run_simulator(
        location="barnsdall",
        max_length=length,
        interventions=interventions,
        save_file=False,
        enable_logging=True,
        log_dir=log_dir,
    )
    return summarize(Path(log_dir))


def summarize(log_dir: Path) -> dict:
    inf_path = log_dir / "infection_logs.csv"
    person_path = log_dir / "person_logs.csv"

    if inf_path.exists():
        df = pd.read_csv(inf_path)
    else:
        df = pd.DataFrame()

    total = len(df)
    unique = int(df["infected_person_id"].nunique()) if total else 0

    by_loc = {}
    by_time = {}
    if total:
        by_loc = (df.groupby(["infection_location_type", "infection_location_id"])
                  .size().reset_index(name="count")
                  .sort_values("count", ascending=False)
                  .head(20).to_dict(orient="records"))
        by_time = (df.groupby("timestep").size()
                   .reset_index(name="count")
                   .to_dict(orient="records"))

    # Trajectory check: verify infected people get proper disease state logs
    trajectory_ok = None
    if person_path.exists() and total:
        ppl = pd.read_csv(person_path)
        first_inf = df.groupby("infected_person_id")["timestep"].min().reset_index()
        merged = first_inf.merge(ppl, how="left",
                                 left_on="infected_person_id", right_on="person_id")
        merged = merged[merged["timestep_y"].notna()]
        merged = merged[merged["timestep_y"] >= merged["timestep_x"]]
        trajectory_ok = float(merged["infection_status"].notna().mean()) if len(merged) else 0.0

    return {
        "log_dir": str(log_dir),
        "total_infection_events": total,
        "unique_infected_people": unique,
        "trajectory_fraction_tagged": trajectory_ok,
        "top_locations": by_loc,
        "infections_over_time": by_time,
    }


def save(name: str, result: dict):
    json_path = OUT_DIR / f"{name}.json"
    # top_locations and infections_over_time are already dicts; write them to CSVs too
    top_locs = result.pop("top_locations", [])
    by_time = result.pop("infections_over_time", [])
    json_path.write_text(json.dumps(result, indent=2))
    if top_locs:
        pd.DataFrame(top_locs).to_csv(OUT_DIR / f"{name}_top_locs.csv", index=False)
    if by_time:
        pd.DataFrame(by_time).to_csv(OUT_DIR / f"{name}_by_time.csv", index=False)
    print(f"  → {json_path.name}  (unique infected: {result.get('unique_infected_people')})")
    return result


# ── calibration ──────────────────────────────────────────────────────────────

def calibrate():
    """Find transmission_rate + infectious_duration that gives ~250 infections."""
    print("\n" + "="*60)
    print("CALIBRATION: targeting ~250 total infections in 6 weeks")
    print("="*60)

    base_interventions = {
        "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
        "lockdown": 0, "selfiso": 0.0, "randseed": False,
        "seed_count": 12, "seed_ids": BASE_SEED_IDS,
    }

    # Grid search: transmission rate × infectious duration
    # Infectious duration in minutes (default 1440 = 24 hrs)
    durations_to_try = [1440, 4320, 10080, 20160]   # 1d, 3d, 7d, 14d
    rates_to_try     = [7000, 5000, 3000]

    results = []
    best = None

    for dur_min in durations_to_try:
        for rate in rates_to_try:
            set_env(rate=rate, infectious_min=dur_min)
            tag = f"calib_rate{rate}_dur{dur_min}"
            log_dir = f"calibration_logs_{tag}"
            print(f"\n  rate={rate}, infectious_dur={dur_min//60}h ... ", end="", flush=True)
            r = run_sim(base_interventions, log_dir)
            n = r["unique_infected_people"]
            print(f"{n} infections")
            entry = {"rate": rate, "infectious_min": dur_min, "infections": n}
            results.append(entry)
            if best is None or abs(n - TARGET_INFECTIONS) < abs(best["infections"] - TARGET_INFECTIONS):
                best = entry
            if abs(n - TARGET_INFECTIONS) <= 15:
                print(f"  *** Close enough! ***")
                break
        if best and abs(best["infections"] - TARGET_INFECTIONS) <= 15:
            break

    print("\nCalibration results:")
    print(f"{'Rate':>8}  {'Infect-dur(h)':>14}  {'Infections':>12}  {'Diff':>6}")
    for r in results:
        d = r["infections"] - TARGET_INFECTIONS
        mark = " <--" if abs(d) <= 15 else ""
        print(f"{r['rate']:>8}  {r['infectious_min']//60:>14}  {r['infections']:>12}  {d:>+6}{mark}")

    print(f"\nBest parameters: rate={best['rate']}, "
          f"infectious_dur={best['infectious_min']//60}h, "
          f"infections={best['infections']}")

    (OUT_DIR / "calibration_results.json").write_text(
        json.dumps({"target": TARGET_INFECTIONS, "results": results, "best": best}, indent=2)
    )
    return best


# ── scenarios ─────────────────────────────────────────────────────────────────

def scenario_a(best_rate: float, best_dur: int, n_runs: int = 5):
    """Same DMP params, same 12 seed IDs → multiple runs to measure variability."""
    print("\n" + "="*60)
    print("SCENARIO A: Variability across runs (same seeds, randseed=True)")
    print("="*60)
    set_env(rate=best_rate, infectious_min=best_dur)
    interventions = {
        "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
        "lockdown": 0, "selfiso": 0.0, "randseed": True,
        "seed_ids": BASE_SEED_IDS,
    }
    summaries = []
    for i in range(n_runs):
        print(f"  Run {i+1}/{n_runs} ... ", end="", flush=True)
        log_dir = f"scenario_a_run{i+1}"
        r = run_sim(interventions, log_dir)
        r["run"] = i + 1
        summaries.append(save(f"scenario_a_run{i+1}", r))
        print(f"  {summaries[-1]['unique_infected_people']} infections")

    counts = [s["unique_infected_people"] for s in summaries]
    print(f"\n  Infections across {n_runs} runs: {counts}")
    print(f"  Mean: {sum(counts)/len(counts):.1f}   Min: {min(counts)}   Max: {max(counts)}")
    (OUT_DIR / "scenario_a_summary.json").write_text(
        json.dumps({"runs": summaries, "infections_per_run": counts,
                    "mean": sum(counts)/len(counts), "min": min(counts), "max": max(counts)}, indent=2)
    )


def scenario_b(best_rate: float, best_dur: int, n_runs: int = 5):
    """Same DMP params but change IDENTITY of 12 seed persons each run."""
    print("\n" + "="*60)
    print("SCENARIO B: Different seed identities across runs")
    print("="*60)
    set_env(rate=best_rate, infectious_min=best_dur)

    # Load all valid person IDs from papdata
    papdata_path = Path("simulator/barnsdall/papdata.json")
    with open(papdata_path) as f:
        papdata = json.load(f)
    all_ids = list(papdata["people"].keys())

    summaries = []
    for i in range(n_runs):
        seed_ids = ",".join(random.sample(all_ids, 12))
        print(f"  Run {i+1}/{n_runs} seeds={seed_ids[:40]}... ", end="", flush=True)
        interventions = {
            "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0, "randseed": True,
            "seed_ids": seed_ids,
        }
        log_dir = f"scenario_b_run{i+1}"
        r = run_sim(interventions, log_dir)
        r["run"] = i + 1
        r["seed_ids"] = seed_ids
        summaries.append(save(f"scenario_b_run{i+1}", r))
        print(f"  {summaries[-1]['unique_infected_people']} infections")

    counts = [s["unique_infected_people"] for s in summaries]
    print(f"\n  Infections across {n_runs} runs: {counts}")
    (OUT_DIR / "scenario_b_summary.json").write_text(
        json.dumps({"runs": summaries, "infections_per_run": counts,
                    "mean": sum(counts)/len(counts), "min": min(counts), "max": max(counts)}, indent=2)
    )


def scenario_c(best_rate: float, best_dur: int):
    """Compare 2 vs 50 seeded infectious persons."""
    print("\n" + "="*60)
    print("SCENARIO C: 2 vs 50 initial seeds")
    print("="*60)
    set_env(rate=best_rate, infectious_min=best_dur)

    for seed_count in [2, 50]:
        print(f"\n  seed_count={seed_count} ... ", end="", flush=True)
        interventions = {
            "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0, "randseed": False,
            "seed_count": seed_count,
        }
        log_dir = f"scenario_c_seeds{seed_count}"
        r = run_sim(interventions, log_dir)
        save(f"scenario_c_seeds{seed_count}", r)
        print(f"  {r['unique_infected_people']} infections")


def scenario_d(best_rate: float, best_dur: int):
    """25 seeds + different interventions."""
    print("\n" + "="*60)
    print("SCENARIO D: Interventions (25 seeds)")
    print("="*60)
    set_env(rate=best_rate, infectious_min=best_dur)

    configs = {
        "no_intervention": {
            "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "masking_50pct": {
            "mask": 0.5, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "masking_80pct": {
            "mask": 0.8, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "vaccine_50pct": {
            "mask": 0.0, "vaccine": 0.5, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "vaccine_80pct": {
            "mask": 0.0, "vaccine": 0.8, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "social_distancing_50pct": {
            "mask": 0.0, "vaccine": 0.0, "capacity": 0.5,
            "lockdown": 0, "selfiso": 0.0,
        },
        "combined_mask_vaccine": {
            "mask": 0.5, "vaccine": 0.5, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.0,
        },
        "selfiso_50pct": {
            "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
            "lockdown": 0, "selfiso": 0.5,
        },
    }

    summaries = {}
    for name, cfg in configs.items():
        print(f"\n  {name} ... ", end="", flush=True)
        interventions = {**cfg, "randseed": False, "seed_count": 25}
        log_dir = f"scenario_d_{name}"
        r = run_sim(interventions, log_dir)
        summaries[name] = save(f"scenario_d_{name}", r)
        print(f"  {r['unique_infected_people']} infections")

    # Summary comparison
    print("\n  Intervention comparison:")
    print(f"  {'Scenario':35}  {'Infections':>12}")
    baseline = summaries.get("no_intervention", {}).get("unique_infected_people", 1)
    for name, s in summaries.items():
        n = s["unique_infected_people"]
        pct_reduction = 100 * (baseline - n) / baseline if baseline > 0 else 0
        print(f"  {name:35}  {n:>12}  ({pct_reduction:+.0f}% vs no-intervention)")

    (OUT_DIR / "scenario_d_summary.json").write_text(json.dumps(summaries, indent=2))


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-calib", action="store_true",
                    help="Skip calibration and use provided rate/duration")
    ap.add_argument("--rate", type=float, default=7000)
    ap.add_argument("--infectious-min", type=int, default=20160,
                    help="Fallback infectious duration in minutes (default: 20160 = 14 days)")
    ap.add_argument("--runs-a", type=int, default=5, help="Runs for scenario A")
    ap.add_argument("--runs-b", type=int, default=5, help="Runs for scenario B")
    ap.add_argument("--only", choices=["calib", "a", "b", "c", "d"],
                    help="Run only one scenario")
    args = ap.parse_args()

    # Calibration
    if args.only in (None, "calib"):
        if args.skip_calib:
            best = {"rate": args.rate, "infectious_min": args.infectious_min,
                    "infections": "skipped"}
        else:
            best = calibrate()
    else:
        best = {"rate": args.rate, "infectious_min": args.infectious_min}

    best_rate = best["rate"]
    best_dur = best["infectious_min"]

    if args.only in (None, "a"):
        scenario_a(best_rate, best_dur, args.runs_a)
    if args.only in (None, "b"):
        scenario_b(best_rate, best_dur, args.runs_b)
    if args.only in (None, "c"):
        scenario_c(best_rate, best_dur)
    if args.only in (None, "d"):
        scenario_d(best_rate, best_dur)

    print("\n" + "="*60)
    print("ALL SCENARIOS COMPLETE")
    print(f"Results in: {OUT_DIR}/")
    print("="*60)


if __name__ == "__main__":
    main()
