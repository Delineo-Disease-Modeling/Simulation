#!/usr/bin/env python3
"""
Debug script to run a short simulation and track infection counts per hour.
Run this directly: python debug_simulation.py
"""

import sys
import os
import json
from datetime import datetime
from collections import defaultdict

# Add simulator to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator import simulate
from simulator.config import SIMULATION, DMP_API
from simulator.pap import InfectionState
import requests


def initialize_dmp_api():
    """Initialize DMP API"""
    BASE_URL = DMP_API["base_url"]
    init_payload = {
        "matrices_path": DMP_API["paths"]["matrices_path"],
        "mapping_path": DMP_API["paths"]["mapping_path"],
        "states_path": DMP_API["paths"]["states_path"]
    }
    
    try:
        init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload, timeout=5)
        init_response.raise_for_status()
        print("✓ DMP API initialized")
        return True
    except Exception as e:
        print(f"✗ DMP API not available: {e}")
        return False


def count_states_from_result(result_data, variants):
    """
    Parse result data and count infection states per timestep.
    
    Result format: {timestep: {variant: {personId: stateValue}}}
    
    InfectionState flags:
        SUSCEPTIBLE = 0
        INFECTED = 1
        INFECTIOUS = 2
        SYMPTOMATIC = 4
        HOSPITALIZED = 8
        RECOVERED = 16
        REMOVED = 32
    """
    timestep_counts = {}
    all_people = set()
    
    # First pass: get all unique people IDs
    for ts, variant_data in result_data.items():
        for variant, people in variant_data.items():
            all_people.update(people.keys())
    
    total_pop = len(all_people)
    
    # Second pass: count states per timestep
    for ts_str, variant_data in result_data.items():
        ts = int(ts_str)
        
        # Aggregate across all variants
        infected = 0
        infectious = 0
        symptomatic = 0
        hospitalized = 0
        recovered = 0
        removed = 0
        people_with_any_state = set()
        
        for variant, people in variant_data.items():
            for person_id, state_val in people.items():
                state = int(state_val)
                people_with_any_state.add(person_id)
                
                # Count each state (flags are combinable)
                if state & 1:  # INFECTED
                    infected += 1
                if state & 2:  # INFECTIOUS
                    infectious += 1
                if state & 4:  # SYMPTOMATIC
                    symptomatic += 1
                if state & 8:  # HOSPITALIZED
                    hospitalized += 1
                if state & 16:  # RECOVERED
                    recovered += 1
                if state & 32:  # REMOVED
                    removed += 1
        
        # Susceptible = total - (anyone with non-zero state)
        susceptible = total_pop - len(people_with_any_state)
        
        timestep_counts[ts] = {
            'susceptible': susceptible,
            'infected': infected,
            'infectious': infectious,
            'symptomatic': symptomatic,
            'hospitalized': hospitalized,
            'recovered': recovered,
            'removed': removed,
            'total': total_pop
        }
    
    return timestep_counts


def run_debug_simulation():
    """Run a short simulation and print infection counts per hour."""
    
    print("=" * 70)
    print("DELINEO DEBUG SIMULATION - HOURLY INFECTION TRACKING")
    print("=" * 70)
    
    # Initialize DMP (optional)
    initialize_dmp_api()
    
    # Simulation parameters - Jan 24 to Feb 4 (11 days)
    location = "barnsdall"  # Default test location with data
    # Jan 24 to Feb 4 = 11 days = 11 * 24 * 60 = 15,840 minutes
    length_minutes = 11 * 24 * 60  # 11 days
    initial_infected_count = 15  # Start with 15 infected for more visible spread
    
    interventions = {
        "mask": 0.0,
        "vaccine": 0.0,
        "capacity": 1.0,
        "lockdown": 0,
        "selfiso": 0.0,
        "randseed": False  # Fixed seed for reproducibility
    }
    
    print(f"\nParameters:")
    print(f"  Location: {location}")
    print(f"  Duration: {length_minutes} minutes ({length_minutes // 60} hours)")
    print(f"  Initial infected: {initial_infected_count}")
    print(f"  Interventions: {interventions}")
    print(f"  Variants: {SIMULATION['variants']}")
    print()
    
    print("Running simulation...")
    print("-" * 70)
    
    start_time = datetime.now()
    
    try:
        result = simulate.run_simulator(
            location=location,
            max_length=length_minutes,
            interventions=interventions,
            initial_infected_count=initial_infected_count,
            initial_infected_ids=None,
            czone_id=None,
            report=None,
            enable_logging=False  # Disable detailed logging for speed
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n✓ Simulation completed in {elapsed:.1f} seconds")
        
        # Extract and print hourly data
        if 'result' in result:
            raw_result = result['result']
            variants = SIMULATION['variants']
            
            # Parse result data into counts
            timestep_counts = count_states_from_result(raw_result, variants)
            
            print("\n" + "=" * 70)
            print("INFECTION COUNTS BY HOUR")
            print("=" * 70)
            print(f"{'Hour':>5} | {'Min':>6} | {'Suscept':>8} | {'Infected':>8} | {'Infect-ious':>10} | {'Recovered':>9} | {'Removed':>8}")
            print("-" * 70)
            
            # Get all timesteps and sort them
            timesteps = sorted(timestep_counts.keys())
            
            # Track hourly changes
            last_hour_data = None
            hourly_summary = []
            
            # Print hourly summaries (every 60 minutes)
            for ts in timesteps:
                hour = ts // 60
                minute = ts % 60
                data = timestep_counts[ts]
                
                # Print at hour marks or first/last
                if minute == 0 or ts == timesteps[0] or ts == timesteps[-1]:
                    change_str = ""
                    if last_hour_data:
                        new_inf = data['infected'] - last_hour_data['infected']
                        new_rec = data['recovered'] - last_hour_data['recovered']
                        if new_inf > 0:
                            change_str = f" (+{new_inf} new infections)"
                    
                    print(f"{hour:>5} | {ts:>6} | {data['susceptible']:>8} | {data['infected']:>8} | {data['infectious']:>10} | {data['recovered']:>9} | {data['removed']:>8}{change_str}")
                    
                    if minute == 0:
                        hourly_summary.append({
                            'hour': hour,
                            'susceptible': data['susceptible'],
                            'infected': data['infected'],
                            'recovered': data['recovered'],
                        })
                        last_hour_data = data
            
            # Print summary
            if timesteps:
                first = timestep_counts[timesteps[0]]
                last = timestep_counts[timesteps[-1]]
                
                print("\n" + "=" * 70)
                print("SUMMARY")
                print("=" * 70)
                print(f"Population:       {first.get('total', 'N/A')}")
                print(f"Initial infected: {first.get('infected', 0)}")
                print(f"Final infected:   {last.get('infected', 0)}")
                print(f"Final recovered:  {last.get('recovered', 0)}")
                print(f"Final removed:    {last.get('removed', 0)}")
                print(f"Total timesteps:  {len(timesteps)}")
                print(f"Variants tracked: {variants}")
                
                # Show new infections
                total_new_infections = last.get('infected', 0) + last.get('recovered', 0) + last.get('removed', 0)
                initial_infections = first.get('infected', 0)
                spread = total_new_infections - initial_infections
                print(f"\nNew infections during simulation: {spread}")
                
        else:
            print("No result data returned")
            print(f"Keys in result: {result.keys() if result else 'None'}")
            if result:
                for k, v in result.items():
                    print(f"  {k}: {type(v)} - {len(v) if hasattr(v, '__len__') else 'N/A'}")
            
    except Exception as e:
        print(f"\n✗ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(run_debug_simulation())
