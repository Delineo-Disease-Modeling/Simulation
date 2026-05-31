#!/usr/bin/env python3
"""Full-sim ensemble equivalence check: pairwise vs aggregate Wells-Riley.

Replays a real cached (papdata, patterns) pair through SimulationRunner K times
per transmission model, each with an independent seed, and compares the two
ensembles. A week of unmitigated Delta saturates the *final* epidemic size
either way, so the discriminating signal is the GROWTH PHASE — this compares the
cumulative-infected curve at hourly checkpoints, not just the endpoint.

For each model it records, per run: the cumulative-infected curve (len of the
ever-infected set at every movement timestep), the final size, and wall-clock.
It then reports, at several checkpoints, mean +/- 95% CI for each model and the
standardized gap |dmean| / combined-SE. Verdict PASS if every checkpoint gap is
within --sigma.

Usage:
    scripts/equivalence_ensemble.py --papdata <gz> --patterns <gz> \\
        --length 10080 --runs 8 --dmp-mode auto
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import io
import json
import math
import os
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_captured: dict = {}
_curve: list = []  # (ts, cumulative_infected) appended by the write_snapshot wrap


def _load_json_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--papdata", required=True)
    p.add_argument("--patterns", required=True)
    p.add_argument("--length", type=int, default=10080)
    p.add_argument("--runs", type=int, default=8, help="replicates per model")
    p.add_argument("--seed-base", type=int, default=1000)
    p.add_argument("--initial-infected", type=int, default=25,
                   help="initial seed count; >1 gives a smoother growth-phase curve")
    p.add_argument("--dmp-mode", default="auto", choices=["auto", "required", "off"])
    p.add_argument("--sigma", type=float, default=3.0)
    p.add_argument("--checkpoints", default="1440,2880,4320,7200,10080",
                   help="minute marks to compare the cumulative curve at")
    return p.parse_args()


def main() -> int:
    import numpy as np

    args = parse_args()
    from simulator.runner import SimulationRunner
    import simulator.infectionmgr as _infmod

    # Capture the InfectionManager (final infected set) and hook write_snapshot
    # to record the cumulative-infected curve cheaply (len of a set per ts).
    _orig_init = _infmod.InfectionManager.__init__

    def _cap_init(self, *a, **k):
        _orig_init(self, *a, **k)
        _captured["mgr"] = self

    _infmod.InfectionManager.__init__ = _cap_init

    _orig_ws = SimulationRunner.write_snapshot

    def _ws(self, context, ts_str):
        _orig_ws(self, context, ts_str)
        _curve.append((int(ts_str), len(context.infection_manager.infected)))

    SimulationRunner.write_snapshot = _ws

    papdata = _load_json_gz(Path(args.papdata).resolve())
    patterns = _load_json_gz(Path(args.patterns).resolve())
    n_people = len(papdata.get("people", {}))
    print(f"loaded {n_people} people; length={args.length}min; runs/model={args.runs}; "
          f"dmp={args.dmp_mode}\n", flush=True)

    def local_loader(_url, timeout=360):
        return papdata, patterns

    interventions = [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                      "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}]

    def one_run(aggregate: bool, seed: int):
        random.seed(seed)
        np.random.seed(seed)
        _captured.clear()
        _curve.clear()
        with tempfile.TemporaryDirectory() as td:
            payload = {
                "length": args.length, "randseed": True,  # we seed manually above
                "interventions": interventions, "czone_id": 1,
                "initial_infected_count": args.initial_infected,
                "dmp_mode": args.dmp_mode, "aggregate_transmission": aggregate,
            }
            logs = io.StringIO()
            t0 = time.perf_counter()
            with contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
                runner = SimulationRunner(payload, enable_logging=False, output_dir=td,
                                          progress_callback=None, data_loader=local_loader)
                result = runner.run()
            elapsed = time.perf_counter() - t0
            if isinstance(result, dict) and "error" in result:
                raise RuntimeError(f"sim failed: {result['error']}\n{logs.getvalue()[-2000:]}")
            final = len(_captured["mgr"].infected)
            curve = dict(_curve)  # ts -> cumulative
        return {"final": final, "curve": curve, "elapsed": elapsed}

    arms = {"pairwise": False, "aggregate": True}
    results = {k: [] for k in arms}
    for arm, agg in arms.items():
        for r in range(args.runs):
            seed = args.seed_base + r
            res = one_run(agg, seed)
            results[arm].append(res)
            print(f"[{arm:9}] run {r+1}/{args.runs} seed={seed}  "
                  f"final={res['final']:6d}  {res['elapsed']:6.1f}s", flush=True)
        print("", flush=True)

    checkpoints = [int(x) for x in args.checkpoints.split(",") if x.strip()]
    checkpoints = [c for c in checkpoints if c <= args.length]

    def stats(vals):
        n = len(vals)
        m = statistics.mean(vals)
        sd = statistics.stdev(vals) if n > 1 else 0.0
        sem = sd / math.sqrt(n) if n else 0.0
        return m, sd, sem

    print("=" * 74)
    print(f"{'checkpoint':>10} | {'pairwise mean+/-95%CI':>26} | {'aggregate mean+/-95%CI':>26} | gap")
    print("-" * 74)
    worst = 0.0
    for cp in checkpoints:
        pv = [run["curve"].get(cp, run["final"]) for run in results["pairwise"]]
        av = [run["curve"].get(cp, run["final"]) for run in results["aggregate"]]
        pm, _, psem = stats(pv)
        am, _, asem = stats(av)
        comb = math.sqrt(psem**2 + asem**2)
        gap = abs(pm - am) / comb if comb > 0 else 0.0
        worst = max(worst, gap)
        label = "final" if cp == args.length else f"{cp//60}h"
        print(f"{label:>10} | {pm:10.1f} +/- {1.96*psem:8.1f} | "
              f"{am:10.1f} +/- {1.96*asem:8.1f} | {gap:4.2f} sigma")

    pe = statistics.mean([r["elapsed"] for r in results["pairwise"]])
    ae = statistics.mean([r["elapsed"] for r in results["aggregate"]])
    print("=" * 74)
    print(f"wall-clock/run: pairwise {pe:.1f}s  aggregate {ae:.1f}s  "
          f"({(pe-ae)/pe*100:+.1f}% end-to-end)")
    verdict = "PASS" if worst <= args.sigma else "FAIL"
    print(f"worst checkpoint gap: {worst:.2f} sigma (tolerance {args.sigma})  -> {verdict}")
    return 0 if worst <= args.sigma else 1


if __name__ == "__main__":
    sys.exit(main())
