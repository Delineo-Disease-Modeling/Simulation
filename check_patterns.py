#!/usr/bin/env python3
"""Check patterns data around hour 186."""
import json
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Load patterns
with open('simulator/barnsdall/patterns.json', 'r') as f:
    patterns = json.load(f)

timestamps = sorted([int(k) for k in patterns.keys() if k.isdigit()])

# Hour 186 = minute 11160
target_minute = 186 * 60
print(f'Looking for data around minute {target_minute} (hour 186)')
print()

# Find nearest timestamps
nearby = [t for t in timestamps if abs(t - target_minute) <= 120]
print(f'Timestamps within 2 hours of {target_minute}: {nearby}')

# Check where target falls
for i in range(len(timestamps)-1):
    if timestamps[i] <= target_minute <= timestamps[i+1]:
        print(f'Target falls between {timestamps[i]} and {timestamps[i+1]}')
        break

# The patterns range
print(f'Patterns min: {min(timestamps)} (hour {min(timestamps)/60:.1f})')
print(f'Patterns max: {max(timestamps)} (hour {max(timestamps)/60:.1f})')

# Check specific hours
for hour in [186, 187, 188, 189, 190, 191, 192, 193]:
    minute = hour * 60
    exists = str(minute) in patterns
    print(f'Hour {hour} ({minute} min): in patterns? {exists}')

# Check population at hour 186 vs 193
print()
print("=== POPULATION CHECK ===")
for minute in [11160, 11580]:  # hour 186 and 193
    if str(minute) in patterns:
        data = patterns[str(minute)]
        home_pop = sum(len(v) for v in data.get('homes', {}).values())
        place_pop = sum(len(v) for v in data.get('places', {}).values())
        print(f"Minute {minute} (hour {minute/60:.1f}): homes={home_pop}, places={place_pop}")
    else:
        print(f"Minute {minute}: NO DATA")
