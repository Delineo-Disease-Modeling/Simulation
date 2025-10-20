#!/usr/bin/env python3
import argparse
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from metrics import mae, rmse, smape, peak_timing_error


def align_series(ground: pd.DataFrame, sim: pd.DataFrame, agg: str) -> pd.DataFrame:
    """
    Align ground-truth and simulator series by index length (no calendar anchoring).
    ground: columns ['date', 'cases' or 'weekly_cases']
    sim: columns ['step_index','days_since_start','new_cases'] possibly per-step
    If agg == 'weekly', aggregate simulator to weekly by 7-day bins; otherwise use per-step as daily proxy
    by grouping each 24 hours assuming step_minutes=60 (days_since_start bins of size 1).
    """
    sim = sim.copy()
    # Aggregate simulator to daily first (bin by day boundary)
    sim['day'] = np.floor(sim['days_since_start']).astype(int)
    daily_sim = sim.groupby('day', as_index=False)['new_cases'].sum()
    daily_sim.rename(columns={'day': 'idx', 'new_cases': 'sim_cases'}, inplace=True)

    if agg == 'weekly':
        daily_sim['week'] = (daily_sim['idx'] // 7).astype(int)
        weekly_sim = daily_sim.groupby('week', as_index=False)['sim_cases'].sum()
        weekly_sim.rename(columns={'week': 'idx', 'sim_cases': 'sim_cases'}, inplace=True)
        sim_series = weekly_sim['sim_cases']
        if 'weekly_cases' in ground.columns:
            gt_series = ground['weekly_cases']
        else:
            # if only daily exists, aggregate ground to weekly similarly
            ground = ground.copy()
            ground['week'] = ground.index // 7
            gt_series = ground.groupby('week')['cases'].sum().reset_index(drop=True)
    else:
        sim_series = daily_sim['sim_cases']
        if 'cases' in ground.columns:
            gt_series = ground['cases']
        else:
            # if weekly provided but requested daily, expand evenly (rough proxy)
            gt_series = ground['weekly_cases']

    # Truncate to overlap
    n = min(len(sim_series), len(gt_series))
    sim_series = sim_series.iloc[:n].reset_index(drop=True)
    gt_series = gt_series.iloc[:n].reset_index(drop=True)

    aligned = pd.DataFrame({
        'gt_cases': gt_series,
        'sim_cases': sim_series
    })
    return aligned


def generate_plot(aligned: pd.DataFrame, out_png: str, title: str):
    plt.figure(figsize=(10,5))
    plt.plot(aligned['gt_cases'].values, label='Ground Truth', linewidth=2)
    plt.plot(aligned['sim_cases'].values, label='Simulator', linewidth=2)
    plt.title(title)
    plt.xlabel('Time index')
    plt.ylabel('Cases')
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_png)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Compare simulator outputs to ground truth and compute metrics')
    parser.add_argument('--processed_dir', default=os.path.join(os.path.dirname(__file__), '..', 'data', 'processed'))
    parser.add_argument('--artifacts', default=os.path.join(os.path.dirname(__file__), '..', 'artifacts'))
    parser.add_argument('--agg', default='weekly', choices=['daily','weekly'])
    parser.add_argument('--reports', default=os.path.join(os.path.dirname(__file__), '..', 'reports'))
    parser.add_argument('--geo', default='us', help='Geographic identifier (e.g., us, washington_maryland)')
    parser.add_argument('--horizon', default='1,2,3,4', help='Comma-separated forecast horizons')
    args = parser.parse_args()

    os.makedirs(args.reports, exist_ok=True)

    # Load ground truth - try geo-specific files first, then fall back to generic
    if args.geo != 'us':
        gt_path_weekly = os.path.join(args.processed_dir, f'ground_truth_weekly_cases_{args.geo}.csv')
        gt_path_daily = os.path.join(args.processed_dir, f'ground_truth_daily_cases_{args.geo}.csv')
    else:
        gt_path_weekly = os.path.join(args.processed_dir, 'ground_truth_weekly_cases.csv')
        gt_path_daily = os.path.join(args.processed_dir, 'ground_truth_daily_cases.csv')
    
    if args.agg == 'weekly' and os.path.exists(gt_path_weekly):
        ground = pd.read_csv(gt_path_weekly)
    elif os.path.exists(gt_path_daily):
        ground = pd.read_csv(gt_path_daily)
    else:
        raise FileNotFoundError(f'Ground truth processed CSV not found at {gt_path_weekly} or {gt_path_daily}. Run prepare_data.py first.')

    # Load simulator series
    sim_path = os.path.join(args.artifacts, 'sim_timeseries.csv')
    if not os.path.exists(sim_path):
        raise FileNotFoundError('Simulator timeseries not found. Run run_simulation.py first.')
    sim = pd.read_csv(sim_path)

    aligned = align_series(ground, sim, args.agg)

    # Metrics
    y = aligned['gt_cases'].values.astype(float)
    yhat = aligned['sim_cases'].values.astype(float)
    metrics = {
        'n_points': len(aligned),
        'mae': mae(y, yhat),
        'rmse': rmse(y, yhat),
        'smape': smape(y, yhat),
        'peak_timing_error_idx': peak_timing_error(aligned['gt_cases'], aligned['sim_cases'])
    }

    # Save metrics and aligned series
    aligned_out = os.path.join(args.reports, f'aligned_{args.agg}.csv')
    aligned.to_csv(aligned_out, index=False)
    metrics_out = os.path.join(args.reports, f'metrics_{args.agg}.csv')
    pd.DataFrame([metrics]).to_csv(metrics_out, index=False)

    plot_out = os.path.join(args.reports, f'comparison_{args.agg}.png')
    generate_plot(aligned, plot_out, f'Simulator vs Ground Truth ({args.agg})')

    print(f'Saved aligned series: {aligned_out}')
    print(f'Saved metrics: {metrics_out}')
    print(f'Saved plot: {plot_out}')


if __name__ == '__main__':
    main()
