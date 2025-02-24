Overview:
This project simulates the progression of individuals through various stages of a disease, based on transition probabilities, time intervals, and demographic information. The system is designed to model how people move through health states such as being infected, hospitalized, and recovered, and it can accommodate a wide range of disease progression scenarios using customizable transition matrices and time intervals.

The simulation is particularly useful for understanding how different demographic groups (e.g., age, sex, vaccination status) may experience different disease timelines. For example, it can help answer questions like:
- How long does it take for a vaccinated person to recover compared to an unvaccinated person?
- What is the probability that an elderly individual moves from infection to hospitalization versus recovery?
- How does the average time spent in the ICU differ across demographic groups?

Each individual's progression through disease states (e.g., Infected, Hospitalized, ICU, Recovered, etc.) is determined by predefined transition probabilities and time intervals, which can be drawn from a variety of statistical distributions (e.g., Normal, Exponential, Gamma, Beta). These distributions allow for flexibility in modeling real-world scenarios, where disease progression may not follow a strict timeline but varies based on individual characteristics and external factors.

Interfaces:
The platform offers three distinct interfaces for running simulations:

1. Web Interface (Streamlit):
   - Interactive UI for matrix creation and editing
   - Real-time visualization of disease progression
   - Demographic parameter customization
   - Default values provided for quick start
   - Run: streamlit run app/app.py

2. Command Line Interface:
   - Batch processing of CSV inputs
   - Automated simulation runs
   - Results export to CSV
   - Run: python cli/user_input.py

3. API Endpoints:
   - /initialize: Set up simulation parameters
   - /simulate: Run simulations with specific demographics
   - Suitable for integration with other applications
   - Run: uvicorn api.dmp_api:app --reload

Input Customization:
The system is designed to be highly customizable while providing sensible defaults:

1. Disease States:
   - Default states: Infected, IA, IS, Hospitalized, ICU, Removed, Recovered
   - Custom states can be defined via states.txt file

2. Transition Matrices:
   - Probability matrices for state transitions
   - Time interval distributions
   - Min/max cutoff values
   - Distribution types (Normal, Exponential, etc.)

3. Demographics:
   - Core demographics: Age, Sex, Vaccination Status
   - Extensible with custom demographic factors
   - Matrix sets can be mapped to specific demographic combinations

Matrix Requirements:
The combined matrices CSV file must follow a specific structure and order. For each matrix set:

1. Matrix Order (6 matrices per set):
   a. Transition Matrix: Probabilities of moving between states
   b. Distribution Type: Type of statistical distribution for time intervals
   c. Mean Matrix: Average time spent in each state
   d. Standard Deviation Matrix: Variation in time intervals
   e. Min Cutoff Matrix: Minimum allowed time in each state
   f. Max Cutoff Matrix: Maximum allowed time in each state

2. Distribution Types:
   0: Fixed time (uses mean value only)
   1: Normal distribution
   2: Uniform distribution
   3: Log-normal distribution
   4: Gamma distribution

3. Matrix Restrictions:
   - Transition Matrix: Values must sum to 1 for each row (or 0 for terminal states)
   - All matrices must be square (n x n where n is number of states)
   - Mean values must be within min/max cutoff range
   - Non-zero transition probabilities must have valid distribution types (not 0)
   - All values must be non-negative

Example Matrix Set Format:
For a 3-state system (Infected, Infectious, Recovered):

# Transition Matrix
0.0, 1.0, 0.0  # Infected -> Infectious (100% probability)
0.0, 0.0, 1.0  # Infectious -> Recovered (100% probability)
0.0, 0.0, 0.0  # Recovered is terminal state (all zeros)

# Distribution Type Matrix
0, 1, 0        # Fixed time for Infected->Infected, Normal for Infected->Infectious
0, 0, 1        # Normal distribution for Infectious->Recovered
0, 0, 0        # No distributions needed for terminal state

# Mean Matrix (days)
0.0, 2.0, 0.0  # Average 2 days from Infected to Infectious
0.0, 0.0, 14.0 # Average 14 days from Infectious to Recovered
0.0, 0.0, 0.0  # No transitions from Recovered state

# Standard Deviation Matrix (days)
0.0, 0.5, 0.0  # 0.5 days std dev for Infected to Infectious
0.0, 0.0, 3.0  # 3 days std dev for Infectious to Recovered
0.0, 0.0, 0.0  # No transitions from Recovered state

# Min Cutoff Matrix (days)
0.0, 1.0, 0.0  # Minimum 1 day from Infected to Infectious
0.0, 0.0, 7.0  # Minimum 7 days from Infectious to Recovered
0.0, 0.0, 0.0  # No transitions from Recovered state

# Max Cutoff Matrix (days)
0.0, 4.0, 0.0  # Maximum 4 days from Infected to Infectious
0.0, 0.0, 21.0 # Maximum 21 days from Infectious to Recovered
0.0, 0.0, 0.0  # No transitions from Recovered state

Note: Multiple matrix sets can be combined in the same CSV file, stacked vertically in the same order. Each matrix set corresponds to a specific demographic combination defined in the mapping file.

Project Structure:
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

Getting Started:
1. Install dependencies: pip install -r requirements.txt
2. Choose interface:
   - Web: streamlit run app/app.py
   - CLI: python cli/user_input.py
   - API: uvicorn api.dmp_api:app --reload
3. Use example data or customize inputs
4. Run simulations and analyze results

Command Line Interface Usage:
The CLI provides a straightforward way to run individual simulations. Here's how to use it:

1. Basic Command Structure:
   python cli/user_input.py --matrices <path> --mapping <path> [--states <path>] --age <number> --sex <M/F> --vaccination_status <status> --variant <type>

2. Example Usage:
   python cli/user_input.py \
     --matrices data/combined_matrices_usecase.csv \
     --mapping data/demographic_mapping_usecase.csv \
     --states data/custom_states.txt \
     --age 25 \
     --sex F \
     --vaccination_status Vaccinated \
     --variant Omicron

3. Required Arguments:
   --matrices: Path to CSV file containing transition matrices
   --mapping: Path to CSV file containing demographic mappings
   --age: Age of the individual (integer)
   --sex: Sex of the individual (M or F)
   --vaccination_status: Vaccination status (Vaccinated or Unvaccinated)
   --variant: Virus variant (e.g., Delta, Omicron)

4. Optional Arguments:
   --states: Path to custom states file (if not provided, defaults will be used)
   --output: Path for output CSV file (default: results_TIMESTAMP.csv)

The simulation will output:
- The states being used
- The input demographics
- Which matrix set matched the demographics
- The disease progression timeline in minutes

Example Output:
Loading input files...
Using states: ['Infected', 'Infectious_Asymptomatic', 'Infectious_Symptomatic', 'Hospitalized', 'ICU', 'Recovered', 'Deceased']

Demographics: {
    'Age': 25,
    'Sex': 'F',
    'Vaccination Status': 'Vaccinated',
    'Variant': 'Omicron'
}

Using matrix set: Matrix_Set_3

Disease Progression Timeline:
    0.0 minutes: Infected
  720.0 minutes: Infectious_Symptomatic  # 12 hours after infection
 5760.0 minutes: Recovered              # 4 days after symptoms

Time Calculations:
1. Input Times:
   - All times in the matrices (mean, std dev, min/max cutoffs) are specified in DAYS
   - Example: mean time of 2.0 represents 2 days

2. Output Times:
   - All output times are converted to MINUTES for more precise tracking
   - Conversion: minutes = days * 24 * 60
   - Example: 2 days = 2 * 24 * 60 = 2,880 minutes

3. Time Generation:
   - For each transition, time is generated based on the specified distribution
   - Times are bounded by min/max cutoffs
   - If a generated time falls outside the min/max range, it is discarded and regenerated
   - This ensures all transition times respect the specified bounds
   - Available distributions:
     * Fixed (0): Always uses mean value
     * Normal (1): Bell curve around mean with given std dev
     * Uniform (2): Random between (mean - std_dev) and (mean + std_dev)
     * Log-normal (3): Skewed distribution, good for long-tailed processes
     * Gamma (4): Shape determined by mean and std dev, always positive

4. Timeline Building:
   - Starts at 0 minutes (initial infection)
   - Each new state's time is cumulative
   - Example progression:
     * Infected → Symptomatic: 0.5 days = 720 minutes
     * Symptomatic → Recovered: 3.5 days = 5040 additional minutes
     * Total time to recovery: 5760 minutes (4 days)

Note: Due to the probabilistic nature of the distributions, actual times will vary between runs, but will always stay within the specified min/max cutoffs.

Demographic Mapping File Format:
The demographic mapping file (CSV) defines which matrix set to use for each combination of demographics. The system is flexible and allows users to define their own demographic categories, with a few rules:

1. Required Column:
   - Matrix_Set: Identifies which matrix set to use (e.g., Matrix_Set_1)

2. Demographic Columns:
   - Age Range: Special column that handles ranges (e.g., "65+" or "19-64")
   - Any other demographic categories (e.g., Sex, Region, Risk Level, etc.)
   - Values can be exact matches or wildcards (*)
   - Empty values are treated as wildcards

3. Example Format:
```

4. Mapping Rules:
   - Age ranges must use the format "N+" or "N-M"
   - Other columns can contain any string values
   - Wildcards (*) match any value
   - First matching row is used
   - Each Matrix_Set must correspond to a set of matrices in the matrices file

Note: While the system is flexible with demographic categories, the Age Range column (if used) must follow the specified format for proper range matching.