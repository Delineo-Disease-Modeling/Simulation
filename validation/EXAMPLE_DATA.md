# Example Data for Hagerstown Validation

This document shows example data structures and expected outputs for the Hagerstown validation.

## Real COVID-19 Data (Washington County, MD - March 2021)

### Raw Data Format
**File**: `data/raw/nyt_county_washington_maryland.csv`

```csv
date,county,state,fips,cases,deaths,daily_cases,daily_deaths
2021-03-01,Washington,Maryland,24043,8234,156,23,0
2021-03-02,Washington,Maryland,24043,8257,156,23,0
2021-03-03,Washington,Maryland,24043,8289,156,32,0
2021-03-04,Washington,Maryland,24043,8315,156,26,0
2021-03-05,Washington,Maryland,24043,8341,157,26,1
2021-03-06,Washington,Maryland,24043,8363,157,22,0
2021-03-07,Washington,Maryland,24043,8384,157,21,0
...
```

**Columns**:
- `date`: Date in YYYY-MM-DD format
- `county`: County name
- `state`: State name
- `fips`: FIPS code (24043 for Washington County, MD)
- `cases`: Cumulative confirmed cases
- `deaths`: Cumulative deaths
- `daily_cases`: New cases that day (calculated)
- `daily_deaths`: New deaths that day (calculated)

### Processed Data Format (Weekly)
**File**: `data/processed/ground_truth_weekly_cases_washington_maryland.csv`

```csv
date,weekly_cases
2021-03-01,173
2021-03-08,168
2021-03-15,156
2021-03-22,142
2021-03-29,138
```

**Explanation**:
- Each row represents one week starting on Monday
- `weekly_cases`: Sum of daily cases for that week
- March 2021 shows declining trend from winter surge

## Simulator Output

### Raw Simulator Output
**File**: `artifacts/sim_raw_result.json`

```json
{
  "result": {
    "0": {
      "Delta": {
        "160": "INFECTED",
        "43": "INFECTED",
        "47": "INFECTED"
      }
    },
    "60": {
      "Delta": {
        "160": "INFECTIOUS",
        "43": "INFECTED",
        "47": "INFECTED",
        "1234": "INFECTED"
      }
    },
    "120": {
      "Delta": {
        "160": "INFECTIOUS",
        "43": "INFECTIOUS",
        "47": "INFECTED",
        "1234": "INFECTED",
        "5678": "INFECTED"
      }
    }
  },
  "movement": { ... }
}
```

**Structure**:
- Keys are timesteps (in minutes)
- Each timestep contains variants
- Each variant contains person_id -> infection_state mappings
- New infections appear as new person IDs

### Standardized Simulator Output
**File**: `artifacts/sim_timeseries.csv`

```csv
step_index,timestep,minutes_per_step,days_since_start,new_cases,cum_cases
0,0,60,0.0,10,10
1,60,60,0.042,1,11
2,120,60,0.083,2,13
3,180,60,0.125,1,14
4,240,60,0.167,3,17
...
```

**Columns**:
- `step_index`: Sequential step number (0, 1, 2, ...)
- `timestep`: Simulation time in minutes
- `minutes_per_step`: Time between steps (typically 60)
- `days_since_start`: Days elapsed (timestep / 1440)
- `new_cases`: New infections in this step
- `cum_cases`: Cumulative infections

## Aligned Comparison Data

### Aligned Series
**File**: `reports/aligned_weekly.csv`

```csv
gt_cases,sim_cases
173,42
168,39
156,38
142,35
138,33
```

**Explanation**:
- `gt_cases`: Ground truth weekly cases from real data
- `sim_cases`: Simulator weekly cases (aggregated from daily)
- Rows are aligned by week index (not calendar date)
- Simulator cases are ~25% of real cases (population scale)

## Validation Metrics

### Metrics Output
**File**: `reports/metrics_weekly.csv`

```csv
n_points,mae,rmse,smape,peak_timing_error_idx
5,132.4,135.2,58.3,0
```

**Metrics Explained**:
- `n_points`: Number of weeks compared (5 for March 2021)
- `mae`: Mean Absolute Error (average difference)
- `rmse`: Root Mean Square Error (penalizes large errors)
- `smape`: Symmetric Mean Absolute Percentage Error (0-100%)
- `peak_timing_error_idx`: Difference in peak timing (weeks)

**Interpretation**:
- MAE of 132.4 means average difference of ~132 cases per week
- sMAPE of 58.3% indicates moderate agreement
- Peak timing error of 0 means peaks aligned

## Expected Scale Differences

### Population Scaling
```
Washington County Population: ~155,000
Simulator Population:         ~40,000
Scale Factor:                 ~0.26 (26%)
```

### Expected Case Scaling (March 2021 Example)
```
Real Weekly Cases:      150-200 cases
Simulator Weekly Cases: 40-50 cases (26% of real)
Scale Factor:           ~0.26
```

### Normalized Comparison
To compare on same scale:
```
Real Cases per 100k:      ~100-130 per week
Simulator Cases per 100k: ~100-125 per week
```

## Sample Validation Run Output

### Console Output
```
============================================================
HAGERSTOWN VALIDATION PIPELINE
============================================================
Location: Washington County, Maryland
Period: 2021-03-01 to 2021-03-31
Duration: 44640 minutes (31 days)
Interventions: mask=0.3, vaccine=0.15, capacity=0.75
============================================================

============================================================
Step 1: Fetching county-level COVID data
============================================================
Command: python scripts/fetch_county_data.py --state Maryland --county Washington --start 2021-03-01 --end 2021-03-31

Saved: data/raw/nyt_county_washington_maryland.csv
Rows: 31
Date range: 2021-03-01 to 2021-03-31

Data summary:
  Total cumulative cases: 8,961
  Total cumulative deaths: 163
  Average daily cases: 25.8
  Peak daily cases: 42 on 2021-03-12

✓ Step 1: Fetching county-level COVID data completed successfully

============================================================
Step 2: Preparing and aggregating data
============================================================
Command: python scripts/prepare_county_data.py --county washington --state maryland --agg weekly

Loaded: data/raw/nyt_county_washington_maryland.csv (31 rows)

Saved: data/processed/ground_truth_weekly_cases_washington_maryland.csv
Rows: 5
Date range: 2021-03-01 to 2021-03-29

Statistics:
  Total cases: 777
  Mean weekly cases: 155.4
  Median weekly cases: 156.0
  Peak weekly cases: 173

✓ Step 2: Preparing and aggregating data completed successfully

============================================================
Step 3: Running simulation
============================================================
Command: python scripts/run_simulation.py --url http://localhost:1880/simulation/ --length 44640 --location hagerstown --step_minutes 60 --interventions {"mask": 0.3, "vaccine": 0.15, "capacity": 0.75, "lockdown": 0, "selfiso": 0.2, "randseed": true}

Saved raw simulator output: artifacts/sim_raw_result.json
Saved standardized series: artifacts/sim_timeseries.csv (745 rows)

✓ Step 3: Running simulation completed successfully

============================================================
Step 4: Comparing results and generating report
============================================================
Command: python scripts/compare.py --geo washington_maryland --horizon 1,2,3,4 --agg weekly

Saved aligned series: reports/aligned_weekly.csv
Saved metrics: reports/metrics_weekly.csv
Saved plot: reports/comparison_weekly.png

✓ Step 4: Comparing results and generating report completed successfully

============================================================
✓ VALIDATION PIPELINE COMPLETED SUCCESSFULLY
============================================================

Results saved in:
  - Artifacts: /Users/navyamehrotra/Documents/Projects/Delineo/Simulation/validation/artifacts
  - Reports: /Users/navyamehrotra/Documents/Projects/Delineo/Simulation/validation/reports

To view the report, open:
  /Users/navyamehrotra/Documents/Projects/Delineo/Simulation/validation/reports/validation_report.html
```

## Interpreting Results

### Good Validation Results
```
MAE:   < 50 (for scaled comparison)
RMSE:  < 60
sMAPE: < 30%
Peak Timing Error: 0-1 weeks
```

### Moderate Validation Results
```
MAE:   50-150
RMSE:  60-180
sMAPE: 30-60%
Peak Timing Error: 1-2 weeks
```

### Poor Validation Results
```
MAE:   > 150
RMSE:  > 180
sMAPE: > 60%
Peak Timing Error: > 2 weeks
```

## Visual Comparison Example

The comparison plot (`reports/comparison_weekly.png`) will show:
- X-axis: Week index (0, 1, 2, 3, 4)
- Y-axis: Weekly cases
- Blue line: Ground truth (real data)
- Orange line: Simulator output

**Expected Pattern**:
- Both lines should show similar trends (rising/falling)
- Simulator line will be lower (due to population scale)
- Peaks should align temporally
- Overall shape should be similar

## Data Quality Checks

### Real Data Checks
✓ No missing dates in range
✓ No negative daily cases (after corrections)
✓ Cumulative cases always increasing
✓ Daily cases within reasonable range (0-100)

### Simulator Data Checks
✓ Timesteps are sequential
✓ Cumulative cases always increasing
✓ New cases are non-negative
✓ Total simulation time matches requested duration

### Alignment Checks
✓ Both series have same number of weeks
✓ No NaN or infinite values
✓ Cases are non-negative
✓ Scale difference is reasonable (~4:1 ratio)

## Example Commands

### Fetch Different Time Periods
```bash
# Full year 2021
python scripts/fetch_county_data.py --state Maryland --county Washington --start 2021-01-01 --end 2021-12-31

# Summer 2021 (Delta surge)
python scripts/fetch_county_data.py --state Maryland --county Washington --start 2021-07-01 --end 2021-08-31

# Single week
python scripts/fetch_county_data.py --state Maryland --county Washington --start 2021-03-01 --end 2021-03-07
```

### Different Aggregations
```bash
# Daily comparison (more granular)
python scripts/prepare_county_data.py --county washington --state maryland --agg daily
python scripts/compare.py --geo washington_maryland --agg daily

# Monthly comparison (less granular)
python scripts/prepare_county_data.py --county washington --state maryland --agg monthly
python scripts/compare.py --geo washington_maryland --agg monthly
```

### Different Interventions
```bash
# High intervention
python scripts/run_hagerstown_validation.py --month 2021-03 --mask 0.8 --vaccine 0.5 --capacity 0.5

# Low intervention
python scripts/run_hagerstown_validation.py --month 2021-03 --mask 0.1 --vaccine 0.05 --capacity 1.0

# No intervention
python scripts/run_hagerstown_validation.py --month 2021-03 --mask 0.0 --vaccine 0.0 --capacity 1.0
```
