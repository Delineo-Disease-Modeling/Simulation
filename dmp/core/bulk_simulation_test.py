#!/usr/bin/env python3
"""
Bulk simulation test for the DMP Local client.

This script generates 1,000 people with random demographics and runs
COVID-19 simulations on them to test the system's performance and accuracy.
"""

import random
import time
import json
from typing import List, Dict, Any
from dmp_local import DMPLocal

def generate_random_demographics() -> Dict[str, str]:
    """Generate random demographics for a person."""
    # Random age: 0-18, 19-64, 65+
    age_groups = ["0-18", "19-64", "65+"]
    age = random.choice(age_groups)
    
    # Random sex
    sex = random.choice(["Male", "Female"])
    
    # Random vaccination status
    vaccination = random.choice(["Unvaccinated", "Vaccinated"])
    
    # Random COVID-19 variant
    variant = random.choice(["Omicron", "Delta"])
    
    return {
        "Age": age,
        "Sex": sex,
        "Vaccination Status": vaccination,
        "Variant": variant
    }

def run_bulk_simulations(num_people: int = 1000) -> List[Dict[str, Any]]:
    """Run simulations for multiple people and collect results."""
    print(f"Starting bulk simulation test with {num_people} people...")
    
    # Initialize DMP client
    dmp = DMPLocal()
    
    # Verify available diseases
    diseases = dmp.get_available_diseases()
    print(f"Available diseases: {diseases}")
    
    if "COVID-19" not in diseases:
        print("Error: COVID-19 not available in the system")
        return []
    
    # Verify COVID-19 variants
    variants = dmp.get_variants_for_disease("COVID-19")
    print(f"Available COVID-19 variants: {variants}")
    
    results = []
    successful_simulations = 0
    failed_simulations = 0
    
    start_time = time.time()
    
    for i in range(num_people):
        if (i + 1) % 500 == 0:
            print(f"Progress: {i + 1}/{num_people} simulations completed")
        
        # Generate random demographics
        demographics = generate_random_demographics()
        variant = demographics.pop("Variant")  # Remove variant from demographics
        
        # Determine model path based on variant
        model_path = f"variant.{variant}.general"
        
        try:
            # Run simulation
            result = dmp.run_simulation(
                disease_name="COVID-19",
                demographics=demographics,
                model_path=model_path
            )
            
            if result:
                # Add metadata to result
                simulation_data = {
                    "person_id": i + 1,
                    "demographics": demographics,
                    "variant": variant,
                    "model_path": model_path,
                    "simulation_successful": True,
                    "state_machine": result.get("state_machine", {}),
                    "timeline": result.get("timeline", []),
                    "total_duration": result.get("timeline", [])[-1][1] if result.get("timeline") else 0
                }
                results.append(simulation_data)
                successful_simulations += 1
            else:
                # Record failed simulation
                simulation_data = {
                    "person_id": i + 1,
                    "demographics": demographics,
                    "variant": variant,
                    "model_path": model_path,
                    "simulation_successful": False,
                    "error": "Simulation returned no result"
                }
                results.append(simulation_data)
                failed_simulations += 1
                
        except Exception as e:
            # Record simulation with error
            simulation_data = {
                "person_id": i + 1,
                "demographics": demographics,
                "variant": variant,
                "model_path": model_path,
                "simulation_successful": False,
                "error": str(e)
            }
            results.append(simulation_data)
            failed_simulations += 1
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Print summary
    print(f"\n=== Bulk Simulation Test Complete ===")
    print(f"Total people simulated: {num_people}")
    print(f"Successful simulations: {successful_simulations}")
    print(f"Failed simulations: {failed_simulations}")
    print(f"Success rate: {(successful_simulations/num_people)*100:.2f}%")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Average time per simulation: {total_time/num_people:.4f} seconds")
    
    return results

def analyze_results(results: List[Dict[str, Any]]) -> None:
    """Analyze and display statistics from the simulation results."""
    if not results:
        print("No results to analyze")
        return
    
    successful_results = [r for r in results if r.get("simulation_successful")]
    
    if not successful_results:
        print("No successful simulations to analyze")
        return
    
    print(f"\n=== Results Analysis ===")
    
    # Demographics distribution
    age_dist = {}
    sex_dist = {}
    vaccination_dist = {}
    variant_dist = {}
    
    for result in successful_results:
        demo = result["demographics"]
        age = demo.get("Age", "Unknown")
        sex = demo.get("Sex", "Unknown")
        vaccination = demo.get("Vaccination Status", "Unknown")
        variant = result.get("variant", "Unknown")
        
        age_dist[age] = age_dist.get(age, 0) + 1
        sex_dist[sex] = sex_dist.get(sex, 0) + 1
        vaccination_dist[vaccination] = vaccination_dist.get(vaccination, 0) + 1
        variant_dist[variant] = variant_dist.get(variant, 0) + 1
    
    print(f"Age distribution: {age_dist}")
    print(f"Sex distribution: {sex_dist}")
    print(f"Vaccination distribution: {vaccination_dist}")
    print(f"Variant distribution: {variant_dist}")
    
    # Duration statistics
    durations = [r.get("total_duration", 0) for r in successful_results if r.get("total_duration")]
    if durations:
        print(f"Average disease duration: {sum(durations)/len(durations):.2f} hours")
        print(f"Min duration: {min(durations):.2f} hours")
        print(f"Max duration: {max(durations):.2f} hours")

def save_results(results: List[Dict[str, Any]], filename: str = "bulk_simulation_results.json") -> None:
    """Save simulation results to a JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {filename}")
    except Exception as e:
        print(f"Error saving results: {e}")

def main():
    """Main function to run the bulk simulation test."""
    print("=== DMP Bulk Simulation Test ===")
    print("This test will simulate 1,000 people with random demographics")
    print("and run COVID-19 simulations on them.\n")
    
    # Run bulk simulations
    results = run_bulk_simulations(1000)
    
    # Analyze results
    analyze_results(results)
    
    # Save results
    save_results(results)
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main() 