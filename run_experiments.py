import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd


SIX_WEEKS_MINUTES = 6 * 7 * 24 * 60


@dataclass(frozen=True)
class RunSpec:
    name: str
    length: int
    interventions: dict


def _summarize_log_dir(log_dir: Path) -> dict:
    infection_path = log_dir / "infection_logs.csv"
    person_path = log_dir / "person_logs.csv"

    if infection_path.exists():
        infections = pd.read_csv(infection_path)
    else:
        infections = pd.DataFrame(
            columns=[
                "timestep",
                "infected_person_id",
                "infector_person_id",
                "infection_location_id",
                "infection_location_type",
                "variant",
            ]
        )

    total_infection_events = int(len(infections))
    unique_infected_people = int(infections["infected_person_id"].nunique()) if total_infection_events else 0

    by_location = (
        infections.groupby(["infection_location_type", "infection_location_id"], dropna=False)
        .size()
        .reset_index(name="infection_events")
        .sort_values("infection_events", ascending=False)
    )

    by_time = (
        infections.groupby(["timestep"], dropna=False)
        .size()
        .reset_index(name="infection_events")
        .sort_values("timestep")
    )

    trajectory_checks = {}
    if person_path.exists() and total_infection_events:
        people = pd.read_csv(person_path)
        first_inf = infections.groupby("infected_person_id")["timestep"].min().reset_index()
        merged = first_inf.merge(people, how="left", left_on="infected_person_id", right_on="person_id")
        merged = merged[merged["timestep_y"].notna()]
        merged = merged[merged["timestep_y"] >= merged["timestep_x"]]
        tagged = merged["infection_status"].notna().mean() if len(merged) else 0.0
        trajectory_checks = {
            "fraction_with_person_log_after_infection": float(tagged),
            "infected_people_with_any_person_log": int(merged["infected_person_id"].nunique()) if len(merged) else 0,
        }

    return {
        "log_dir": str(log_dir),
        "total_infection_events": int(total_infection_events),
        "unique_infected_people": int(unique_infected_people),
        "trajectory_checks": trajectory_checks,
        "top_locations": by_location.head(20),
        "by_time": by_time,
    }


def run_once(spec: RunSpec, out_dir: Path) -> dict:
    from simulator import simulate
    ts = int(datetime.now().timestamp())
    log_dir = f"simulation_logs_{spec.name}_{ts}"
    simulate.run_simulator(
        location="barnsdall",
        max_length=spec.length,
        interventions=spec.interventions,
        save_file=False,
        enable_logging=True,
        log_dir=log_dir,
    )
    summary = _summarize_log_dir(Path(log_dir))

    out_dir.mkdir(parents=True, exist_ok=True)
    summary["top_locations"].to_csv(out_dir / f"{spec.name}_top_locations.csv", index=False)
    summary["by_time"].to_csv(out_dir / f"{spec.name}_infections_over_time.csv", index=False)

    json_summary = {k: v for k, v in summary.items() if k not in {"top_locations", "by_time"}}
    (out_dir / f"{spec.name}_summary.json").write_text(json.dumps(json_summary, indent=2))
    return json_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="experiment_outputs")
    parser.add_argument("--length", type=int, default=SIX_WEEKS_MINUTES)
    parser.add_argument("--transmission_rate", type=float, default=None)
    parser.add_argument("--randseed", action="store_true")
    parser.add_argument("--no-randseed", dest="randseed", action="store_false")
    parser.set_defaults(randseed=True)

    parser.add_argument("--seed-count", type=int, default=12)
    parser.add_argument("--seed-ids", type=str, default=None)

    parser.add_argument("--mask", type=float, default=0.0)
    parser.add_argument("--vaccine", type=float, default=0.0)
    parser.add_argument("--capacity", type=float, default=1.0)
    parser.add_argument("--lockdown", type=int, default=0)
    parser.add_argument("--selfiso", type=float, default=0.0)

    args = parser.parse_args()

    if args.transmission_rate is not None:
        os.environ["INFECTION_TRANSMISSION_RATE"] = str(args.transmission_rate)

    # Import after env vars are set so simulator/config.py sees the right values.
    # (Import occurs inside run_once.)

    interventions = {
        "mask": args.mask,
        "vaccine": args.vaccine,
        "capacity": args.capacity,
        "lockdown": args.lockdown,
        "selfiso": args.selfiso,
        "randseed": args.randseed,
        "seed_count": args.seed_count,
    }
    if args.seed_ids:
        interventions["seed_ids"] = args.seed_ids

    spec = RunSpec(name="single_run", length=args.length, interventions=interventions)
    out = run_once(spec, Path(args.out))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
