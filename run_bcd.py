#!/usr/bin/env python3
"""
Run Scenarios B, C, D for the Barnsdall disease simulation.

Scenario B: Same DMP params, 5 runs with different 12-person seed identities
Scenario C: 2 seeds vs 50 seeds (same DMP params)
Scenario D: 25 seeds + various interventions
"""
import json, os, sys, random, importlib
from pathlib import Path

SIX_WEEKS = 60480  # minutes
SEED_IDS_12 = "160,43,47,4,36,9,14,19,27,22,3,5"
OUT_DIR = Path("experiment_outputs")
OUT_DIR.mkdir(exist_ok=True)

# Fixed DMP params from calibration
RATE = 7000
DUR  = 1440  # fallback infected duration (minutes)

os.environ["INFECTION_TRANSMISSION_RATE"]  = str(RATE)
os.environ["FALLBACK_INFECTED_DURATION"]   = str(DUR)


def reload_sim():
    mods = [k for k in sys.modules if k.startswith('simulator')]
    for m in mods:
        try:
            importlib.reload(sys.modules[m])
        except Exception:
            pass
    from simulator import simulate
    return simulate


def run_sim(interventions, log_dir_name):
    sim = reload_sim()
    log_dir = str(Path(log_dir_name))
    sim.run_simulator(
        location="barnsdall",
        max_length=SIX_WEEKS,
        interventions=interventions,
        save_file=False,
        enable_logging=True,
        log_dir=log_dir,
    )
    return summarize(Path(log_dir))


def summarize(log_dir):
    import pandas as pd
    inf_path = log_dir / "infection_logs.csv"
    person_path = log_dir / "person_logs.csv"

    if inf_path.exists():
        df = pd.read_csv(inf_path)
    else:
        df = pd.DataFrame()

    total = len(df)
    unique = int(df["infected_person_id"].nunique()) if total else 0

    by_loc = []
    by_time = []
    if total:
        by_loc = (df.groupby(["infection_location_type", "infection_location_id"])
                  .size().reset_index(name="count")
                  .sort_values("count", ascending=False)
                  .head(15).to_dict(orient="records"))
        by_time = (df.groupby("timestep").size()
                   .reset_index(name="count")
                   .to_dict(orient="records"))

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
        "unique_infected": unique,
        "trajectory_tagged": trajectory_ok,
        "by_location": by_loc,
        "by_timestep": by_time,
    }


def save_json(name, data):
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2))
    print(f"  => {path.name}  (unique infected: {data.get('unique_infected', data.get('infections_per_run', '?'))})")


# ─── Scenario B ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SCENARIO B: 5 runs with different 12-person seed identities")
print("="*60)

all_ids = list(range(3478))  # person IDs 0..3477
random.seed(42)

b_results = []
for i in range(1, 6):
    seed_ids = ",".join(str(x) for x in random.sample(all_ids, 12))
    print(f"\n  Run {i}/5  seeds: {seed_ids[:60]}...")
    iv = {
        "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
        "lockdown": 0, "selfiso": 0.0, "randseed": True,
        "seed_ids": seed_ids,
    }
    r = run_sim(iv, f"scenB_run{i}_logs")
    r["run"] = i
    r["seed_ids"] = seed_ids
    b_results.append(r)
    save_json(f"scenB_run{i}", r)
    print(f"     => {r['unique_infected']} infections")

b_counts = [r["unique_infected"] for r in b_results]
b_summary = {
    "description": "Different 12-person seed identities, randseed=True, 5 runs",
    "rate": RATE, "infectious_dur_min": DUR,
    "runs": b_results,
    "infections_per_run": b_counts,
    "mean": sum(b_counts)/len(b_counts),
    "min": min(b_counts),
    "max": max(b_counts),
}
save_json("scenario_b_summary", b_summary)
print(f"\n  B results: {b_counts}  mean={b_summary['mean']:.1f}  range=[{b_summary['min']},{b_summary['max']}]")


# ─── Scenario C ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SCENARIO C: 2 seeds vs 50 seeds (no randseed)")
print("="*60)

c_results = {}
for seed_count in [2, 50]:
    print(f"\n  seed_count={seed_count} ...")
    iv = {
        "mask": 0.0, "vaccine": 0.0, "capacity": 1.0,
        "lockdown": 0, "selfiso": 0.0, "randseed": False,
        "seed_count": seed_count,
    }
    r = run_sim(iv, f"scenC_seeds{seed_count}_logs")
    c_results[str(seed_count)] = r
    save_json(f"scenC_seeds{seed_count}", r)
    print(f"     => {r['unique_infected']} infections")

save_json("scenario_c_summary", {
    "description": "2 vs 50 seed persons, randseed=False",
    "rate": RATE, "infectious_dur_min": DUR,
    "seeds_2": c_results["2"],
    "seeds_50": c_results["50"],
})


# ─── Scenario D ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("SCENARIO D: 25 seeds + interventions")
print("="*60)

d_configs = {
    "no_intervention":       {"mask": 0.0, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "masking_50pct":         {"mask": 0.5, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "masking_80pct":         {"mask": 0.8, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "vaccine_50pct":         {"mask": 0.0, "vaccine": 0.5, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "vaccine_80pct":         {"mask": 0.0, "vaccine": 0.8, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "social_distancing_50":  {"mask": 0.0, "vaccine": 0.0, "capacity": 0.5, "lockdown": 0, "selfiso": 0.0},
    "combined_mask_vaccine": {"mask": 0.5, "vaccine": 0.5, "capacity": 1.0, "lockdown": 0, "selfiso": 0.0},
    "selfiso_50pct":         {"mask": 0.0, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0, "selfiso": 0.5},
}

d_results = {}
for name, cfg in d_configs.items():
    print(f"\n  {name} ...")
    iv = {**cfg, "randseed": False, "seed_count": 25}
    r = run_sim(iv, f"scenD_{name}_logs")
    d_results[name] = r
    save_json(f"scenD_{name}", r)
    print(f"     => {r['unique_infected']} infections")

baseline = d_results.get("no_intervention", {}).get("unique_infected", 1)
print("\n  === Scenario D Summary ===")
print(f"  {'Scenario':35}  {'Infected':>9}  {'Reduction':>10}")
for name, r in d_results.items():
    n = r["unique_infected"]
    pct = 100 * (baseline - n) / baseline if baseline > 0 else 0
    print(f"  {name:35}  {n:>9}  {pct:>+9.1f}%")

save_json("scenario_d_summary", {
    "description": "25 seeds, randseed=False, various interventions",
    "rate": RATE, "infectious_dur_min": DUR,
    "baseline_infected": baseline,
    "results": d_results,
})

print("\n" + "="*60)
print("ALL SCENARIOS COMPLETE")
print(f"Results written to: {OUT_DIR}/")
print("="*60)
