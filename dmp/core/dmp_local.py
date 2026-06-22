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
from app.state_machine.state_machine_matching import find_matching_state_machine as _shared_find_matching_state_machine

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
        """Find a matching state machine using model_path logic with specificity prioritization.

        Delegates to the shared matcher (state_machine.state_machine_matching) so the
        in-process path and the HTTP API stay in lockstep. Errors are swallowed to
        None here, preserving this path's historical behavior.
        """
        try:
            return _shared_find_matching_state_machine(
                self.db, disease_name, demographics, model_path
            )
        except Exception as e:
            print(f"Error finding matching state machine: {e}")
            return None

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

