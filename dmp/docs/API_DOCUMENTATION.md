# Disease Modeling Platform API v2.0

## Overview

The Disease Modeling Platform (DMP) API is a web service that allows external applications to run disease simulations. Think of it as a "simulation engine" that other programs can use to model how diseases spread and progress through different populations.

The API provides a unified interface for disease progression simulation using a hierarchical state machine database system.

## What is this API?

The Disease Modeling Platform (DMP) API is a web service that allows external applications to run disease simulations. Think of it as a "simulation engine" that other programs can use to model how diseases spread and progress through different populations.

## How it Works

### 1. **Database Storage**
- The API connects to a SQLite database that stores "state machines"
- Each state machine represents a disease model (like COVID-19, Measles, etc.)
- State machines contain:
  - **States**: Different stages of the disease (Infected → Hospitalized → Recovered)
  - **Edges**: Transitions between states with probabilities and timing
  - **Demographics**: Population characteristics (Age, Sex, etc.)

### 2. **Simulation Process**

When you request a simulation:

1. **Input**: You provide demographics (Age: "19-64", Sex: "M") and disease info
2. **Matching**: API finds the best matching state machine in the database
3. **Conversion**: Converts the state machine to mathematical matrices
4. **Simulation**: Runs the simulation using probability and timing data
5. **Output**: Returns a timeline showing disease progression

## Features

### 🏥 **Disease-Specific Models**
- Support for multiple diseases (COVID-19, Measles, etc.)
- Variant-specific models (Delta, Omicron, etc.)
- Model categories (Default, Variant-Specific, Vaccination)
- Demographic-specific configurations

### 🔍 **Advanced Discovery**
- List available diseases and variants
- Browse state machines with filtering
- Get detailed state machine information
- Automatic matching based on demographics

## API Endpoints

### Root Information
```http
GET /
```
Returns API information and current mode.

### Initialization
```http
POST /initialize
```
```json
{
  "use_state_machines": true
}
```

### Disease Discovery

#### Get All Diseases
```http
GET /diseases
```

Response:
```json
{
    "status": "success",
    "diseases": ["COVID-19", "Measles"]
}
```

#### Get Variants for Disease
```http
GET /diseases/{disease_name}/variants
```

Response:
```json
{
    "status": "success",
    "variants": ["Measles"]
}
```

### State Machine Management

#### List State Machines
```http
GET /state-machines?disease_name=COVID-19&model_category=default
```

#### Get Specific State Machine
```http
GET /state-machines/{machine_id}
```

### Simulation
```http
POST /simulate
```
```json
{
  "demographics": {
    "Age": "3",
    "Sex": "M",
    "Vaccination Status": "Unvaccinated"
  },
  "disease_name": "Measles",
  "model_category": "vaccination",
  "initial_state": "Exposed"
}
```

**Note**: `variant_name` is only used for COVID-19 (e.g., "Delta", "Omicron"). For other diseases like Measles, omit this field.

## Usage Examples

### 1. Basic Setup and Discovery

```bash
# Initialize with state machine database
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{
    "use_state_machines": true
  }'

# Discover available diseases
curl http://localhost:8000/diseases

# Get variants for Measles
curl http://localhost:8000/diseases/Measles/variants

# List Measles state machines
curl "http://localhost:8000/state-machines?disease_name=Measles"
```

### 2. Running Simulations

```bash
# Run simulation with specific disease and demographics
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "demographics": {
      "Age": "3",
      "Sex": "M",
      "Vaccination Status": "Unvaccinated"
    },
    "disease_name": "Measles",
    "model_category": "vaccination",
    "initial_state": "Exposed"
  }'
```

### 3. Python Integration

```python
import requests

# Initialize API
response = requests.post("http://localhost:8000/initialize", 
                        json={"use_state_machines": True})

# Get available diseases
diseases = requests.get("http://localhost:8000/diseases").json()

# Run simulation for individual
simulation = requests.post("http://localhost:8000/simulate", json={
    "demographics": {
        "Age": "3",
        "Sex": "M",
        "Vaccination Status": "Unvaccinated"
    },
    "disease_name": "Measles"
})

timeline = simulation.json()["timeline"]
```

## Response Formats

### Simulation Response
```json
{
  "status": "success",
  "mode": "state_machines",
  "timeline": [
    ["Exposed", 0.0],
    ["Infectious_Presymptomatic", 187.0],
    ["Infectious_Symptomatic", 294.5],
    ["Hospitalized", 354.4],
    ["Recovered", 453.8]
  ],
  "state_machine": {
    "id": 45,
    "name": "Measles | vaccination=Unvaccinated | Age=0-4",
    "disease_name": "Measles",
    "model_category": "vaccination",
    "demographics": {
      "Age": "3",
      "Sex": "M",
      "Vaccination Status": "Unvaccinated"
    }
  }
}
```

### State Machine List Response
```json
{
  "status": "success",
  "state_machines": [
    {
      "id": 45,
      "name": "Measles | vaccination=Unvaccinated | Age=0-4",
      "disease_name": "Measles",
      "model_category": "vaccination",
      "demographics": {
        "Age": "0-4",
        "Sex": "*",
        "Vaccination Status": "Unvaccinated"
      },
      "states": ["Exposed", "Infectious_Presymptomatic", "Infectious_Symptomatic", "Hospitalized", "Recovered"],
      "created_at": "2024-01-15 10:30:00",
      "updated_at": "2024-01-15 10:30:00"
    }
  ]
}
```

## Key Concepts

### **State Machine**
- A mathematical model representing disease progression
- Like a flowchart showing how people move through different disease stages

### **Demographics**
- Population characteristics that affect disease progression
- Examples: Age, Sex, Vaccination Status

### **Model Categories**
- Different types of models for the same disease
- Examples: "default", "variant-specific", "vaccination"

### **Variants**
- **COVID-19 only**: Use `variant_name` for different virus strains (Delta, Omicron)
- **Other diseases**: Do not use `variant_name` (e.g., Measles has no variants)

### **Timeline**
- The simulation result showing disease progression over time
- Each entry: [State Name, Time in Hours]

## State Machine Matching Logic

### Hierarchical Matching
1. **Disease Name**: Must match exactly
2. **Variant Name**: Optional, must match if specified
3. **Model Category**: Optional, must match if specified
4. **Demographics**: Supports wildcard matching (`*` matches any value)

### Example Matching Scenarios

#### Scenario 1: Specific Measles Vaccination Model
```json
{
  "disease_name": "Measles",
  "demographics": {
    "Age": "3",
    "Sex": "M"
  }
}
```
Matches: Measles state machine with vaccination model and demographics containing Age=3, Sex=M (or wildcards)

#### Scenario 2: COVID-19 with Variant (for comparison)
```json
{
  "disease_name": "COVID-19",
  "variant_name": "Omicron",
  "demographics": {
    "Age": "25",
    "Sex": "F"
  }
}
```
Matches: COVID-19 state machine with Omicron variant and demographics containing Age=25, Sex=F (or wildcards)

## Error Handling

### Common Error Responses

#### 404 - No Matching State Machine
```json
{
  "detail": "No matching state machine found for disease 'Measles' with the provided demographics"
}
```

#### 400 - Missing Required Fields
```json
{
  "detail": "disease_name is required when using state machines"
}
```

#### 500 - Internal Server Error
```json
{
  "detail": "Error during simulation: [specific error message]"
}
```

## Benefits

1. **Separation of Concerns**: Web interface for creation, API for external access
2. **Scalability**: Multiple applications can use the same simulation engine
3. **Flexibility**: Easy to add new diseases and models
4. **Integration**: Can be integrated into other systems (mobile apps, web apps, etc.)

## Architecture

```
External Application → API → Database → Simulation Engine → Results
```

The API acts as a bridge between external applications and the disease modeling system, providing a clean, standardized way to access simulation capabilities.

## Performance Considerations

- **State Machine Mode**: Fast matching due to database indexing
- **Caching**: Consider caching frequently used state machines
- **Batch Operations**: API supports individual simulations (batch processing can be added)

## Security Notes

- API is designed for internal use within disease modeling systems
- No authentication currently implemented
- Consider adding rate limiting for production use
- Validate all input demographics before processing

## Running the API

```bash
# Start the v2.0 API server
uvicorn api.dmp_api_v2:app --reload --port 8000
```

## API Documentation

Once the server is running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

## Testing

```bash
# Test the API
python test_api_v2.py
```

## For External Disease Modeling Simulators

The API is designed to work seamlessly with external simulators:

1. **Initialize once** at startup
2. **Discover available models** using `/diseases` and `/state-machines`
3. **Run simulations** with individual demographics
4. **Handle responses** consistently

### Example External Simulator Usage

```python
import requests

# Initialize API
response = requests.post("http://localhost:8000/initialize", 
                        json={"use_state_machines": True})

# Get available diseases
diseases = requests.get("http://localhost:8000/diseases").json()

# Run simulation for individual
simulation = requests.post("http://localhost:8000/simulate", json={
    "demographics": {
        "Age": "3",
        "Sex": "M",
        "Vaccination Status": "Unvaccinated"
    },
    "disease_name": "Measles"
})

timeline = simulation.json()["timeline"]
``` 