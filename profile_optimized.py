#!/usr/bin/env python3
"""
Profiling script for the optimized disease simulation
"""
import cProfile
import pstats
import io
import time
import json
from datetime import datetime

def profile_optimized_simulation(output_file="profile_optimized.prof"):
    """Profile the optimized simulation and save results"""
    print(f"Starting optimized profiling run at {datetime.now()}")
    
    # Set up profiler
    profiler = cProfile.Profile()
    
    # Start profiling
    profiler.enable()
    start_time = time.time()
    
    try:
        from simulator import simulate
        
        # Run simulation with same parameters as baseline
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
            log_dir="profiling_logs_optimized"
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
            f.write(f"Simulation Profiling Results - Optimized\n")
            f.write(f"Start time: {datetime.fromtimestamp(start_time)}\n")
            f.write(f"End time: {datetime.fromtimestamp(end_time)}\n")
            f.write(f"Total runtime: {end_time - start_time:.2f} seconds\n")
            f.write(f"Result timesteps: {len(result.get('result', {})) if result else 0}\n")
            f.write("="*80 + "\n")
            f.write(stats_output.getvalue())
        
        print(f"Optimized profiling completed in {end_time - start_time:.2f} seconds")
        print(f"Results saved to {output_file} and {output_file}.txt")
        
        return {
            'runtime': end_time - start_time,
            'result_size': len(result.get('result', {})) if result else 0,
            'profile_file': output_file
        }
        
    except Exception as e:
        profiler.disable()
        print(f"Error during optimized profiling: {e}")
        return None

if __name__ == "__main__":
    profile_optimized_simulation()
