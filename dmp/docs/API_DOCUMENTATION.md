# Disease Modeling Platform API Documentation

Complete API reference for the Disease Modeling Platform (DMP) v2.0.

## Base URL

```
http://localhost:8000
```

## Endpoints

### 1. Run Simulation

**POST** `/simulate`

Run a disease simulation using the specified parameters.

**Request Body:**
```json
{
  "disease_name": "Measles",
  "demographics": {
    "Age": "3",
    "Sex": "M",
    "Vaccination Status": "Unvaccinated"
  },
  "model_path": "vaccination.Unvaccinated.general",
  "initial_state": "Exposed"
}
```

**Parameters:**
- `disease_name` (required): Name of the disease (e.g., "COVID-19", "Measles")
- `demographics` (required): Dictionary of demographic values
- `model_path` (optional): Model path in dot notation (e.g., "variant.Delta.general", "vaccination.Unvaccinated.general")
- `initial_state` (optional): Initial state for simulation (defaults to first state)

**Response:**
```json
{
  "success": true,
  "simulation_id": "sim_12345",
  "model_path": "vaccination.Unvaccinated.general",
  "timeline": [
    ["Exposed", 0.0],
    ["Infectious_Presymptomatic", 216.7],
    ["Infectious_Symptomatic", 272.9],
    ["Hospitalized", 400.7],
    ["Recovered", 533.8]
  ],
  "total_duration": 533.8,
  "final_state": "Recovered",
  "states_visited": ["Exposed", "Infectious_Presymptomatic", "Infectious_Symptomatic", "Hospitalized", "Recovered"]
}
```

## Model Path Structure

The `model_path` parameter uses a hierarchical structure: `category.subcategory.type`

### Examples:
- `variant.Delta.general` - Delta variant, general type
- `variant.Omicron.general` - Omicron variant, general type  
- `vaccination.Unvaccinated.general` - Unvaccinated, general type
- `vaccination.Fully Vaccinated.general` - Fully vaccinated, general type
- `default.general` - Default model, general type

**Note:** The `.general` suffix is a placeholder for any future subcategory expansion.

## Disease-Specific API Usage

### COVID-19

**Available Model Paths:**
- `variant.Delta.general` - Delta variant
- `variant.Omicron.general` - Omicron variant
- `default.general` - Default COVID-19 model

**Demographics:**
- Age: 0-4, 5-18, 19-64, 65+
- Sex: M, F
- Vaccination Status: Unvaccinated, Vaccinated

**Example Request:**
```bash
curl -X POST http://localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "disease_name": "COVID-19",
    "demographics": {
      "Age": "65+",
      "Sex": "M",
      "Vaccination Status": "Unvaccinated"
    },
    "model_path": "variant.Delta.general"
  }'
```

### Measles

**Available Model Paths:**
- `vaccination.Unvaccinated.general` - Unvaccinated
- `vaccination.Partially Vaccinated.general` - Partially vaccinated
- `vaccination.Fully Vaccinated.general` - Fully vaccinated
- `default.general` - Default measles model

**Demographics:**
- Age: 0-4, 5-18, 19-64, 65+
- Sex: M, F

**Example Request:**
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

### Placeholder Diseases

Influenza, Ebola, and Zika are placeholder only with no models implemented. Requests for these diseases will return errors.

## Fallback Strategy

The API implements a simple, predictable fallback strategy for model matching:

1. **Exact match**: Try the exact `model_path` provided
2. **Parent match**: Try the parent path (e.g., `variant.Delta` if `variant.Delta.general` not found)
3. **Default match**: Try `default.general`
4. **Error**: Return error if no matching state machine found

### Demographic Matching Rules

The API uses simple, clear rules for demographic compatibility:

- **If a state machine has a demographic defined** → **must match exactly** (or be within age range)
- **If a state machine doesn't have a demographic defined** → **OK (wildcard)** - can be used
- **More specific matches are prioritized** - machines with more defined demographics win over general ones
- **First compatible machine found wins** - no complex scoring, just simple fallback order

### Example Fallback Scenarios

**Scenario 1: Exact Match Found**
- Request: `model_path: "variant.Delta.general"`
- Result: Uses exact match

**Scenario 2: Parent Match with Demographics**
- Request: `model_path: "variant.Delta.general"` with demographics `{"Age": "4", "Vaccination Status": "Unvaccinated"}`
- Fallback: Tries `variant.Delta.Unvaccinated` (if demographics are compatible)
- Result: Uses first compatible machine found

**Scenario 3: Default Match**
- Request: `model_path: "variant.Unknown.general"` (doesn't exist)
- Fallback: Tries `default.general`
- Result: Uses first compatible machine found

### Demographic Compatibility Examples

**Machine A**: `{"Age": "5-14", "Vaccination Status": "Unvaccinated"}`
- **Request**: `{"Age": "4", "Vaccination Status": "Unvaccinated"}`
- **Result**: ❌ **Incompatible** (Age 4 not in 5-14 range)

**Machine B**: `{"Vaccination Status": "Unvaccinated"}` (no Age defined)
- **Request**: `{"Age": "4", "Vaccination Status": "Unvaccinated"}`
- **Result**: ✅ **Compatible** (Age not defined = wildcard, Vaccination matches)

**Machine C**: `{"Age": "0-4", "Vaccination Status": "Vaccinated"}`
- **Request**: `{"Age": "4", "Vaccination Status": "Unvaccinated"}`
- **Result**: ❌ **Incompatible** (Vaccination status mismatch)

### Specificity Priority Example

**Available Machines for `vaccination.Unvaccinated.general`:**
1. `{"Age": "0-4", "Vaccination Status": "Unvaccinated"}` ← **Most specific (2 demographics)**
2. `{"Age": "5-18", "Vaccination Status": "Unvaccinated"}` ← **Specific (2 demographics)**
3. `{"Vaccination Status": "Unvaccinated"}` ← **General (1 demographic)**

**Request**: `{"Age": "3", "Vaccination Status": "Unvaccinated"}`

**Result**: ✅ **Machine 1 wins** because it has the most specific demographics that match the request

## Error Handling

### Invalid Request
```json
{
  "success": false,
  "error": "Invalid request format",
  "details": "Missing required field: disease_name"
}
```

### No Matching State Machine
```json
{
  "success": false,
  "error": "No matching state machine found",
  "details": "No state machine found for disease: Measles, demographics: {'Age': '3', 'Sex': 'M'}, model_path: vaccination.Unvaccinated.general"
}
```

### Simulation Error
```json
{
  "success": false,
  "error": "Simulation failed",
  "details": "Invalid transition probabilities in state machine"
}
```

## Common Error Scenarios

### 1. Using `variant_name` for Non-COVID-19 Diseases
```json
{
  "disease_name": "Measles",
  "variant_name": "Delta",  // ❌ Wrong - Measles has no variants
  "demographics": {...}
}
```

### 2. Using Non-Existent Model Paths
```json
{
  "disease_name": "COVID-19",
  "model_path": "severity.Delta.critical",  // ❌ Wrong - severity not defined
  "demographics": {...}
}
```

### 3. Requesting Placeholder Diseases
```json
{
  "disease_name": "Influenza",  // ❌ Wrong - placeholder only
  "demographics": {...}
}
```

## Integration Examples

### Python Integration
```python
import requests

# Run simulation
response = requests.post("http://localhost:8000/simulate", json={
    "disease_name": "Measles",
    "demographics": {
        "Age": "3",
        "Sex": "M",
        "Vaccination Status": "Unvaccinated"
    },
    "model_path": "vaccination.Unvaccinated.general"
})

if response.status_code == 200:
    result = response.json()
    timeline = result["timeline"]
    print(f"Simulation completed in {result['total_duration']} hours")
else:
    print(f"Error: {response.json()}")
```

### JavaScript Integration
```javascript
const response = await fetch('http://localhost:8000/simulate', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        disease_name: "COVID-19",
        demographics: {
            Age: "25",
            Sex: "F",
            "Vaccination Status": "Vaccinated"
        },
        model_path: "variant.Omicron.general"
    })
});

const result = await response.json();
console.log(`Final state: ${result.final_state}`);
```

### R Integration
```r
library(httr)
library(jsonlite)

response <- POST("http://localhost:8000/simulate",
    add_headers("Content-Type" = "application/json"),
    body = toJSON(list(
        disease_name = "Measles",
        demographics = list(
            Age = "3",
            Sex = "M",
            "Vaccination Status" = "Unvaccinated"
        ),
        model_path = "vaccination.Unvaccinated.general"
    ))
)

result <- fromJSON(rawToChar(response$content))
cat("Duration:", result$total_duration, "hours\n")
```

## Performance Considerations

- **Response Time**: Typically 100-500ms per simulation
- **Concurrent Requests**: No built-in rate limiting, but consider server resources
- **Database Size**: SQLite database grows with number of state machines
- **Memory Usage**: Minimal for individual simulations

## Best Practices

1. **Always check response status** before processing results
2. **Handle errors gracefully** with appropriate fallback logic
3. **Use appropriate model paths** for each disease
4. **Include relevant demographics** for better matching
5. **Cache frequently used state machines** if making many requests
6. **Test with known working examples** before implementing custom solutions

## Versioning

This documentation covers API v2.0. The API version is included in the response headers.

## Support

For issues or questions:
1. Check the error messages for specific details
2. Verify the model_path exists for your disease
3. Ensure demographics match available options
4. Test with the provided examples first 