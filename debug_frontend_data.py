#!/usr/bin/env python3
"""
Debug script to trace exactly what data the frontend receives.
Replicates the transformSimData logic to find where infections disappear.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator import simulate
import json

def transform_sim_data(result, movement, timestamps):
    """
    Replicate the frontend's transformSimData function in Python.
    This helps us debug what the frontend sees.
    """
    transformed = {}
    
    for timestamp in timestamps:
        ts_str = str(timestamp)
        move_data = movement.get(ts_str, {})
        result_data = result.get(ts_str, {})
        
        if not move_data:
            print(f"  [WARN] ts={timestamp}: No movement data")
            continue
        
        # Get all infected person IDs across all variants
        # InfectionState flags: SUSCEPTIBLE=0, INFECTED=1, INFECTIOUS=2, etc.
        infected_persons = set()
        for variant, persons in result_data.items():
            for person_id, state in persons.items():
                # Check if INFECTED bit is set (bitwise AND with 1)
                if (int(state) & 1) == 1:
                    infected_persons.add(str(person_id))
        
        # Transform homes
        homes = {}
        for home_id, person_ids in move_data.get('homes', {}).items():
            population = len(person_ids)
            infected = sum(1 for pid in person_ids if str(pid) in infected_persons)
            homes[home_id] = {'population': population, 'infected': infected}
        
        # Transform places
        places = {}
        for place_id, person_ids in move_data.get('places', {}).items():
            population = len(person_ids)
            infected = sum(1 for pid in person_ids if str(pid) in infected_persons)
            places[place_id] = {'population': population, 'infected': infected}
        
        total_infected = sum(h['infected'] for h in homes.values()) + sum(p['infected'] for p in places.values())
        transformed[ts_str] = {
            'homes': homes, 
            'places': places,
            '_debug': {
                'infected_persons_count': len(infected_persons),
                'total_infected_in_locations': total_infected,
                'variants_in_result': list(result_data.keys()),
                'result_persons_count': sum(len(v) for v in result_data.values()),
            }
        }
    
    return transformed


def main():
    # Run a simulation (same as frontend would trigger)
    print("=" * 60)
    print("Running simulation to debug frontend data...")
    print("=" * 60)
    
    # Simulate 24 hours (enough to cover your screenshots at 1 PM and 8 PM)
    length_hours = 24
    length_minutes = length_hours * 60
    
    interventions = {
        'mask': 0.0,
        'vaccine': 0.0,
        'capacity': 1.0,
        'lockdown': 0,
        'selfiso': 0.0,
        'randseed': True
    }
    
    sim_result = simulate.run_simulator(
        location='barnsdall',
        max_length=length_minutes,
        interventions=interventions,
        log_dir='simulation_logs_debug',
        enable_logging=False,
        save_file=False,
        initial_infected_count=33  # Match previous runs
    )
    
    result = sim_result.get('result', {})
    movement = sim_result.get('movement', {})
    
    print(f"\n{'=' * 60}")
    print(f"Simulation complete!")
    print(f"Result keys: {len(result)}")
    print(f"Movement keys: {len(movement)}")
    print(f"{'=' * 60}")
    
    # Get all timestamps and sort them
    all_timestamps = sorted([int(k) for k in movement.keys()])
    print(f"\nTimestamps range: {all_timestamps[0]} to {all_timestamps[-1]} minutes")
    print(f"That's {all_timestamps[-1] / 60:.1f} hours")
    
    # Transform data like frontend does
    transformed = transform_sim_data(result, movement, all_timestamps)
    
    # Now analyze infections over time
    print(f"\n{'=' * 60}")
    print("INFECTION ANALYSIS BY HOUR")
    print("=" * 60)
    print(f"{'Hour':<6} {'Minute':<8} {'Infected Persons':<18} {'In Locations':<15} {'Variants'}")
    print("-" * 70)
    
    infection_drops = []
    prev_infected = None
    
    for ts in all_timestamps:
        ts_str = str(ts)
        if ts_str not in transformed:
            continue
            
        data = transformed[ts_str]
        debug = data.get('_debug', {})
        infected_persons = debug.get('infected_persons_count', 0)
        in_locations = debug.get('total_infected_in_locations', 0)
        variants = debug.get('variants_in_result', [])
        
        hour = ts / 60
        
        # Check for sudden drops
        drop_marker = ""
        if prev_infected is not None and infected_persons < prev_infected * 0.5:
            drop_marker = " <-- SUDDEN DROP!"
            infection_drops.append({
                'hour': hour,
                'prev': prev_infected,
                'curr': infected_persons,
                'variants': variants
            })
        
        # Print every hour
        if ts % 60 == 0:
            print(f"{hour:<6.1f} {ts:<8} {infected_persons:<18} {in_locations:<15} {','.join(variants)}{drop_marker}")
        
        prev_infected = infected_persons
    
    # Report drops
    if infection_drops:
        print(f"\n{'=' * 60}")
        print("⚠️  DETECTED SUDDEN INFECTION DROPS")
        print("=" * 60)
        for drop in infection_drops:
            print(f"  Hour {drop['hour']:.1f}: {drop['prev']} → {drop['curr']} infected")
            print(f"    Variants in result: {drop['variants']}")
    else:
        print(f"\n✅ No sudden infection drops detected")
    
    # Check for missing data alignment
    print(f"\n{'=' * 60}")
    print("DATA ALIGNMENT CHECK")
    print("=" * 60)
    
    result_keys = set(result.keys())
    movement_keys = set(movement.keys())
    
    only_in_result = result_keys - movement_keys
    only_in_movement = movement_keys - result_keys
    
    print(f"Keys only in result (no movement): {len(only_in_result)}")
    if only_in_result:
        print(f"  First few: {sorted(list(only_in_result))[:5]}")
    
    print(f"Keys only in movement (no result): {len(only_in_movement)}")
    if only_in_movement:
        print(f"  First few: {sorted(list(only_in_movement))[:5]}")
    
    # Check if result has empty data at any point
    print(f"\n{'=' * 60}")
    print("RESULT DATA INSPECTION")
    print("=" * 60)
    
    empty_results = []
    for ts in all_timestamps:
        ts_str = str(ts)
        result_data = result.get(ts_str, {})
        total_persons = sum(len(v) for v in result_data.values())
        if total_persons == 0:
            empty_results.append(ts)
    
    if empty_results:
        print(f"⚠️  Found {len(empty_results)} timestamps with empty result data!")
        print(f"  First few: {empty_results[:10]}")
        print(f"  Corresponding hours: {[t/60 for t in empty_results[:10]]}")
    else:
        print(f"✅ All timestamps have result data")


if __name__ == '__main__':
    main()
