#!/usr/bin/env python3
"""Minimal sim-stage performance harness + behavioral golden guard.

Times `SimulationRunner.run` against a cached papdata + patterns pair,
N measured runs after a discarded smoke run (covers JIT warmup and
import-side-effect noise). Re-seeds Python and numpy RNGs before each run
for reproducibility, and reports a fast file hash so timing-run drift is
visible at a glance.

Golden guard (--write-golden / --check-golden): freezes a behavioral
fingerprint — a *canonical* content hash of simdata and patterns plus the
total infected count — at a fixed seed/length/dmp-mode. The canonical hash
decompresses, parses, and re-serializes with sorted keys, so it is immune
to serialization-format changes (orjson vs json, gzip level, key order)
and trips only on a genuine change in simulation output. This is the guard
rail for representation-only refactors (e.g. struct-of-arrays), which must
keep output byte-identical.

Usage:
    scripts/perf_bench.py --sim-root <root> --papdata <gz> --patterns <gz> \\
        --length 2880 --runs 3 --dmp-mode off --label baseline

    # freeze a golden, then later check against it:
    scripts/perf_bench.py ... --write-golden _perf-runs/golden.json
    scripts/perf_bench.py ... --check-golden _perf-runs/golden.json

Emits a summary JSON on stdout; per-run progress on stderr. In
--check-golden mode, exits non-zero on drift.
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

# Populated by the InfectionManager.__init__ monkeypatch so we can read the
# final infected set after a run without the runner exposing it.
_captured: dict = {}


def hash_file(path: Path) -> str:
    """Fast hash of the raw (gzipped) bytes — sensitive to serialization
    format. Used for the cheap per-run consistency check."""
    h = hashlib.sha256()
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(path: Path) -> str:
    """Format-agnostic content hash: decompress, parse, re-serialize with
    sorted keys. Immune to whitespace/gzip-level/key-order changes; trips
    only on a change in the actual data."""
    with gzip.open(path, "rb") as f:
        data = json.loads(f.read())
    canon = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canon).hexdigest()


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
    p.add_argument("--write-golden", metavar="PATH",
                   help="Write a behavioral golden (canonical hashes + infected) to PATH")
    p.add_argument("--check-golden", metavar="PATH",
                   help="Check the run against a golden at PATH; exit 1 on drift")
    return p.parse_args()


def main() -> int:
    import numpy as np  # imported here to avoid before-args side effects

    args = parse_args()
    golden_mode = bool(args.write_golden or args.check_golden)

    sim_root = Path(args.sim_root).resolve()
    if not (sim_root / "simulator").is_dir():
        print(f"[bench] error: {sim_root} does not contain simulator/", file=sys.stderr)
        return 2

    sys.path.insert(0, str(sim_root))
    from simulator.runner import SimulationRunner  # type: ignore[import-not-found]
    import simulator.infectionmgr as _infmod  # type: ignore[import-not-found]

    # Capture the InfectionManager so we can read its final infected set (total
    # ever infected) — the human-readable companion to the canonical hashes.
    _orig_init = _infmod.InfectionManager.__init__

    def _cap_init(self, *a, **k):
        _orig_init(self, *a, **k)
        _captured["mgr"] = self

    _infmod.InfectionManager.__init__ = _cap_init

    papdata_path = Path(args.papdata).resolve()
    patterns_path = Path(args.patterns).resolve()

    def _load_json_gz(path: Path):
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return json.load(fh)

    # Pre-load papdata + patterns once and reuse; the default data_loader hits
    # the Fullstack dev server over HTTP, which we bypass with a closure.
    cached_papdata = _load_json_gz(papdata_path)
    cached_patterns = _load_json_gz(patterns_path)

    def local_loader(_url: str, timeout: int = 360):
        return cached_papdata, cached_patterns

    interventions = [{
        "time": 0, "mask": 0.0, "vaccine": 0.0,
        "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0,
    }]

    def one_run(label: str, want_canonical: bool = False) -> dict:
        random.seed(args.seed)
        np.random.seed(args.seed)
        _captured.clear()
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
                    simdata=payload, enable_logging=False, output_dir=td,
                    progress_callback=None, data_loader=local_loader,
                )
                result = runner.run()
            elapsed = time.perf_counter() - t0
            if isinstance(result, dict) and "error" in result:
                raise RuntimeError(
                    f"simulation failed in {label}: {result['error']}\n"
                    f"--- logs ---\n{logs.getvalue()}"
                )
            simdata_path = Path(result["simdata"])
            patterns_out = Path(result["patterns"])
            if not simdata_path.is_file():
                raise RuntimeError(f"missing simdata at {simdata_path}; keys={list(result)}")
            out = {"elapsed": elapsed, "file_sha": hash_file(simdata_path)}
            if want_canonical:
                out["simdata_canon"] = canonical_hash(simdata_path)
                out["patterns_canon"] = canonical_hash(patterns_out)
        mgr = _captured.get("mgr")
        out["infected"] = len(mgr.infected) if mgr is not None else None
        return out

    timings: list[float] = []
    hashes: list[str] = []

    smoke = one_run("smoke")
    print(f"[{args.label}] smoke   {smoke['elapsed']:6.2f}s  sha={smoke['file_sha'][:16]}", file=sys.stderr)

    # In golden mode, capture canonical fingerprint on the first measured run.
    fingerprint: dict = {}
    for i in range(args.runs):
        r = one_run(f"measured-{i+1}", want_canonical=(golden_mode and i == 0))
        timings.append(r["elapsed"])
        hashes.append(r["file_sha"])
        if golden_mode and i == 0:
            fingerprint = {
                "simdata_canon_sha": r["simdata_canon"],
                "patterns_canon_sha": r["patterns_canon"],
                "infected": r["infected"],
            }
        print(f"[{args.label}] meas {i+1}  {r['elapsed']:6.2f}s  sha={r['file_sha'][:16]}  infected={r['infected']}", file=sys.stderr)

    params = {
        "length": args.length, "seed": args.seed, "dmp_mode": args.dmp_mode,
        "papdata": papdata_path.name, "patterns": patterns_path.name,
    }
    summary = {
        "label": args.label,
        "sim_root": str(sim_root),
        "params": params,
        "measured": {
            "n": args.runs, "min": min(timings),
            "median": statistics.median(timings), "max": max(timings), "all": timings,
        },
        "hashes": hashes,
        "hashes_consistent": len(set(hashes)) == 1,
        "infected": fingerprint.get("infected"),
    }

    exit_code = 0

    if args.write_golden:
        golden = {"params": params, **fingerprint}
        Path(args.write_golden).write_text(json.dumps(golden, indent=2))
        print(f"[{args.label}] wrote golden -> {args.write_golden}", file=sys.stderr)
        summary["golden_written"] = args.write_golden

    if args.check_golden:
        golden = json.loads(Path(args.check_golden).read_text())
        if golden.get("params") != params:
            print(f"[{args.label}] WARNING: params differ from golden "
                  f"(golden={golden.get('params')} current={params})", file=sys.stderr)
        diffs = []
        for field in ("simdata_canon_sha", "patterns_canon_sha", "infected"):
            want, got = golden.get(field), fingerprint.get(field)
            if want != got:
                diffs.append(f"{field}: golden={want} current={got}")
        if diffs:
            print(f"[{args.label}] GOLDEN DRIFT:", file=sys.stderr)
            for d in diffs:
                print(f"    {d}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"[{args.label}] golden OK (infected={fingerprint.get('infected')}, "
                  f"simdata+patterns canonical match)", file=sys.stderr)
        summary["golden_ok"] = not diffs

    print(json.dumps(summary, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
