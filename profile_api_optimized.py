#!/usr/bin/env python3
"""
Final profiling script for the DMP API optimized disease simulation.
This measures performance after optimizations including:
- Connection pooling and session reuse for DMP API calls
- Concurrent API requests with thread pool
- Enhanced caching with thread-safe operations
- Batch processing of new infections
- Fast lookup structures for infected people
"""

import cProfile
import pstats
import io
import time
import requests
import json
import os
from datetime import datetime

def profile_simulation_api_optimized():
    """Profile the API-optimized simulation"""
    print("=== PROFILING API OPTIMIZED SIMULATION ===")
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Start timing
    start_time = time.time()
    
    # Start profiling
    profiler.enable()
    
    try:
        # Run simulation via HTTP API (Flask app is on port 1880)
        url = "http://localhost:1880/simulation/"
        params = {
            'location': 'barnsdall',
            'max_length': 1440,  # 24 hours in minutes
            'save_file': False,
            'enable_logging': True,
            'log_dir': 'profiling_logs_api_optimized'
        }
        
        print(f"Making request to {url} with params: {params}")
        response = requests.post(url, json=params, timeout=300)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Simulation completed successfully")
            print(f"Response keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        else:
            print(f"Simulation failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Error during simulation: {e}")
    finally:
        # Stop profiling
        profiler.disable()
    
    # End timing
    end_time = time.time()
    total_runtime = end_time - start_time
    
    print(f"\n=== API OPTIMIZED SIMULATION PROFILING RESULTS ===")
    print(f"Total runtime: {total_runtime:.2f} seconds")
    
    # Save profiling stats
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    profile_filename = f"api_optimized_simulation_{timestamp}.prof"
    profiler.dump_stats(profile_filename)
    print(f"Profiling data saved to: {profile_filename}")
    
    # Generate and save text report
    s = io.StringIO()
    ps = pstats.Stats(profiler, stream=s)
    ps.sort_stats('cumulative')
    ps.print_stats(50)  # Top 50 functions
    
    report_filename = f"api_optimized_simulation_{timestamp}.txt"
    with open(report_filename, 'w') as f:
        f.write(f"API Optimized Simulation Profiling Report\n")
        f.write(f"Generated: {datetime.now()}\n")
        f.write(f"Total Runtime: {total_runtime:.2f} seconds\n")
        f.write("=" * 80 + "\n\n")
        f.write(s.getvalue())
    
    print(f"Profiling report saved to: {report_filename}")
    
    # Print summary to console
    print(f"\n=== TOP 20 FUNCTIONS BY CUMULATIVE TIME ===")
    ps = pstats.Stats(profiler)
    ps.sort_stats('cumulative')
    ps.print_stats(20)
    
    return total_runtime, profile_filename, report_filename

if __name__ == "__main__":
    runtime, prof_file, report_file = profile_simulation_api_optimized()
    print(f"\nAPI optimized simulation completed in {runtime:.2f} seconds")
    print(f"Profile: {prof_file}")
    print(f"Report: {report_file}")
