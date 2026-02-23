#!/usr/bin/env python3
"""
Full data-generation pipeline for Barnsdall, OK.

Steps:
  1. (Optional) Convert Dewey CSV to SafeGraph-compatible format via convert_dewey.py
  2. Run Algorithms/server/popgen.py to generate papdata.json (people, homes, places)
  3. Run Algorithms/server/patterns.py to generate patterns.json (movement patterns)
  4. Copy outputs to simulator/barnsdall/ for the disease simulator

Usage:
  # After Dewey download completes:
  python generate_barnsdall_data.py --input /path/to/2019-01-OK.csv

  # If patterns.csv is already in Algorithms/server/data/:
  python generate_barnsdall_data.py --skip-convert

  # Specify simulation duration (default: 1008 hrs = 6 weeks):
  python generate_barnsdall_data.py --skip-convert --duration 1008
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ALGO_SERVER = REPO_ROOT.parent / 'Algorithms' / 'server'
SIM_DIR = REPO_ROOT / 'simulator'
BARNSDALL_DIR = SIM_DIR / 'barnsdall'
ALGO_DATA_DIR = ALGO_SERVER / 'data'
ALGO_OUTPUT_DIR = ALGO_SERVER / 'output'


def run(cmd, cwd=None, check=True):
    print(f'\n>>> {" ".join(str(c) for c in cmd)}')
    result = subprocess.run([str(c) for c in cmd], cwd=str(cwd or REPO_ROOT), check=check)
    return result


def main():
    ap = argparse.ArgumentParser(description='Generate Barnsdall simulator data from Dewey CSV')
    ap.add_argument('--input', '-i', help='Path to Dewey CSV input file (patterns_n format)')
    ap.add_argument('--skip-convert', action='store_true',
                    help='Skip convert_dewey.py step (patterns.csv already in Algorithms/server/data/)')
    ap.add_argument('--duration', type=int, default=1008,
                    help='Pattern generation duration in hours (default: 1008 = 6 weeks)')
    ap.add_argument('--start', default='2025-10-01T00:00:00',
                    help='Simulation start datetime ISO string (default: 2025-10-01)')
    ap.add_argument('--no-copy', action='store_true',
                    help='Do not copy outputs to simulator/barnsdall/')
    args = ap.parse_args()

    # ── Step 1: Convert Dewey CSV ────────────────────────────────────────────
    patterns_csv = ALGO_DATA_DIR / 'patterns.csv'
    if not args.skip_convert:
        if not args.input:
            ap.error('--input is required unless --skip-convert is set')
        input_path = Path(args.input).resolve()
        if not input_path.exists():
            sys.exit(f'Input file not found: {input_path}')

        ALGO_DATA_DIR.mkdir(parents=True, exist_ok=True)
        run([
            sys.executable,
            REPO_ROOT / 'convert_dewey.py',
            '--input', input_path,
            '--output', patterns_csv,
        ])
        print(f'Converted Dewey CSV → {patterns_csv}')
    else:
        if not patterns_csv.exists():
            sys.exit(f'patterns.csv not found at {patterns_csv}. '
                     'Run without --skip-convert to generate it.')
        print(f'Using existing patterns.csv at {patterns_csv}')

    # ── Step 2: Generate papdata.json ────────────────────────────────────────
    ALGO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run([sys.executable, ALGO_SERVER / 'popgen.py'], cwd=ALGO_SERVER)
    papdata_out = ALGO_OUTPUT_DIR / 'papdata.json'
    if not papdata_out.exists():
        sys.exit(f'popgen.py did not produce {papdata_out}')
    print(f'Generated papdata.json ({papdata_out.stat().st_size // 1024} KB)')

    # ── Step 3: Generate patterns.json ───────────────────────────────────────
    run([
        sys.executable,
        ALGO_SERVER / 'patterns.py',
        '--papdata', papdata_out,
        '--output', ALGO_OUTPUT_DIR / 'patterns.json',
        '--duration', str(args.duration),
        '--start', args.start,
    ], cwd=ALGO_SERVER)
    patterns_out = ALGO_OUTPUT_DIR / 'patterns.json'
    if not patterns_out.exists():
        sys.exit(f'patterns.py did not produce {patterns_out}')
    print(f'Generated patterns.json ({patterns_out.stat().st_size // 1024} KB)')

    # ── Step 4: Copy to simulator/barnsdall/ ─────────────────────────────────
    if not args.no_copy:
        BARNSDALL_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(papdata_out, BARNSDALL_DIR / 'papdata.json')
        shutil.copy2(patterns_out, BARNSDALL_DIR / 'patterns.json')
        print(f'\nCopied to {BARNSDALL_DIR}/')
        print('  papdata.json')
        print('  patterns.json')

        # Clear Python __pycache__ in simulator so config changes take effect
        for cache_dir in SIM_DIR.rglob('__pycache__'):
            shutil.rmtree(cache_dir, ignore_errors=True)
        print('Cleared simulator __pycache__')

    print('\nDone! Barnsdall data is ready for the disease simulator.')


if __name__ == '__main__':
    main()
