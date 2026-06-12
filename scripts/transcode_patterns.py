"""Transcode a legacy JSON patterns blob into the DLNOPAT binary format.

Reference for the Algorithms producer and a way to convert existing fixtures /
cached patterns for testing. Reads papdata to enumerate the person + location id
spaces (the binary format ships these tables in its header).

Usage:
    python scripts/transcode_patterns.py PAPDATA.json[.gz] PATTERNS.json[.gz] OUT.bin [--level 3]
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from simulator.patterns_codec import build_arrays_from_legacy, encode_patterns_binary


def _load_json(path: str) -> dict:
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        return json.loads(fh.read())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("papdata")
    ap.add_argument("patterns")
    ap.add_argument("out")
    ap.add_argument("--level", type=int, default=3)
    args = ap.parse_args()

    papdata = _load_json(args.papdata)
    patterns = _load_json(args.patterns)
    M, ts_minutes, pids, loc_ids, n_homes = build_arrays_from_legacy(patterns, papdata)
    blob = encode_patterns_binary(M, ts_minutes, pids, loc_ids, n_homes, level=args.level)
    Path(args.out).write_bytes(blob)

    print(
        f"wrote {args.out}: {len(blob):,} bytes "
        f"(matrix {M.shape[0]}x{M.shape[1]} {M.dtype}, "
        f"{len(loc_ids):,} locations, n_homes={n_homes})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
