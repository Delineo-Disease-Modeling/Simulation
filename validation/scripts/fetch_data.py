#!/usr/bin/env python3
import argparse
import os
import io
import sys
import requests
import pandas as pd
from datetime import datetime

JHU_GLOBAL_CONFIRMED = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/" \
                       "csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"
JHU_GLOBAL_DEATHS = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/" \
                    "csse_covid_19_time_series/time_series_covid19_deaths_global.csv"


def fetch_jhu_global(country: str) -> pd.DataFrame:
    r = requests.get(JHU_GLOBAL_CONFIRMED, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    # Filter by country
    df_country = df[df["Country/Region"].str.lower() == country.lower()].copy()
    if df_country.empty:
        raise ValueError(f"Country '{country}' not found in JHU global confirmed dataset")
    # Sum across provinces
    date_cols = df_country.columns[4:]
    s = df_country[date_cols].sum(axis=0)
    out = s.reset_index()
    out.columns = ["date", "cumulative_confirmed"]
    out["date"] = pd.to_datetime(out["date"], format="%m/%d/%y")
    out.sort_values("date", inplace=True)
    return out


def main():
    parser = argparse.ArgumentParser(description="Fetch reliable COVID data (JHU global)")
    parser.add_argument("--country", default="US", help="Country name as in JHU dataset (default: US)")
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"),
                        help="Output directory for raw data")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    df = fetch_jhu_global(args.country)
    out_path = os.path.join(args.outdir, f"jhu_global_confirmed_{args.country.lower()}.csv")
    df.to_csv(out_path, index=False)
    print(f"Saved: {out_path} ({len(df)} rows)")


if __name__ == "__main__":
    main()
