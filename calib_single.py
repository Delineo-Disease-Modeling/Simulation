#!/usr/bin/env python3
"""Single calibration run - called by subprocess."""
import json
import sys
from pathlib import Path
import pandas as pd

SIX_WEEKS_MINUTES = 6 * 7 * 24 * 60
SEED_IDS = "160,43,47,4,36,9,14,19,27,22,3,5"

def main():
    rate = float(sys.argv[1])
    
    from simulator import simulate
    
    log_dir = f"calibration_logs_{rate}"
    
    interventions = {
        "mask": 0.0,
        "vaccine": 0.0,
        "capacity": 1.0,
        "lockdown": 0,
        "selfiso": 0.0,
        "randseed": False,
        "seed_count": 12,
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
    
    infection_path = Path(log_dir) / "infection_logs.csv"
    if infection_path.exists():
        infections = pd.read_csv(infection_path)
        total = len(infections)
    else:
        total = 0
    
    print(json.dumps({"rate": rate, "total_infections": total}))

if __name__ == "__main__":
    main()
