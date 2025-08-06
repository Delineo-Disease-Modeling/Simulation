# Disease Modeling Platform (DMP)

## Overview
This project simulates the progression of individuals through various stages of a disease, based on transition probabilities, time intervals, and demographic information. The system models how people move through health states such as being infected, hospitalized, and recovered, accommodating a wide range of disease progression scenarios using customizable state machines.

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
    --age 25 \
    --vaccination_status Vaccinated \
    --sex F \
    --variant Omicron
```

### Arguments

Required:
- `--age`: Age of the individual
- `--vaccination_status`: Vaccination status (e.g., "Vaccinated", "Unvaccinated")
- `--sex`: Sex of the individual ("M" or "F")
- `--variant`: Virus variant (e.g., "Delta", "Omicron")

### Example Output
```
Demographics:
- Age: 70
- Sex: M
- Vaccination Status: Vaccinated
- Variant: Omicron

Disease Progression Timeline:
   0.0 hours: Infected
  40.3 hours: Infectious_Symptomatic
  92.9 hours: Hospitalized
  212.9 hours: Recovered
```

### 2. REST API v2.0
Start the API server:
```bash
uvicorn api.dmp_api_v2:app --reload
```

Initialize the DMP:
```bash
curl -X POST http://localhost:8000/initialize \
     -H "Content-Type: application/json" \
     -d '{"use_state_machines": true}'
```

Run a simulation:
```bash
curl -X POST http://localhost:8000/simulate \
     -H "Content-Type: application/json" \
     -d '{
           "disease_name": "Measles",
           "demographics": {
             "Age": "3",
             "Vaccination Status": "Unvaccinated",
             "Sex": "M"
           },
           "model_category": "vaccination"
         }'
```

### 3. Web Interface (Streamlit)
```bash
streamlit run app/graph_visualization.py
```

Features:
- **State Machine Creator**: Interactive visual graph editor for creating disease progression models
  * Visual node-based interface using Cytoscape.js
  * Drag-and-drop state positioning
  * Interactive edge creation with parameter editing
  * JSON editor for bulk edge modifications
  * Disease templates (COVID-19, Measles) with predefined states and transitions
  * Demographics integration (Age, Sex, Vaccination Status, Custom)
  * Real-time validation of transition probabilities
  * Support for 3 decimal precision in probability inputs

- **State Machine Manager**: Comprehensive management of saved state machines
  * Load, edit, and delete saved state machines
  * Disease and category filtering (Default Models, Variant-Specific Models, Vaccination Models)
  * Demographic filtering and organization
  * Interactive graph visualization of loaded machines
  * Edge editing with individual parameter controls
  * JSON editor for bulk edge modifications
  * Matrix representation with validation
  * Single simulation with timeline visualization
  * Multi-run analysis with statistical analysis:
    - Final state distribution analysis
    - Duration statistics (mean, median, std dev, percentiles)
    - State visit rates (% of simulations visiting each state)
    - Time statistics for each state
    - Visualizations (pie charts, histograms, bar charts)
    - Sample timeline display

- **Disease Configurations**: Template-based disease model creation
  * Predefined disease templates (COVID-19, Measles)
  * Disease-specific age ranges and demographics
  * Variant-specific model configurations
  * Vaccination status models for Measles
  * Template application with automatic state and edge generation

- **State Machine Comparison**: Side-by-side analysis of different models
  * Load two different state machines for comparison
  * Run simulations on both machines with same parameters
  * Compare final state distributions
  * Compare duration statistics
  * Compare state visit rates
  * Visual comparison with side-by-side charts
  * Statistical analysis of differences

- **Database Integration**: SQLite database for persistent storage
  * Automatic saving of state machines with metadata
  * Demographics stored as JSON for flexible categorization
  * Disease, variant, and model category organization
  * Version tracking with creation and update timestamps

- **Advanced Features**:
  * Real-time validation with detailed error messages
  * Support for multiple distribution types (triangular, uniform, log-normal, gamma)
  * Configurable time parameters (mean, std dev, min/max cutoffs)
  * Export/import functionality for state machines
  * Responsive design with collapsible sections
  * Progress tracking for multi-run simulations

## Project Structure
```
api/
- dmp_api_v2.py: FastAPI v2.0 endpoints
- test_api_v2.py: API testing suite

app/
- graph_visualization.py: Main Streamlit application entry point
- state_machine/
  - state_machine_creator.py: Interactive state machine creation
  - state_machine_manager.py: State machine management and analysis
  - state_machine_comparison.py: Side-by-side comparison functionality
  - disease_configurations.py: Disease templates and configurations
  - state_machine_db.py: Database operations
  - utils/
    - edge_editor.py: Edge parameter editing components
    - graph_utils.py: Graph utility functions
    - graph_visualizer.py: Cytoscape.js visualization components

cli/
- user_input.py: Command line interface

core/
- simulation_functions.py: Core simulation logic

data/
- custom_states.txt: Default state definitions
- default_states.txt: Alternative state definitions
- legacy/: Legacy CSV files (no longer used)

docs/
- API_DOCUMENTATION.md: Complete API documentation

examples/
- (Placeholder for example scripts and use cases)

results/
- (Simulation output files - auto-generated)

tests/
- (Placeholder for test files)
```

## State Machine System

### State Machine Structure
Each state machine contains:
- **States**: Different stages of the disease (Infected → Hospitalized → Recovered)
- **Edges**: Transitions between states with probabilities and timing
- **Demographics**: Population characteristics (Age, Sex, Vaccination Status, etc.)

### Model Categories
- **Default Models**: Basic disease progression models
- **Variant-Specific Models**: Models tailored to specific virus variants
- **Vaccination Models**: Models accounting for vaccination status

### Disease Templates
Pre-built templates for common diseases:
- **COVID-19**: Multiple variants (Delta, Omicron) with vaccination models
- **Measles**: Vaccination status models
- **Custom Diseases**: User-defined disease models

## Time Calculations

1. Input Times:
   - All times in state machines are specified in HOURS
   - Example: mean time of 48.0 represents 48 hours

2. Output Times:
   - All output times are in HOURS
   - Example: 48 hours = 2 days

3. Time Generation:
   - Times generated based on specified distribution
   - Bounded by min/max cutoffs
   - Out-of-bounds times are regenerated
   - Available distributions handle different scenarios:
     * Triangular: Most likely value with min/max bounds
     * Uniform: Equal probability across min/max range
     * Log-normal: Right-skewed distribution
     * Gamma: Flexible right-skewed distribution

Example Output:
```
Disease Progression Timeline:
   0.0 hours: Infected
  12.0 hours: Infectious_Symptomatic  # 0.5 days after infection
  96.0 hours: Recovered              # 4 days after symptoms
```

## Development

Run tests:
```bash
python3 -m api.test_api_v2
```

## Documentation

For detailed API documentation and advanced usage examples, see:
- **API Documentation**: `docs/API_DOCUMENTATION.md` - Complete API reference with examples
- **Quick Start Guide**: `docs/QUICK_START.md` - Getting started guide for new users

## License
[Your license information here]

## API Reference

### POST /initialize
Initialize the DMP with state machine database.

Request:
```json
{
    "use_state_machines": true
}
```

Response:
```json
{
    "status": "success",
    "message": "DMP initialized with state machine database",
    "mode": "state_machines"
}
```

### GET /diseases
Get all available diseases.

Response:
```json
{
    "status": "success",
    "diseases": ["COVID-19", "Measles"]
}
```

### GET /diseases/{disease_name}/variants
Get variants for a specific disease.

Response:
```json
{
    "status": "success",
    "variants": ["Delta", "Omicron"]
}
```

### GET /state-machines
List state machines with optional filtering.

Response:
```json
{
    "status": "success",
    "state_machines": [
        {
            "id": 1,
            "name": "COVID-19 Default Model",
            "disease_name": "COVID-19",
            "variant_name": null,
            "model_category": "default",
            "demographics": {
                "Age": "*",
                "Sex": "*",
                "Vaccination Status": "*"
            },
            "states": ["Infected", "Infectious_Symptomatic", "Recovered"],
            "created_at": "2024-01-15 10:30:00",
            "updated_at": "2024-01-15 10:30:00"
        }
    ]
}
```

### POST /simulate
Run a simulation with provided demographics.

Request:
```json
{
    "disease_name": "COVID-19",
    "demographics": {
        "Age": "25",
        "Vaccination Status": "Vaccinated",
        "Sex": "F"
    },
    "variant_name": "Omicron",
    "model_category": "variant",
    "initial_state": "Infected"
}
```

Response:
```json
{
    "status": "success",
    "mode": "state_machines",
    "timeline": [
        ["Infected", 0.0],
        ["Infectious_Symptomatic", 21.8],
        ["Recovered", 69.8]
    ],
    "state_machine": {
        "id": 1,
        "name": "COVID-19 | variant=Omicron | Age=25 | Sex=F | Vaccination Status=Vaccinated",
        "disease_name": "COVID-19",
        "variant_name": "Omicron",
        "model_category": "variant",
        "demographics": {
            "Age": "25",
            "Sex": "F",
            "Vaccination Status": "Vaccinated"
        }
    }
}
```

Note: Times in the timeline are in hours. 