# Hagerstown, MD Validation Guide

This guide explains how to validate the Delineo simulator using real COVID-19 data from Hagerstown, MD (Washington County) for 2021.

## Overview

The validation process compares simulator outputs against real-world COVID-19 case data from Washington County, Maryland. This provides a concrete test of the simulator's ability to reproduce observed epidemic dynamics in a specific geographic location.

## Data Sources

### Real-World Data
- **Source**: New York Times COVID-19 Dataset
- **URL**: https://github.com/nytimes/covid-19-data
- **Level**: County-level (Washington County, MD)
- **FIPS Code**: 24043
- **Metrics**: Daily confirmed cases and deaths
- **Coverage**: January 2020 - Present

### Simulator Data
- **Location**: Hagerstown, MD
- **Data Files**: 
  - `simulator/hagerstown/papdata.json` - Population and places data
  - `simulator/hagerstown/patterns.json` - Movement patterns
- **Population**: ~40,000 simulated individuals
- **County Population**: ~155,000 (2021 estimate)

## Quick Start

### Prerequisites

1. **Start the simulator services**:
   ```bash
   cd /Users/navyamehrotra/Documents/Projects/Delineo/Simulation
   make up
   # or
   docker compose up -d
   ```

2. **Install validation dependencies**:
   ```bash
   cd validation
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

### Run Complete Validation

The easiest way to run the full validation pipeline is using the orchestration script:

```bash
# Validate March 2021 (recommended starting point)
python scripts/run_hagerstown_validation.py --month 2021-03

# Validate a different month
python scripts/run_hagerstown_validation.py --month 2021-06

# Validate a custom date range
python scripts/run_hagerstown_validation.py --start 2021-03-01 --end 2021-03-31
```

This single command will:
1. Fetch real COVID-19 data for Washington County, MD
2. Prepare and aggregate the data
3. Run the simulator with Hagerstown configuration
4. Compare results and generate validation report

### View Results

After completion, view the validation report:
```bash
open reports/validation_report.html
```

Or check the metrics:
```bash
cat reports/metrics_weekly.csv
```

## Step-by-Step Manual Validation

If you prefer to run each step manually:

### Step 1: Fetch Real Data

Fetch COVID-19 data for Washington County, MD:

```bash
# Fetch March 2021 data
python scripts/fetch_county_data.py \
  --state Maryland \
  --county Washington \
  --start 2021-03-01 \
  --end 2021-03-31

# Output: data/raw/nyt_county_washington_maryland.csv
```

### Step 2: Prepare Data

Aggregate daily cases into weekly totals:

```bash
python scripts/prepare_county_data.py \
  --county washington \
  --state maryland \
  --agg weekly

# Output: data/processed/ground_truth_weekly_cases_washington_maryland.csv
```

### Step 3: Run Simulation

Run the simulator for the same time period:

```bash
# March 2021 = 31 days = 44,640 minutes
python scripts/run_simulation.py \
  --url http://localhost:1880/simulation/ \
  --length 44640 \
  --location hagerstown \
  --step_minutes 60 \
  --interventions '{"mask": 0.3, "vaccine": 0.15, "capacity": 0.75, "lockdown": 0, "selfiso": 0.2, "randseed": true}'

# Output: 
#   artifacts/sim_raw_result.json
#   artifacts/sim_timeseries.csv
```

### Step 4: Compare and Analyze

Compare simulator output with ground truth:

```bash
python scripts/compare.py \
  --geo washington_maryland \
  --horizon 1,2,3,4 \
  --agg weekly

# Output:
#   reports/aligned_weekly.csv
#   reports/metrics_weekly.csv
#   reports/comparison_weekly.png
```

## Configuration

### Time Periods

Different time periods in 2021 represent different epidemic phases:

- **January-February 2021**: Winter surge, high cases
- **March-April 2021**: Declining cases, vaccination ramp-up
- **May-June 2021**: Low cases, pre-Delta
- **July-September 2021**: Delta variant surge
- **October-December 2021**: Delta decline, Omicron emergence

**Recommended**: Start with March 2021 for moderate, stable case counts.

### Intervention Parameters

The simulation supports these intervention parameters:

```json
{
  "mask": 0.3,        // Mask compliance (0-1)
  "vaccine": 0.15,    // Vaccination coverage (0-1)
  "capacity": 0.75,   // Capacity restrictions (0-1)
  "lockdown": 0,      // Lockdown level (0=none, 1=partial, 2=full)
  "selfiso": 0.2,     // Self-isolation rate (0-1)
  "randseed": true    // Use random seed for reproducibility
}
```

**March 2021 Realistic Values**:
- Mask: 0.3 (30% compliance, mandates still in effect)
- Vaccine: 0.15 (15% coverage, early rollout phase)
- Capacity: 0.75 (75% capacity, some restrictions)
- Lockdown: 0 (no lockdown)
- Self-isolation: 0.2 (20% of symptomatic isolate)

### Custom Interventions

Test different scenarios:

```bash
# High intervention scenario
python scripts/run_hagerstown_validation.py \
  --month 2021-03 \
  --mask 0.8 \
  --vaccine 0.5 \
  --capacity 0.5

# Low intervention scenario
python scripts/run_hagerstown_validation.py \
  --month 2021-03 \
  --mask 0.1 \
  --vaccine 0.05 \
  --capacity 1.0
```

## Understanding Results

### Metrics

The validation computes these metrics:

- **MAE** (Mean Absolute Error): Average absolute difference between predicted and actual cases
- **RMSE** (Root Mean Square Error): Square root of average squared differences
- **sMAPE** (Symmetric Mean Absolute Percentage Error): Percentage error metric (0-100%)
- **Peak Timing Error**: Difference in timing of peak cases (in time steps)

### Interpretation

**Good validation results**:
- sMAPE < 30%: Good agreement
- Peak timing error < 2 weeks: Captures epidemic dynamics
- Visual alignment: Similar trends and magnitudes

**Expected challenges**:
- Simulator uses synthetic population (~40k) vs. county population (~155k)
- Scale differences: Simulator cases should be ~25% of real cases
- Stochastic variation: Run multiple simulations for confidence intervals

## Data Files

### Input Data
```
validation/
├── data/
│   ├── raw/
│   │   └── nyt_county_washington_maryland.csv      # Raw COVID data
│   └── processed/
│       └── ground_truth_weekly_cases_washington_maryland.csv  # Aggregated data
```

### Output Data
```
validation/
├── artifacts/
│   ├── sim_raw_result.json          # Full simulation output
│   └── sim_timeseries.csv           # Standardized time series
└── reports/
    ├── aligned_weekly.csv           # Aligned ground truth vs. simulation
    ├── metrics_weekly.csv           # Validation metrics
    ├── comparison_weekly.png        # Visualization
    └── validation_report.html       # Full HTML report
```

## Configuration Files

Pre-configured validation setup:

```
validation/
└── configs/
    └── hagerstown_2021_config.json  # March 2021 configuration
```

This file contains:
- Location metadata (population, FIPS code)
- Time period definition
- Intervention parameters
- Data source information

## Troubleshooting

### Simulator Not Running

If you get connection errors:

```bash
# Check if simulator is running
curl http://localhost:1880/

# Restart services
cd /Users/navyamehrotra/Documents/Projects/Delineo/Simulation
docker compose down
docker compose up -d

# Wait for services to be ready
docker compose logs -f
```

### Data Not Found

If ground truth data is missing:

```bash
# Re-fetch the data
python scripts/fetch_county_data.py --state Maryland --county Washington --start 2021-03-01 --end 2021-03-31

# Re-prepare the data
python scripts/prepare_county_data.py --county washington --state maryland --agg weekly
```

### Poor Validation Results

If metrics are poor:

1. **Check scale**: Simulator population is ~25% of county population
2. **Adjust interventions**: Try different parameter values
3. **Try different time period**: Some periods are easier to model
4. **Run multiple times**: Stochastic variation affects results
5. **Check data quality**: Verify ground truth data looks reasonable

## Advanced Usage

### Multiple Runs for Confidence Intervals

```bash
# Run 10 simulations with different random seeds
for i in {1..10}; do
  python scripts/run_simulation.py \
    --length 44640 \
    --location hagerstown \
    --interventions '{"mask": 0.3, "vaccine": 0.15, "capacity": 0.75, "randseed": true}'
  mv artifacts/sim_timeseries.csv artifacts/sim_timeseries_run${i}.csv
done
```

### Custom Aggregation

```bash
# Daily comparison (more granular)
python scripts/prepare_county_data.py --county washington --state maryland --agg daily
python scripts/compare.py --geo washington_maryland --agg daily

# Monthly comparison (less granular)
python scripts/prepare_county_data.py --county washington --state maryland --agg monthly
python scripts/compare.py --geo washington_maryland --agg monthly
```

### Different Counties

The scripts support any US county:

```bash
# Baltimore County, MD
python scripts/run_hagerstown_validation.py \
  --month 2021-03 \
  --county Baltimore \
  --state Maryland \
  --location hagerstown  # Note: still uses Hagerstown simulator data

# Montgomery County, MD
python scripts/run_hagerstown_validation.py \
  --month 2021-03 \
  --county Montgomery \
  --state Maryland \
  --location hagerstown
```

## References

- **NYT COVID-19 Data**: https://github.com/nytimes/covid-19-data
- **Washington County, MD**: https://www.washingtoncountymd.gov/
- **CDC COVID Data**: https://covid.cdc.gov/covid-data-tracker/

## Next Steps

After validating Hagerstown:

1. **Try different time periods**: Test various epidemic phases
2. **Experiment with interventions**: See how parameters affect outcomes
3. **Add more locations**: Extend validation to other counties
4. **Improve calibration**: Adjust simulator parameters based on results
5. **Add more metrics**: Implement additional validation measures
