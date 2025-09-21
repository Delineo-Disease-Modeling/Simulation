#!/usr/bin/env python3
"""
Simple cProfile script for the disease simulation
"""
import cProfile
import pstats
import io
import time
import sys
import os
from datetime import datetime

def run_profiling():
    """Run cProfile on the simulation and generate detailed breakdown"""
    print(f"Starting cProfile analysis at {datetime.now()}")
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Start profiling
    profiler.enable()
    start_time = time.time()
    
    try:
        # Import and run the simulation
        sys.path.append('/Users/navyamehrotra/Documents/Projects/Delineo/Simulation')
        from simulator import simulate
        
        # Run simulation with reduced parameters for faster profiling
        result = simulate.run_simulator(
            location="default",
            max_length=360,  # 6 hours for faster profiling
            interventions={
                'capacity': 1.0,
                'lockdown': 0.0,
                'selfiso': 0.0,
                'mask': 0.1,
                'vaccine': 0.2,
                'randseed': False
            },
            save_file=False,
            enable_logging=False  # Disable logging for cleaner profiling
        )
        
        end_time = time.time()
        profiler.disable()
        
        # Save profiling data
        profile_file = f"cprofile_results_{int(time.time())}.prof"
        profiler.dump_stats(profile_file)
        
        # Generate detailed analysis
        print(f"\n{'='*80}")
        print(f"CPROFILE PERFORMANCE BREAKDOWN")
        print(f"{'='*80}")
        print(f"Total Runtime: {end_time - start_time:.2f} seconds")
        print(f"Profile saved to: {profile_file}")
        
        # Create stats object for analysis
        stats = pstats.Stats(profiler)
        
        # 1. Overall statistics
        print(f"\n{'='*50}")
        print("OVERALL STATISTICS")
        print(f"{'='*50}")
        print(f"Total function calls: {stats.total_calls:,}")
        print(f"Primitive calls: {stats.prim_calls:,}")
        print(f"Total time: {stats.total_tt:.3f} seconds")
        
        # 2. Top functions by cumulative time
        print(f"\n{'='*50}")
        print("TOP 20 FUNCTIONS BY CUMULATIVE TIME")
        print(f"{'='*50}")
        stats.sort_stats('cumulative')
        stats.print_stats(20)
        
        # 3. Top functions by total time (self time)
        print(f"\n{'='*50}")
        print("TOP 20 FUNCTIONS BY SELF TIME")
        print(f"{'='*50}")
        stats.sort_stats('tottime')
        stats.print_stats(20)
        
        # 4. Most called functions
        print(f"\n{'='*50}")
        print("TOP 20 MOST CALLED FUNCTIONS")
        print(f"{'='*50}")
        stats.sort_stats('ncalls')
        stats.print_stats(20)
        
        # 5. Functions with highest time per call
        print(f"\n{'='*50}")
        print("FUNCTIONS WITH HIGHEST TIME PER CALL")
        print(f"{'='*50}")
        stats.sort_stats('percall')
        stats.print_stats(20)
        
        # 6. Save detailed report to file
        report_file = f"cprofile_report_{int(time.time())}.txt"
        with open(report_file, 'w') as f:
            f.write(f"cProfile Performance Analysis Report\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Total Runtime: {end_time - start_time:.2f} seconds\n")
            f.write(f"Total function calls: {stats.total_calls:,}\n")
            f.write(f"Primitive calls: {stats.prim_calls:,}\n")
            f.write(f"Total time: {stats.total_tt:.3f} seconds\n")
            f.write(f"\n{'='*80}\n")
            
            # Redirect stats output to file
            old_stdout = sys.stdout
            sys.stdout = f
            
            f.write("TOP FUNCTIONS BY CUMULATIVE TIME:\n")
            f.write("-" * 40 + "\n")
            stats.sort_stats('cumulative')
            stats.print_stats(50)
            
            f.write("\nTOP FUNCTIONS BY SELF TIME:\n")
            f.write("-" * 40 + "\n")
            stats.sort_stats('tottime')
            stats.print_stats(50)
            
            f.write("\nMOST CALLED FUNCTIONS:\n")
            f.write("-" * 40 + "\n")
            stats.sort_stats('ncalls')
            stats.print_stats(50)
            
            sys.stdout = old_stdout
        
        print(f"\nDetailed report saved to: {report_file}")
        
        # 7. Performance hotspots analysis
        print(f"\n{'='*50}")
        print("PERFORMANCE HOTSPOTS ANALYSIS")
        print(f"{'='*50}")
        
        # Get function statistics
        stats_dict = stats.stats
        
        # Find simulation-specific functions (exclude built-ins)
        sim_functions = []
        for func_key, func_stats in stats_dict.items():
            filename, line_num, func_name = func_key
            if ('simulator' in filename or 'infection' in filename or 
                'simulate' in filename or 'app.py' in filename):
                cumtime = func_stats[3]  # cumulative time
                tottime = func_stats[2]  # total time (self)
                ncalls = func_stats[0]   # number of calls
                sim_functions.append((func_name, filename, cumtime, tottime, ncalls))
        
        # Sort by cumulative time and show top simulation functions
        sim_functions.sort(key=lambda x: x[2], reverse=True)
        
        print("Top simulation-specific functions by cumulative time:")
        print(f"{'Function':<30} {'File':<25} {'Cum Time':<10} {'Self Time':<10} {'Calls':<10}")
        print("-" * 95)
        for i, (func_name, filename, cumtime, tottime, ncalls) in enumerate(sim_functions[:15]):
            short_file = os.path.basename(filename)
            print(f"{func_name[:29]:<30} {short_file[:24]:<25} {cumtime:<10.3f} {tottime:<10.3f} {ncalls:<10}")
        
        return {
            'runtime': end_time - start_time,
            'total_calls': stats.total_calls,
            'total_time': stats.total_tt,
            'profile_file': profile_file,
            'report_file': report_file
        }
        
    except Exception as e:
        profiler.disable()
        print(f"Error during profiling: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = run_profiling()
    if result:
        print(f"\n{'='*50}")
        print("PROFILING COMPLETED SUCCESSFULLY")
        print(f"{'='*50}")
        print(f"Runtime: {result['runtime']:.2f} seconds")
        print(f"Total calls: {result['total_calls']:,}")
        print(f"Files generated:")
        print(f"  - {result['profile_file']} (binary profile data)")
        print(f"  - {result['report_file']} (detailed text report)")
    else:
        print("Profiling failed!")
