# Test Playground

Minimal test environment for debugging the Delineo simulation engine.

## Quick Start

```bash
cd Simulation

# Run with existing minimal data (5 people, 2 homes, 1 store)
python -m simulator.test_playground.run_test

# Generate and run a specific scenario
python -m simulator.test_playground.run_test --scenario office

# Test with interventions
python -m simulator.test_playground.run_test --mask 0.5 --vaccine 0.3

# Longer simulation (default is 480 min = 8 hours)
python -m simulator.test_playground.run_test --length 1440  # 24 hours
```

## Available Scenarios

| Scenario | People | Homes | Places | Description |
|----------|--------|-------|--------|-------------|
| `minimal` | 5 | 2 | 1 | Simple grocery store visits |
| `office` | 6 | 3 | 2 | Workday with office + cafe |
| `superspreader` | 5 | 3 | 3 | One infected visits multiple locations |

## Patterns CSV Generator

Generate SafeGraph-style patterns CSV files for testing the Algorithms server:

```bash
cd Simulation/simulator/test_playground

# List available scenarios and place types
python patterns_csv_generator.py --list

# Generate a test CSV
python patterns_csv_generator.py --scenario neighborhood

# Output: TEST/2019-01-TEST.csv (SafeGraph format)
```

### Available Place Types

| Type | Category | Median Dwell |
|------|----------|--------------|
| `grocery` | Shopping | 35 min |
| `restaurant` | Food | 60 min |
| `cafe` | Food | 30 min |
| `office` | Business | 480 min |
| `gym` | Recreation | 75 min |
| `church` | Religious | 90 min |
| `school` | Education | 420 min |
| `pharmacy` | Health | 20 min |
| `bar` | Food | 120 min |
| `bank` | Finance | 25 min |

### Custom Patterns CSV

```python
from simulator.test_playground.patterns_csv_generator import (
    PatternsCsvBuilder, save_scenario
)

builder = PatternsCsvBuilder("my_test")
builder.set_cbg("240430001001")  # Real CBG
builder.add_place("Joe's Diner", "restaurant", raw_visitor_counts=100)
builder.add_place("Corner Store", "grocery")
builder.add_place("Local Gym", "gym")

scenario = builder.build()
save_scenario(scenario)  # Creates TEST/2019-01-TEST.csv
```

## Custom Scenarios

Use the `ScenarioBuilder` for programmatic scenario creation:

```python
from simulator.test_playground.generator import ScenarioBuilder, save_scenario

builder = ScenarioBuilder("my_test")

# Add locations
home1 = builder.add_home()
home2 = builder.add_home()
store = builder.add_place("Corner Store", capacity=10)

# Add people
alice = builder.add_person(home1, age=30, sex=1)
bob = builder.add_person(home1, age=32, sex=0)
charlie = builder.add_person(home2, age=25, sex=0)

# Define movements (timestep in minutes)
builder.add_movement(60, alice, "place", store)    # Alice goes to store at hour 1
builder.add_movement(60, charlie, "place", store)  # Charlie too
builder.add_movement(120, alice, "home", home1)    # Both return at hour 2
builder.add_movement(120, charlie, "home", home2)

# Set patient zero
builder.set_infected([alice])

# Generate files
scenario = builder.build()
save_scenario(scenario)
```

## Data Format

### papdata.json
```json
{
  "people": {"0": {"sex": 0, "age": 35, "home": "0"}},
  "homes": {"0": {"cbg": "000000000001", "members": 2}},
  "places": {"0": {"label": "Store", "cbg": "-1", "latitude": 39.0, "longitude": -76.5, "capacity": 20}}
}
```

### patterns.json
```json
{
  "60": {
    "homes": {"0": ["1"]},
    "places": {"0": ["0", "2"]}
  }
}
```
Keys are minutes from simulation start. Values are lists of person IDs moving to that location.

## Files

- `generator.py` - Scenario generation and builder classes
- `run_test.py` - Quick test runner
- `papdata.json` - Current population/places data
- `patterns.json` - Current movement patterns
- `scenario_meta.json` - Metadata about current scenario
