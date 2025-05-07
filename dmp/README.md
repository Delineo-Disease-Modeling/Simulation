# Disease Modeling Platform (DMP)

## Overview
This project simulates the progression of individuals through various stages of a disease, based on transition probabilities, time intervals, and demographic information. The system models how people move through health states such as being infected, hospitalized, and recovered, accommodating a wide range of disease progression scenarios using customizable transition matrices and time intervals.

The simulation helps answer questions like:
- How long does it take for a vaccinated person to recover compared to an unvaccinated person?
- What is the probability that an elderly individual moves from infection to hospitalization versus recovery?
- How does the average time spent in the ICU differ across demographic groups?

## Installation

```bash
# Clone the repository
git clone [repository-url]
cd Simulation/dmp

# Install dependencies
pip install -r requirements.txt
```

## Interfaces

The platform offers three distinct interfaces:

### 1. Command Line Interface
Run simulations directly from the command line:

### Basic Usage
From the `Simulation/dmp` directory:

```bash
python3 -m cli.user_input \
    --matrices data/combined_matrices.csv \
    --mapping data/demographic_mapping.csv \
    --age 25 \
    --vaccination_status Vaccinated \
    --sex F \
    --variant Omicron
```

### Optional States File
```bash
python3 -m cli.user_input \
    --matrices data/combined_matrices.csv \
    --mapping data/demographic_mapping.csv \
    --states data/custom_states.txt \
    --age 25 \
    --vaccination_status Vaccinated \
    --sex F \
    --variant Omicron
```

### Arguments

Required:
- `--matrices`: Path to CSV file containing transition matrices
- `--mapping`: Path to CSV file containing demographic mappings
- `--age`: Age of the individual
- `--vaccination_status`: Vaccination status (e.g., "Vaccinated", "Unvaccinated")
- `--sex`: Sex of the individual ("M" or "F")
- `--variant`: Virus variant (e.g., "Delta", "Omicron")

Optional:
- `--states`: Path to custom states file (if not provided, uses default_states.txt)

### Example Output
```
Loading input files...
Using states: ['Infected', 'Hospitalized', 'ICU', 'Recovered', 'Deceased']

Demographics:
- Age: 70
- Sex: M
- Vaccination Status: Vaccinated
- Variant: Omicron

Using matrix set: Matrix_Set_23

Disease Progression Timeline:
   0.0 hours: Infected
  40.3 hours: Infectious_Syptomatic
  92.9 hours: Hospitalized
  212.9 hours: Recovered
```

### 2. REST API
Start the API server:
```bash
uvicorn api.dmp_api:app --reload
```

Initialize the DMP:
```bash
curl -X POST http://localhost:8000/initialize \
     -H "Content-Type: application/json" \
     -d '{
           "matrices_path": "data/combined_matrices.csv",
           "mapping_path": "data/demographic_mapping.csv",
           "states_path": "data/custom_states.txt"
         }'
```

Run a simulation:
```bash
curl -X POST http://localhost:8000/simulate \
     -H "Content-Type: application/json" \
     -d '{
           "demographics": {
             "Age": "25",
             "Vaccination Status": "Vaccinated",
             "Sex": "F",
             "Variant": "Omicron"
           }
         }'
```

### 3. Web Interface (Streamlit)
```bash
streamlit run app/app.py
```
Features:
- Interactive UI for matrix creation and editing
- Real-time visualization of disease progression
- Demographic parameter customization
- Default values provided for quick start

## Configuration Files

### States File
- Default: `data/default_states.txt`
- One state per line
- Example states: Infected, Hospitalized, ICU, Recovered, Deceased

### Matrix Requirements
The combined matrices CSV file must follow a specific structure. For each matrix set:

1. Matrix Order (6 matrices per set):
   - Transition Matrix: Probabilities of moving between states
   - Distribution Type: Type of statistical distribution for time intervals
   - Mean Matrix: Average time spent in each state
   - Standard Deviation Matrix: Variation in time intervals
   - Min Cutoff Matrix: Minimum allowed time in each state
   - Max Cutoff Matrix: Maximum allowed time in each state

2. Distribution Types:
   - 0: Fixed time (uses mean value only)
   - 1: Normal distribution
   - 2: Uniform distribution
   - 3: Log-normal distribution
   - 4: Gamma distribution

3. Matrix Restrictions:
   - Transition Matrix: Values must sum to 1 for each row (or 0 for terminal states)
   - All matrices must be square (n x n where n is number of states)
   - Mean values must be within min/max cutoff range
   - Non-zero transition probabilities must have valid distribution types
   - All values must be non-negative

### Demographic Mapping File
CSV file mapping demographics to matrix sets:
- Must include "Matrix_Set" column
- Other columns define demographic categories
- Supports wildcards (*) for flexible matching
- Age ranges support both "N-M" and "N+" formats

## Time Calculations

1. Input Times:
   - All times in matrices are specified in DAYS
   - Example: mean time of 2.0 represents 2 days

2. Output Times:
   - All output times are converted to HOURS
   - Conversion: hours = days * 24
   - Example: 2 days = 48 hours

3. Time Generation:
   - Times generated based on specified distribution
   - Bounded by min/max cutoffs
   - Out-of-bounds times are regenerated
   - Available distributions handle different scenarios:
     * Fixed: Always uses mean value
     * Normal: Bell curve around mean
     * Uniform: Random between (mean ± std_dev)
     * Log-normal: Skewed distribution
     * Gamma: Shape determined by mean and std dev

Example Output:
```
Disease Progression Timeline:
   0.0 hours: Infected
  12.0 hours: Infectious_Symptomatic  # 0.5 days after infection
  96.0 hours: Recovered              # 4 days after symptoms
```

## Project Structure
```
api/
- dmp_api.py: FastAPI endpoints
- test_api.py: API testing suite

app/
- app.py: Streamlit web interface
- state_management.py: States handling
- demographic_management.py: Demographics handling
- simulation_management.py: Simulation execution

cli/
- user_input.py: Command line interface

core/
- simulation_functions.py: Core simulation logic

data/
- Example matrices and demographic mappings
- Default configuration files
```

## Development

Run tests:
```bash
python3 -m api.test_api
```

## License
[Your license information here]

## API Reference

### POST /initialize
Initialize the DMP with configuration files.

Request:
```json
{
    "matrices_path": "path/to/matrices.csv",
    "mapping_path": "path/to/mapping.csv",
    "states_path": "path/to/states.txt"  // Optional
}
```

Response:
```json
{
    "status": "success",
    "message": "DMP initialized successfully",
    "states": ["Infected", "Hospitalized", "ICU", "Recovered", "Deceased"],
    "demographic_categories": ["Age", "Sex", "Vaccination Status", "Variant"],
    "available_demographics": {
        "Age": ["0-18", "19-64", "65+"],
        "Sex": ["M", "F"],
        "Vaccination Status": ["Vaccinated", "Unvaccinated"],
        "Variant": ["Delta", "Omicron"]
    }
}
```

### POST /simulate
Run a simulation with provided demographics.

Request:
```json
{
    "demographics": {
                    "Age": "15",
                    "Vaccination Status": "Vaccinated",
                    "Sex": "F",
                    "Variant": "Omicron"
                }
}
```

Response:
```json
{
    "status": "success",
    "timeline": [
        ["Infected", 0.0],
        ["Infectious_Symptomatic", 21.8],
        ["Recovered", 69.8]
    ],
    "matrix_set": "Matrix_Set_14"
}
```

Note: Times in the timeline are in hours. 