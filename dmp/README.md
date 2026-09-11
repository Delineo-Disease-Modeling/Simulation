# Disease Modeling Platform (DMP)

A comprehensive platform for creating, managing, and simulating disease progression models using state machines.

## Overview

The Disease Modeling Platform (DMP) provides a web interface and API for modeling disease progression through state machines. It supports multiple diseases, variants, and demographic-specific models with a hierarchical model structure.

## Features

- **Web Interface**: Interactive state machine creation and management
- **API Access**: RESTful API for external applications
- **Multi-Disease Support**: COVID-19, Measles, and placeholder diseases
- **Hierarchical Models**: Organized model structure with fallback strategies
- **Demographic Matching**: Population-specific disease models
- **Simulation Engine**: Monte Carlo simulation with configurable parameters

## Quick Start

Use the [shared local walkthrough](https://github.com/Delineo-Disease-Modeling/Fullstack/blob/main/docs/getting-started.md)
for the full application. Simulation normally loads DMP within its own process;
the API and editor below are optional services. All commands in this section run
from the **Simulation repository root**, not from `Simulation/dmp/`.

### 1. Installation

```bash
# From the Simulation root; skip venv creation/install if already completed.
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Start the web interface
.venv/bin/python -m streamlit run dmp/app/graph_visualization.py
```

### 2. Web Interface

The web interface provides four main tabs:

1. **State Machine Manager** - View, load, and manage saved state machines
2. **State Machine Creator** - Create new state machines with visual editor
3. **Disease Configurations** - View available disease models
4. **State Machine Comparison** - Compare multiple simulations

### 3. API Usage

```bash
# Start the API server
.venv/bin/python -m uvicorn dmp.api.dmp_api_v2:app --host 127.0.0.1 --port 8000
```

Inspect the API at `http://localhost:8000/docs`. Query `/diseases` and
`/state-machines` for the models actually available in the bundled SQLite database
at `dmp/app/state_machine/state_machines.db`. The editor modifies that database.

**Example API Request:**
```bash
curl -X POST http://localhost:8000/simulate \
     -H "Content-Type: application/json" \
     -d '{
    "disease_name": "Measles",
           "demographics": {
      "Age": "3",
      "Sex": "M",
      "Vaccination Status": "Unvaccinated"
    },
    "model_path": "vaccination.Unvaccinated.general"
         }'
```

## Model Structure

The DMP uses a hierarchical model structure: `category.subcategory.type`

### Model examples

| Disease | Model Path Example | Demographics | Status |
|---------|-------------------|--------------|--------|
| **COVID-19** | `variant.Delta.general` | Age, Sex, Vaccination Status | Bundled entries; inspect the API for supported demographics |
| **Measles** | `vaccination.Unvaccinated.general` | Age, Sex | Bundled entries; inspect the API for supported demographics |
| **Influenza** | None | None | ⚠️ Placeholder |
| **Ebola** | None | None | ⚠️ Placeholder |
| **Zika** | None | None | ⚠️ Placeholder |

The disease list above describes data availability, not model validation. Query
`/diseases` and `/state-machines` for the current database contents.

### Model Path Examples

- `variant.Delta.general` - COVID-19 Delta variant
- `variant.Omicron.general` - COVID-19 Omicron variant
- `vaccination.Unvaccinated.general` - Measles unvaccinated
- `vaccination.Fully Vaccinated.general` - Measles fully vaccinated
- `default.general` - Default model for any disease

**Note:** The `.general` suffix is a placeholder for any future subcategory expansion.

## API Documentation

### Endpoints

#### Run Simulation
**POST** `/simulate`

**Request:**
```json
{
  "disease_name": "Measles",
  "demographics": {
    "Age": "3",
    "Sex": "M",
    "Vaccination Status": "Unvaccinated"
  },
  "model_path": "vaccination.Unvaccinated.general",
  "initial_state": "Susceptible"
}
```

**Response:**
```json
{
  "success": true,
  "simulation_id": "sim_12345",
  "model_path": "vaccination.Unvaccinated.general",
  "timeline": [
    ["Susceptible", 0.0],
    ["Exposed", 2.5],
    ["Infectious", 12.3],
    ["Recovered", 168.7]
  ],
  "total_duration": 168.7,
  "final_state": "Recovered",
  "states_visited": ["Susceptible", "Exposed", "Infectious", "Recovered"]
}
```

### Fallback Strategy

The API implements hierarchical fallback for model matching:
1. **Exact match**: Try the exact `model_path` provided
2. **Parent match**: Try the parent path (e.g., `variant.Delta` if `variant.Delta.general` not found)
3. **Default match**: Try `default.general`
4. **Error**: Return error if no matching state machine found

### Error Handling

```json
{
  "success": false,
  "error": "No matching state machine found",
  "details": "No state machine found for disease: Measles, demographics: {'Age': '3', 'Sex': 'M'}, model_path: vaccination.Unvaccinated.general"
}
```

## Disease-Specific Information

### COVID-19
- **Variants**: Delta, Omicron
- **Demographics**: Age, Sex, Vaccination Status, Comorbidity
- **Model Paths**: `variant.Delta.general`, `variant.Omicron.general`, `default.general`

### Measles
- **Vaccination Models**: Unvaccinated, Partially Vaccinated, Fully Vaccinated
- **Demographics**: Age, Sex
- **Model Paths**: `vaccination.Unvaccinated.general`, `vaccination.Fully Vaccinated.general`, `default.general`

### Placeholder Diseases
Influenza, Ebola, and Zika are placeholder only with no models implemented.

## Local Integration

For direct database access and local integration, from the Simulation root:

```bash
# List available diseases
.venv/bin/python -m dmp.core.dmp_local --action list-diseases

# List variants for a disease
.venv/bin/python -m dmp.core.dmp_local --action list-variants --disease COVID-19

# List state machines
.venv/bin/python -m dmp.core.dmp_local --action list-machines --disease Measles

# Run simulation
.venv/bin/python -m dmp.core.dmp_local --action simulate \
    --disease Measles \
    --demographics '{"Age": "3", "Sex": "M", "Vaccination Status": "Unvaccinated"}'
```

**Benefits of Local Integration:**
- **Faster performance** - Direct database access, no API overhead
- **Local integration** - Easy to use in Python scripts and batch processing
- **Same functionality** - Uses the same state machine database as the web interface

## Project Structure

```
dmp/
├── app/                    # Web interface
│   ├── graph_visualization.py
│   └── state_machine/     # State machine components
├── api/                   # API server
│   └── dmp_api_v2.py
├── core/                  # Core DMP functionality and local client
│   ├── dmp_local.py       # Local DMP client for direct database access
│   ├── simulation_functions.py  # Core simulation functions
│   └── example_usage.py   # Example usage of the local client
├── docs/                  # Documentation
└── requirements.txt       # Dependencies
```

## Development

### Adding New Diseases

1. **Update `disease_configurations.py`**:
   ```python
   DISEASE_MODELS = {
       "New Disease": {
           "default": {
               "general": {
                   "description": "General model",
                   "demographics": ["Age", "Sex"]
               }
           }
       }
   }
   ```

2. **Add disease templates** with states, transitions, and parameters

3. **Test with web interface** and API

### Database Schema

The system uses SQLite with the following main tables:
- `state_machines`: Core state machine metadata
- `states`: Individual states for each machine
- `edges`: Transitions between states with timing parameters

## Troubleshooting

### Common Issues

1. **"No matching state machine found"**
   - Check that the disease name is correct
   - Verify demographics match available options
   - Ensure model_path exists for the disease

2. **"Invalid transition probabilities"**
   - Ensure outgoing probabilities sum to 1.0 for each state
   - Check for negative or invalid probability values

3. **API connection errors**
   - Verify the API server is running on port 8000
   - Check firewall settings

### Validation

The system validates:
- Transition probabilities sum to 1.0 for each state
- All states have valid transitions
- Demographic values match available options
- Model paths follow the hierarchical structure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request


---

For the current API schema and interactive requests, use
`http://localhost:8000/docs` while the API is running. The
[API notes](docs/API_DOCUMENTATION.md) provide additional model-matching examples.
