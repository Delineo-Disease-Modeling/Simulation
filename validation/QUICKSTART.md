# Quick Start: Stan Validation in 5 Minutes

## Prerequisites

```bash
cd ~/Documents/Projects/Delineo/Simulation/validation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```

## Run Complete Validation

```bash
# Quick mode (5 minutes)
python scripts/run_full_validation.py \
    --county Washington \
    --state Maryland \
    --start 2021-03-01 \
    --end 2021-03-31 \
    --population 150000 \
    --quick

# Full mode (10-15 minutes, more accurate)
python scripts/run_full_validation.py \
    --county Washington \
    --state Maryland \
    --start 2021-03-01 \
    --end 2021-03-31 \
    --population 150000
```

## View Results

```bash
# Open visualizations
open artifacts/full_validation/stan/stan_fit_results.png
open artifacts/full_validation/comparison/stan_vs_abm_comparison.png

# Read validation report
cat artifacts/full_validation/comparison/validation_report.txt

# Check summary
cat artifacts/full_validation/validation_summary.json
```

## What You'll See

### Stan Fit Results
- **R₀ posterior**: e.g., 2.45 [2.12, 2.89]
- **Transmission parameters**: β, σ, γ with credible intervals
- **Disease periods**: Latent and infectious period estimates
- **Predicted cases**: With 95% confidence bands

### Comparison Results
- **Coverage**: % of ABM outputs within Stan 95% CI (target: >80%)
- **Correlation**: ABM vs Stan (target: >0.8)
- **RMSE**: Prediction error
- **Validation status**: ✓ Pass or ✗ Fail with diagnostics

## Interpretation

### ✅ Validation Passed
```
✓ ABM outputs fall within Stan credible intervals (85%)
✓ Strong correlation (0.87)
✓ Total case counts within 20% (12% error)
```
**Meaning**: Your ABM is validated against mechanistic epidemiology!

### ⚠️ Investigate
```
⚠ ABM outputs fall within Stan credible intervals (65%)
✓ Strong correlation (0.82)
✓ Total case counts within 20% (15% error)
```
**Meaning**: Good overall, but some outliers. Check for stochastic effects.

### ❌ Issues Found
```
✗ ABM outputs fall within Stan credible intervals (45%)
✗ Weak correlation (0.55)
✗ Total case counts differ by 45%
```
**Meaning**: Fundamental mismatch. Check transmission parameters or model logic.

## Next Steps

1. **Review results**: Look at plots and reports
2. **If validation passes**: Document and move to next county
3. **If validation fails**: Investigate using residual plots and parameter comparisons
4. **Iterate**: Adjust ABM parameters and re-run

## Troubleshooting

### "CmdStan not found"
```bash
python -c "import cmdstanpy; cmdstanpy.install_cmdstan()"
```

### "Simulator not responding"
```bash
cd ../..
docker compose up -d
curl http://localhost:1880/simulation/
```

### "MCMC convergence warnings"
Use full mode (not --quick) or increase iterations:
```bash
python scripts/fit_stan_model.py ... --iter-sampling 2000 --iter-warmup 2000
```

## More Information

- **Full documentation**: `STAN_VALIDATION.md`
- **Presentation script**: `PRESENTATION_SCRIPT.md`
- **County validation**: `HAGERSTOWN_VALIDATION.md`
