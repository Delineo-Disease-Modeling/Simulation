#!/usr/bin/env python3
"""
Profiling script for the disease simulation via HTTP requests
"""
import cProfile
import pstats
import io
import time
import json
import requests
from datetime import datetime

def profile_simulation_via_api(output_file="profile_baseline.prof"):
    """Profile the simulation via HTTP API and save results"""
    print(f"Starting profiling run at {datetime.now()}")
    
    # Set up profiler
    profiler = cProfile.Profile()
    
    # Simulation parameters
    simulation_params = {
        'length': 720,  # 12 hours in minutes for faster profiling
        'location': 'default',
        'capacity': 1.0,
        'lockdown': 0.0,
        'selfiso': 0.0,
        'mask': 0.1,
        'vaccine': 0.2,
        'randseed': False
    }
    
    # Start profiling
    profiler.enable()
    start_time = time.time()
    
    try:
        # Make HTTP request to simulation endpoint
        response = requests.post(
            "http://127.0.0.1:1880/simulation/",
            json=simulation_params,
            timeout=300  # 5 minute timeout
        )
        
        end_time = time.time()
        profiler.disable()
        
        if response.status_code == 200:
            result = response.json()
            print(f"Simulation completed successfully")
        else:
            print(f"Simulation failed with status {response.status_code}: {response.text}")
            result = {}
        
        # Save profiling results
        profiler.dump_stats(output_file)
        
        # Generate readable stats
        stats_output = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_output)
        stats.sort_stats('cumulative')
        stats.print_stats(50)  # Top 50 functions
        
        # Save stats to file
        with open(f"{output_file}.txt", "w") as f:
            f.write(f"Simulation Profiling Results - Baseline (via API)\n")
            f.write(f"Start time: {datetime.fromtimestamp(start_time)}\n")
            f.write(f"End time: {datetime.fromtimestamp(end_time)}\n")
            f.write(f"Total runtime: {end_time - start_time:.2f} seconds\n")
            f.write(f"HTTP Status: {response.status_code}\n")
            f.write(f"Result size: {len(str(result))}\n")
            f.write("="*80 + "\n")
            f.write(stats_output.getvalue())
        
        print(f"Profiling completed in {end_time - start_time:.2f} seconds")
        print(f"Results saved to {output_file} and {output_file}.txt")
        
        return {
            'runtime': end_time - start_time,
            'result_size': len(str(result)),
            'profile_file': output_file,
            'http_status': response.status_code
        }
        
    except Exception as e:
        profiler.disable()
        print(f"Error during profiling: {e}")
        return None

def profile_simulation_direct(output_file="profile_baseline_direct.prof"):
    """Profile the simulation directly and save results"""
    print(f"Starting direct profiling run at {datetime.now()}")
    
    # Set up profiler
    profiler = cProfile.Profile()
    
    # Start profiling
    profiler.enable()
    start_time = time.time()
    
    try:
        from simulator import simulate
        
        # Run simulation with default parameters
        result = simulate.run_simulator(
            location="default",
            max_length=720,  # 12 hours in minutes for faster profiling
            interventions={
                'capacity': 1.0,
                'lockdown': 0.0,
                'selfiso': 0.0,
                'mask': 0.1,
                'vaccine': 0.2,
                'randseed': False
            },
            save_file=False,
            enable_logging=True,
            log_dir="profiling_logs_baseline"
        )
        
        end_time = time.time()
        profiler.disable()
        
        # Save profiling results
        profiler.dump_stats(output_file)
        
        # Generate readable stats
        stats_output = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_output)
        stats.sort_stats('cumulative')
        stats.print_stats(50)  # Top 50 functions
        
        # Save stats to file
        with open(f"{output_file}.txt", "w") as f:
            f.write(f"Simulation Profiling Results - Baseline (Direct)\n")
            f.write(f"Start time: {datetime.fromtimestamp(start_time)}\n")
            f.write(f"End time: {datetime.fromtimestamp(end_time)}\n")
            f.write(f"Total runtime: {end_time - start_time:.2f} seconds\n")
            f.write(f"Result timesteps: {len(result.get('result', {})) if result else 0}\n")
            f.write("="*80 + "\n")
            f.write(stats_output.getvalue())
        
        print(f"Direct profiling completed in {end_time - start_time:.2f} seconds")
        print(f"Results saved to {output_file} and {output_file}.txt")
        
        return {
            'runtime': end_time - start_time,
            'result_size': len(result.get('result', {})) if result else 0,
            'profile_file': output_file
        }
        
    except Exception as e:
        profiler.disable()
        print(f"Error during direct profiling: {e}")
        return None

if __name__ == "__main__":
    # Try direct profiling first
    print("Running direct profiling...")
    direct_result = profile_simulation_direct()
    
    if direct_result:
        print(f"Direct profiling successful: {direct_result}")
    else:
        print("Direct profiling failed, trying API profiling...")
        api_result = profile_simulation_via_api()
        if api_result:
            print(f"API profiling successful: {api_result}")
        else:
            print("Both profiling methods failed")
