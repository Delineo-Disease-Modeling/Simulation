# DMP-Simulator Integration Documentation

## Overview

This documentation covers the integration between the Disease Modeling Platform (DMP) and the Simulator, allowing for calculation of infection probabilities and disease progression trajectories.

## Version 0: Initial Integration

### Components

#### 1. Simulator (`simulation.py`)
- **Purpose**: Simulates infection probabilities and interacts with the DMP.
- **Key Functions**:
  - Reads demographic data from `demographics.csv`.
  - Creates `Person` objects for each individual.
  - Calculates infection probability using `infection_model.py`.
  - Sends data to the DMP for individuals with a high probability of infection.

#### 2. Person Class
- **Attributes**:
  - `age`: Age of the individual.
  - `vaccination_status`: Vaccination status of the individual.
  - `sex`: Sex of the individual.
  - `variant`: Disease variant affecting the individual.
  - `invisible`: Status indicating if the person is deceased.

- **Methods**:
  - `getDemographics()`: Returns a dictionary of the person's demographics.
  - `setInvisible()`: Sets the person's status to invisible if deceased.

### Integration Workflow

#### Step 1: Data Loading
- The simulator reads demographic data from `demographics.csv` and creates `Person` objects.

#### Step 2: Infection Probability Calculation
- For each person, the simulator calculates the probability of infection using the infection model V0 and takes in parameters such as:
  - Virion threshold (`R₀`)
  - Disease variant
  - Particle degradation rate
  - Exposure duration
  - Emission rate
  - Mask filtration rate
  - Room volume
  - Time spent in room and close proximity
  - Air changes per hour
  - Distance from infected person
At the moment, the parameters are the same for every individual, but these can be changed by the user to better suit the simulation. 

#### Step 3: DMP Interaction
- If a person's infection probability exceeds 50% (assumed threshold), the simulator:
  1. Initializes the DMP with necessary data paths.
  2. Sends the person's demographics to the DMP.
  3. Receives the disease trajectory and updates the person's status if they are deceased.

### API Endpoints

#### DMP Initialization
- **Endpoint**: `POST http://localhost:8000/initialize`
- **Payload**: Paths to matrices, demographic mapping, and disease states.

#### Simulation Request
- **Endpoint**: `POST http://localhost:8000/simulate`
- **Payload**: Person's demographics.

### Output
- The integration outputs the infection probability for each individual and the disease trajectory for those with a high probability of infection. It also updates the status of individuals who are deceased.

## Version 0.1: Enhanced Time-Based Simulation

### Key Improvements

#### 1. Time-Based Disease State
- **Random Time Point**: Each person's simulation now runs until a random time point which can be adjusted in the code
- **Current vs. Final State**: Uses the person's disease state at the current simulation time instead of the final disease state

#### 2. Enhanced Invisibility Rules
- **Additional States**: Persons are now marked invisible for three conditions:
  - Deceased
  - Hospitalized 
  - ICU
- **Impact**: This creates a more realistic simulation by removing severely ill individuals from the active population

#### 3. Comprehensive Statistics
- **Disease State Counters**: Tracks how many people are in each disease state at simulation end
- **Invisibility Tracking**: Counts how many people are invisible, broken down by reason
- **Visibility Summary**: Shows what percentage of infected people remain visible vs. invisible
- **Infection Rate**: Calculates the percentage of the total population that becomes infected

#### 4. Bug Fixes
- **CSV Parsing**: Fixed matrix file reading by explicitly setting delimiter to comma
- **Header Handling**: Ensured proper handling of CSV data with `header=None` parameter
- **Spacing Handling**: Added `skipinitialspace=True` to properly handle whitespace after commas

This documentation provides a comprehensive overview of the integration process, detailing the components, workflow, and future enhancements. 