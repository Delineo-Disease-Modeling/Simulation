#!/usr/bin/env python3
"""
Complete validation pipeline for Hagerstown, MD using 2021 COVID-19 data.

This script orchestrates the entire validation process:
1. Fetch real COVID-19 data for Washington County, MD
2. Prepare and aggregate the data
3. Run the simulator with Hagerstown configuration
4. Compare simulator output with ground truth
5. Generate validation report

Example usage:
    # Run full validation for March 2021
    python run_hagerstown_validation.py --month 2021-03
    
    # Run with custom date range
    python run_hagerstown_validation.py --start 2021-03-01 --end 2021-03-31
    
    # Run with custom interventions
    python run_hagerstown_validation.py --month 2021-03 --mask 0.5 --vaccine 0.2
"""

import argparse
import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
VALIDATION_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(VALIDATION_DIR))


def run_command(cmd: list, description: str) -> bool:
    """Run a shell command and return success status."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"✓ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed with error code {e.returncode}")
        return False


def parse_month(month_str: str) -> tuple:
    """Parse YYYY-MM format into start and end dates."""
    dt = datetime.strptime(month_str, "%Y-%m")
    start_date = dt.strftime("%Y-%m-01")
    
    # Calculate last day of month
    if dt.month == 12:
        next_month = dt.replace(year=dt.year + 1, month=1, day=1)
    else:
        next_month = dt.replace(month=dt.month + 1, day=1)
    
    end_date = (next_month - timedelta(days=1)).strftime("%Y-%m-%d")
    
    return start_date, end_date


def calculate_duration_minutes(start_date: str, end_date: str) -> int:
    """Calculate duration in minutes between two dates."""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days + 1  # Include end date
    return days * 24 * 60


def main():
    parser = argparse.ArgumentParser(
        description="Run complete validation for Hagerstown, MD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate March 2021
  python run_hagerstown_validation.py --month 2021-03
  
  # Validate with custom date range
  python run_hagerstown_validation.py --start 2021-01-01 --end 2021-01-31
  
  # Validate with custom interventions
  python run_hagerstown_validation.py --month 2021-03 --mask 0.5 --vaccine 0.2 --capacity 0.8
        """
    )
    
    # Date arguments
    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument("--month", help="Month to validate (YYYY-MM format)")
    date_group.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD, required if --start is used)")
    
    # Location arguments
    parser.add_argument("--county", default="Washington", help="County name (default: Washington)")
    parser.add_argument("--state", default="Maryland", help="State name (default: Maryland)")
    parser.add_argument("--location", default="hagerstown", help="Simulator location key (default: hagerstown)")
    
    # Simulation parameters
    parser.add_argument("--mask", type=float, default=0.3, help="Mask intervention level (0-1, default: 0.3)")
    parser.add_argument("--vaccine", type=float, default=0.15, help="Vaccine coverage (0-1, default: 0.15)")
    parser.add_argument("--capacity", type=float, default=0.75, help="Capacity restriction (0-1, default: 0.75)")
    parser.add_argument("--lockdown", type=int, default=0, help="Lockdown level (0-2, default: 0)")
    parser.add_argument("--selfiso", type=float, default=0.2, help="Self-isolation rate (0-1, default: 0.2)")
    
    # Processing arguments
    parser.add_argument("--agg", choices=["daily", "weekly", "monthly"], default="weekly",
                       help="Aggregation level (default: weekly)")
    parser.add_argument("--step-minutes", type=int, default=60, help="Simulation step size in minutes (default: 60)")
    
    # API endpoint
    parser.add_argument("--url", default="http://localhost:1880/simulation/",
                       help="Simulator API endpoint (default: http://localhost:1880/simulation/)")
    
    # Skip steps
    parser.add_argument("--skip-fetch", action="store_true", help="Skip data fetching step")
    parser.add_argument("--skip-prepare", action="store_true", help="Skip data preparation step")
    parser.add_argument("--skip-simulate", action="store_true", help="Skip simulation step")
    parser.add_argument("--skip-compare", action="store_true", help="Skip comparison step")
    
    args = parser.parse_args()
    
    # Validate date arguments
    if args.month:
        start_date, end_date = parse_month(args.month)
    else:
        if not args.end:
            parser.error("--end is required when using --start")
        start_date = args.start
        end_date = args.end
    
    # Calculate simulation duration
    duration_minutes = calculate_duration_minutes(start_date, end_date)
    
    print("\n" + "="*60)
    print("HAGERSTOWN VALIDATION PIPELINE")
    print("="*60)
    print(f"Location: {args.county} County, {args.state}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Duration: {duration_minutes} minutes ({duration_minutes // (24*60)} days)")
    print(f"Interventions: mask={args.mask}, vaccine={args.vaccine}, capacity={args.capacity}")
    print("="*60)
    
    success = True
    
    # Step 1: Fetch county data
    if not args.skip_fetch:
        cmd = [
            "python", str(SCRIPT_DIR / "fetch_county_data.py"),
            "--state", args.state,
            "--county", args.county,
            "--start", start_date,
            "--end", end_date
        ]
        success = run_command(cmd, "Step 1: Fetching county-level COVID data")
        if not success:
            print("\n⚠ Warning: Data fetch failed. Continuing with existing data if available.")
    
    # Step 2: Prepare data
    if not args.skip_prepare and success:
        cmd = [
            "python", str(SCRIPT_DIR / "prepare_county_data.py"),
            "--county", args.county.lower(),
            "--state", args.state.lower(),
            "--agg", args.agg
        ]
        success = run_command(cmd, "Step 2: Preparing and aggregating data")
        if not success:
            print("\n✗ Data preparation failed. Cannot continue.")
            return 1
    
    # Step 3: Run simulation
    if not args.skip_simulate and success:
        interventions = {
            "mask": args.mask,
            "vaccine": args.vaccine,
            "capacity": args.capacity,
            "lockdown": args.lockdown,
            "selfiso": args.selfiso,
            "randseed": True
        }
        
        cmd = [
            "python", str(SCRIPT_DIR / "run_simulation.py"),
            "--url", args.url,
            "--length", str(duration_minutes),
            "--location", args.location,
            "--step_minutes", str(args.step_minutes),
            "--interventions", json.dumps(interventions)
        ]
        success = run_command(cmd, "Step 3: Running simulation")
        if not success:
            print("\n✗ Simulation failed. Check if the simulator is running at", args.url)
            return 1
    
    # Step 4: Compare and generate report
    if not args.skip_compare and success:
        # Determine horizons based on aggregation
        if args.agg == "weekly":
            horizons = "1,2,3,4"
        elif args.agg == "monthly":
            horizons = "1"
        else:  # daily
            horizons = "7,14,21,28"
        
        cmd = [
            "python", str(SCRIPT_DIR / "compare.py"),
            "--geo", f"{args.county.lower()}_{args.state.lower()}",
            "--horizon", horizons,
            "--agg", args.agg
        ]
        success = run_command(cmd, "Step 4: Comparing results and generating report")
        if not success:
            print("\n✗ Comparison failed.")
            return 1
    
    # Summary
    print("\n" + "="*60)
    if success:
        print("✓ VALIDATION PIPELINE COMPLETED SUCCESSFULLY")
        print("="*60)
        print(f"\nResults saved in:")
        print(f"  - Artifacts: {VALIDATION_DIR / 'artifacts'}")
        print(f"  - Reports: {VALIDATION_DIR / 'reports'}")
        print(f"\nTo view the report, open:")
        print(f"  {VALIDATION_DIR / 'reports' / 'validation_report.html'}")
    else:
        print("✗ VALIDATION PIPELINE FAILED")
        print("="*60)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
