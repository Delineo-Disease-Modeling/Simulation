#!/usr/bin/env python3
"""
Disease Modeling Platform - Direct Database Access Module

This module provides direct access to the state machine database for local Python code,
bypassing the API for faster performance and easier integration.
"""

import sys
import os
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import the state machine database and simulation functions
from app.state_machine.state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from app.state_machine.utils.graph_utils import convert_graph_to_matrices

class DMPLocal:
    """Local access to the Disease Modeling Platform database."""
    
    def __init__(self):
        """Initialize the DMP local access."""
        self.db = StateMachineDB()
    
    def get_available_diseases(self) -> List[str]:
        """Get all available diseases in the database."""
        try:
            # Get unique diseases from the database
            saved_machines = self.db.list_state_machines()
            diseases = set()
            for machine in saved_machines:
                if machine[2]:  # disease_name
                    diseases.add(machine[2])
            return sorted(list(diseases))
        except Exception as e:
            print(f"Error getting diseases: {e}")
            return []
    
    def get_variants_for_disease(self, disease_name: str) -> List[str]:
        """Get variants for a specific disease."""
        try:
            saved_machines = self.db.list_state_machines()
            variants = set()
            for machine in saved_machines:
                if machine[2] == disease_name and machine[3]:  # disease_name and variant_name
                    variants.add(machine[3])
            return sorted(list(variants))
        except Exception as e:
            print(f"Error getting variants for {disease_name}: {e}")
            return []
    
    def find_matching_state_machine(self, disease_name: str, demographics: Dict[str, str], 
                                  model_path: Optional[str] = None) -> Optional[Dict]:
        """Find a matching state machine using new model_path logic with specificity prioritization."""
        try:
            # Import the disease configuration functions
            from app.state_machine.disease_configurations import (
                get_parent_model_path, get_default_model_path
            )
            
            saved_machines = self.db.list_state_machines()
            
            # Determine the model path to search for
            search_paths = []
            
            if model_path:
                # Start with the exact model path
                search_paths.append(model_path)
                
                # Add parent paths for fallback (e.g., variant.Delta if variant.Delta.general not found)
                current_path = model_path
                while True:
                    parent_path = get_parent_model_path(disease_name, current_path)
                    if parent_path:
                        search_paths.append(parent_path)
                        current_path = parent_path
                    else:
                        break
            
            # Add default model path as final fallback
            default_path = get_default_model_path(disease_name)
            if default_path and default_path not in search_paths:
                search_paths.append(default_path)
            
            print(f"Search paths (in order): {search_paths}")
            
            # Search for matching state machines using simple rules
            for search_path in search_paths:
                compatible_machines = []
                
                # First, collect all compatible machines for this search path
                for machine in saved_machines:
                    machine_data = self.db.load_state_machine(machine[0])
                    if not machine_data:
                        continue
                    
                    # Check disease name
                    if machine_data["disease_name"] != disease_name:
                        continue
                    
                    # Check if this machine matches the current search path
                    machine_model_path = machine_data.get("model_path", "default")
                    if machine_model_path != search_path:
                        continue
                    
                    # Simple demographic matching rules:
                    # 1. If machine has a demographic defined and it doesn't match request, skip this machine
                    # 2. If machine doesn't have a demographic defined, it's OK (wildcard)
                    # 3. If all demographics are compatible, use this machine
                    
                    machine_demographics = machine_data["demographics"]
                    demographics_compatible = True
                    
                    for key, value in demographics.items():
                        if key in machine_demographics:
                            # Machine has this demographic defined - must match
                            if key == "Age":
                                # Special handling for age range matching
                                if not self._age_in_range(str(value), machine_demographics[key]):
                                    demographics_compatible = False
                                    break
                            else:
                                # Normal demographic matching
                                if machine_demographics[key] != str(value):
                                    demographics_compatible = False
                                    break
                        # If machine doesn't have this demographic defined, it's OK (wildcard)
                    
                    if demographics_compatible:
                        compatible_machines.append(machine_data)
                
                # If we found compatible machines, pick the most specific one
                if compatible_machines:
                    # Sort by specificity: machines with more defined demographics are more specific
                    compatible_machines.sort(
                        key=lambda m: len([k for k in m["demographics"].keys() if m["demographics"][k] != "*"]),
                        reverse=True
                    )
                    
                    matching_machine = compatible_machines[0]
                    print(f"Found matching machine: {matching_machine['name']} with path: {search_path}")
                    print(f"Demographics: {matching_machine['demographics']}")
                    return matching_machine
            
            # No matching machine found
            print(f"No matching state machine found for {disease_name} with demographics {demographics}")
            return None
            
        except Exception as e:
            print(f"Error finding matching state machine: {e}")
            return None
    
    def _age_in_range(self, age_value: str, age_range: str) -> bool:
        """Check if a single age value falls within an age range"""
        try:
            # Convert age value to integer
            age = int(age_value)
            
            # Parse age range (e.g., "5-14", "65+", "0-18")
            if age_range == "*":
                return True
            
            if "+" in age_range:
                # Handle ranges like "65+"
                min_age = int(age_range.replace("+", ""))
                return age >= min_age
            
            if "-" in age_range:
                # Handle ranges like "5-14", "0-18"
                min_age, max_age = map(int, age_range.split("-"))
                return min_age <= age <= max_age
            
            # Single age value (e.g., "25")
            range_age = int(age_range)
            return age == range_age
            
        except (ValueError, TypeError):
            # If parsing fails, fall back to exact string matching
            return age_value == age_range
    
    def run_simulation(self, disease_name: str, demographics: Dict[str, str], 
                      model_path: Optional[str] = None,
                      initial_state: Optional[str] = None) -> Optional[Dict]:
        """Run a simulation using the state machine database."""
        try:
            # Find matching state machine
            state_machine = self.find_matching_state_machine(
                disease_name, demographics, model_path
            )
            
            if not state_machine:
                print(f"No matching state machine found for {disease_name} with demographics {demographics}")
                return None
            
            # Get states and edges
            states = state_machine["states"]
            edges = state_machine["edges"]
            
            # Convert to matrices
            matrices = convert_graph_to_matrices(states, edges)
            
            # Determine initial state
            if not initial_state:
                initial_state = states[0]  # Use first state as default
            
            initial_state_idx = states.index(initial_state)
            
            # Run simulation
            timeline = run_simulation(
        transition_matrix=matrices["Transition Matrix"],
                mean_matrix=matrices["Mean Matrix"],
                std_dev_matrix=matrices["Standard Deviation Matrix"],
                min_cutoff_matrix=matrices["Min Cutoff Matrix"],
                max_cutoff_matrix=matrices["Max Cutoff Matrix"],
                distribution_matrix=matrices["Distribution Type Matrix"],
                initial_state_idx=initial_state_idx,
        states=states
    )
    
            return {
                "success": True,
                "timeline": timeline,
                "total_duration": timeline[-1][1] if timeline else 0,
                "final_state": timeline[-1][0] if timeline else None,
                "states_visited": [entry[0] for entry in timeline],
                "state_machine": {
                    "id": state_machine.get("id"),
                    "name": state_machine.get("name"),
                    "disease_name": state_machine.get("disease_name"),
                    "model_path": state_machine.get("model_path", "default"),
                    "demographics": state_machine.get("demographics"),
                    "states": states
                }
            }
            
        except Exception as e:
            print(f"Error running simulation: {e}")
            return None
    
    def list_state_machines(self, disease_name: Optional[str] = None) -> List[Dict]:
        """List state machines with optional filtering."""
        try:
            saved_machines = self.db.list_state_machines()
            machines = []
            
            for machine in saved_machines:
                # Filter by disease if specified
                if disease_name and machine[2] != disease_name:
                    continue
                
                machine_data = self.db.load_state_machine(machine[0])
                if machine_data:
                    machines.append({
                        "id": machine[0],
                        "name": machine[1],
                        "disease_name": machine[2],
                        "variant_name": machine[3],
                        "model_category": machine[4],
                        "model_path": machine[5],  # New column
                        "created_at": machine[6],  # Updated index
                        "updated_at": machine[7],  # Updated index
                        "demographics": machine_data.get("demographics", {}),
                        "states": machine_data.get("states", [])
                    })
            
            return machines
        
        except Exception as e:
            print(f"Error listing state machines: {e}")
            return []

def main():
    """Command line interface for the DMP local module."""
    parser = argparse.ArgumentParser(description="Disease Modeling Platform - Local Access")
    parser.add_argument("--action", required=True, 
                       choices=["list-diseases", "list-variants", "list-machines", "simulate"],
                       help="Action to perform")
    parser.add_argument("--disease", help="Disease name")
    parser.add_argument("--demographics", help="Demographics as JSON string")
    parser.add_argument("--model-path", help="Model path (e.g., 'variant.Delta.general', 'vaccination.Unvaccinated.general')")
    parser.add_argument("--initial-state", help="Initial state for simulation")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    dmp = DMPLocal()
    
    if args.action == "list-diseases":
        diseases = dmp.get_available_diseases()
        print("Available diseases:")
        for disease in diseases:
            print(f"  - {disease}")
    
    elif args.action == "list-variants":
        if not args.disease:
            print("Error: --disease is required for list-variants")
            return
        variants = dmp.get_variants_for_disease(args.disease)
        print(f"Variants for {args.disease}:")
        for variant in variants:
            print(f"  - {variant}")
    
    elif args.action == "list-machines":
        machines = dmp.list_state_machines(args.disease)
        print(f"State machines{f' for {args.disease}' if args.disease else ''}:")
        for machine in machines:
            print(f"  - {machine['name']} (ID: {machine['id']})")
    
    elif args.action == "simulate":
        if not args.disease or not args.demographics:
            print("Error: --disease and --demographics are required for simulate")
            return
        
        try:
            demographics = json.loads(args.demographics)
        except json.JSONDecodeError:
            print("Error: --demographics must be valid JSON")
            return
        
        result = dmp.run_simulation(
            disease_name=args.disease,
            demographics=demographics,
            model_path=args.model_path,
            initial_state=args.initial_state
        )
        
        if result:
            print("Simulation successful!")
            print(f"State machine: {result['state_machine']['name']}")
            print(f"Model path: {result['state_machine']['model_path']}")
            print("\nTimeline:")
            for state, time in result['timeline']:
                print(f"  {time:>6.1f} hours: {state}")
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\nResults saved to: {args.output}")
        else:
            print("Simulation failed!")

if __name__ == "__main__":
    main()

