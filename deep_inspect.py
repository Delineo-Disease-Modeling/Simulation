#!/usr/bin/env python3
"""
Deep inspection of simulation data to find why infections drop to 0.
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator import simulate
import json

def count_infected_in_result(result_data):
    """Count people with INFECTED bit set in result data."""
    count = 0
    for variant, people in result_data.items():
        for person_id, state in people.items():
            if (int(state) & 1) == 1:  # INFECTED bit
                count += 1
    return count

def count_in_movement(movement_data):
    """Count total people in movement data."""
    home_count = sum(len(pids) for pids in movement_data.get('homes', {}).values())
    place_count = sum(len(pids) for pids in movement_data.get('places', {}).values())
    return home_count, place_count

def main():
    print("Running 200-hour simulation to cover hour 186-193...")
    
    sim_result = simulate.run_simulator(
        location='barnsdall',
        max_length=200 * 60,  # 200 hours in minutes
        interventions={'mask': 0.0, 'vaccine': 0.0},
        save_file=False,
        enable_logging=False,
        initial_infected_count=33
    )
    
    result = sim_result.get('result', {})
    movement = sim_result.get('movement', {})
    
    print(f"\nResult has {len(result)} timestamps")
    print(f"Movement has {len(movement)} timestamps")
    
    # Analyze hours 180-200
    print("\n" + "="*70)
    print("DETAILED ANALYSIS: Hours 180-200")
    print("="*70)
    print(f"{'Hour':<6} {'Min':<8} {'Infected(R)':<12} {'InHomes(M)':<12} {'InPlaces(M)':<12} {'Notes'}")
    print("-"*70)
    
    for hour in range(180, 201):
        minute = hour * 60
        
        result_data = result.get(minute, {})
        movement_data = movement.get(minute, {})
        
        infected_count = count_infected_in_result(result_data)
        home_count, place_count = count_in_movement(movement_data)
        
        notes = []
        if not result_data:
            notes.append("NO_RESULT")
        if not movement_data:
            notes.append("NO_MOVEMENT")
        if infected_count == 0 and result_data:
            notes.append("ZERO_INFECTED")
        
        print(f"{hour:<6} {minute:<8} {infected_count:<12} {home_count:<12} {place_count:<12} {', '.join(notes)}")
    
    # Check if any result has 0 infected after having non-zero
    print("\n" + "="*70)
    print("INFECTION STATE TRANSITIONS")
    print("="*70)
    
    timestamps = sorted(result.keys())
    prev_infected = None
    
    for ts in timestamps:
        result_data = result[ts]
        infected = count_infected_in_result(result_data)
        
        if prev_infected is not None and prev_infected > 0 and infected == 0:
            print(f"⚠️  INFECTION DROP: Hour {ts/60:.1f} went from {prev_infected} to {infected}")
        
        prev_infected = infected
    
    # Check the specific transformation
    print("\n" + "="*70)
    print("FRONTEND TRANSFORMATION SIMULATION")
    print("="*70)
    
    # Simulate what the frontend does
    for hour in [186, 193]:
        minute = hour * 60
        result_data = result.get(minute, {})
        movement_data = movement.get(minute, {})
        
        print(f"\n--- Hour {hour} (minute {minute}) ---")
        
        # Get infected persons set (like frontend does)
        infected_persons = set()
        for variant, people in result_data.items():
            for person_id, state in people.items():
                if (int(state) & 1) == 1:
                    infected_persons.add(str(person_id))
        
        print(f"Infected persons in result: {len(infected_persons)}")
        
        # Transform homes
        total_infected_in_homes = 0
        for home_id, person_ids in movement_data.get('homes', {}).items():
            infected = sum(1 for pid in person_ids if str(pid) in infected_persons)
            total_infected_in_homes += infected
        
        # Transform places
        total_infected_in_places = 0
        for place_id, person_ids in movement_data.get('places', {}).items():
            infected = sum(1 for pid in person_ids if str(pid) in infected_persons)
            total_infected_in_places += infected
        
        print(f"Total in movement (homes): {sum(len(v) for v in movement_data.get('homes', {}).values())}")
        print(f"Total in movement (places): {sum(len(v) for v in movement_data.get('places', {}).values())}")
        print(f"Infected found in homes: {total_infected_in_homes}")
        print(f"Infected found in places: {total_infected_in_places}")
        print(f"DISPLAYED INFECTED TOTAL: {total_infected_in_homes + total_infected_in_places}")
        
        # Sample infected persons
        if infected_persons:
            sample = list(infected_persons)[:5]
            print(f"Sample infected IDs: {sample}")
            
            # Check if these IDs appear in movement
            for pid in sample:
                in_homes = any(pid in pids for pids in movement_data.get('homes', {}).values())
                in_places = any(str(pid) in pids for pids in movement_data.get('places', {}).values())
                print(f"  Person {pid}: in_homes={in_homes}, in_places={in_places}")


if __name__ == '__main__':
    main()
