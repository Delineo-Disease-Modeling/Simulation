import argparse
import cProfile
import io
import os
import sys
import time
import pstats
import subprocess
from datetime import datetime

DEFAULT_NAME = "simulation_profile"
PROFILES_DIR = os.path.join(os.path.dirname(__file__), "profiles")


def ensure_profiles_dir():
    os.makedirs(PROFILES_DIR, exist_ok=True)


def run_simulation_direct(length: int, location: str, randseed: bool):
    # Import locally to avoid import costs when using --api
    from simulator import simulate
    return simulate.run_simulator(
        location=location,
        max_length=length,
        interventions={
            "capacity": 1.0,
            "lockdown": 0.0,
            "selfiso": 0.0,
            "mask": 0.1,
            "vaccine": 0.2,
            "randseed": randseed,
        },
        save_file=False,
        enable_logging=False,
    )


def run_simulation_api(length: int, location: str, randseed: bool, base_url: str = "http://127.0.0.1:1880"):
    import requests
    payload = {
        "length": length,
        "location": location,
        "capacity": 1.0,
        "lockdown": 0.0,
        "selfiso": 0.0,
        "mask": 0.1,
        "vaccine": 0.2,
        "randseed": randseed,
    }
    resp = requests.post(f"{base_url}/simulation/", json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json()


def save_text_report(profiler: cProfile.Profile, txt_path: str, header: str):
    stats_output = io.StringIO()
    stats = pstats.Stats(profiler, stream=stats_output)
    stats.sort_stats("cumulative")
    stats.print_stats(80)
    with open(txt_path, "w") as f:
        f.write(header)
        f.write("\n" + "=" * 80 + "\n")
        f.write(stats_output.getvalue())


def try_generate_callgraph(pstats_path: str, svg_path: str) -> bool:
    """Generate a call graph SVG using gprof2dot + graphviz (dot). Returns True on success."""
    # Try to invoke: python -m gprof2dot -f pstats <file> | dot -Tsvg -o <svg>
    try:
        # Check that graphviz `dot` is available
        dot_ok = subprocess.run(["dot", "-V"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if dot_ok.returncode != 0:
            return False
    except FileNotFoundError:
        return False

    try:
        gprof_cmd = [sys.executable, "-m", "gprof2dot", "-f", "pstats", pstats_path]
        dot_cmd = ["dot", "-Tsvg", "-o", svg_path]
        # Run pipeline: gprof2dot | dot
        gprof = subprocess.Popen(gprof_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dot = subprocess.Popen(dot_cmd, stdin=gprof.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gprof.stdout.close()  # allow gprof to receive a SIGPIPE if dot exits
        _, dot_err = dot.communicate()
        gprof.wait()
        return dot.returncode == 0
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Profile simulator and generate call graph")
    parser.add_argument("--api", action="store_true", help="Profile by hitting the Flask API instead of direct call")
    parser.add_argument("--length", type=int, default=720, help="Simulation length (minutes)")
    parser.add_argument("--location", type=str, default="default", help="Simulation location")
    parser.add_argument("--no-graph", action="store_true", help="Skip generating SVG call graph")
    parser.add_argument("--name", type=str, default=DEFAULT_NAME, help="Base name for output files")
    parser.add_argument("--randseed", action="store_true", help="Use random seed for deterministic run")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:1880", help="Base URL for simulator API")
    parser.add_argument("--open-snakeviz", action="store_true", help="Open the generated .prof in Snakeviz if installed")

    args = parser.parse_args()

    ensure_profiles_dir()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{args.name}_{'api' if args.api else 'direct'}_{timestamp}"
    prof_path = os.path.join(PROFILES_DIR, f"{base}.prof")
    txt_path = os.path.join(PROFILES_DIR, f"{base}.txt")
    svg_path = os.path.join(PROFILES_DIR, f"{base}.svg")

    print(f"Starting profiling at {datetime.now()}\n")
    print(f"Mode: {'API' if args.api else 'Direct import'}")
    print(f"Length: {args.length} minutes, Location: {args.location}\n")

    profiler = cProfile.Profile()
    profiler.enable()
    t0 = time.time()

    try:
        if args.api:
            _ = run_simulation_api(args.length, args.location, args.randseed, base_url=args.api_url)
        else:
            _ = run_simulation_direct(args.length, args.location, args.randseed)
    finally:
        t1 = time.time()
        profiler.disable()

    # Persist pstats and text report
    profiler.dump_stats(prof_path)
    save_text_report(
        profiler,
        txt_path,
        header=(
            f"Simulation Profiling Results ({'API' if args.api else 'Direct'})\n"
            f"Start: {datetime.fromtimestamp(t0)}\n"
            f"End:   {datetime.fromtimestamp(t1)}\n"
            f"Total runtime: {t1 - t0:.2f} seconds\n"
        ),
    )

    print(f"Saved cProfile to: {prof_path}")
    print(f"Saved top-functions report to: {txt_path}")

    if not args.no_graph:
        print("\nGenerating call graph (SVG) with gprof2dot + graphviz (if installed)...")
        ok = try_generate_callgraph(prof_path, svg_path)
        if ok:
            print(f"Call graph written to: {svg_path}")
        else:
            print("- Skipped or failed to generate SVG call graph.")
            print("  To enable, install: pip install gprof2dot; and Graphviz (e.g., brew install graphviz)")

    print("\nViewing options:")
    print(f"- snakeviz {prof_path}")
    print(f"- open {svg_path}  # or view in your browser")

    if args.open_snakeviz:
        print("\nAttempting to open Snakeviz...")
        try:
            # Launch snakeviz; do not block permanently
            subprocess.Popen([sys.executable, "-m", "snakeviz", prof_path])
            print("Snakeviz launched. If nothing happens, ensure 'snakeviz' is installed: pip install snakeviz")
        except Exception:
            print("Could not launch Snakeviz automatically. Try: pip install snakeviz && snakeviz profiles/<name>.prof")


if __name__ == "__main__":
    main()
