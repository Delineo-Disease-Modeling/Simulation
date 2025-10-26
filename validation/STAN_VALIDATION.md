# Stan-Based Bayesian Validation Framework

## Overview

This validation framework uses **Stan**, a probabilistic programming language, to provide rigorous Bayesian validation of the Delineo ABM simulator. It implements a three-phase approach that combines mechanistic disease modeling with uncertainty quantification.

## Why Stan?

1. **Bayesian Parameter Estimation**: Provides full posterior distributions for transmission parameters (β, γ, R₀) with credible intervals
2. **Mechanistic Modeling**: SEIR compartmental models capture the same disease dynamics as our ABM at the population level
3. **Uncertainty Quantification**: Quantifies both parameter uncertainty and prediction uncertainty
4. **Model Validation**: Simulation-based calibration ensures our inference is reliable
5. **Industry Standard**: Used extensively in epidemiology (Imperial College COVID-19 models, CDC forecasting)

## Three-Phase Validation Approach

### Phase 1: Traditional Metrics (Existing)
- Point estimate comparisons (MAE, RMSE, sMAPE)
- Quick iteration and debugging
- **Location**: `scripts/compare.py`, `scripts/metrics.py`

### Phase 2: Stan Bayesian Calibration (New)
- Fit SEIR model to real county data using MCMC
- Extract posterior distributions for epidemiological parameters
- Provides benchmark parameter estimates with uncertainty
- **Location**: `scripts/fit_stan_model.py`, `models/seir_model.stan`

### Phase 3: Hybrid Comparison (New)
- Compare ABM outputs against Stan posterior predictive distributions
- Check if ABM falls within Stan's 95% credible intervals
- Validate that ABM's emergent behavior matches mechanistic expectations
- **Location**: `scripts/compare_with_stan.py`

## File Structure

```
validation/
├── models/
│   ├── seir_model.stan              # Basic SEIR model
│   └── seir_interventions.stan      # SEIR with time-varying transmission
├── scripts/
│   ├── fit_stan_model.py            # Phase 2: Fit Stan to real data
│   ├── compare_with_stan.py         # Phase 3: Compare ABM vs Stan
│   ├── run_full_validation.py       # Orchestrate all phases
│   └── fetch_county_data.py         # (Existing) Get real data
├── artifacts/
│   ├── stan/                        # Stan fit results
│   │   ├── stan_fit.pkl
│   │   ├── stan_posterior.csv
│   │   └── stan_fit_results.png
│   └── comparison/                  # Phase 3 outputs
│       ├── stan_vs_abm_comparison.png
│       └── validation_report.txt
└── requirements.txt                 # Updated with Stan dependencies
```

## Installation

```bash
# Install Stan and dependencies
pip install -r requirements.txt

# Install CmdStan (Stan's command-line interface)
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```

## Quick Start

### Run Complete Validation Pipeline

```bash
# Full validation for Washington County, MD (March 2021)
python scripts/run_full_validation.py \
    --county Washington \
    --state Maryland \
    --start 2021-03-01 \
    --end 2021-03-31 \
    --population 150000

# Quick mode (fewer MCMC iterations, faster)
python scripts/run_full_validation.py \
    --county Washington \
    --state Maryland \
    --start 2021-03-01 \
    --end 2021-03-31 \
    --quick
```

### Run Individual Phases

**Phase 2: Fit Stan Model**
```bash
python scripts/fit_stan_model.py \
    --data data/processed/washington_md_daily.csv \
    --population 150000 \
    --output-dir artifacts/stan
```

**Phase 3: Compare with ABM**
```bash
python scripts/compare_with_stan.py \
    --stan-fit artifacts/stan/stan_fit.pkl \
    --sim-data artifacts/simulation_results.csv \
    --real-data data/processed/washington_md_daily.csv \
    --output-dir artifacts/comparison
```

## What You Get

### Stan Fit Results (`artifacts/stan/`)

1. **Parameter Posteriors**: Full distributions for β, γ, σ, R₀
2. **Credible Intervals**: 95% CI for all parameters
3. **Disease Periods**: Latent period (1/σ) and infectious period (1/γ)
4. **Posterior Predictive Samples**: Simulated case trajectories from the model
5. **Diagnostics**: MCMC convergence checks (R-hat, ESS)

**Example Output:**
```
R₀: 2.45 [2.12, 2.89]
Transmission rate (β): 0.489 [0.424, 0.578]
Recovery rate (γ): 0.200 [0.180, 0.220]
Latent period: 4.2 days [3.5, 5.1]
Infectious period: 5.0 days [4.5, 5.6]
```

### Comparison Results (`artifacts/comparison/`)

1. **Trajectory Comparison**: ABM vs Stan predictions over time
2. **Coverage Analysis**: % of ABM outputs within Stan 95% CI
3. **Parameter Agreement**: ABM's emergent R₀ vs Stan's estimate
4. **Residual Analysis**: Systematic deviations between models
5. **Validation Report**: Pass/fail assessment with metrics

**Key Metrics:**
- **Coverage**: ABM within Stan CI (target: >80%)
- **Correlation**: ABM vs Stan predictions (target: >0.8)
- **RMSE**: Root mean squared error
- **Relative Error**: Total case count difference

## Interpreting Results

### ✅ Good Validation
- ABM outputs fall within Stan 95% CI >80% of the time
- Strong correlation (>0.8) between ABM and Stan trajectories
- ABM's emergent R₀ matches Stan's estimate within uncertainty
- Total case counts agree within 20%

### ⚠️ Investigate Further
- Coverage 60-80%: ABM may have additional stochasticity
- Correlation 0.6-0.8: Check timing of interventions
- R₀ mismatch: Review transmission parameters in ABM

### ❌ Model Issues
- Coverage <60%: Fundamental mismatch in dynamics
- Correlation <0.6: ABM not capturing epidemic trajectory
- Large systematic residuals: Check for bugs or missing mechanisms

## Stan Model Details

### Basic SEIR Model (`seir_model.stan`)

**Compartments:**
- S: Susceptible
- E: Exposed (infected but not yet infectious)
- I: Infectious
- R: Recovered

**Parameters:**
- β: Transmission rate (contacts × probability of transmission)
- σ: Incubation rate (1/latent period)
- γ: Recovery rate (1/infectious period)
- φ: Overdispersion parameter (for negative binomial likelihood)

**Priors:**
- β ~ Normal(0.5, 0.2): Based on COVID-19 R₀ ~ 2-4
- σ ~ Normal(0.25, 0.1): Latent period ~ 3-5 days
- γ ~ Normal(0.2, 0.05): Infectious period ~ 5-7 days

### Interventions Model (`seir_interventions.stan`)

Allows β to vary across time periods (e.g., before/after lockdown).

## Advanced Usage

### Custom Priors

Edit the Stan data preparation in `fit_stan_model.py`:

```python
stan_data = {
    ...
    'beta_mean': 0.6,    # Stronger transmission
    'beta_sd': 0.15,     # More certain
    'gamma_mean': 0.25,  # Shorter infectious period
    ...
}
```

### Multiple Intervention Periods

Use `seir_interventions.stan` for time-varying transmission:

```python
stan_data = {
    ...
    'n_periods': 3,
    'period_ends': [30, 60, 90],  # Days where interventions change
    ...
}
```

### Simulation-Based Calibration

For rigorous validation, implement SBC:

```python
# Generate synthetic data from Stan priors
# Fit model to synthetic data
# Check if posteriors recover true parameters
# Repeat 100+ times
```

See: https://arxiv.org/abs/1804.06788

## Troubleshooting

### Stan Compilation Errors
```bash
# Reinstall CmdStan
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```

### MCMC Convergence Issues
- Increase `--iter-warmup` (e.g., 2000)
- Check for divergent transitions in diagnostics
- Try tighter priors if parameters are poorly identified

### ABM API Not Running
```bash
cd ../..  # Go to Simulation/ root
docker compose up -d
# Wait for health check
curl http://localhost:1880/simulation/
```

### Memory Issues
- Use `--quick` mode for faster iterations
- Reduce `--chains` to 2
- Process shorter time periods

## References

1. **Stan Documentation**: https://mc-stan.org/
2. **Epidemiology Case Studies**: https://epidemiology-stan.github.io/
3. **Boarding School Tutorial**: https://mc-stan.org/learn-stan/case-studies/boarding_school_case_study.html
4. **Bayesian Workflow**: Gelman et al. (2020) "Bayesian Workflow"
5. **SBC**: Talts et al. (2018) "Validating Bayesian Inference Algorithms"

## Next Steps

1. **Run validation on multiple counties** to test generalizability
2. **Implement SBC** for rigorous inference validation
3. **Add spatial models** (CAR/ICAR) for multi-county validation
4. **Calibrate ABM parameters** using Stan posteriors as targets
5. **Model selection** using LOO-CV or WAIC to compare model variants

## Support

For questions about:
- **Stan models**: See Stan documentation or Discourse forum
- **Validation framework**: Check this README or `HAGERSTOWN_VALIDATION.md`
- **ABM simulator**: See main `Simulation/README.md`
