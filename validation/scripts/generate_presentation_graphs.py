#!/usr/bin/env python3
"""
Generate publication-quality presentation graphs for Delineo validation.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Professional color palette
COLORS = {
    'real': '#1f77b4',      # Professional blue
    'delineo': '#d62728',   # Professional red
    'accent': '#ff7f0e',    # Orange
    'success': '#2ca02c',   # Green
    'neutral': '#7f7f7f'    # Gray
}

def load_and_process_data(delineo_dir, real_file, max_runs=100):
    """Load and process both datasets."""
    # Load Delineo
    runs = []
    run_dirs = sorted([d for d in Path(delineo_dir).glob("run*") if d.is_dir()])[:max_runs]
    
    for run_dir in run_dirs:
        infection_file = run_dir / "infection_logs.csv"
        if infection_file.exists():
            try:
                df = pd.read_csv(infection_file)
                infections = df.groupby('timestep').size().reset_index(name='infections')
                infections['run'] = run_dir.name
                runs.append(infections)
            except:
                pass
    
    delineo_raw = pd.concat(runs, ignore_index=True) if runs else None
    
    # Aggregate to daily
    delineo_raw['day'] = delineo_raw['timestep'] // 24
    delineo_daily = delineo_raw.groupby(['run', 'day'])['infections'].sum().reset_index()
    
    # Load real-world
    real_data = pd.read_csv(real_file, parse_dates=['date'])
    
    return delineo_daily, real_data

def create_presentation_figure(delineo_data, real_data, output_dir):
    """Create a single high-impact presentation figure."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Aggregate statistics
    delineo_stats = delineo_data.groupby('day')['infections'].agg([
        'mean', 'std',
        ('q05', lambda x: x.quantile(0.05)),
        ('q25', lambda x: x.quantile(0.25)),
        ('q75', lambda x: x.quantile(0.75)),
        ('q95', lambda x: x.quantile(0.95))
    ]).reset_index()
    
    # Calculate scale factor
    scale_factor = real_data['weekly_cases'].mean() / delineo_stats['mean'].mean()
    
    # Scale Delineo data
    for col in ['mean', 'std', 'q05', 'q25', 'q75', 'q95']:
        delineo_stats[f'{col}_scaled'] = delineo_stats[col] * scale_factor
    
    # Align for metrics
    min_len = min(len(real_data), len(delineo_stats))
    real_vals = real_data['weekly_cases'].values[:min_len]
    delineo_vals = delineo_stats['mean_scaled'].values[:min_len]
    correlation = np.corrcoef(real_vals, delineo_vals)[0, 1]
    
    # Create figure
    fig = plt.figure(figsize=(20, 10))
    gs = fig.add_gridspec(2, 3, hspace=0.25, wspace=0.25, 
                          left=0.08, right=0.95, top=0.92, bottom=0.08)
    
    # ============ MAIN PLOT: Trajectory with Confidence Bands ============
    ax_main = fig.add_subplot(gs[:, :2])
    
    days = delineo_stats['day'].values
    
    # Plot 95% confidence interval
    ax_main.fill_between(days, 
                          delineo_stats['q05_scaled'],
                          delineo_stats['q95_scaled'],
                          color=COLORS['delineo'], alpha=0.15, 
                          label='Delineo 90% CI', zorder=1)
    
    # Plot 50% confidence interval
    ax_main.fill_between(days,
                          delineo_stats['q25_scaled'],
                          delineo_stats['q75_scaled'],
                          color=COLORS['delineo'], alpha=0.3,
                          label='Delineo 50% CI', zorder=2)
    
    # Plot mean
    ax_main.plot(days, delineo_stats['mean_scaled'],
                 '-', color=COLORS['delineo'], linewidth=3.5,
                 label='Delineo Mean', alpha=0.95, zorder=4)
    
    # Plot real-world data
    ax_main.plot(range(len(real_data)), real_data['weekly_cases'],
                 'o-', color=COLORS['real'], linewidth=3, markersize=8,
                 label='Real-World COVID-19', alpha=0.85, zorder=5,
                 markeredgecolor='white', markeredgewidth=1.5)
    
    ax_main.set_xlabel('Time Period (weeks)', fontsize=16, fontweight='bold')
    ax_main.set_ylabel('Weekly Cases', fontsize=16, fontweight='bold')
    ax_main.set_title('Epidemic Trajectory Validation: Real-World vs Delineo ABM',
                      fontsize=18, fontweight='bold', pad=20)
    
    # Enhanced legend
    legend = ax_main.legend(loc='upper left', fontsize=13, framealpha=0.95,
                           edgecolor='black', fancybox=True, shadow=True)
    legend.get_frame().set_linewidth(1.5)
    
    ax_main.grid(True, alpha=0.3, linestyle='--', linewidth=0.8)
    ax_main.set_xlim(0, max(len(real_data), len(days)))
    ax_main.tick_params(labelsize=12)
    
    # Add annotation for key insight
    peak_idx = real_data['weekly_cases'].idxmax()
    peak_val = real_data['weekly_cases'].max()
    ax_main.annotate(f'Peak: {peak_val:,.0f} cases',
                     xy=(peak_idx, peak_val),
                     xytext=(peak_idx + 10, peak_val * 0.7),
                     fontsize=12, fontweight='bold',
                     bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                     arrowprops=dict(arrowstyle='->', lw=2, color='black'))
    
    # ============ TOP RIGHT: Correlation Metrics ============
    ax_corr = fig.add_subplot(gs[0, 2])
    
    # Scatter with density
    ax_corr.scatter(real_vals, delineo_vals, 
                    alpha=0.5, s=120, c=range(len(real_vals)),
                    cmap='viridis', edgecolor='black', linewidth=1)
    
    # Perfect agreement line
    max_val = max(real_vals.max(), delineo_vals.max())
    ax_corr.plot([0, max_val], [0, max_val], 'k--', linewidth=2.5, 
                 alpha=0.6, label='Perfect Agreement')
    
    # Regression line
    z = np.polyfit(real_vals, delineo_vals, 1)
    p = np.poly1d(z)
    x_line = np.linspace(0, real_vals.max(), 100)
    ax_corr.plot(x_line, p(x_line), 'r-', linewidth=2.5, alpha=0.8,
                 label=f'Fit (R²={correlation**2:.3f})')
    
    # Metrics box
    metrics_text = f'Correlation: {correlation:.3f}\nR² Score: {correlation**2:.3f}'
    ax_corr.text(0.05, 0.95, metrics_text,
                 transform=ax_corr.transAxes, fontsize=13, fontweight='bold',
                 verticalalignment='top',
                 bbox=dict(boxstyle='round,pad=0.8', facecolor='lightblue', 
                          alpha=0.9, edgecolor='black', linewidth=2))
    
    ax_corr.set_xlabel('Real-World Cases', fontsize=13, fontweight='bold')
    ax_corr.set_ylabel('Delineo Cases', fontsize=13, fontweight='bold')
    ax_corr.set_title('Model Correlation', fontsize=14, fontweight='bold', pad=10)
    ax_corr.legend(loc='lower right', fontsize=10)
    ax_corr.grid(True, alpha=0.3)
    ax_corr.tick_params(labelsize=11)
    
    # ============ BOTTOM RIGHT: Key Performance Indicators ============
    ax_kpi = fig.add_subplot(gs[1, 2])
    ax_kpi.axis('off')
    
    # Calculate KPIs
    rmse = np.sqrt(np.mean((real_vals - delineo_vals)**2))
    mae = np.mean(np.abs(real_vals - delineo_vals))
    
    # Create KPI cards
    kpis = [
        ('Correlation', f'{correlation:.3f}', COLORS['success'] if correlation > 0.7 else COLORS['accent']),
        ('R² Score', f'{correlation**2:.3f}', COLORS['success'] if correlation**2 > 0.5 else COLORS['accent']),
        ('RMSE', f'{rmse/1000:.0f}K', COLORS['neutral']),
        ('MAE', f'{mae/1000:.0f}K', COLORS['neutral']),
        ('Runs', f'{len(delineo_data["run"].unique())}', COLORS['real']),
        ('Scale', f'{scale_factor:.0f}x', COLORS['delineo'])
    ]
    
    # Create grid of KPI cards
    for i, (label, value, color) in enumerate(kpis):
        row = i // 2
        col = i % 2
        
        x = 0.1 + col * 0.5
        y = 0.85 - row * 0.28
        
        # Card background
        rect = plt.Rectangle((x, y), 0.35, 0.2, 
                            transform=ax_kpi.transAxes,
                            facecolor=color, alpha=0.2,
                            edgecolor=color, linewidth=2.5)
        ax_kpi.add_patch(rect)
        
        # Value (large)
        ax_kpi.text(x + 0.175, y + 0.12, value,
                   transform=ax_kpi.transAxes,
                   fontsize=20, fontweight='bold',
                   ha='center', va='center', color=color)
        
        # Label (small)
        ax_kpi.text(x + 0.175, y + 0.04, label,
                   transform=ax_kpi.transAxes,
                   fontsize=11, fontweight='bold',
                   ha='center', va='center', color='black')
    
    ax_kpi.set_xlim(0, 1)
    ax_kpi.set_ylim(0, 1)
    ax_kpi.set_title('Key Performance Indicators', 
                     fontsize=14, fontweight='bold', pad=10, loc='left')
    
    # Overall title
    fig.suptitle('Delineo Agent-Based Model: Epidemic Simulation Validation',
                 fontsize=20, fontweight='bold', y=0.98)
    
    # Save
    plt.savefig(output_dir / 'presentation_validation.png', 
                dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved: {output_dir / 'presentation_validation.png'}")
    
    return correlation, scale_factor

def create_detailed_comparison(delineo_data, real_data, output_dir):
    """Create detailed multi-panel comparison."""
    output_dir = Path(output_dir)
    
    # Aggregate
    delineo_stats = delineo_data.groupby('day')['infections'].agg([
        'mean', 'std', 'min', 'max'
    ]).reset_index()
    
    scale_factor = real_data['weekly_cases'].mean() / delineo_stats['mean'].mean()
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Detailed Epidemic Dynamics Comparison', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    # Plot 1: Raw trajectories
    ax = axes[0, 0]
    
    # Sample individual runs
    sample_runs = delineo_data['run'].unique()[:30]
    for run in sample_runs:
        run_data = delineo_data[delineo_data['run'] == run]
        ax.plot(run_data['day'], run_data['infections'] * scale_factor,
                alpha=0.2, linewidth=0.8, color=COLORS['delineo'])
    
    # Mean
    ax.plot(delineo_stats['day'], delineo_stats['mean'] * scale_factor,
            '-', color=COLORS['delineo'], linewidth=3, label='Delineo Mean')
    
    # Real data
    ax.plot(range(len(real_data)), real_data['weekly_cases'],
            'o-', color=COLORS['real'], linewidth=2.5, markersize=6,
            label='Real-World', alpha=0.8)
    
    ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cases', fontsize=12, fontweight='bold')
    ax.set_title('Individual Run Variability', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Log scale
    ax = axes[0, 1]
    
    ax.semilogy(range(len(real_data)), real_data['weekly_cases'],
                'o-', color=COLORS['real'], linewidth=2.5, markersize=6,
                label='Real-World', alpha=0.8)
    ax.semilogy(delineo_stats['day'], delineo_stats['mean'] * scale_factor,
                '-', color=COLORS['delineo'], linewidth=2.5,
                label='Delineo Mean', alpha=0.9)
    
    ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cases (log scale)', fontsize=12, fontweight='bold')
    ax.set_title('Exponential Growth Phase', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, which='both')
    
    # Plot 3: Cumulative
    ax = axes[1, 0]
    
    real_cumulative = real_data['weekly_cases'].cumsum()
    delineo_cumulative = (delineo_stats['mean'] * scale_factor).cumsum()
    
    ax.plot(range(len(real_cumulative)), real_cumulative,
            'o-', color=COLORS['real'], linewidth=2.5, markersize=6,
            label='Real-World', alpha=0.8)
    ax.plot(range(len(delineo_cumulative)), delineo_cumulative,
            '-', color=COLORS['delineo'], linewidth=2.5,
            label='Delineo', alpha=0.9)
    
    ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cumulative Cases', fontsize=12, fontweight='bold')
    ax.set_title('Cumulative Burden', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Distribution comparison
    ax = axes[1, 1]
    
    # Violin plot of Delineo at different time points
    sample_days = [10, 20, 30, 40, 50]
    violin_data = []
    labels = []
    
    for day in sample_days:
        if day < len(delineo_stats):
            day_data = delineo_data[delineo_data['day'] == day]['infections'] * scale_factor
            if len(day_data) > 0:
                violin_data.append(day_data.values)
                labels.append(f'D{day}')
    
    parts = ax.violinplot(violin_data, positions=range(len(violin_data)),
                          showmeans=True, showmedians=True)
    
    for pc in parts['bodies']:
        pc.set_facecolor(COLORS['delineo'])
        pc.set_alpha(0.6)
    
    ax.set_xlabel('Time Point', fontsize=12, fontweight='bold')
    ax.set_ylabel('Cases', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of Outcomes', fontsize=13, fontweight='bold')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'detailed_comparison.png', 
                dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved: {output_dir / 'detailed_comparison.png'}")

def main():
    base_dir = Path(__file__).parent.parent
    delineo_dir = base_dir.parent.parent / "AI-counterfactual-analysis" / "data" / "raw"
    real_file = base_dir / "data" / "processed" / "ground_truth_weekly_cases.csv"
    output_dir = base_dir / "reports" / "validation_graphs"
    
    print("="*70)
    print("PRESENTATION-QUALITY VALIDATION GRAPHS")
    print("="*70)
    
    print("\n1. Loading and processing data...")
    delineo_data, real_data = load_and_process_data(delineo_dir, real_file, max_runs=100)
    print(f"   • {len(delineo_data['run'].unique())} simulation runs")
    print(f"   • {len(real_data)} weeks of real-world data")
    
    print("\n2. Creating presentation figure...")
    correlation, scale_factor = create_presentation_figure(delineo_data, real_data, output_dir)
    
    print("\n3. Creating detailed comparison...")
    create_detailed_comparison(delineo_data, real_data, output_dir)
    
    print("\n" + "="*70)
    print("GRAPHS GENERATED SUCCESSFULLY")
    print("="*70)
    print(f"\nKey Results:")
    print(f"  • Correlation: {correlation:.3f}")
    print(f"  • R² Score: {correlation**2:.3f}")
    print(f"  • Scale Factor: {scale_factor:.2f}")
    print(f"\nOutput Files:")
    print(f"  • presentation_validation.png (main figure)")
    print(f"  • detailed_comparison.png (supplementary)")
    print(f"\nLocation: {output_dir}")
    print("="*70)

if __name__ == '__main__':
    main()
