#!/usr/bin/env python3
"""
Prepare county-level COVID-19 data for validation.
This script aggregates daily case data into weekly totals to match simulator output format.

Example usage:
    python prepare_county_data.py --county washington --state maryland --agg weekly
"""

import argparse
import os
import pandas as pd
from datetime import datetime


def aggregate_to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily cases to weekly totals.
    
    Args:
        df: DataFrame with date and daily_cases columns
    
    Returns:
        DataFrame with weekly aggregated cases
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # Set date as index for resampling
    df.set_index("date", inplace=True)
    
    # Resample to weekly (Monday start) and sum daily cases
    weekly = df[["daily_cases"]].resample("W-MON", label="left", closed="left").sum()
    weekly.columns = ["weekly_cases"]
    weekly = weekly.reset_index()
    
    # Remove weeks with zero cases (typically at the start)
    weekly = weekly[weekly["weekly_cases"] > 0]
    
    return weekly


def aggregate_to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily cases to monthly totals.
    
    Args:
        df: DataFrame with date and daily_cases columns
    
    Returns:
        DataFrame with monthly aggregated cases
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True)
    
    # Resample to monthly and sum daily cases
    monthly = df[["daily_cases"]].resample("MS").sum()
    monthly.columns = ["monthly_cases"]
    monthly = monthly.reset_index()
    
    return monthly


def main():
    parser = argparse.ArgumentParser(
        description="Prepare county-level COVID data for validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Prepare weekly aggregated data for Washington County, MD
  python prepare_county_data.py --county washington --state maryland --agg weekly
  
  # Prepare monthly aggregated data
  python prepare_county_data.py --county washington --state maryland --agg monthly
        """
    )
    parser.add_argument("--county", required=True, help="County name (lowercase)")
    parser.add_argument("--state", required=True, help="State name (lowercase)")
    parser.add_argument(
        "--agg", 
        choices=["daily", "weekly", "monthly"], 
        default="weekly",
        help="Aggregation level (default: weekly)"
    )
    parser.add_argument(
        "--rawdir",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
        help="Input directory with raw data"
    )
    parser.add_argument(
        "--outdir",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "processed"),
        help="Output directory for processed data"
    )
    args = parser.parse_args()
    
    os.makedirs(args.outdir, exist_ok=True)
    
    # Load raw data
    raw_filename = f"nyt_county_{args.county}_{args.state}.csv"
    raw_path = os.path.join(args.rawdir, raw_filename)
    
    if not os.path.exists(raw_path):
        raise FileNotFoundError(
            f"Raw data file not found: {raw_path}\n"
            f"Please run fetch_county_data.py first to download the data."
        )
    
    df = pd.read_csv(raw_path)
    print(f"Loaded: {raw_path} ({len(df)} rows)")
    
    # Aggregate based on specified level
    if args.agg == "weekly":
        result = aggregate_to_weekly(df)
        out_filename = f"ground_truth_weekly_cases_{args.county}_{args.state}.csv"
    elif args.agg == "monthly":
        result = aggregate_to_monthly(df)
        out_filename = f"ground_truth_monthly_cases_{args.county}_{args.state}.csv"
    else:  # daily
        result = df[["date", "daily_cases"]].copy()
        out_filename = f"ground_truth_daily_cases_{args.county}_{args.state}.csv"
    
    # Save processed data
    out_path = os.path.join(args.outdir, out_filename)
    result.to_csv(out_path, index=False)
    
    print(f"\nSaved: {out_path}")
    print(f"Rows: {len(result)}")
    print(f"Date range: {result['date'].min()} to {result['date'].max()}")
    
    # Show statistics
    case_col = result.columns[1]  # weekly_cases, monthly_cases, or daily_cases
    print(f"\nStatistics:")
    print(f"  Total cases: {result[case_col].sum():,.0f}")
    print(f"  Mean {args.agg} cases: {result[case_col].mean():.1f}")
    print(f"  Median {args.agg} cases: {result[case_col].median():.1f}")
    print(f"  Peak {args.agg} cases: {result[case_col].max():.0f}")
    
    # Show sample
    print(f"\nFirst 10 rows:")
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
