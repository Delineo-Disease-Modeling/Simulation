#!/usr/bin/env python3
"""
Experiment (b): Run simulations with different seed identities.
Compare facility infection counts across runs.
"""

import json
import os
import random
import sys
from pathlib import Path

import pandas as pd

SIX_WEEKS_MINUTES = 6 * 7 * 24 * 60
TRANSMISSION_RATE = 7000
SEED_COUNT = 12
NUM_RUNS = 5

# Set transmission rate before importing simulator
os.environ["INFECTION_TRANSMISSION_RATE"] = str(TRANSMISSION_RATE)

def get_available_person_ids():
    """Get list of person IDs from papdata."""
    papdata_path = Path(__file__).parent / "simulator" / "barnsdall" / "papdata.json"
    with open(papdata_path) as f:
        papdata = json.load(f)
    return list(papdata["people"].keys())

def run_single(name: str, seed_ids: list[str], out_dir: Path):
    """Run a single simulation with given seed IDs."""
    from simulator import simulate
    
    log_dir = f"simulation_logs_{name}"
    
    interventions = {
        "mask": 0.0,
        "vaccine": 0.0,
        "capacity": 1.0,
        "lockdown": 0,
        "selfiso": 0.0,
        "randseed": False,  # deterministic
        "seed_count": len(seed_ids),
        "seed_ids": ",".join(seed_ids),
    }
    
    simulate.run_simulator(
        location="barnsdall",
        max_length=SIX_WEEKS_MINUTES,
        interventions=interventions,
        save_file=False,
        enable_logging=True,
        log_dir=log_dir,
    )
    
    # Summarize
    infection_path = Path(log_dir) / "infection_logs.csv"
    if infection_path.exists():
        infections = pd.read_csv(infection_path)
    else:
        infections = pd.DataFrame(columns=["timestep", "infected_person_id", "infector_person_id", 
                                           "infection_location_id", "infection_location_type", "variant"])
    
    total = len(infections)
    unique = infections["infected_person_id"].nunique() if total else 0
    
    by_location = (
        infections.groupby(["infection_location_type", "infection_location_id"], dropna=False)
        .size()
        .reset_index(name="infections")
        .sort_values("infections", ascending=False)
    )
    
    # Save outputs
    out_dir.mkdir(parents=True, exist_ok=True)
    by_location.to_csv(out_dir / f"{name}_locations.csv", index=False)
    
    summary = {
        "name": name,
        "seed_ids": seed_ids,
        "total_infections": int(total),
        "unique_infected": int(unique),
        "top_5_locations": by_location.head(5).to_dict(orient="records"),
    }
    (out_dir / f"{name}_summary.json").write_text(json.dumps(summary, indent=2))
    
    return summary, by_location

def main():
    out_dir = Path("experiment_b_outputs")
    out_dir.mkdir(exist_ok=True)
    
    # Get all person IDs
    all_ids = get_available_person_ids()
    print(f"Total available persons: {len(all_ids)}")
    
    # Generate different seed sets
    random.seed(42)  # reproducible selection
    seed_sets = []
    for i in range(NUM_RUNS):
        selected = random.sample(all_ids, SEED_COUNT)
        seed_sets.append(selected)
    
    # Run simulations
    results = []
    location_dfs = []
    
    for i, seed_ids in enumerate(seed_sets):
        name = f"seedset_{i}"
        print(f"\n=== Running {name} with seeds: {seed_ids} ===")
        summary, loc_df = run_single(name, seed_ids, out_dir)
        loc_df["run"] = name
        results.append(summary)
        location_dfs.append(loc_df)
        print(f"  Total infections: {summary['total_infections']}")
    
    # Aggregate analysis
    print("\n" + "="*60)
    print("SUMMARY OF EXPERIMENT (b): Different Seed Identities")
    print("="*60)
    
    # Variation in total infections
    totals = [r["total_infections"] for r in results]
    print(f"\nTotal infections across runs: {totals}")
    print(f"Mean: {sum(totals)/len(totals):.1f}, Min: {min(totals)}, Max: {max(totals)}")
    
    # Combine location data
    all_locs = pd.concat(location_dfs, ignore_index=True)
    
    # Find facilities with high variance
    loc_pivot = all_locs.pivot_table(
        index=["infection_location_type", "infection_location_id"],
        columns="run",
        values="infections",
        fill_value=0
    )
    loc_pivot["mean"] = loc_pivot.mean(axis=1)
    loc_pivot["std"] = loc_pivot.std(axis=1)
    loc_pivot["cv"] = loc_pivot["std"] / loc_pivot["mean"].replace(0, 1)  # coefficient of variation
    loc_pivot = loc_pivot.sort_values("mean", ascending=False)
    
    # Top 10 facilities by average infections
    print("\nTop 10 facilities by average infections:")
    print(loc_pivot.head(10)[["mean", "std", "cv"]].to_string())
    
    # Facilities with highest variance
    high_var = loc_pivot[loc_pivot["mean"] >= 2].sort_values("cv", ascending=False).head(10)
    print("\nFacilities with highest relative variation (CV, min 2 mean infections):")
    print(high_var[["mean", "std", "cv"]].to_string())
    
    # Save final report
    loc_pivot.to_csv(out_dir / "facility_comparison.csv")
    
    final_report = {
        "transmission_rate": TRANSMISSION_RATE,
        "seed_count": SEED_COUNT,
        "num_runs": NUM_RUNS,
        "infection_totals": totals,
        "mean_infections": sum(totals) / len(totals),
        "results": results,
    }
    (out_dir / "experiment_b_report.json").write_text(json.dumps(final_report, indent=2))
    
    print(f"\nOutputs saved to {out_dir}/")
    
    # Analysis of why variation occurs
    print("\n" + "="*60)
    print("ANALYSIS: Why do facility infection counts vary?")
    print("="*60)
    print("""
1. **Initial seed placement**: Different seeded persons live in different households
   and visit different facilities, affecting which locations get early infections.

2. **Network effects**: Some persons are "super-spreaders" due to their movement patterns
   (visiting crowded facilities more often), leading to more downstream infections.

3. **Timing effects**: When a person becomes infectious relative to when they visit
   high-traffic locations determines spread potential.

4. **Household structure**: Seeds in larger households spread to more people initially.
""")

if __name__ == "__main__":
    main()
