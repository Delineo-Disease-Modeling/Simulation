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
                                  variant_name: Optional[str] = None, 
                                  model_category: Optional[str] = None) -> Optional[Dict]:
        """Find a matching state machine based on disease and demographics."""
        try:
            saved_machines = self.db.list_state_machines()
            
            # Filter by disease name
            candidates = [machine for machine in saved_machines if machine[2] == disease_name]
            
            # Filter by variant if specified
            if variant_name:
                candidates = [machine for machine in candidates if machine[3] == variant_name]
            
            # Filter by model category if specified
            if model_category:
                candidates = [machine for machine in candidates if machine[4] == model_category]
            
            # Find best match based on demographics
            best_match = None
            best_score = 0
            
            for machine in candidates:
                machine_data = self.db.load_state_machine(machine[0])
                if not machine_data:
                    continue
                
                machine_demographics = machine_data.get("demographics", {})
                score = self._calculate_demographic_match(demographics, machine_demographics)
                
                if score > best_score:
                    best_score = score
                    best_match = machine_data
            
            return best_match
            
        except Exception as e:
            print(f"Error finding matching state machine: {e}")
            return None
    
    def _calculate_demographic_match(self, input_demographics: Dict[str, str], 
                                   machine_demographics: Dict[str, str]) -> int:
        """Calculate how well demographics match (higher score = better match)."""
        score = 0
        
        for key, input_value in input_demographics.items():
            machine_value = machine_demographics.get(key, "*")
            
            # Wildcard matches everything
            if machine_value == "*":
                score += 1
            # Exact match
            elif machine_value == input_value:
                score += 2
            # Range matching (e.g., "0-4" matches "3")
            elif "-" in machine_value:
                try:
                    range_start, range_end = map(int, machine_value.split("-"))
                    input_num = int(input_value)
                    if range_start <= input_num <= range_end:
                        score += 2
                except ValueError:
                    pass
            # "N+" format (e.g., "65+" matches "70")
            elif machine_value.endswith("+"):
                try:
                    min_value = int(machine_value.rstrip("+"))
                    input_num = int(input_value)
                    if input_num >= min_value:
                        score += 2
                except ValueError:
                    pass
        
        return score
    
    def run_simulation(self, disease_name: str, demographics: Dict[str, str], 
                      variant_name: Optional[str] = None, 
                      model_category: Optional[str] = None,
                      initial_state: Optional[str] = None) -> Optional[Dict]:
        """Run a simulation using the state machine database."""
        try:
            # Find matching state machine
            state_machine = self.find_matching_state_machine(
                disease_name, demographics, variant_name, model_category
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
                "status": "success",
                "timeline": timeline,
                "state_machine": {
                    "id": state_machine.get("id"),
                    "name": state_machine.get("name"),
                    "disease_name": state_machine.get("disease_name"),
                    "variant_name": state_machine.get("variant_name"),
                    "model_category": state_machine.get("model_category"),
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
                        "created_at": machine[5],
                        "updated_at": machine[6],
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
    parser.add_argument("--variant", help="Variant name (for COVID-19)")
    parser.add_argument("--model-category", help="Model category")
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
            variant_name=args.variant,
            model_category=args.model_category,
            initial_state=args.initial_state
        )
        
        if result:
            print("Simulation successful!")
            print(f"State machine: {result['state_machine']['name']}")
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

