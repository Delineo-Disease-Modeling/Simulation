#!/usr/bin/env python3
"""
Test what the frontend receives and how it might fail.
"""
import os
import sys
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator import simulate
import json

print("Running 200-hour simulation...")
sim_result = simulate.run_simulator(
    location='barnsdall', max_length=200 * 60,
    interventions={'mask': 0.0, 'vaccine': 0.0},
    save_file=False, enable_logging=False, initial_infected_count=10
)

result = sim_result.get('result', {})
movement = sim_result.get('movement', {})

# Simulate what frontend does
print("\n=== SIMULATING FRONTEND PROCESSING ===")

# 1. JSON round-trip
result_json = json.loads(json.dumps(result))
movement_json = json.loads(json.dumps(movement))

# 2. Sample timestamps (like frontend does)
allTimestamps = sorted([int(k) for k in movement_json.keys()])
maxTimestamps = 100
sampleRate = max(1, len(allTimestamps) // maxTimestamps)
sampledTimestamps = [t for i, t in enumerate(allTimestamps) if i % sampleRate == 0 or i == len(allTimestamps) - 1]

print(f"All timestamps: {len(allTimestamps)}")
print(f"Sample rate: 1/{sampleRate}")
print(f"Sampled timestamps: {len(sampledTimestamps)}")
print(f"Sampled range: {sampledTimestamps[0]} to {sampledTimestamps[-1]}")

# 3. Transform (like frontend's transformSimData)
def transform_sim_data(result, movement, sampled_timestamps):
    transformed = {}
    for ts in sampled_timestamps:
        ts_str = str(ts)
        move_data = movement.get(ts_str)
        result_data = result.get(ts_str, {})
        
        if not move_data:
            continue
        
        infected_persons = set()
        for variant in result_data.values():
            for pid, state in variant.items():
                if (state & 1) == 1:
                    infected_persons.add(pid)
        
        homes = {}
        for home_id, person_ids in move_data.get('homes', {}).items():
            infected = sum(1 for pid in person_ids if pid in infected_persons)
            homes[home_id] = {'population': len(person_ids), 'infected': infected}
        
        places = {}
        for place_id, person_ids in move_data.get('places', {}).items():
            infected = sum(1 for pid in person_ids if pid in infected_persons)
            places[place_id] = {'population': len(person_ids), 'infected': infected}
        
        transformed[ts_str] = {'homes': homes, 'places': places}
    
    return transformed

sim_data = transform_sim_data(result_json, movement_json, sampledTimestamps)
print(f"Transformed sim_data has {len(sim_data)} timestamps")

# 4. Check what happens at hour 186 and 193
print("\n=== HOUR 186 AND 193 LOOKUP ===")

# Available timestamps in sim_data
available = sorted([int(k) for k in sim_data.keys()])
print(f"Available timesteps in sim_data: {available[:20]}...")

def find_nearest(target_minutes, available_ts):
    if not available_ts:
        return None
    closest = available_ts[0]
    for ts in available_ts:
        if abs(ts - target_minutes) < abs(closest - target_minutes):
            closest = ts
        if ts > target_minutes:
            break
    return closest

for hour in [186, 193]:
    target_minutes = hour * 60
    nearest_ts = find_nearest(target_minutes, available)
    data = sim_data.get(str(nearest_ts))
    
    print(f"\nHour {hour} (target: {target_minutes} min)")
    print(f"  Nearest available timestamp: {nearest_ts}")
    print(f"  Data found: {data is not None}")
    
    if data:
        total_infected = sum(h['infected'] for h in data['homes'].values()) + sum(p['infected'] for p in data['places'].values())
        print(f"  Total infected displayed: {total_infected}")
    else:
        print(f"  !!! No data - would show 0 infected !!!")

# 5. Check if there are any gaps in sampled data
print("\n=== CHECKING FOR GAPS ===")
gaps = []
for i in range(len(sampledTimestamps) - 1):
    gap = sampledTimestamps[i+1] - sampledTimestamps[i]
    if gap > 120:  # gap > 2 hours
        gaps.append((sampledTimestamps[i], sampledTimestamps[i+1], gap))

if gaps:
    print(f"Found {len(gaps)} gaps > 2 hours:")
    for g in gaps[:10]:
        print(f"  Gap from {g[0]} to {g[1]} ({g[2]/60:.1f} hours)")
else:
    print("No significant gaps in sampled data")
