#!/usr/bin/env python3
"""
Generate validation graphs comparing real-world COVID data with Delineo simulation results.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime, timedelta
import glob

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 11

def load_delineo_runs(data_dir):
    """Load infection data from all Delineo simulation runs."""
    runs = []
    run_dirs = sorted([d for d in Path(data_dir).glob("run*") if d.is_dir()])
    
    print(f"   Found {len(run_dirs)} run directories")
    
    for run_dir in run_dirs:
        run_name = Path(run_dir).name
        infection_file = f"{run_dir}/infection_logs.csv"
        
        if Path(infection_file).exists():
            try:
                df = pd.read_csv(infection_file)
                # Count infections per timestep
                infections_per_timestep = df.groupby('timestep').size().reset_index(name='infections')
                infections_per_timestep['run'] = run_name
                runs.append(infections_per_timestep)
            except Exception as e:
                print(f"Warning: Could not load {run_name}: {e}")
    
    return pd.concat(runs, ignore_index=True) if runs else None

def aggregate_delineo_data(df, timesteps_per_day=24):
    """Aggregate Delineo timesteps into daily cases."""
    df['day'] = df['timestep'] // timesteps_per_day
    daily = df.groupby(['run', 'day'])['infections'].sum().reset_index()
    return daily

def load_real_world_data(data_file):
    """Load real-world COVID case data."""
    df = pd.read_csv(data_file, parse_dates=['date'])
    df = df.sort_values('date')
    return df

def create_comparison_plots(real_data, delineo_data, output_dir):
    """Create comprehensive comparison plots."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Figure 1: Time series comparison with uncertainty bands
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Daily cases comparison
    ax = axes[0, 0]
    
    # Real-world data
    ax.plot(real_data['date'], real_data['weekly_cases'], 
            'o-', color='#2E86AB', linewidth=2.5, markersize=6,
            label='Real-World Data (US Weekly)', alpha=0.8)
    
    # Delineo simulation - aggregate across runs
    delineo_stats = delineo_data.groupby('day')['infections'].agg(['mean', 'std', 'min', 'max'])
    days = delineo_stats.index
    
    # Scale Delineo to match real-world magnitude (approximate)
    scale_factor = real_data['weekly_cases'].mean() / delineo_stats['mean'].mean()
    
    ax.plot(days, delineo_stats['mean'] * scale_factor, 
            '-', color='#A23B72', linewidth=2.5, 
            label='Delineo Simulation (Mean)', alpha=0.9)
    
    ax.fill_between(days, 
                     (delineo_stats['mean'] - delineo_stats['std']) * scale_factor,
                     (delineo_stats['mean'] + delineo_stats['std']) * scale_factor,
                     color='#A23B72', alpha=0.2, label='Delineo ±1 SD')
    
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cases', fontsize=12, fontweight='bold')
    ax.set_title('Epidemic Trajectory: Real-World vs Delineo', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Log-scale comparison
    ax = axes[0, 1]
    ax.semilogy(real_data['date'], real_data['weekly_cases'], 
                'o-', color='#2E86AB', linewidth=2, markersize=5,
                label='Real-World Data', alpha=0.8)
    ax.semilogy(days, delineo_stats['mean'] * scale_factor, 
                '-', color='#A23B72', linewidth=2,
                label='Delineo Mean', alpha=0.9)
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cases (log scale)', fontsize=12, fontweight='bold')
    ax.set_title('Log-Scale Epidemic Growth', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3, which='both')
    
    # Plot 3: Distribution of simulation outcomes
    ax = axes[1, 0]
    
    # Sample some runs to show variability
    sample_runs = delineo_data['run'].unique()[:20]
    for run in sample_runs:
        run_data = delineo_data[delineo_data['run'] == run]
        ax.plot(run_data['day'], run_data['infections'] * scale_factor,
                alpha=0.3, linewidth=1, color='#A23B72')
    
    # Overlay mean
    ax.plot(days, delineo_stats['mean'] * scale_factor,
            '-', color='#F18F01', linewidth=3, label='Mean Trajectory')
    
    ax.set_xlabel('Day', fontsize=12, fontweight='bold')
    ax.set_ylabel('Daily Infections', fontsize=12, fontweight='bold')
    ax.set_title('Delineo Simulation Variability (20 runs)', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Peak timing comparison
    ax = axes[1, 1]
    
    # Find peaks
    real_peak_idx = real_data['weekly_cases'].idxmax()
    real_peak_value = real_data.loc[real_peak_idx, 'weekly_cases']
    real_peak_time = real_data.loc[real_peak_idx, 'date']
    
    delineo_peak_day = delineo_stats['mean'].idxmax()
    delineo_peak_value = delineo_stats.loc[delineo_peak_day, 'mean'] * scale_factor
    
    # Bar chart comparison
    categories = ['Real-World\nPeak', 'Delineo\nPeak']
    values = [real_peak_value, delineo_peak_value]
    colors = ['#2E86AB', '#A23B72']
    
    bars = ax.bar(categories, values, color=colors, alpha=0.7, edgecolor='black', linewidth=2)
    ax.set_ylabel('Peak Cases', fontsize=12, fontweight='bold')
    ax.set_title('Peak Magnitude Comparison', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, val in zip(bars, values):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:,.0f}',
                ha='center', va='bottom', fontweight='bold', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'validation_comparison.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'validation_comparison.png'}")
    
    # Figure 2: Statistical validation metrics
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Cumulative cases
    ax = axes[0, 0]
    real_cumulative = real_data['weekly_cases'].cumsum()
    delineo_cumulative = (delineo_stats['mean'] * scale_factor).cumsum()
    
    ax.plot(real_data['date'], real_cumulative, 
            'o-', color='#2E86AB', linewidth=2.5, markersize=6,
            label='Real-World Cumulative', alpha=0.8)
    ax.plot(days, delineo_cumulative,
            '-', color='#A23B72', linewidth=2.5,
            label='Delineo Cumulative', alpha=0.9)
    
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cumulative Cases', fontsize=12, fontweight='bold')
    ax.set_title('Cumulative Case Comparison', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Growth rate comparison
    ax = axes[0, 1]
    
    # Calculate growth rates (7-day moving average)
    real_growth = real_data['weekly_cases'].pct_change().rolling(window=3).mean() * 100
    delineo_growth = delineo_stats['mean'].pct_change().rolling(window=3).mean() * 100
    
    ax.plot(real_data['date'], real_growth,
            'o-', color='#2E86AB', linewidth=2, markersize=4,
            label='Real-World Growth Rate', alpha=0.8)
    ax.plot(days, delineo_growth,
            '-', color='#A23B72', linewidth=2,
            label='Delineo Growth Rate', alpha=0.9)
    
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Time', fontsize=12, fontweight='bold')
    ax.set_ylabel('Growth Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Epidemic Growth Rate Comparison', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Correlation scatter
    ax = axes[1, 0]
    
    # Align data for correlation (use overlapping time periods)
    min_len = min(len(real_data), len(delineo_stats))
    real_vals = real_data['weekly_cases'].values[:min_len]
    delineo_vals = (delineo_stats['mean'] * scale_factor).values[:min_len]
    
    ax.scatter(real_vals, delineo_vals, alpha=0.6, s=80, color='#6A4C93', edgecolor='black')
    
    # Add diagonal line
    max_val = max(real_vals.max(), delineo_vals.max())
    ax.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Perfect Agreement')
    
    # Calculate correlation
    correlation = np.corrcoef(real_vals, delineo_vals)[0, 1]
    ax.text(0.05, 0.95, f'Correlation: {correlation:.3f}',
            transform=ax.transAxes, fontsize=12, fontweight='bold',
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    ax.set_xlabel('Real-World Cases', fontsize=12, fontweight='bold')
    ax.set_ylabel('Delineo Cases', fontsize=12, fontweight='bold')
    ax.set_title('Case-by-Case Correlation', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Summary statistics table
    ax = axes[1, 1]
    ax.axis('off')
    
    # Calculate metrics
    metrics = {
        'Metric': [
            'Total Cases',
            'Peak Cases',
            'Mean Daily Cases',
            'Std Daily Cases',
            'Correlation',
            'RMSE (scaled)'
        ],
        'Real-World': [
            f"{real_data['weekly_cases'].sum():,.0f}",
            f"{real_peak_value:,.0f}",
            f"{real_data['weekly_cases'].mean():,.0f}",
            f"{real_data['weekly_cases'].std():,.0f}",
            '-',
            '-'
        ],
        'Delineo': [
            f"{delineo_cumulative.iloc[-1]:,.0f}",
            f"{delineo_peak_value:,.0f}",
            f"{(delineo_stats['mean'] * scale_factor).mean():,.0f}",
            f"{(delineo_stats['std'] * scale_factor).mean():,.0f}",
            f"{correlation:.3f}",
            f"{np.sqrt(np.mean((real_vals - delineo_vals)**2)):,.0f}"
        ]
    }
    
    table_data = pd.DataFrame(metrics)
    
    table = ax.table(cellText=table_data.values, colLabels=table_data.columns,
                     cellLoc='center', loc='center',
                     colWidths=[0.4, 0.3, 0.3])
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)
    
    # Style header
    for i in range(len(table_data.columns)):
        table[(0, i)].set_facecolor('#6A4C93')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(len(table_data.columns)):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#F0F0F0')
    
    ax.set_title('Validation Metrics Summary', fontsize=14, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'validation_metrics.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'validation_metrics.png'}")
    
    return correlation, scale_factor

def main():
    # Paths
    base_dir = Path(__file__).parent.parent
    delineo_data_dir = base_dir.parent.parent / "AI-counterfactual-analysis" / "data" / "raw"
    real_data_file = base_dir / "data" / "processed" / "ground_truth_weekly_cases.csv"
    output_dir = base_dir / "reports" / "validation_graphs"
    
    print("="*70)
    print("DELINEO VALIDATION GRAPH GENERATION")
    print("="*70)
    
    # Load data
    print("\n1. Loading Delineo simulation data...")
    delineo_raw = load_delineo_runs(delineo_data_dir)
    if delineo_raw is None:
        print("❌ No Delineo data found!")
        return
    
    print(f"   Loaded {len(delineo_raw['run'].unique())} simulation runs")
    
    print("\n2. Aggregating Delineo data to daily cases...")
    delineo_daily = aggregate_delineo_data(delineo_raw, timesteps_per_day=24)
    print(f"   Aggregated to {len(delineo_daily)} daily records")
    
    print("\n3. Loading real-world COVID data...")
    real_data = load_real_world_data(real_data_file)
    print(f"   Loaded {len(real_data)} weeks of real-world data")
    
    print("\n4. Generating comparison plots...")
    correlation, scale_factor = create_comparison_plots(real_data, delineo_daily, output_dir)
    
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)
    print(f"\nKey Findings:")
    print(f"  • Correlation: {correlation:.3f}")
    print(f"  • Scale factor: {scale_factor:.2f}")
    print(f"  • Number of runs analyzed: {len(delineo_daily['run'].unique())}")
    print(f"\nOutputs saved to: {output_dir}")
    print(f"  • validation_comparison.png")
    print(f"  • validation_metrics.png")
    print("="*70)

if __name__ == '__main__':
    main()
