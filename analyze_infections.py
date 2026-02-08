#!/usr/bin/env python3
"""Analyze infection logs from simulation."""

import csv
from collections import defaultdict
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Count infections by timestep and variant
infections_by_variant = defaultdict(lambda: defaultdict(int))
unique_infected = set()

with open('simulation_logs/infection_logs.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ts = int(row['timestep'])
        variant = row['variant']
        person_id = row['infected_person_id']
        infections_by_variant[variant][ts] += 1
        unique_infected.add(person_id)

print('=' * 60)
print('HOURLY INFECTION COUNTS BY VARIANT')
print('=' * 60)
print(f"{'Hour':>5} | {'Delta':>8} | {'Omicron':>8} | {'Total':>8}")
print('-' * 60)

all_ts = sorted(set(sum([list(v.keys()) for v in infections_by_variant.values()], [])))
cumulative_delta = 0
cumulative_omicron = 0

for ts in all_ts:
    hour = ts // 60
    delta = infections_by_variant['Delta'].get(ts, 0)
    omicron = infections_by_variant['Omicron'].get(ts, 0)
    cumulative_delta += delta
    cumulative_omicron += omicron
    print(f'{hour:>5} | {delta:>8} | {omicron:>8} | {delta + omicron:>8}')

print('-' * 60)
print(f'TOTAL | {cumulative_delta:>8} | {cumulative_omicron:>8} | {cumulative_delta + cumulative_omicron:>8}')
print()
print(f'Unique people infected: {len(unique_infected)}')
print(f'Total infection events: {cumulative_delta + cumulative_omicron}')
print(f'Multi-variant infections: {cumulative_delta + cumulative_omicron - len(unique_infected)}')
