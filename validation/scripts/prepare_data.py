#!/usr/bin/env python3
import argparse
import os
import pandas as pd


def compute_daily_from_cumulative(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values("date").reset_index(drop=True)
    out["daily_confirmed"] = out["cumulative_confirmed"].diff().clip(lower=0).fillna(0).astype(int)
    return out


def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["week"] = df["date"].dt.to_period("W-SUN").apply(lambda r: r.start_time)
    weekly = df.groupby("week", as_index=False)["daily_confirmed"].sum()
    weekly.rename(columns={"week": "date", "daily_confirmed": "weekly_cases"}, inplace=True)
    return weekly


def main():
    parser = argparse.ArgumentParser(description="Prepare raw ground-truth data into comparable series")
    parser.add_argument("--indir", default=os.path.join(os.path.dirname(__file__), "..", "data", "raw"))
    parser.add_argument("--infile", default=None, help="Raw CSV filename. If None, tries to find 'jhu_global_confirmed_*.csv'")
    parser.add_argument("--outdir", default=os.path.join(os.path.dirname(__file__), "..", "data", "processed"))
    parser.add_argument("--agg", default="daily", choices=["daily", "weekly"], help="Aggregation level for output")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Pick input file
    if args.infile is None:
        # select the first JHU file found
        candidates = [f for f in os.listdir(args.indir) if f.startswith("jhu_global_confirmed_") and f.endswith(".csv")]
        if not candidates:
            raise FileNotFoundError("No JHU raw file found in raw/ directory")
        infile = os.path.join(args.indir, sorted(candidates)[-1])
    else:
        infile = os.path.join(args.indir, args.infile)

    df = pd.read_csv(infile, parse_dates=["date"])  # columns: date, cumulative_confirmed
    df = compute_daily_from_cumulative(df)           # adds daily_confirmed

    if args.agg == "weekly":
        out = aggregate_weekly(df)                   # columns: date, weekly_cases
        out_path = os.path.join(args.outdir, "ground_truth_weekly_cases.csv")
    else:
        out = df[["date", "daily_confirmed"]].rename(columns={"daily_confirmed": "cases"})
        out_path = os.path.join(args.outdir, "ground_truth_daily_cases.csv")

    out.to_csv(out_path, index=False)
    print(f"Saved: {out_path} ({len(out)} rows)")


if __name__ == "__main__":
    main()
