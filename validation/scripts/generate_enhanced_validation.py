#!/usr/bin/env python3
"""
Enhanced validation graphs with better real-world alignment and additional metrics.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (16, 10)
plt.rcParams['font.size'] = 11

def load_delineo_runs(data_dir, max_runs=100):
    """Load infection data from Delineo simulation runs."""
    runs = []
    run_dirs = sorted([d for d in Path(data_dir).glob("run*") if d.is_dir()])[:max_runs]
    
    print(f"   Loading {len(run_dirs)} simulation runs...")
    
    for run_dir in run_dirs:
        run_name = Path(run_dir).name
        infection_file = run_dir / "infection_logs.csv"
        
        if infection_file.exists():
            try:
                df = pd.read_csv(infection_file)
                infections_per_timestep = df.groupby('timestep').size().reset_index(name='infections')
                infections_per_timestep['run'] = run_name
                runs.append(infections_per_timestep)
            except Exception as e:
                pass
    
    return pd.concat(runs, ignore_index=True) if runs else None

def aggregate_to_daily(df, timesteps_per_day=24):
    """Aggregate timesteps to daily cases."""
    df['day'] = df['timestep'] // timesteps_per_day
    daily = df.groupby(['run', 'day'])['infections'].sum().reset_index()
    return daily

def create_comprehensive_validation(real_data, delineo_data, output_dir):
    """Create comprehensive validation visualizations."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Aggregate Delineo statistics
    delineo_stats = delineo_data.groupby('day')['infections'].agg([
        'mean', 'std', 'min', 'max',
        ('q25', lambda x: x.quantile(0.25)),
        ('q75', lambda x: x.quantile(0.75))
    ]).reset_index()
    
    # Scale Delineo to match real-world magnitude
    real_mean = real_data['weekly_cases'].mean()
    delineo_mean = delineo_stats['mean'].mean()
    scale_factor = real_mean / delineo_mean
    
    print(f"   Scale factor: {scale_factor:.2f}")
    
    # Create main figure
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # ============ Plot 1: Main Trajectory Comparison ============
    ax1 = fig.add_subplot(gs[0, :2])
    
    # Plot real-world data
    ax1.plot(range(len(real_data)), real_data['weekly_cases'], 
             'o-', color='#2E86AB', linewidth=3, markersize=7,
             label='Real-World COVID-19 Data (US)', alpha=0.85, zorder=3)
    
    # Plot Delineo mean
    days = delineo_stats['day'].values
    scaled_mean = delineo_stats['mean'] * scale_factor
    scaled_std = delineo_stats['std'] * scale_factor
    scaled_q25 = delineo_stats['q25'] * scale_factor
    scaled_q75 = delineo_stats['q75'] * scale_factor
    
    ax1.plot(days, scaled_mean, 
             '-', color='#A23B72', linewidth=3,
             label='Delineo Simulation (Mean)', alpha=0.9, zorder=2)
    
    # 50% confidence interval
    ax1.fill_between(days, scaled_q25, scaled_q75,
                      color='#A23B72', alpha=0.25, label='Delineo 25-75% Range', zorder=1)
    
    # ±1 SD
    ax1.fill_between(days, 
                      np.maximum(0, scaled_mean - scaled_std),
                      scaled_mean + scaled_std,
                      color='#A23B72', alpha=0.15, label='Delineo ±1 SD', zorder=0)
    
    ax1.set_xlabel('Time Period', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Weekly Cases', fontsize=13, fontweight='bold')
    ax1.set_title('Epidemic Trajectory: Real-World vs Delineo Simulation', 
                  fontsize=15, fontweight='bold', pad=15)
    ax1.legend(loc='upper left', framealpha=0.95, fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, max(len(real_data), len(days)))
    
    # ============ Plot 2: Distribution Box Plot ============
    ax2 = fig.add_subplot(gs[0, 2])
    
    # Sample some time points for box plot
    sample_days = [10, 20, 30, 40, 50] if len(days) > 50 else list(range(0, len(days), max(1, len(days)//5)))
    box_data = []
    positions = []
    
    for i, day in enumerate(sample_days):
        if day < len(days):
            day_data = delineo_data[delineo_data['day'] == day]['infections'] * scale_factor
            if len(day_data) > 0:
                box_data.append(day_data.values)
                positions.append(i)
    
    bp = ax2.boxplot(box_data, positions=positions, widths=0.6,
                     patch_artist=True, showfliers=False)
    
    for patch in bp['boxes']:
        patch.set_facecolor('#A23B72')
        patch.set_alpha(0.6)
    
    ax2.set_xlabel('Time Point', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Cases', fontsize=11, fontweight='bold')
    ax2.set_title('Delineo Variability\nAcross Runs', fontsize=12, fontweight='bold')
    ax2.set_xticks(positions)
    ax2.set_xticklabels([f'D{d}' for d in sample_days], fontsize=9)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # ============ Plot 3: Correlation Scatter ============
    ax3 = fig.add_subplot(gs[1, 0])
    
    # Align data for correlation
    min_len = min(len(real_data), len(delineo_stats))
    real_vals = real_data['weekly_cases'].values[:min_len]
    delineo_vals = scaled_mean[:min_len]
    
    # Calculate correlation
    correlation = np.corrcoef(real_vals, delineo_vals)[0, 1]
    
    ax3.scatter(real_vals, delineo_vals, alpha=0.6, s=100, 
                color='#6A4C93', edgecolor='black', linewidth=1)
    
    # Fit line
    z = np.polyfit(real_vals, delineo_vals, 1)
    p = np.poly1d(z)
    x_line = np.linspace(real_vals.min(), real_vals.max(), 100)
    ax3.plot(x_line, p(x_line), "r--", linewidth=2, alpha=0.8, label=f'Fit: y={z[0]:.2f}x+{z[1]:.0f}')
    
    # Perfect agreement line
    max_val = max(real_vals.max(), delineo_vals.max())
    ax3.plot([0, max_val], [0, max_val], 'k:', linewidth=2, alpha=0.5, label='Perfect Agreement')
    
    ax3.text(0.05, 0.95, f'Correlation: {correlation:.3f}\nR²: {correlation**2:.3f}',
             transform=ax3.transAxes, fontsize=11, fontweight='bold',
             verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))
    
    ax3.set_xlabel('Real-World Cases', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Delineo Cases', fontsize=11, fontweight='bold')
    ax3.set_title('Case-by-Case Correlation', fontsize=12, fontweight='bold')
    ax3.legend(loc='lower right', fontsize=9)
    ax3.grid(True, alpha=0.3)
    
    # ============ Plot 4: Residuals ============
    ax4 = fig.add_subplot(gs[1, 1])
    
    residuals = delineo_vals - real_vals
    ax4.scatter(range(len(residuals)), residuals, alpha=0.6, s=80, 
                color='#F18F01', edgecolor='black', linewidth=1)
    ax4.axhline(y=0, color='red', linestyle='--', linewidth=2)
    ax4.axhline(y=residuals.mean(), color='blue', linestyle=':', linewidth=2, 
                label=f'Mean: {residuals.mean():.0f}')
    
    ax4.set_xlabel('Time Point', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Residual (Delineo - Real)', fontsize=11, fontweight='bold')
    ax4.set_title('Prediction Residuals', fontsize=12, fontweight='bold')
    ax4.legend(loc='best', fontsize=9)
    ax4.grid(True, alpha=0.3)
    
    # ============ Plot 5: Growth Rate ============
    ax5 = fig.add_subplot(gs[1, 2])
    
    # Calculate growth rates
    real_growth = np.diff(real_vals) / (real_vals[:-1] + 1) * 100
    delineo_growth = np.diff(delineo_vals) / (delineo_vals[:-1] + 1) * 100
    
    ax5.plot(range(len(real_growth)), real_growth, 
             'o-', color='#2E86AB', linewidth=2, markersize=4,
             label='Real-World', alpha=0.7)
    ax5.plot(range(len(delineo_growth)), delineo_growth,
             '-', color='#A23B72', linewidth=2,
             label='Delineo', alpha=0.7)
    
    ax5.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    ax5.set_xlabel('Time Point', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Growth Rate (%)', fontsize=11, fontweight='bold')
    ax5.set_title('Epidemic Growth Rate', fontsize=12, fontweight='bold')
    ax5.legend(loc='best', fontsize=9)
    ax5.grid(True, alpha=0.3)
    
    # ============ Plot 6: Cumulative Comparison ============
    ax6 = fig.add_subplot(gs[2, 0])
    
    real_cumulative = np.cumsum(real_vals)
    delineo_cumulative = np.cumsum(delineo_vals)
    
    ax6.plot(range(len(real_cumulative)), real_cumulative,
             'o-', color='#2E86AB', linewidth=2.5, markersize=5,
             label='Real-World', alpha=0.8)
    ax6.plot(range(len(delineo_cumulative)), delineo_cumulative,
             '-', color='#A23B72', linewidth=2.5,
             label='Delineo', alpha=0.9)
    
    ax6.set_xlabel('Time Point', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Cumulative Cases', fontsize=11, fontweight='bold')
    ax6.set_title('Cumulative Case Comparison', fontsize=12, fontweight='bold')
    ax6.legend(loc='best', fontsize=9)
    ax6.grid(True, alpha=0.3)
    
    # ============ Plot 7: Peak Analysis ============
    ax7 = fig.add_subplot(gs[2, 1])
    
    real_peak = real_vals.max()
    real_peak_idx = real_vals.argmax()
    delineo_peak = delineo_vals.max()
    delineo_peak_idx = delineo_vals.argmax()
    
    categories = ['Peak\nMagnitude', 'Peak\nTiming']
    real_values = [real_peak, real_peak_idx]
    delineo_values = [delineo_peak, delineo_peak_idx]
    
    x = np.arange(len(categories))
    width = 0.35
    
    # Normalize for visualization
    norm_real = [real_peak/real_peak, real_peak_idx/max(real_peak_idx, delineo_peak_idx)]
    norm_delineo = [delineo_peak/real_peak, delineo_peak_idx/max(real_peak_idx, delineo_peak_idx)]
    
    bars1 = ax7.bar(x - width/2, norm_real, width, label='Real-World', 
                    color='#2E86AB', alpha=0.7, edgecolor='black', linewidth=1.5)
    bars2 = ax7.bar(x + width/2, norm_delineo, width, label='Delineo',
                    color='#A23B72', alpha=0.7, edgecolor='black', linewidth=1.5)
    
    ax7.set_ylabel('Normalized Value', fontsize=11, fontweight='bold')
    ax7.set_title('Peak Characteristics', fontsize=12, fontweight='bold')
    ax7.set_xticks(x)
    ax7.set_xticklabels(categories, fontsize=10)
    ax7.legend(fontsize=9)
    ax7.grid(True, alpha=0.3, axis='y')
    
    # Add actual values as text
    for i, (r, d) in enumerate(zip(real_values, delineo_values)):
        ax7.text(i, 1.05, f'R: {r:,.0f}\nD: {d:,.0f}', 
                ha='center', fontsize=8, fontweight='bold')
    
    # ============ Plot 8: Metrics Table ============
    ax8 = fig.add_subplot(gs[2, 2])
    ax8.axis('off')
    
    # Calculate comprehensive metrics
    rmse = np.sqrt(np.mean((real_vals - delineo_vals)**2))
    mae = np.mean(np.abs(real_vals - delineo_vals))
    mape = np.mean(np.abs((real_vals - delineo_vals) / (real_vals + 1))) * 100
    
    metrics = {
        'Metric': [
            'Correlation',
            'R² Score',
            'RMSE',
            'MAE',
            'MAPE (%)',
            '',
            'Total Cases (Real)',
            'Total Cases (Sim)',
            'Peak (Real)',
            'Peak (Sim)',
            'Peak Timing Diff'
        ],
        'Value': [
            f'{correlation:.3f}',
            f'{correlation**2:.3f}',
            f'{rmse:,.0f}',
            f'{mae:,.0f}',
            f'{mape:.1f}',
            '',
            f'{real_cumulative.iloc[-1] if isinstance(real_cumulative, pd.Series) else real_cumulative[-1]:,.0f}',
            f'{delineo_cumulative.iloc[-1] if isinstance(delineo_cumulative, pd.Series) else delineo_cumulative[-1]:,.0f}',
            f'{real_peak:,.0f}',
            f'{delineo_peak:,.0f}',
            f'{abs(real_peak_idx - delineo_peak_idx)} periods'
        ]
    }
    
    table_data = pd.DataFrame(metrics)
    
    table = ax8.table(cellText=table_data.values, colLabels=table_data.columns,
                      cellLoc='left', loc='center', colWidths=[0.6, 0.4])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2.2)
    
    # Style header
    for i in range(len(table_data.columns)):
        table[(0, i)].set_facecolor('#6A4C93')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(len(table_data.columns)):
            if table_data.iloc[i-1, 0] == '':
                table[(i, j)].set_facecolor('#FFFFFF')
            elif i % 2 == 0:
                table[(i, j)].set_facecolor('#F0F0F0')
    
    ax8.set_title('Validation Metrics', fontsize=12, fontweight='bold', pad=20)
    
    plt.suptitle('Delineo Epidemic Simulation Validation', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(output_dir / 'comprehensive_validation.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'comprehensive_validation.png'}")
    
    return {
        'correlation': correlation,
        'r_squared': correlation**2,
        'rmse': rmse,
        'mae': mae,
        'mape': mape,
        'scale_factor': scale_factor
    }

def main():
    base_dir = Path(__file__).parent.parent
    delineo_data_dir = base_dir.parent.parent / "AI-counterfactual-analysis" / "data" / "raw"
    real_data_file = base_dir / "data" / "processed" / "ground_truth_weekly_cases.csv"
    output_dir = base_dir / "reports" / "validation_graphs"
    
    print("="*70)
    print("ENHANCED DELINEO VALIDATION")
    print("="*70)
    
    print("\n1. Loading Delineo simulation data...")
    delineo_raw = load_delineo_runs(delineo_data_dir, max_runs=100)
    if delineo_raw is None:
        print("❌ No Delineo data found!")
        return
    
    print(f"   Loaded {len(delineo_raw['run'].unique())} runs")
    
    print("\n2. Aggregating to daily cases...")
    delineo_daily = aggregate_to_daily(delineo_raw)
    
    print("\n3. Loading real-world data...")
    real_data = pd.read_csv(real_data_file, parse_dates=['date'])
    print(f"   Loaded {len(real_data)} weeks")
    
    print("\n4. Generating comprehensive validation plots...")
    metrics = create_comprehensive_validation(real_data, delineo_daily, output_dir)
    
    print("\n" + "="*70)
    print("VALIDATION COMPLETE")
    print("="*70)
    print(f"\nKey Metrics:")
    print(f"  • Correlation: {metrics['correlation']:.3f}")
    print(f"  • R² Score: {metrics['r_squared']:.3f}")
    print(f"  • RMSE: {metrics['rmse']:,.0f}")
    print(f"  • MAE: {metrics['mae']:,.0f}")
    print(f"  • MAPE: {metrics['mape']:.1f}%")
    print(f"  • Scale Factor: {metrics['scale_factor']:.2f}")
    print(f"\nOutput: {output_dir}/comprehensive_validation.png")
    print("="*70)

if __name__ == '__main__':
    main()
