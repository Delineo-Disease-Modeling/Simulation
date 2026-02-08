#!/usr/bin/env python3
"""Check key types in result vs movement."""
import os
import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator import simulate
import json

# Suppress simulation output
import io
import contextlib

print("Running quick simulation...")

sim_result = simulate.run_simulator(
    location='barnsdall', max_length=120,
    interventions={'mask': 0.0, 'vaccine': 0.0},
    save_file=False, enable_logging=False, initial_infected_count=5
)

result = sim_result.get('result', {})
movement = sim_result.get('movement', {})

print("\n=== KEY TYPE INSPECTION (BEFORE JSON) ===")
for ts in list(result.keys())[:2]:
    print(f"Timestamp {ts} (type: {type(ts).__name__})")
    for variant, people in result[ts].items():
        for pid in list(people.keys())[:3]:
            print(f"  Result person ID: '{pid}' (type: {type(pid).__name__})")
        break
    break

for ts in list(movement.keys())[:2]:
    print(f"Movement timestamp {ts} (type: {type(ts).__name__})")
    for home_id, person_ids in list(movement[ts].get('homes', {}).items())[:2]:
        for pid in person_ids[:3]:
            print(f"  Movement person ID: '{pid}' (type: {type(pid).__name__})")
        break
    break

# Simulate JSON serialization (what browser receives)
print("\n=== AFTER JSON ROUND-TRIP ===")
json_result = json.loads(json.dumps(result))
json_movement = json.loads(json.dumps(movement))

for ts in list(json_result.keys())[:1]:
    for variant, people in json_result[ts].items():
        for pid in list(people.keys())[:3]:
            print(f"  JSON Result person ID: '{pid}' (type: {type(pid).__name__})")
        break

for ts in list(json_movement.keys())[:1]:
    for home_id, person_ids in list(json_movement[ts].get('homes', {}).items())[:1]:
        for pid in person_ids[:3]:
            print(f"  JSON Movement person ID: '{pid}' (type: {type(pid).__name__})")

# Key matching test
print("\n=== KEY MATCHING TEST ===")
ts = list(json_result.keys())[0]
result_data = json_result[ts]
movement_data = json_movement.get(ts, {})

infected_persons = set()
for variant, people in result_data.items():
    for person_id, state in people.items():
        if (state & 1) == 1:
            infected_persons.add(person_id)  # As-is from result

print(f"Infected persons (from result): {list(infected_persons)[:5]}")

# Check movement person IDs
all_movement_pids = []
for pids in movement_data.get('homes', {}).values():
    all_movement_pids.extend(pids)
for pids in movement_data.get('places', {}).values():
    all_movement_pids.extend(pids)

print(f"Sample movement person IDs: {all_movement_pids[:10]}")

# Test matching
matches = [pid for pid in all_movement_pids if pid in infected_persons]
str_matches = [pid for pid in all_movement_pids if str(pid) in infected_persons]

print(f"Direct matches: {len(matches)}")
print(f"String-converted matches: {len(str_matches)}")

# Check types
if all_movement_pids:
    print(f"Movement ID type: {type(all_movement_pids[0]).__name__}")
if infected_persons:
    print(f"Infected ID type: {type(list(infected_persons)[0]).__name__}")
