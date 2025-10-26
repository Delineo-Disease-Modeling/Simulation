#!/usr/bin/env python3
"""
Phase 3: Compare ABM simulator outputs with Stan SEIR model posteriors.
This hybrid validation checks if the agent-based model's aggregate behavior
matches the Bayesian estimates from the mechanistic model.

Example usage:
    python compare_with_stan.py --stan-fit artifacts/stan/stan_fit.pkl --sim-data artifacts/simulation_results.csv
"""

import argparse
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import json

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 10)


def load_stan_results(fit_path):
    """Load Stan fit object and extract key results."""
    with open(fit_path, 'rb') as f:
        fit = pickle.load(f)
    
    posterior = fit.draws_pd()
    
    # Extract key parameters
    results = {
        'R0': {
            'median': np.median(posterior['R0']),
            'mean': np.mean(posterior['R0']),
            'std': np.std(posterior['R0']),
            'ci_lower': np.percentile(posterior['R0'], 2.5),
            'ci_upper': np.percentile(posterior['R0'], 97.5),
            'samples': posterior['R0'].values
        },
        'beta': {
            'median': np.median(posterior['beta']),
            'mean': np.mean(posterior['beta']),
            'std': np.std(posterior['beta']),
            'ci_lower': np.percentile(posterior['beta'], 2.5),
            'ci_upper': np.percentile(posterior['beta'], 97.5),
            'samples': posterior['beta'].values
        },
        'gamma': {
            'median': np.median(posterior['gamma']),
            'mean': np.mean(posterior['gamma']),
            'std': np.std(posterior['gamma']),
            'ci_lower': np.percentile(posterior['gamma'], 2.5),
            'ci_upper': np.percentile(posterior['gamma'], 97.5),
            'samples': posterior['gamma'].values
        },
        'latent_period': {
            'median': np.median(posterior['latent_period']),
            'mean': np.mean(posterior['latent_period']),
            'std': np.std(posterior['latent_period']),
            'ci_lower': np.percentile(posterior['latent_period'], 2.5),
            'ci_upper': np.percentile(posterior['latent_period'], 97.5),
            'samples': posterior['latent_period'].values
        },
        'infectious_period': {
            'median': np.median(posterior['infectious_period']),
            'mean': np.mean(posterior['infectious_period']),
            'std': np.std(posterior['infectious_period']),
            'ci_lower': np.percentile(posterior['infectious_period'], 2.5),
            'ci_upper': np.percentile(posterior['infectious_period'], 97.5),
            'samples': posterior['infectious_period'].values
        },
        'posterior': posterior
    }
    
    return results


def load_simulator_results(sim_path):
    """Load simulator results and extract comparable metrics."""
    df = pd.read_csv(sim_path, parse_dates=['date'] if 'date' in pd.read_csv(sim_path, nrows=0).columns else None)
    
    # Assuming simulator outputs daily cases or cumulative cases
    # Adjust column names as needed based on your simulator output
    if 'daily_cases' in df.columns:
        cases = df['daily_cases'].values
    elif 'new_infections' in df.columns:
        cases = df['new_infections'].values
    elif 'cases' in df.columns:
        cases = df['cases'].diff().fillna(df['cases'].iloc[0]).values
    else:
        raise ValueError("Cannot find case data in simulator output")
    
    results = {
        'daily_cases': cases,
        'total_cases': np.sum(cases),
        'peak_cases': np.max(cases),
        'peak_day': np.argmax(cases),
        'dataframe': df
    }
    
    return results


def estimate_abm_r0(sim_df, method='exponential_growth'):
    """
    Estimate effective R0 from ABM simulation output.
    
    Methods:
        - exponential_growth: Fit exponential to early growth phase
        - generation_time: Use generation time distribution if available
    """
    if 'daily_cases' in sim_df.columns:
        cases = sim_df['daily_cases'].values
    elif 'new_infections' in sim_df.columns:
        cases = sim_df['new_infections'].values
    else:
        return None, None
    
    # Find exponential growth phase (first 20% of data or until peak)
    peak_idx = np.argmax(cases)
    growth_end = min(peak_idx, len(cases) // 5)
    
    if growth_end < 5:
        return None, None
    
    # Fit exponential: cases(t) = cases(0) * exp(r * t)
    t = np.arange(growth_end)
    log_cases = np.log(cases[:growth_end] + 1)  # Add 1 to avoid log(0)
    
    # Linear regression on log scale
    slope, intercept = np.polyfit(t, log_cases, 1)
    r = slope  # Growth rate
    
    # R0 = 1 + r * generation_time
    # Assume generation time ~ 5 days for COVID-19
    generation_time = 5.0
    R0_estimate = 1 + r * generation_time
    
    # Calculate uncertainty (rough estimate)
    residuals = log_cases - (intercept + slope * t)
    r_std = np.std(residuals) / np.sqrt(len(t))
    R0_std = r_std * generation_time
    
    return R0_estimate, R0_std


def compare_trajectories(stan_results, sim_results, real_data_path=None):
    """
    Compare case trajectories from Stan model and ABM simulator.
    """
    posterior = stan_results['posterior']
    n_days = len(sim_results['daily_cases'])
    
    # Extract Stan predictions
    stan_pred_cols = [f'pred_cases[{i}]' for i in range(1, n_days + 1)]
    if not all(col in posterior.columns for col in stan_pred_cols):
        print("Warning: Stan predictions don't match simulation length")
        n_days = min(n_days, sum(1 for col in posterior.columns if col.startswith('pred_cases')))
        stan_pred_cols = [f'pred_cases[{i}]' for i in range(1, n_days + 1)]
    
    stan_predictions = posterior[stan_pred_cols].values
    stan_median = np.median(stan_predictions, axis=0)
    stan_lower = np.percentile(stan_predictions, 2.5, axis=0)
    stan_upper = np.percentile(stan_predictions, 97.5, axis=0)
    
    # ABM predictions
    abm_cases = sim_results['daily_cases'][:n_days]
    
    # Load real data if provided
    real_cases = None
    if real_data_path and os.path.exists(real_data_path):
        real_df = pd.read_csv(real_data_path, parse_dates=['date'])
        if 'daily_cases' in real_df.columns:
            real_cases = real_df['daily_cases'].values[:n_days]
    
    # Calculate metrics
    mae_stan = np.mean(np.abs(stan_median - (real_cases if real_cases is not None else abm_cases)))
    mae_abm = np.mean(np.abs(abm_cases - (real_cases if real_cases is not None else stan_median)))
    
    # Check if ABM falls within Stan credible intervals
    abm_in_ci = np.sum((abm_cases >= stan_lower) & (abm_cases <= stan_upper))
    coverage = abm_in_ci / n_days * 100
    
    metrics = {
        'mae_stan_vs_real': mae_stan if real_cases is not None else None,
        'mae_abm_vs_real': mae_abm if real_cases is not None else None,
        'mae_abm_vs_stan': np.mean(np.abs(abm_cases - stan_median)),
        'rmse_abm_vs_stan': np.sqrt(np.mean((abm_cases - stan_median)**2)),
        'correlation': np.corrcoef(abm_cases, stan_median)[0, 1],
        'abm_in_stan_ci_percent': coverage,
        'abm_peak_day': np.argmax(abm_cases),
        'stan_peak_day': np.argmax(stan_median),
        'abm_total_cases': np.sum(abm_cases),
        'stan_total_cases': np.sum(stan_median)
    }
    
    return metrics, (stan_median, stan_lower, stan_upper, abm_cases, real_cases)


def plot_comprehensive_comparison(stan_results, sim_results, metrics, trajectory_data, output_path):
    """
    Create comprehensive comparison visualization.
    """
    fig = plt.figure(figsize=(16, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    stan_median, stan_lower, stan_upper, abm_cases, real_cases = trajectory_data
    days = np.arange(len(abm_cases))
    
    # 1. Case Trajectories Comparison (large plot)
    ax1 = fig.add_subplot(gs[0, :])
    ax1.fill_between(days, stan_lower, stan_upper, alpha=0.3, color='blue', label='Stan 95% CI')
    ax1.plot(days, stan_median, '-', color='blue', linewidth=2, label='Stan (median)')
    ax1.plot(days, abm_cases, '-', color='red', linewidth=2, label='ABM Simulator')
    if real_cases is not None:
        ax1.plot(days, real_cases, 'o', color='black', markersize=4, alpha=0.6, label='Real Data')
    ax1.set_xlabel('Days')
    ax1.set_ylabel('Daily Cases')
    ax1.set_title('Case Trajectories: Stan SEIR vs ABM Simulator', fontsize=14, fontweight='bold')
    ax1.legend(loc='best')
    ax1.grid(True, alpha=0.3)
    
    # Add coverage annotation
    coverage_text = f"ABM within Stan 95% CI: {metrics['abm_in_stan_ci_percent']:.1f}%"
    ax1.text(0.02, 0.98, coverage_text, transform=ax1.transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 2. R0 Comparison
    ax2 = fig.add_subplot(gs[1, 0])
    stan_r0_samples = stan_results['R0']['samples']
    ax2.hist(stan_r0_samples, bins=40, density=True, alpha=0.7, color='blue', edgecolor='black', label='Stan Posterior')
    
    # Estimate ABM R0
    abm_r0, abm_r0_std = estimate_abm_r0(sim_results['dataframe'])
    if abm_r0 is not None:
        ax2.axvline(abm_r0, color='red', linestyle='--', linewidth=2, label=f'ABM Estimate: {abm_r0:.2f}')
        if abm_r0_std is not None:
            ax2.axvspan(abm_r0 - abm_r0_std, abm_r0 + abm_r0_std, alpha=0.2, color='red')
    
    ax2.axvline(stan_results['R0']['median'], color='blue', linestyle=':', linewidth=2, 
                label=f"Stan Median: {stan_results['R0']['median']:.2f}")
    ax2.set_xlabel('R₀')
    ax2.set_ylabel('Density')
    ax2.set_title('R₀ Comparison')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)
    
    # 3. Residuals Plot
    ax3 = fig.add_subplot(gs[1, 1])
    residuals = abm_cases - stan_median
    ax3.plot(days, residuals, 'o-', alpha=0.6, markersize=3)
    ax3.axhline(0, color='black', linestyle='--', linewidth=1)
    ax3.fill_between(days, -2*np.std(residuals), 2*np.std(residuals), alpha=0.2, color='gray')
    ax3.set_xlabel('Days')
    ax3.set_ylabel('Residuals (ABM - Stan)')
    ax3.set_title(f'Residuals (RMSE: {metrics["rmse_abm_vs_stan"]:.2f})')
    ax3.grid(True, alpha=0.3)
    
    # 4. Scatter Plot: ABM vs Stan
    ax4 = fig.add_subplot(gs[1, 2])
    ax4.scatter(stan_median, abm_cases, alpha=0.6, s=30)
    max_val = max(np.max(stan_median), np.max(abm_cases))
    ax4.plot([0, max_val], [0, max_val], 'k--', linewidth=1, label='Perfect Agreement')
    ax4.set_xlabel('Stan Predicted Cases')
    ax4.set_ylabel('ABM Predicted Cases')
    ax4.set_title(f'Correlation: {metrics["correlation"]:.3f}')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. Disease Period Comparison
    ax5 = fig.add_subplot(gs[2, 0])
    periods = ['Latent\nPeriod', 'Infectious\nPeriod']
    stan_vals = [stan_results['latent_period']['median'], stan_results['infectious_period']['median']]
    stan_errs = [
        [stan_results['latent_period']['median'] - stan_results['latent_period']['ci_lower'],
         stan_results['infectious_period']['median'] - stan_results['infectious_period']['ci_lower']],
        [stan_results['latent_period']['ci_upper'] - stan_results['latent_period']['median'],
         stan_results['infectious_period']['ci_upper'] - stan_results['infectious_period']['median']]
    ]
    
    x_pos = np.arange(len(periods))
    ax5.bar(x_pos, stan_vals, yerr=stan_errs, capsize=5, alpha=0.7, color='blue', edgecolor='black')
    ax5.set_xticks(x_pos)
    ax5.set_xticklabels(periods)
    ax5.set_ylabel('Days')
    ax5.set_title('Disease Periods (Stan Estimates)')
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Metrics Summary Table
    ax6 = fig.add_subplot(gs[2, 1:])
    ax6.axis('off')
    
    metrics_text = [
        ["Metric", "Value"],
        ["─" * 40, "─" * 20],
        ["MAE (ABM vs Stan)", f"{metrics['mae_abm_vs_stan']:.2f}"],
        ["RMSE (ABM vs Stan)", f"{metrics['rmse_abm_vs_stan']:.2f}"],
        ["Correlation", f"{metrics['correlation']:.3f}"],
        ["ABM in Stan 95% CI", f"{metrics['abm_in_stan_ci_percent']:.1f}%"],
        ["", ""],
        ["ABM Total Cases", f"{metrics['abm_total_cases']:.0f}"],
        ["Stan Total Cases", f"{metrics['stan_total_cases']:.0f}"],
        ["Difference", f"{metrics['abm_total_cases'] - metrics['stan_total_cases']:.0f}"],
        ["", ""],
        ["ABM Peak Day", f"{metrics['abm_peak_day']}"],
        ["Stan Peak Day", f"{metrics['stan_peak_day']}"],
    ]
    
    table = ax6.table(cellText=metrics_text, cellLoc='left', loc='center',
                      colWidths=[0.6, 0.4])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Style header row
    for i in range(2):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    plt.suptitle('Stan SEIR vs ABM Simulator: Comprehensive Comparison', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved comparison plot: {output_path}")
    
    return fig


def generate_validation_report(stan_results, sim_results, metrics, output_path):
    """
    Generate a detailed validation report in JSON and text formats.
    """
    report = {
        'timestamp': pd.Timestamp.now().isoformat(),
        'stan_parameters': {
            'R0': {
                'median': float(stan_results['R0']['median']),
                'ci_95': [float(stan_results['R0']['ci_lower']), float(stan_results['R0']['ci_upper'])],
                'mean': float(stan_results['R0']['mean']),
                'std': float(stan_results['R0']['std'])
            },
            'beta': {
                'median': float(stan_results['beta']['median']),
                'ci_95': [float(stan_results['beta']['ci_lower']), float(stan_results['beta']['ci_upper'])]
            },
            'gamma': {
                'median': float(stan_results['gamma']['median']),
                'ci_95': [float(stan_results['gamma']['ci_lower']), float(stan_results['gamma']['ci_upper'])]
            },
            'latent_period_days': {
                'median': float(stan_results['latent_period']['median']),
                'ci_95': [float(stan_results['latent_period']['ci_lower']), 
                         float(stan_results['latent_period']['ci_upper'])]
            },
            'infectious_period_days': {
                'median': float(stan_results['infectious_period']['median']),
                'ci_95': [float(stan_results['infectious_period']['ci_lower']), 
                         float(stan_results['infectious_period']['ci_upper'])]
            }
        },
        'abm_estimates': {
            'R0': estimate_abm_r0(sim_results['dataframe'])[0],
            'total_cases': float(sim_results['total_cases']),
            'peak_cases': float(sim_results['peak_cases']),
            'peak_day': int(sim_results['peak_day'])
        },
        'comparison_metrics': {k: float(v) if v is not None else None for k, v in metrics.items()},
        'validation_summary': {
            'abm_matches_stan': metrics['abm_in_stan_ci_percent'] > 80,
            'correlation_strong': metrics['correlation'] > 0.8,
            'relative_error': abs(metrics['abm_total_cases'] - metrics['stan_total_cases']) / metrics['stan_total_cases'] * 100
        }
    }
    
    # Save JSON
    json_path = output_path.replace('.txt', '.json')
    with open(json_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Saved JSON report: {json_path}")
    
    # Save text report
    with open(output_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write("STAN SEIR vs ABM SIMULATOR: VALIDATION REPORT\n")
        f.write("="*70 + "\n\n")
        
        f.write("STAN BAYESIAN ESTIMATES\n")
        f.write("-"*70 + "\n")
        f.write(f"R₀: {stan_results['R0']['median']:.2f} [{stan_results['R0']['ci_lower']:.2f}, {stan_results['R0']['ci_upper']:.2f}]\n")
        f.write(f"Transmission rate (β): {stan_results['beta']['median']:.3f} [{stan_results['beta']['ci_lower']:.3f}, {stan_results['beta']['ci_upper']:.3f}]\n")
        f.write(f"Recovery rate (γ): {stan_results['gamma']['median']:.3f} [{stan_results['gamma']['ci_lower']:.3f}, {stan_results['gamma']['ci_upper']:.3f}]\n")
        f.write(f"Latent period: {stan_results['latent_period']['median']:.1f} days [{stan_results['latent_period']['ci_lower']:.1f}, {stan_results['latent_period']['ci_upper']:.1f}]\n")
        f.write(f"Infectious period: {stan_results['infectious_period']['median']:.1f} days [{stan_results['infectious_period']['ci_lower']:.1f}, {stan_results['infectious_period']['ci_upper']:.1f}]\n\n")
        
        f.write("ABM SIMULATOR ESTIMATES\n")
        f.write("-"*70 + "\n")
        abm_r0, abm_r0_std = estimate_abm_r0(sim_results['dataframe'])
        if abm_r0 is not None:
            f.write(f"R₀ (estimated): {abm_r0:.2f} ± {abm_r0_std:.2f}\n")
        f.write(f"Total cases: {sim_results['total_cases']:.0f}\n")
        f.write(f"Peak cases: {sim_results['peak_cases']:.0f} on day {sim_results['peak_day']}\n\n")
        
        f.write("COMPARISON METRICS\n")
        f.write("-"*70 + "\n")
        f.write(f"MAE (ABM vs Stan): {metrics['mae_abm_vs_stan']:.2f}\n")
        f.write(f"RMSE (ABM vs Stan): {metrics['rmse_abm_vs_stan']:.2f}\n")
        f.write(f"Correlation: {metrics['correlation']:.3f}\n")
        f.write(f"ABM within Stan 95% CI: {metrics['abm_in_stan_ci_percent']:.1f}%\n")
        f.write(f"Relative error (total cases): {report['validation_summary']['relative_error']:.1f}%\n\n")
        
        f.write("VALIDATION ASSESSMENT\n")
        f.write("-"*70 + "\n")
        if report['validation_summary']['abm_matches_stan']:
            f.write("✓ ABM outputs fall within Stan credible intervals (>80%)\n")
        else:
            f.write("✗ ABM outputs deviate from Stan credible intervals\n")
        
        if report['validation_summary']['correlation_strong']:
            f.write("✓ Strong correlation between ABM and Stan predictions\n")
        else:
            f.write("✗ Weak correlation suggests model mismatch\n")
        
        if report['validation_summary']['relative_error'] < 20:
            f.write("✓ Total case counts are within 20% agreement\n")
        else:
            f.write("✗ Significant difference in total case counts\n")
    
    print(f"Saved text report: {output_path}")
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Compare ABM simulator with Stan SEIR model",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--stan-fit', required=True, help='Path to Stan fit pickle file')
    parser.add_argument('--sim-data', required=True, help='Path to simulator results CSV')
    parser.add_argument('--real-data', help='Optional: Path to real data for comparison')
    parser.add_argument('--output-dir', default='artifacts/comparison', help='Output directory')
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    validation_dir = os.path.dirname(script_dir)
    
    output_dir = os.path.join(validation_dir, args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    
    print("="*70)
    print("STAN vs ABM COMPARISON")
    print("="*70)
    
    # Load results
    print("\nLoading Stan results...")
    stan_results = load_stan_results(args.stan_fit)
    
    print("Loading simulator results...")
    sim_results = load_simulator_results(args.sim_data)
    
    # Compare trajectories
    print("\nComparing trajectories...")
    metrics, trajectory_data = compare_trajectories(stan_results, sim_results, args.real_data)
    
    # Generate visualizations
    print("\nGenerating comparison plots...")
    plot_path = os.path.join(output_dir, 'stan_vs_abm_comparison.png')
    plot_comprehensive_comparison(stan_results, sim_results, metrics, trajectory_data, plot_path)
    
    # Generate report
    print("\nGenerating validation report...")
    report_path = os.path.join(output_dir, 'validation_report.txt')
    report = generate_validation_report(stan_results, sim_results, metrics, report_path)
    
    print("\n" + "="*70)
    print("COMPARISON COMPLETE")
    print("="*70)
    print(f"Results saved to: {output_dir}")
    
    # Print summary
    print("\nQUICK SUMMARY:")
    print(f"  ABM within Stan 95% CI: {metrics['abm_in_stan_ci_percent']:.1f}%")
    print(f"  Correlation: {metrics['correlation']:.3f}")
    print(f"  RMSE: {metrics['rmse_abm_vs_stan']:.2f}")
    print(f"  Stan R₀: {stan_results['R0']['median']:.2f} [{stan_results['R0']['ci_lower']:.2f}, {stan_results['R0']['ci_upper']:.2f}]")


if __name__ == '__main__':
    main()
