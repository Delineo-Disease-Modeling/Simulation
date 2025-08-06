# Disease Modeling Platform API v2.0

## Overview

The DMP API v2.0 provides a unified interface for disease progression simulation, supporting both legacy CSV-based matrix systems and the new hierarchical state machine database system.

## Features

### 🔄 **Dual Mode Support**
- **Legacy Mode**: Backward compatibility with CSV-based matrix files
- **State Machine Mode**: New hierarchical database system with disease/variant/category organization

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

#### Legacy Mode Initialization
```http
POST /initialize
```
```json
{
  "matrices_path": "path/to/combined_matrices.csv",
  "mapping_path": "path/to/demographic_mapping.csv",
  "states_path": "path/to/states.txt",
  "use_state_machines": false
}
```

#### State Machine Mode Initialization
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

#### Get Variants for Disease
```http
GET /diseases/{disease_name}/variants
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

#### Legacy Mode Simulation
```http
POST /simulate
```
```json
{
  "demographics": {
    "Age": "25",
    "Sex": "F",
    "Vaccination Status": "Vaccinated",
    "Variant": "Omicron"
  }
}
```

#### State Machine Mode Simulation
```http
POST /simulate
```
```json
{
  "demographics": {
    "Age": "25",
    "Sex": "F",
    "Vaccination Status": "Vaccinated"
  },
  "disease_name": "COVID-19",
  "variant_name": "Omicron",
  "model_category": "variant",
  "initial_state": "Infected"
}
```

## Usage Examples

### 1. Using Legacy Mode (Backward Compatibility)

```bash
# Initialize with CSV files
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{
    "matrices_path": "data/combined_matrices.csv",
    "mapping_path": "data/demographic_mapping.csv",
    "use_state_machines": false
  }'

# Run simulation
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "demographics": {
      "Age": "25",
      "Sex": "F",
      "Vaccination Status": "Vaccinated",
      "Variant": "Omicron"
    }
  }'
```

### 2. Using State Machine Mode (New System)

```bash
# Initialize with state machine database
curl -X POST http://localhost:8000/initialize \
  -H "Content-Type: application/json" \
  -d '{
    "use_state_machines": true
  }'

# Discover available diseases
curl http://localhost:8000/diseases

# Get variants for COVID-19
curl http://localhost:8000/diseases/COVID-19/variants

# List COVID-19 state machines
curl "http://localhost:8000/state-machines?disease_name=COVID-19"

# Run simulation with specific disease and demographics
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "demographics": {
      "Age": "25",
      "Sex": "F",
      "Vaccination Status": "Vaccinated"
    },
    "disease_name": "COVID-19",
    "variant_name": "Omicron",
    "model_category": "variant",
    "initial_state": "Infected"
  }'
```

## Response Formats

### Legacy Mode Simulation Response
```json
{
  "status": "success",
  "mode": "legacy",
  "timeline": [
    ["Infected", 0.0],
    ["Infectious_Symptomatic", 21.8],
    ["Recovered", 69.8]
  ],
  "matrix_set": "Matrix_Set_14"
}
```

### State Machine Mode Simulation Response
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

### State Machine List Response
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

## State Machine Matching Logic

### Hierarchical Matching
1. **Disease Name**: Must match exactly
2. **Variant Name**: Optional, must match if specified
3. **Model Category**: Optional, must match if specified
4. **Demographics**: Supports wildcard matching (`*` matches any value)

### Example Matching Scenarios

#### Scenario 1: Specific COVID-19 Omicron Variant
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

#### Scenario 2: Default COVID-19 Model
```json
{
  "disease_name": "COVID-19",
  "demographics": {
    "Age": "25",
    "Sex": "F"
  }
}
```
Matches: COVID-19 state machine with no variant specified and demographics containing Age=25, Sex=F (or wildcards)

## Error Handling

### Common Error Responses

#### 404 - No Matching State Machine
```json
{
  "detail": "No matching state machine found for disease 'COVID-19' with the provided demographics"
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

## Migration Guide

### From Legacy to State Machine Mode

1. **Initialize in State Machine Mode**:
   ```bash
   curl -X POST http://localhost:8000/initialize \
     -H "Content-Type: application/json" \
     -d '{"use_state_machines": true}'
   ```

2. **Update Simulation Requests**:
   - Add `disease_name` field (required)
   - Add `variant_name` field (optional)
   - Add `model_category` field (optional)
   - Add `initial_state` field (optional)

3. **Handle New Response Format**:
   - Check for `mode` field in response
   - Access `state_machine` object for metadata
   - Timeline format remains the same

## External Simulator Integration

### For External Disease Modeling Simulators

The API is designed to work seamlessly with external simulators:

1. **Initialize once** at startup
2. **Discover available models** using `/diseases` and `/state-machines`
3. **Run simulations** with individual demographics
4. **Handle responses** consistently regardless of mode

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
        "Age": "25",
        "Sex": "F",
        "Vaccination Status": "Vaccinated"
    },
    "disease_name": "COVID-19",
    "variant_name": "Omicron"
})

timeline = simulation.json()["timeline"]
```

## Performance Considerations

- **State Machine Mode**: Faster matching due to database indexing
- **Legacy Mode**: Slower due to CSV file parsing
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