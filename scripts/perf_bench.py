#!/usr/bin/env python3
"""Minimal sim-stage performance harness.

Times `simulate.run_simulator` against a cached papdata + patterns pair,
N measured runs after a discarded smoke run (covers JIT warmup and
import-side-effect noise). Re-seeds Python and numpy RNGs before each
run for reproducibility. Hashes the resulting simdata.json.gz so a
behavioral drift between runs or branches is visible.

Usage:
    scripts/perf_bench.py \\
        --sim-root /path/to/Simulation/_worktrees/phase2a-numba-transmission \\
        --papdata  /Users/ryad/Code/delineo/Fullstack/db/be97844d-527d-4057-b5a0-cd74653041b7.gz \\
        --patterns /Users/ryad/Code/delineo/Fullstack/db/5e2cfba0-bb54-4e12-8588-dd55e14a40c3.gz \\
        --runs 3 --length 1440 --label baseline

Emits a summary JSON on stdout; per-run progress on stderr.
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import io
import json
import random
import statistics
import sys
import tempfile
import time
from pathlib import Path


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sim-root", required=True,
                   help="Path to Simulation checkout root (must contain simulator/)")
    p.add_argument("--papdata", required=True, help="Path to papdata .gz")
    p.add_argument("--patterns", required=True, help="Path to patterns .gz")
    p.add_argument("--length", type=int, default=1440,
                   help="Simulation length in minutes (default: 1440 = 24h)")
    p.add_argument("--runs", type=int, default=3,
                   help="Measured runs (default 3); 1 smoke run is always discarded")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--label", default="run")
    p.add_argument("--dmp-mode", default="auto", choices=["auto", "required", "off"],
                   help="DMP timeline source. 'off' uses the local fallback and "
                        "skips the per-infection HTTP call (default: auto)")
    return p.parse_args()


def main() -> int:
    import numpy as np  # imported here to avoid before-args side effects

    args = parse_args()

    sim_root = Path(args.sim_root).resolve()
    if not (sim_root / "simulator").is_dir():
        print(f"[bench] error: {sim_root} does not contain simulator/", file=sys.stderr)
        return 2

    sys.path.insert(0, str(sim_root))
    from simulator.runner import SimulationRunner  # type: ignore[import-not-found]

    papdata_path = Path(args.papdata).resolve()
    patterns_path = Path(args.patterns).resolve()

    # Pre-load papdata + patterns once and reuse across runs. The default
    # data_loader hits the Fullstack dev server over HTTP; we replace it
    # with a closure that returns the cached pair directly.
    def _load_json_gz(path: Path):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    cached_papdata = _load_json_gz(papdata_path)
    cached_patterns = _load_json_gz(patterns_path)

    def local_loader(_url: str, timeout: int = 360):
        return cached_papdata, cached_patterns

    interventions = [{
        "time": 0,
        "mask": 0.0,
        "vaccine": 0.0,
        "capacity": 1.0,
        "lockdown": 0.0,
        "selfiso": 0.0,
    }]

    def one_run(label: str) -> tuple[float, str]:
        random.seed(args.seed)
        np.random.seed(args.seed)
        with tempfile.TemporaryDirectory() as td:
            payload = {
                "length": args.length,
                "randseed": False,
                "interventions": interventions,
                "czone_id": 1,
                "dmp_mode": args.dmp_mode,
            }
            logs = io.StringIO()
            t0 = time.perf_counter()
            with contextlib.redirect_stdout(logs), contextlib.redirect_stderr(logs):
                runner = SimulationRunner(
                    simdata=payload,
                    enable_logging=False,
                    output_dir=td,
                    progress_callback=None,
                    data_loader=local_loader,
                )
                result = runner.run()
            elapsed = time.perf_counter() - t0
            if isinstance(result, dict) and "error" in result:
                raise RuntimeError(
                    f"simulation failed in {label}: {result['error']}\n"
                    f"--- logs ---\n{logs.getvalue()}"
                )
            simdata_path = Path(result["simdata"])
            if not simdata_path.is_file():
                raise RuntimeError(
                    f"expected simdata at {simdata_path} but file is missing; "
                    f"result keys={list(result)}"
                )
            sha = hash_file(simdata_path)
        return elapsed, sha

    timings: list[float] = []
    hashes: list[str] = []

    smoke_elapsed, smoke_sha = one_run("smoke")
    print(f"[{args.label}] smoke   {smoke_elapsed:6.2f}s  sha={smoke_sha[:16]}", file=sys.stderr)

    for i in range(args.runs):
        elapsed, sha = one_run(f"measured-{i+1}")
        timings.append(elapsed)
        hashes.append(sha)
        print(f"[{args.label}] meas {i+1}  {elapsed:6.2f}s  sha={sha[:16]}", file=sys.stderr)

    summary = {
        "label": args.label,
        "sim_root": str(sim_root),
        "length_minutes": args.length,
        "seed": args.seed,
        "papdata": str(papdata_path),
        "patterns": str(patterns_path),
        "smoke": {"elapsed": smoke_elapsed, "sha": smoke_sha},
        "measured": {
            "n": args.runs,
            "min": min(timings),
            "median": statistics.median(timings),
            "max": max(timings),
            "all": timings,
        },
        "hashes": hashes,
        "hashes_consistent": len(set(hashes)) == 1,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
