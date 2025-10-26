#!/usr/bin/env python3
"""
Phase 2: Fit Stan SEIR model to real county data.
This provides Bayesian parameter estimates and uncertainty quantification.

Example usage:
    python fit_stan_model.py --data data/processed/washington_md_weekly.csv --output artifacts/stan_fit.pkl
"""

import argparse
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from cmdstanpy import CmdStanModel
import arviz as az
from datetime import datetime

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)


def prepare_stan_data(df, population=150000, intervention_dates=None):
    """
    Prepare data for Stan SEIR model.
    
    Args:
        df: DataFrame with 'date' and 'daily_cases' columns
        population: Total population size
        intervention_dates: Optional list of dates where interventions occurred
    
    Returns:
        Dictionary of data for Stan model
    """
    df = df.copy().sort_values('date').reset_index(drop=True)
    
    n_days = len(df)
    cases = df['daily_cases'].fillna(0).astype(int).values
    
    # Initial conditions: S, E, I, R
    # Assume small initial outbreak
    initial_infected = max(1, cases[0])
    initial_exposed = initial_infected * 2  # Rough estimate
    y0 = [
        population - initial_exposed - initial_infected,  # S
        initial_exposed,                                   # E
        initial_infected,                                  # I
        0                                                  # R
    ]
    
    # Time points
    t0 = 0.0
    ts = np.arange(1, n_days + 1, dtype=float).tolist()
    
    # Priors based on COVID-19 literature
    # Beta: transmission rate (R0 = beta/gamma, R0 ~ 2-4 for COVID)
    # Sigma: 1/latent period (latent ~ 3-5 days)
    # Gamma: 1/infectious period (infectious ~ 5-7 days)
    
    stan_data = {
        'n_days': n_days,
        't0': t0,
        'ts': ts,
        'N': population,
        'y0': y0,
        'cases': cases.tolist(),
        'beta_mean': 0.5,      # R0 ~ 2.5 with gamma ~ 0.2
        'beta_sd': 0.2,
        'sigma_mean': 0.25,    # ~4 day latent period
        'sigma_sd': 0.1,
        'gamma_mean': 0.2,     # ~5 day infectious period
        'gamma_sd': 0.05,
    }
    
    return stan_data, df


def fit_stan_seir(stan_data, model_path, output_dir, chains=4, iter_sampling=1000, iter_warmup=1000):
    """
    Fit Stan SEIR model using MCMC.
    
    Args:
        stan_data: Dictionary of data for Stan
        model_path: Path to .stan file
        output_dir: Directory to save outputs
        chains: Number of MCMC chains
        iter_sampling: Number of sampling iterations per chain
        iter_warmup: Number of warmup iterations per chain
    
    Returns:
        CmdStanMCMC fit object
    """
    print(f"\n{'='*60}")
    print("FITTING STAN SEIR MODEL")
    print(f"{'='*60}")
    print(f"Data: {stan_data['n_days']} days, Population: {stan_data['N']:,}")
    print(f"Total observed cases: {sum(stan_data['cases']):,}")
    print(f"Model: {model_path}")
    print(f"Chains: {chains}, Iterations: {iter_sampling} (+ {iter_warmup} warmup)")
    
    # Compile model
    print("\nCompiling Stan model...")
    model = CmdStanModel(stan_file=model_path)
    
    # Fit model
    print("\nRunning MCMC sampling...")
    fit = model.sample(
        data=stan_data,
        chains=chains,
        iter_sampling=iter_sampling,
        iter_warmup=iter_warmup,
        show_progress=True,
        output_dir=output_dir
    )
    
    # Print diagnostics
    print("\n" + "="*60)
    print("MCMC DIAGNOSTICS")
    print("="*60)
    print(fit.diagnose())
    
    # Print summary
    print("\n" + "="*60)
    print("PARAMETER ESTIMATES")
    print("="*60)
    summary_df = fit.summary()
    params_of_interest = ['beta', 'sigma', 'gamma', 'R0', 'latent_period', 'infectious_period', 'phi', 'i0']
    print(summary_df[summary_df.index.isin(params_of_interest)])
    
    return fit


def plot_stan_results(fit, stan_data, df, output_path):
    """
    Create comprehensive visualization of Stan fit results.
    """
    fig, axes = plt.subplots(3, 2, figsize=(15, 12))
    
    # Extract posterior samples
    posterior = fit.draws_pd()
    
    # 1. Observed vs Predicted Cases
    ax = axes[0, 0]
    pred_cases = posterior[[f'pred_cases[{i}]' for i in range(1, stan_data['n_days'] + 1)]].values
    
    dates = df['date'].values
    observed = stan_data['cases']
    
    # Plot credible intervals
    pred_median = np.median(pred_cases, axis=0)
    pred_lower = np.percentile(pred_cases, 2.5, axis=0)
    pred_upper = np.percentile(pred_cases, 97.5, axis=0)
    
    ax.plot(dates, observed, 'o', label='Observed', alpha=0.6, markersize=4)
    ax.plot(dates, pred_median, '-', label='Predicted (median)', linewidth=2)
    ax.fill_between(dates, pred_lower, pred_upper, alpha=0.3, label='95% CI')
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Cases')
    ax.set_title('Observed vs Predicted Cases')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 2. R0 Posterior Distribution
    ax = axes[0, 1]
    ax.hist(posterior['R0'], bins=50, density=True, alpha=0.7, edgecolor='black')
    r0_median = np.median(posterior['R0'])
    r0_lower = np.percentile(posterior['R0'], 2.5)
    r0_upper = np.percentile(posterior['R0'], 97.5)
    ax.axvline(r0_median, color='red', linestyle='--', linewidth=2, label=f'Median: {r0_median:.2f}')
    ax.axvline(r0_lower, color='red', linestyle=':', alpha=0.5)
    ax.axvline(r0_upper, color='red', linestyle=':', alpha=0.5)
    ax.set_xlabel('R₀')
    ax.set_ylabel('Density')
    ax.set_title(f'R₀ Posterior: {r0_median:.2f} [{r0_lower:.2f}, {r0_upper:.2f}]')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Transmission Parameters
    ax = axes[1, 0]
    params = ['beta', 'sigma', 'gamma']
    param_labels = ['β (transmission)', 'σ (incubation)', 'γ (recovery)']
    positions = range(len(params))
    
    for i, (param, label) in enumerate(zip(params, param_labels)):
        values = posterior[param]
        ax.violinplot([values], positions=[i], widths=0.7, showmedians=True)
    
    ax.set_xticks(positions)
    ax.set_xticklabels(param_labels, rotation=15, ha='right')
    ax.set_ylabel('Rate (per day)')
    ax.set_title('Transmission Parameter Posteriors')
    ax.grid(True, alpha=0.3, axis='y')
    
    # 4. Latent and Infectious Periods
    ax = axes[1, 1]
    latent = posterior['latent_period']
    infectious = posterior['infectious_period']
    
    ax.hist(latent, bins=30, alpha=0.6, label='Latent Period', density=True)
    ax.hist(infectious, bins=30, alpha=0.6, label='Infectious Period', density=True)
    ax.axvline(np.median(latent), color='blue', linestyle='--', alpha=0.7)
    ax.axvline(np.median(infectious), color='orange', linestyle='--', alpha=0.7)
    ax.set_xlabel('Days')
    ax.set_ylabel('Density')
    ax.set_title(f'Disease Periods (Latent: {np.median(latent):.1f}d, Infectious: {np.median(infectious):.1f}d)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 5. Posterior Predictive Check
    ax = axes[2, 0]
    # Sample 100 posterior predictive trajectories
    n_samples = min(100, len(posterior))
    sample_indices = np.random.choice(len(posterior), n_samples, replace=False)
    
    for idx in sample_indices:
        pred_sample = [posterior.iloc[idx][f'pred_cases_samples[{i}]'] for i in range(1, stan_data['n_days'] + 1)]
        ax.plot(dates, pred_sample, alpha=0.05, color='blue')
    
    ax.plot(dates, observed, 'o', color='red', label='Observed', markersize=4, zorder=10)
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Cases')
    ax.set_title('Posterior Predictive Check (100 samples)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 6. SEIR Compartments Over Time
    ax = axes[2, 1]
    compartments = ['S', 'E', 'I', 'R']
    colors = ['blue', 'orange', 'red', 'green']
    
    for comp_idx, (comp, color) in enumerate(zip(compartments, colors)):
        comp_data = posterior[[f'y[{i},{comp_idx+1}]' for i in range(1, stan_data['n_days'] + 1)]].values
        comp_median = np.median(comp_data, axis=0)
        ax.plot(dates, comp_median, label=comp, color=color, linewidth=2)
    
    ax.set_xlabel('Date')
    ax.set_ylabel('Population')
    ax.set_title('SEIR Compartments (Median)')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"\nSaved plot: {output_path}")
    
    return fig


def save_results(fit, stan_data, output_dir):
    """
    Save fit results and diagnostics.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Save fit object
    fit_path = os.path.join(output_dir, 'stan_fit.pkl')
    with open(fit_path, 'wb') as f:
        pickle.dump(fit, f)
    print(f"Saved fit object: {fit_path}")
    
    # Save posterior samples as CSV
    posterior_df = fit.draws_pd()
    posterior_path = os.path.join(output_dir, 'stan_posterior.csv')
    posterior_df.to_csv(posterior_path, index=False)
    print(f"Saved posterior samples: {posterior_path}")
    
    # Save summary statistics
    summary_df = fit.summary()
    summary_path = os.path.join(output_dir, 'stan_summary.csv')
    summary_df.to_csv(summary_path)
    print(f"Saved summary: {summary_path}")
    
    # Create ArviZ InferenceData for advanced diagnostics
    idata = az.from_cmdstanpy(fit)
    
    # Save diagnostics
    diagnostics_path = os.path.join(output_dir, 'stan_diagnostics.txt')
    with open(diagnostics_path, 'w') as f:
        f.write("="*60 + "\n")
        f.write("STAN MODEL DIAGNOSTICS\n")
        f.write("="*60 + "\n\n")
        f.write(fit.diagnose())
        f.write("\n\n" + "="*60 + "\n")
        f.write("PARAMETER SUMMARY\n")
        f.write("="*60 + "\n")
        f.write(summary_df.to_string())
    print(f"Saved diagnostics: {diagnostics_path}")
    
    return idata


def main():
    parser = argparse.ArgumentParser(
        description="Fit Stan SEIR model to county COVID-19 data",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--data', required=True, help='Path to processed data CSV')
    parser.add_argument('--population', type=int, default=150000, help='County population')
    parser.add_argument('--model', default='models/seir_model.stan', help='Path to Stan model file')
    parser.add_argument('--output-dir', default='artifacts/stan', help='Output directory')
    parser.add_argument('--chains', type=int, default=4, help='Number of MCMC chains')
    parser.add_argument('--iter-sampling', type=int, default=1000, help='Sampling iterations')
    parser.add_argument('--iter-warmup', type=int, default=1000, help='Warmup iterations')
    
    args = parser.parse_args()
    
    # Resolve paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    validation_dir = os.path.dirname(script_dir)
    
    data_path = os.path.join(validation_dir, args.data) if not os.path.isabs(args.data) else args.data
    model_path = os.path.join(validation_dir, args.model) if not os.path.isabs(args.model) else args.model
    output_dir = os.path.join(validation_dir, args.output_dir) if not os.path.isabs(args.output_dir) else args.output_dir
    
    # Load data
    print(f"Loading data from: {data_path}")
    df = pd.read_csv(data_path, parse_dates=['date'])
    
    # Prepare Stan data
    stan_data, df = prepare_stan_data(df, population=args.population)
    
    # Fit model
    fit = fit_stan_seir(
        stan_data, 
        model_path, 
        output_dir,
        chains=args.chains,
        iter_sampling=args.iter_sampling,
        iter_warmup=args.iter_warmup
    )
    
    # Save results
    idata = save_results(fit, stan_data, output_dir)
    
    # Plot results
    plot_path = os.path.join(output_dir, 'stan_fit_results.png')
    plot_stan_results(fit, stan_data, df, plot_path)
    
    print("\n" + "="*60)
    print("STAN FITTING COMPLETE")
    print("="*60)
    print(f"Results saved to: {output_dir}")


if __name__ == '__main__':
    main()
