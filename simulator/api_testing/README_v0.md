# DMP-Simulator Integration Documentation

## Overview

This is version 0 of the integration, allowing the simulator to calculate infection probabilities for individuals and interact with the DMP to simulate disease trajectories.

## Components

### 1. Simulator (`simulation.py`)
- **Purpose**: Simulates infection probabilities and interacts with the DMP.
- **Key Functions**:
  - Reads demographic data from `demographics.csv`.
  - Creates `Person` objects for each individual.
  - Calculates infection probability using `infection_model.py`.
  - Sends data to the DMP for individuals with a high probability of infection.

### 2. Person Class
- **Attributes**:
  - `age`: Age of the individual.
  - `vaccination_status`: Vaccination status of the individual.
  - `sex`: Sex of the individual.
  - `variant`: Disease variant affecting the individual.
  - `invisible`: Status indicating if the person is deceased.

- **Methods**:
  - `getDemographics()`: Returns a dictionary of the person's demographics.
  - `setInvisible()`: Sets the person's status to invisible if deceased.

## Integration Workflow

### Step 1: Data Loading
- The simulator reads demographic data from `demographics.csv` and creates `Person` objects.

### Step 2: Infection Probability Calculation
- For each person, the simulator calculates the probability of infection using parameters such as:
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

### Step 3: DMP Interaction
- If a person's infection probability exceeds 50%, the simulator:
  1. Initializes the DMP with necessary data paths.
  2. Sends the person's demographics to the DMP.
  3. Receives the disease trajectory and updates the person's status if they are deceased.

## API Endpoints

### DMP Initialization
- **Endpoint**: `POST http://localhost:8000/initialize`
- **Payload**: Paths to matrices, demographic mapping, and disease states.

### Simulation Request
- **Endpoint**: `POST http://localhost:8000/simulate`
- **Payload**: Person's demographics.

## Output
- The integration outputs the infection probability for each individual and the disease trajectory for those with a high probability of infection. It also updates the status of individuals who are deceased.

## Future Improvements
- Enhance error handling for API interactions.
- Expand to accommodate different disease models.
- 

This documentation provides a comprehensive overview of the integration process, detailing the components, workflow, and future enhancements. 