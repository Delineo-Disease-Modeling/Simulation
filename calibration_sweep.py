#!/usr/bin/env python3
"""
Calibration sweep to find transmission rate yielding ~250 infections.
"""

import json
import os
from pathlib import Path

import pandas as pd

SIX_WEEKS_MINUTES = 6 * 7 * 24 * 60
SEED_COUNT = 12
TARGET_INFECTIONS = 250

# Use consistent seed IDs for calibration
SEED_IDS = "160,43,47,4,36,9,14,19,27,22,3,5"

# Sweep transmission rates - these are quanta rates, smaller = fewer infections
RATES_TO_TEST = [0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.08, 0.05]

def run_single(rate: int) -> dict:
    """Run simulation with given transmission rate."""
    # Set env var before importing simulator
    os.environ["INFECTION_TRANSMISSION_RATE"] = str(rate)
    
    # Force reimport
    import importlib
    import simulator.config
    importlib.reload(simulator.config)
    
    from simulator import simulate
    
    log_dir = f"calibration_logs_{rate}"
    
    interventions = {
        "mask": 0.0,
        "vaccine": 0.0,
        "capacity": 1.0,
        "lockdown": 0,
        "selfiso": 0.0,
        "randseed": False,
        "seed_count": SEED_COUNT,
        "seed_ids": SEED_IDS,
    }
    
    simulate.run_simulator(
        location="barnsdall",
        max_length=SIX_WEEKS_MINUTES,
        interventions=interventions,
        save_file=False,
        enable_logging=True,
        log_dir=log_dir,
    )
    
    # Count infections
    infection_path = Path(log_dir) / "infection_logs.csv"
    if infection_path.exists():
        infections = pd.read_csv(infection_path)
        total = len(infections)
    else:
        total = 0
    
    return {"rate": rate, "total_infections": total}

def main():
    results = []
    
    print("Calibration Sweep: Finding transmission rate for ~250 infections")
    print("=" * 60)
    
    for rate in RATES_TO_TEST:
        print(f"\nTesting rate={rate}...", end=" ", flush=True)
        result = run_single(rate)
        results.append(result)
        print(f"Infections: {result['total_infections']}")
        
        # Early stop if we're close enough
        if abs(result["total_infections"] - TARGET_INFECTIONS) <= 10:
            print(f"\n*** Found target! Rate {rate} yields {result['total_infections']} infections ***")
            break
    
    print("\n" + "=" * 60)
    print("CALIBRATION RESULTS")
    print("=" * 60)
    
    for r in results:
        diff = r["total_infections"] - TARGET_INFECTIONS
        marker = " <-- TARGET" if abs(diff) <= 15 else ""
        print(f"Rate {r['rate']:5d}: {r['total_infections']:3d} infections (diff: {diff:+4d}){marker}")
    
    # Find best rate
    best = min(results, key=lambda x: abs(x["total_infections"] - TARGET_INFECTIONS))
    print(f"\nBest rate: {best['rate']} with {best['total_infections']} infections")
    
    # Save results
    Path("calibration_outputs").mkdir(exist_ok=True)
    with open("calibration_outputs/calibration_results.json", "w") as f:
        json.dump({"target": TARGET_INFECTIONS, "results": results, "best": best}, f, indent=2)
    
    print(f"\nResults saved to calibration_outputs/calibration_results.json")

if __name__ == "__main__":
    main()
