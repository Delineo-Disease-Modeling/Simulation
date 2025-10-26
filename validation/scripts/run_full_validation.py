#!/usr/bin/env python3
"""
Complete validation pipeline: Phases 1-3
Orchestrates data fetching, Stan fitting, simulator running, and comparison.

Example usage:
    # Full pipeline for Hagerstown, MD (March 2021)
    python run_full_validation.py --county Washington --state Maryland --start 2021-03-01 --end 2021-03-31
    
    # Quick validation with fewer MCMC iterations
    python run_full_validation.py --county Washington --state Maryland --start 2021-03-01 --end 2021-03-31 --quick
"""

import argparse
import os
import sys
import subprocess
import json
from datetime import datetime
import pandas as pd

# Add parent directory to path for imports
script_dir = os.path.dirname(os.path.abspath(__file__))
validation_dir = os.path.dirname(script_dir)
sys.path.insert(0, validation_dir)


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*70}")
    print(f"STEP: {description}")
    print(f"{'='*70}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=False, text=True)
    
    if result.returncode != 0:
        print(f"\n❌ ERROR: {description} failed")
        sys.exit(1)
    
    print(f"\n✓ {description} completed successfully")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Run complete validation pipeline (Phases 1-3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline Steps:
  1. Fetch real county data from NYT dataset
  2. Prepare and aggregate data
  3. Fit Stan SEIR model to real data (Phase 2)
  4. Run ABM simulator
  5. Compare Stan vs ABM (Phase 3)
  6. Generate comprehensive reports

Example:
  python run_full_validation.py --county Washington --state Maryland \\
      --start 2021-03-01 --end 2021-03-31 --population 150000
        """
    )
    
    # Data parameters
    parser.add_argument('--county', required=True, help='County name (e.g., Washington)')
    parser.add_argument('--state', required=True, help='State name (e.g., Maryland)')
    parser.add_argument('--start', required=True, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', required=True, help='End date (YYYY-MM-DD)')
    parser.add_argument('--population', type=int, default=150000, help='County population')
    
    # Stan parameters
    parser.add_argument('--quick', action='store_true', help='Quick mode: fewer MCMC iterations')
    parser.add_argument('--chains', type=int, default=4, help='Number of MCMC chains')
    
    # Simulator parameters
    parser.add_argument('--sim-endpoint', default='http://localhost:1880/simulation/', 
                       help='Simulator API endpoint')
    
    # Output
    parser.add_argument('--output-dir', default='artifacts/full_validation', help='Output directory')
    
    args = parser.parse_args()
    
    # Setup paths
    output_dir = os.path.join(validation_dir, args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    data_dir = os.path.join(validation_dir, 'data')
    raw_data_dir = os.path.join(data_dir, 'raw')
    processed_data_dir = os.path.join(data_dir, 'processed')
    os.makedirs(raw_data_dir, exist_ok=True)
    os.makedirs(processed_data_dir, exist_ok=True)
    
    # Stan parameters
    if args.quick:
        iter_sampling = 500
        iter_warmup = 500
    else:
        iter_sampling = 1000
        iter_warmup = 1000
    
    # File paths
    county_slug = f"{args.county.lower()}_{args.state.lower()}"
    raw_data_file = os.path.join(raw_data_dir, f"nyt_county_{county_slug}.csv")
    processed_data_file = os.path.join(processed_data_dir, f"{county_slug}_daily.csv")
    stan_output_dir = os.path.join(output_dir, 'stan')
    sim_output_file = os.path.join(output_dir, 'simulator_results.csv')
    comparison_output_dir = os.path.join(output_dir, 'comparison')
    
    print("="*70)
    print("DELINEO VALIDATION PIPELINE")
    print("="*70)
    print(f"County: {args.county}, {args.state}")
    print(f"Period: {args.start} to {args.end}")
    print(f"Population: {args.population:,}")
    print(f"Output: {output_dir}")
    print(f"Mode: {'Quick' if args.quick else 'Full'}")
    print("="*70)
    
    # Step 1: Fetch county data
    run_command([
        'python', os.path.join(script_dir, 'fetch_county_data.py'),
        '--state', args.state,
        '--county', args.county,
        '--start', args.start,
        '--end', args.end,
        '--outdir', raw_data_dir
    ], "Fetch County Data")
    
    # Step 2: Prepare data (no aggregation, keep daily)
    print(f"\n{'='*70}")
    print("STEP: Prepare Data")
    print(f"{'='*70}")
    
    # Simple preparation: just ensure we have daily_cases column
    df = pd.read_csv(raw_data_file, parse_dates=['date'])
    if 'daily_cases' not in df.columns:
        df['daily_cases'] = df['cases'].diff().fillna(df['cases'])
        df['daily_cases'] = df['daily_cases'].clip(lower=0)
    df.to_csv(processed_data_file, index=False)
    print(f"✓ Data prepared: {processed_data_file}")
    
    # Step 3: Fit Stan model
    run_command([
        'python', os.path.join(script_dir, 'fit_stan_model.py'),
        '--data', processed_data_file,
        '--population', str(args.population),
        '--output-dir', stan_output_dir,
        '--chains', str(args.chains),
        '--iter-sampling', str(iter_sampling),
        '--iter-warmup', str(iter_warmup)
    ], "Fit Stan SEIR Model (Phase 2)")
    
    # Step 4: Run simulator
    print(f"\n{'='*70}")
    print("STEP: Run ABM Simulator")
    print(f"{'='*70}")
    print("Note: Ensure simulator is running at", args.sim_endpoint)
    print("If not running, start with: cd ../.. && docker compose up -d")
    print()
    
    # Check if we have a run_simulation.py script, otherwise create a simple one
    run_sim_script = os.path.join(script_dir, 'run_simulation.py')
    if not os.path.exists(run_sim_script):
        print("⚠️  run_simulation.py not found. Creating a placeholder...")
        print("You'll need to implement this to call your simulator API.")
        
        # Create a mock simulator output for demonstration
        n_days = len(pd.read_csv(processed_data_file))
        mock_sim_df = pd.DataFrame({
            'date': pd.date_range(args.start, periods=n_days),
            'daily_cases': pd.read_csv(processed_data_file)['daily_cases'].values * 0.9  # Mock: 90% of real
        })
        mock_sim_df.to_csv(sim_output_file, index=False)
        print(f"✓ Created mock simulator output: {sim_output_file}")
        print("⚠️  Replace this with actual simulator API call!")
    else:
        run_command([
            'python', run_sim_script,
            '--length', str(len(pd.read_csv(processed_data_file))),
            '--location', f"{args.county}_{args.state}",
            '--output', sim_output_file
        ], "Run ABM Simulator")
    
    # Step 5: Compare Stan vs ABM
    stan_fit_file = os.path.join(stan_output_dir, 'stan_fit.pkl')
    
    run_command([
        'python', os.path.join(script_dir, 'compare_with_stan.py'),
        '--stan-fit', stan_fit_file,
        '--sim-data', sim_output_file,
        '--real-data', processed_data_file,
        '--output-dir', comparison_output_dir
    ], "Compare Stan vs ABM (Phase 3)")
    
    # Step 6: Generate summary
    print(f"\n{'='*70}")
    print("VALIDATION PIPELINE COMPLETE")
    print(f"{'='*70}")
    print(f"\nResults saved to: {output_dir}")
    print(f"\nKey outputs:")
    print(f"  - Stan fit: {stan_output_dir}/")
    print(f"  - Simulator output: {sim_output_file}")
    print(f"  - Comparison: {comparison_output_dir}/")
    print(f"\nView results:")
    print(f"  - Stan plots: {stan_output_dir}/stan_fit_results.png")
    print(f"  - Comparison: {comparison_output_dir}/stan_vs_abm_comparison.png")
    print(f"  - Report: {comparison_output_dir}/validation_report.txt")
    
    # Create a summary JSON
    summary = {
        'timestamp': datetime.now().isoformat(),
        'parameters': {
            'county': args.county,
            'state': args.state,
            'start_date': args.start,
            'end_date': args.end,
            'population': args.population
        },
        'outputs': {
            'stan_fit': stan_fit_file,
            'simulator_output': sim_output_file,
            'comparison_dir': comparison_output_dir
        }
    }
    
    summary_file = os.path.join(output_dir, 'validation_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary: {summary_file}")


if __name__ == '__main__':
    main()
