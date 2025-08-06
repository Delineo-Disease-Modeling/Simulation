# Disease Modeling Platform API v2.0 - Basic Explanation

## What is this API?

The Disease Modeling Platform (DMP) API is a web service that allows external applications to run disease simulations. Think of it as a "simulation engine" that other programs can use to model how diseases spread and progress through different populations.

## How it Works (Simple Version)

### 1. **Database Storage**
- The API connects to a SQLite database that stores "state machines"
- Each state machine represents a disease model (like COVID-19, Measles, etc.)
- State machines contain:
  - **States**: Different stages of the disease (Infected → Hospitalized → Recovered)
  - **Edges**: Transitions between states with probabilities and timing
  - **Demographics**: Population characteristics (Age, Sex, etc.)

### 2. **API Endpoints**
The API provides several "doors" (endpoints) to access the system:

#### **GET /** - Information
- Returns basic info about the API
- Like checking if the service is running

#### **GET /diseases** - List Diseases
- Returns all available diseases in the database
- Example: `["COVID-19", "Measles", "Influenza"]`

#### **GET /diseases/{disease}/variants** - Disease Variants
- Returns variants for a specific disease
- Example: COVID-19 might have "Delta", "Omicron" variants

#### **GET /state-machines** - List Models
- Returns all disease models in the database
- Can filter by disease name or model category

#### **GET /state-machines/{id}** - Get Specific Model
- Returns detailed information about one specific model
- Shows states, edges, demographics, etc.

#### **POST /simulate** - Run Simulation
- The main endpoint for running simulations
- Takes demographics and disease parameters
- Returns a timeline of disease progression

### 3. **Simulation Process**

When you request a simulation:

1. **Input**: You provide demographics (Age: "19-64", Sex: "M") and disease info
2. **Matching**: API finds the best matching state machine in the database
3. **Conversion**: Converts the state machine to mathematical matrices
4. **Simulation**: Runs the simulation using probability and timing data
5. **Output**: Returns a timeline showing disease progression

### 4. **Example Request**

```json
{
  "disease_name": "COVID-19",
  "demographics": {
    "Age": "19-64",
    "Sex": "M"
  },
  "model_category": "default",
  "initial_state": "Infected"
}
```

### 5. **Example Response**

```json
{
  "status": "success",
  "timeline": [
    ["Infected", 0],
    ["Infectious_Symptomatic", 5.2],
    ["Hospitalized", 12.8],
    ["Recovered", 19.5]
  ],
  "state_machine": {
    "id": 1,
    "name": "COVID-19 Default Model",
    "disease_name": "COVID-19",
    "model_category": "default",
    "demographics": {"Age": "19-64", "Sex": "M"}
  }
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

### **Timeline**
- The simulation result showing disease progression over time
- Each entry: [State Name, Time in Days]

## How to Use

### 1. **Start the Server**
```bash
cd Simulation/dmp/api
uvicorn dmp_api_v2:app --reload --host 0.0.0.0 --port 8000
```

### 2. **Test the API**
```bash
python test_api_v2.py
```

### 3. **Make Requests**
```python
import requests

# Get all diseases
response = requests.get("http://localhost:8000/diseases")
diseases = response.json()["diseases"]

# Run simulation
simulation_request = {
    "disease_name": "COVID-19",
    "demographics": {"Age": "19-64", "Sex": "M"},
    "model_category": "default"
}

response = requests.post("http://localhost:8000/simulate", json=simulation_request)
result = response.json()
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