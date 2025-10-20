#!/usr/bin/env python3
"""
Fetch county-level COVID-19 data from the New York Times COVID-19 dataset.
This script downloads historical COVID-19 case and death data for specific counties.

Example usage:
    # Fetch data for Washington County, MD (Hagerstown)
    python fetch_county_data.py --state Maryland --county "Washington" --start 2021-01-01 --end 2021-12-31
    
    # Fetch data for a specific month
    python fetch_county_data.py --state Maryland --county "Washington" --start 2021-03-01 --end 2021-03-31
"""

import argparse
import os
import io
import pandas as pd
import requests
from datetime import datetime

# New York Times COVID-19 dataset - county level
NYT_COUNTY_URL = "https://raw.githubusercontent.com/nytimes/covid-19-data/master/us-counties.csv"

# FIPS codes for common counties (can be extended)
COUNTY_FIPS = {
    "Washington_MD": "24043",  # Washington County, Maryland (Hagerstown)
    "Baltimore_MD": "24005",   # Baltimore County, Maryland
    "Montgomery_MD": "24031",  # Montgomery County, Maryland
}


def fetch_nyt_county_data(state: str, county: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Fetch county-level COVID-19 data from NYT dataset.
    
    Args:
        state: State name (e.g., "Maryland")
        county: County name (e.g., "Washington")
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
    
    Returns:
        DataFrame with columns: date, county, state, fips, cases, deaths
    """
    print(f"Fetching data from NYT COVID-19 dataset...")
    r = requests.get(NYT_COUNTY_URL, timeout=30)
    r.raise_for_status()
    
    df = pd.read_csv(io.StringIO(r.text))
    
    # Filter by state and county
    df_filtered = df[
        (df["state"].str.lower() == state.lower()) & 
        (df["county"].str.lower() == county.lower())
    ].copy()
    
    if df_filtered.empty:
        raise ValueError(f"No data found for {county} County, {state}")
    
    # Convert date column to datetime
    df_filtered["date"] = pd.to_datetime(df_filtered["date"])
    
    # Filter by date range if provided
    if start_date:
        start = pd.to_datetime(start_date)
        df_filtered = df_filtered[df_filtered["date"] >= start]
    
    if end_date:
        end = pd.to_datetime(end_date)
        df_filtered = df_filtered[df_filtered["date"] <= end]
    
    df_filtered = df_filtered.sort_values("date").reset_index(drop=True)
    
    return df_filtered


def calculate_daily_cases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate daily new cases from cumulative cases.
    
    Args:
        df: DataFrame with cumulative cases column
    
    Returns:
        DataFrame with additional daily_cases column
    """
    df = df.copy()
    df["daily_cases"] = df["cases"].diff().fillna(df["cases"])
    df["daily_deaths"] = df["deaths"].diff().fillna(df["deaths"])
    
    # Handle negative values (data corrections)
    df["daily_cases"] = df["daily_cases"].clip(lower=0)
    df["daily_deaths"] = df["daily_deaths"].clip(lower=0)
    
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Fetch county-level COVID-19 data from NYT dataset",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch full year 2021 for Washington County, MD
  python fetch_county_data.py --state Maryland --county Washington --start 2021-01-01 --end 2021-12-31
  
  # Fetch March 2021 for Washington County, MD
  python fetch_county_data.py --state Maryland --county Washington --start 2021-03-01 --end 2021-03-31
        """
    )
    parser.add_argument("--state", required=True, help="State name (e.g., Maryland)")
    parser.add_argument("--county", required=True, help="County name (e.g., Washington)")
    parser.add_argument("--start", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", help="End date (YYYY-MM-DD)")
    parser.add_argument(
        "--outdir", 
        default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
        help="Output directory for raw data"
    )
    args = parser.parse_args()
    
    os.makedirs(args.outdir, exist_ok=True)
    
    # Fetch data
    df = fetch_nyt_county_data(args.state, args.county, args.start, args.end)
    
    # Calculate daily cases
    df = calculate_daily_cases(df)
    
    # Save raw data
    filename = f"nyt_county_{args.county.lower()}_{args.state.lower()}.csv"
    out_path = os.path.join(args.outdir, filename)
    df.to_csv(out_path, index=False)
    
    print(f"\nSaved: {out_path}")
    print(f"Rows: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nData summary:")
    print(f"  Total cumulative cases: {df['cases'].iloc[-1]:,}")
    print(f"  Total cumulative deaths: {df['deaths'].iloc[-1]:,}")
    print(f"  Average daily cases: {df['daily_cases'].mean():.1f}")
    print(f"  Peak daily cases: {df['daily_cases'].max():.0f} on {df.loc[df['daily_cases'].idxmax(), 'date'].strftime('%Y-%m-%d')}")
    
    # Show sample of data
    print(f"\nFirst few rows:")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
