#!/usr/bin/env python3
"""
Example usage of the DMPLocal class for direct database access.

This demonstrates how to use the DMP as a Python module for local integration.
"""

import sys
import os
import json

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from cli.user_input import DMPLocal

def main():
    """Example usage of the DMPLocal class."""
    
    # Initialize the DMP local access
    dmp = DMPLocal()
    
    print("=== Disease Modeling Platform - Local Access Example ===\n")
    
    # 1. List available diseases
    print("1. Available diseases:")
    diseases = dmp.get_available_diseases()
    for disease in diseases:
        print(f"   - {disease}")
    print()
    
    # 2. List variants for COVID-19
    print("2. COVID-19 variants:")
    variants = dmp.get_variants_for_disease("COVID-19")
    for variant in variants:
        print(f"   - {variant}")
    print()
    
    # 3. List state machines for Measles
    print("3. Measles state machines:")
    machines = dmp.list_state_machines("Measles")
    for machine in machines:
        print(f"   - {machine['name']} (ID: {machine['id']})")
    print()
    
    # 4. Run a simulation
    print("4. Running simulation for Measles:")
    demographics = {
        "Age": "3",
        "Sex": "M", 
        "Vaccination Status": "Unvaccinated"
    }
    
    result = dmp.run_simulation(
        disease_name="Measles",
        demographics=demographics,
        model_path="vaccination.Unvaccinated.general"
    )
    
    if result:
        print(f"   State machine: {result['state_machine']['name']}")
        print(f"   Model path: {result['state_machine']['model_path']}")
        print("   Timeline:")
        for state, time in result['timeline']:
            print(f"     {time:>6.1f} hours: {state}")
    else:
        print("   Simulation failed!")
    print()
    
    # 5. Run a COVID-19 simulation with variant
    print("5. Running COVID-19 simulation with Omicron variant:")
    covid_demographics = {
        "Age": "66",
        "Sex": "Male",
        "Vaccination Status": "Unvaccinated"
    }
    
    covid_result = dmp.run_simulation(
        disease_name="COVID-19",
        demographics=covid_demographics,
        model_path="variant.Omicron.general"
    )
    
    if covid_result:
        print(f"   State machine: {covid_result['state_machine']['name']}")
        print("   Timeline:")
        for state, time in covid_result['timeline']:
            print(f"     {time:>6.1f} hours: {state}")
    else:
        print("   Simulation failed!")
    print()
    
    # 6. Save results to file
    print("6. Saving results to file...")
    if result:
        with open("simulation_results.json", "w") as f:
            json.dump(result, f, indent=2)
        print("   Results saved to simulation_results.json")
    
    print("\n=== Example completed ===")

if __name__ == "__main__":
    main() 