"""Ensemble / scenario-sweep runner — run many simulations in parallel.

Two axes of variation, one mechanism:

* **replicates** — same scenario, different RNG seed → a *distribution* of
  outcomes (uncertainty bands), since the simulator is stochastic.
* **scenarios** — different inputs (e.g. interventions) → comparison.

The cross-product (M scenarios × K replicates) yields **intervention
comparison with confidence bands** — e.g. "masks-at-day-0 → 8.0k ± 1.5k
infected vs no-intervention → 15.0k ± 3.0k".

Design notes:
* Process-based (`ProcessPoolExecutor`, one worker per core) to sidestep the
  GIL — each replicate is CPU-bound pure Python.
* Workers load the cached papdata/patterns from disk (paths, not pickled
  65 MB dicts) and cache them per process, so each worker loads once and
  reuses across the tasks it handles.
* Each task runs the existing ``SimulationRunner`` with ``randseed=True`` and
  a per-task seed, then reduces the in-memory output to a per-timestep
  cumulative-infected count (a ~720-int array) — tiny to ship back.

Seeding is reproducible: ``SeedSequence(base_seed).spawn(M*K)`` gives
independent per-(scenario,replicate) streams. Relies on the runner respecting
the process RNG when ``randseed=True`` and on run_simulation no longer
reseeding numpy per call (both merged earlier).
"""
from __future__ import annotations

import argparse
import gzip
import json
import multiprocessing
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

# Per-process cache so each worker loads papdata/patterns once, not per task.
_DATA_CACHE: dict = {}

# Read-only data loaded once in the parent and inherited by forked workers via
# copy-on-write — avoids each worker re-decompressing the (large) patterns file,
# which otherwise thrashes memory and makes parallel *slower* than serial.
_SHARED: dict = {}


def _load_gz(path: str):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _get_data(papdata_path: str, patterns_path: str):
    key = (papdata_path, patterns_path)
    if key not in _DATA_CACHE:
        _DATA_CACHE[key] = (_load_gz(papdata_path), _load_gz(patterns_path))
    return _DATA_CACHE[key]


def _count_cumulative_infected(infection_snapshot: dict) -> int:
    """Distinct people with any non-susceptible state at this timestep
    (variant_infected accumulates, so this is the cumulative attack count)."""
    pids: set = set()
    for variant_map in infection_snapshot.values():
        pids.update(variant_map.keys())
    return len(pids)


def _run_replicate(task: dict) -> dict:
    """Worker: one (scenario, replicate). Seeds RNG, runs the sim, returns a
    compact per-timestep cumulative-infected series."""
    sim_root = task["sim_root"]
    if sim_root not in sys.path:
        sys.path.insert(0, sim_root)
    from simulator.runner import SimulationRunner  # type: ignore[import-not-found]

    # Prefer data inherited from the parent via fork (copy-on-write); fall back
    # to loading it ourselves (e.g. spawn start method, or direct call).
    if "data" in _SHARED:
        papdata, patterns = _SHARED["data"]
    else:
        papdata, patterns = _get_data(task["papdata_path"], task["patterns_path"])

    seed = task["seed"]
    random.seed(seed)
    np.random.seed(seed)

    simdata = {**task["simdata"], "randseed": True}  # don't let runner force seed 0
    t0 = time.perf_counter()
    runner = SimulationRunner(
        simdata=simdata,
        enable_logging=False,
        output_dir=None,  # in-memory; we reduce and discard
        progress_callback=None,
        data_loader=lambda _u, timeout=360: (papdata, patterns),
    )
    result = runner.run()
    elapsed = time.perf_counter() - t0

    simdata_out = result.get("result", {}) if isinstance(result, dict) else {}
    ordered_ts = sorted(simdata_out, key=lambda t: int(t))
    infected_by_ts = [_count_cumulative_infected(simdata_out[t]) for t in ordered_ts]
    return {
        "label": task["label"],
        "seed": seed,
        "timesteps": [int(t) for t in ordered_ts],
        "infected_by_ts": infected_by_ts,
        "final": infected_by_ts[-1] if infected_by_ts else 0,
        "elapsed": elapsed,
    }


def run_ensemble(
    scenarios: list[dict],
    papdata_path: str,
    patterns_path: str,
    replicates: int = 10,
    base_seed: int = 0,
    max_workers: int | None = None,
    percentiles: tuple = (5, 50, 95),
    sim_root: str | None = None,
) -> dict:
    """Run ``scenarios`` × ``replicates`` simulations in parallel and aggregate.

    Each scenario is ``{"label": str, "simdata": {...}}`` where ``simdata``
    carries its own ``interventions``/``length``/etc. Returns per-scenario
    percentile bands over time plus a cross-scenario comparison.
    """
    sim_root = sim_root or str(Path(__file__).resolve().parent.parent)
    n = len(scenarios) * replicates
    seed_states = np.random.SeedSequence(base_seed).spawn(n)

    tasks: list[dict] = []
    i = 0
    for scenario in scenarios:
        for _rep in range(replicates):
            tasks.append({
                "label": scenario["label"],
                "seed": int(seed_states[i].generate_state(1)[0]),
                "simdata": scenario["simdata"],
                "papdata_path": papdata_path,
                "patterns_path": patterns_path,
                "sim_root": sim_root,
            })
            i += 1

    if max_workers is None:
        cores = max(1, (os.cpu_count() or 2) - 1)
        # Throughput here is memory-bound, not core-bound: under spawn each
        # worker re-loads the (large) data, so too many workers thrash and run
        # *slower* than fewer. Under fork the data is shared (COW), so cores is
        # fine. Cap spawn conservatively; callers can override.
        if multiprocessing.get_context().get_start_method() == "fork":
            max_workers = cores
        else:
            max_workers = min(cores, 4)

    # Use the platform default start method. On Linux that's fork: load the
    # large read-only data once in the parent and let workers inherit it via
    # copy-on-write (no per-worker re-decompression, pages shared not copied).
    # On macOS the default is spawn (forcing fork crashes after numpy/Accelerate
    # init), and spawn doesn't inherit globals, so workers load their own copy —
    # bound max_workers there to avoid memory thrash from N big copies.
    mp_context = multiprocessing.get_context()
    if mp_context.get_start_method() == "fork":
        _SHARED["data"] = (_load_gz(papdata_path), _load_gz(patterns_path))
    else:
        _SHARED.pop("data", None)

    t0 = time.perf_counter()
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp_context) as pool:
        for r in pool.map(_run_replicate, tasks):
            results.append(r)
    wall = time.perf_counter() - t0
    _SHARED.pop("data", None)

    return _aggregate(results, replicates, base_seed, max_workers, wall, percentiles)


def _aggregate(results, replicates, base_seed, max_workers, wall, percentiles) -> dict:
    by_label: dict[str, list] = {}
    for r in results:
        by_label.setdefault(r["label"], []).append(r)

    scenarios_out: dict[str, dict] = {}
    for label, reps in by_label.items():
        timesteps = reps[0]["timesteps"]
        matrix = np.array([r["infected_by_ts"] for r in reps])  # (K, T)
        bands = {f"p{p}": np.percentile(matrix, p, axis=0).round(1).tolist() for p in percentiles}
        bands["mean"] = matrix.mean(axis=0).round(1).tolist()
        finals = sorted(int(r["final"]) for r in reps)
        scenarios_out[label] = {
            "replicates": len(reps),
            "timesteps": timesteps,
            "infected_bands": bands,
            "final_infected": {
                "mean": round(float(np.mean(finals)), 1),
                **{f"p{p}": round(float(np.percentile(finals, p)), 1) for p in percentiles},
                "min": finals[0],
                "max": finals[-1],
                "all": finals,
            },
        }

    comparison = sorted(
        (
            {
                "label": label,
                "final_mean": s["final_infected"]["mean"],
                "final_p5": s["final_infected"].get("p5"),
                "final_p95": s["final_infected"].get("p95"),
            }
            for label, s in scenarios_out.items()
        ),
        key=lambda x: x["final_mean"],
    )

    return {
        "base_seed": base_seed,
        "replicates_per_scenario": replicates,
        "n_scenarios": len(by_label),
        "total_runs": len(results),
        "max_workers": max_workers,
        "wall_clock_s": round(wall, 2),
        "throughput_runs_per_min": round(len(results) / wall * 60, 1),
        "scenarios": scenarios_out,
        "comparison": comparison,
    }


def _demo_scenarios(length: int, dmp_mode: str) -> list[dict]:
    """Two contrasting intervention scenarios for the CLI demo."""
    def iv(mask):
        return [{"time": 0, "mask": mask, "vaccine": 0.0, "capacity": 1.0,
                 "lockdown": 0.0, "selfiso": 0.0}]

    base = {"length": length, "czone_id": 1, "dmp_mode": dmp_mode}
    return [
        {"label": "baseline", "simdata": {**base, "interventions": iv(0.0)}},
        {"label": "masks_0.7", "simdata": {**base, "interventions": iv(0.7)}},
    ]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--papdata", required=True)
    p.add_argument("--patterns", required=True)
    p.add_argument("--length", type=int, default=43200)
    p.add_argument("--replicates", type=int, default=4)
    p.add_argument("--base-seed", type=int, default=0)
    p.add_argument("--max-workers", type=int, default=None)
    p.add_argument("--dmp-mode", default="auto", choices=["auto", "required", "off"])
    args = p.parse_args()

    scenarios = _demo_scenarios(args.length, args.dmp_mode)
    out = run_ensemble(
        scenarios,
        papdata_path=str(Path(args.papdata).resolve()),
        patterns_path=str(Path(args.patterns).resolve()),
        replicates=args.replicates,
        base_seed=args.base_seed,
        max_workers=args.max_workers,
    )

    c = out
    print(f"\n{c['total_runs']} runs ({c['n_scenarios']} scenarios x "
          f"{c['replicates_per_scenario']} replicates) on {c['max_workers']} workers "
          f"in {c['wall_clock_s']}s  ->  {c['throughput_runs_per_min']} runs/min",
          file=sys.stderr)
    print("\nfinal cumulative infected (mean [p5, p95]):", file=sys.stderr)
    for row in c["comparison"]:
        print(f"  {row['label']:>12}: {row['final_mean']:>8.0f}  "
              f"[{row['final_p5']:.0f}, {row['final_p95']:.0f}]", file=sys.stderr)
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
