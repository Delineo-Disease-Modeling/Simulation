import cProfile
import pstats
import time
import os
from simulator import simulate
from simulator.config import SIMULATION

# Create directory for profiling results
os.makedirs('profiling_results', exist_ok=True)

def run_profiling(dataset_size):
    """Run profiling with specific dataset size"""
    location = SIMULATION["default_location"]
    interventions = SIMULATION["default_interventions"]
    
    # Start profiling
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    profile_file = f"profiling_results/delineo_size_{dataset_size}_{timestamp}.prof"
    
    print(f"Profiling simulation with dataset size: {dataset_size}")
    start_time = time.time()
    
    # Run profiling
    cProfile.run(
        f'simulate.run_simulator("{location}", {dataset_size}, {interventions})', 
        profile_file
    )
    
    execution_time = time.time() - start_time
    print(f"Execution time: {execution_time:.2f} seconds")
    
    # Print stats
    stats = pstats.Stats(profile_file)
    stats.sort_stats('cumulative').print_stats(20)
    
    print(f"Full profiling data saved to: {profile_file}")
    print(f"To visualize results, run: snakeviz {profile_file}")

if __name__ == "__main__":
    # Run profiling with different dataset sizes
    for size in [100, 1000, 10000]:  # Adjust these sizes as needed
        run_profiling(size)
        print("\n" + "="*50 + "\n")