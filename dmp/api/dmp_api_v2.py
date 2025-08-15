from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import pandas as pd
import os
import sys
from pathlib import Path
import json
import time

# Add the parent directory to the Python path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from core.simulation_functions import run_simulation
from app.state_machine.state_machine_db import StateMachineDB
from app.state_machine.utils.graph_utils import convert_graph_to_matrices

app = FastAPI(
    title="Disease Modeling Platform API v2.0",
    description="API for state machine database-based disease modeling",
    version="2.0.0"
)

# Initialize database connection
db = StateMachineDB()

def _age_in_range(age_value: str, age_range: str) -> bool:
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

class SimulationRequest(BaseModel):
    demographics: Dict[str, str] = Field(
        ..., 
        description="Dictionary of demographic values"
    )
    disease_name: str = Field(
        ...,
        description="Disease name (required)"
    )
    model_path: Optional[str] = Field(
        None,
        description="Model path in dot notation (e.g., 'variant.Delta.general', 'vaccination.Unvaccinated.general'). The .general suffix is a placeholder for any future subcategory expansion."
    )
    initial_state: Optional[str] = Field(
        None,
        description="Initial state for simulation (defaults to first state)"
    )

class StateMachineInfo(BaseModel):
    id: int
    name: str
    disease_name: str
    variant_name: Optional[str]
    model_category: str
    demographics: Dict[str, str]
    states: List[str]
    created_at: str
    updated_at: str

@app.get("/")
async def root():
    """API root endpoint with system information"""
    return {
        "message": "Disease Modeling Platform API v2.0",
        "version": "2.0.0",
        "description": "State machine database-based disease modeling API",
        "endpoints": {
            "GET /": "API information",
            "GET /diseases": "List all available diseases",
            "GET /diseases/{disease_name}/variants": "Get variants for a disease",
            "GET /state-machines": "List all state machines",
            "GET /state-machines/{machine_id}": "Get specific state machine",
            "POST /simulate": "Run simulation"
        }
    }

@app.get("/diseases")
async def get_diseases():
    """Get all available diseases in the state machine database"""
    try:
        diseases = db.get_unique_diseases()
        return {
            "status": "success",
            "diseases": diseases
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving diseases: {str(e)}"
        )

@app.get("/diseases/{disease_name}/variants")
async def get_variants(disease_name: str):
    """Get all variants for a specific disease"""
    try:
        variants = db.get_variants_for_disease(disease_name)
        return {
            "status": "success",
            "disease": disease_name,
            "variants": variants
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving variants: {str(e)}"
        )

@app.get("/state-machines")
async def list_state_machines(
    disease_name: Optional[str] = None,
    model_category: Optional[str] = None
):
    """List all state machines with optional filtering"""
    try:
        saved_machines = db.list_state_machines()
        machines = []
        
        for machine in saved_machines:
            # Apply filters
            if disease_name and machine[2] != disease_name:
                continue
            if model_category and machine[4] != model_category:
                continue
            
            machine_data = db.load_state_machine(machine[0])
            if machine_data:
                machines.append(StateMachineInfo(
                    id=machine[0],
                    name=machine_data["name"],
                    disease_name=machine_data["disease_name"],
                    variant_name=machine_data.get("variant_name"),
                    model_category=machine_data.get("model_category", "default"),
                    demographics=machine_data["demographics"],
                    states=machine_data["states"],
                    created_at=machine[5],
                    updated_at=machine[6]
                ))
        
        return {
            "status": "success",
            "state_machines": [machine.dict() for machine in machines]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error listing state machines: {str(e)}"
        )

@app.get("/state-machines/{machine_id}")
async def get_state_machine(machine_id: int):
    """Get detailed information about a specific state machine"""
    try:
        machine_data = db.load_state_machine(machine_id)
        if not machine_data:
            raise HTTPException(
                status_code=404,
                detail=f"State machine with ID {machine_id} not found"
            )
        
        return {
            "status": "success",
            "state_machine": machine_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving state machine: {str(e)}"
        )

@app.post("/simulate")
async def run_dmp_simulation(request: SimulationRequest):
    """Run simulation with provided demographics and disease parameters"""
    try:
        print(f"Running simulation for disease: {request.disease_name}")
        print(f"Demographics: {request.demographics}")
        print(f"Model path: {request.model_path}")
        
        # Import the disease configuration functions
        from app.state_machine.disease_configurations import (
            validate_model_path, get_parent_model_path, get_default_model_path,
            get_model_info
        )
        
        # Find matching state machine with simple, clear fallback rules
        saved_machines = db.list_state_machines()
        matching_machine = None
        
        # Determine the model path to search for
        search_paths = []
        
        if request.model_path:
            # Start with the exact model path
            search_paths.append(request.model_path)
            
            # Add parent paths for fallback (e.g., variant.Delta if variant.Delta.general not found)
            current_path = request.model_path
            while True:
                parent_path = get_parent_model_path(request.disease_name, current_path)
                if parent_path:
                    search_paths.append(parent_path)
                    current_path = parent_path
                else:
                    break
        
        # Add default model path as final fallback
        default_path = get_default_model_path(request.disease_name)
        if default_path and default_path not in search_paths:
            search_paths.append(default_path)
        
        print(f"Search paths (in order): {search_paths}")
        
        # Search for matching state machines using simple rules
        for search_path in search_paths:
            compatible_machines = []
            
            # First, collect all compatible machines for this search path
            for machine in saved_machines:
                machine_data = db.load_state_machine(machine[0])
                if not machine_data:
                    continue
                
                # Check disease name
                if machine_data["disease_name"] != request.disease_name:
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
                
                for key, value in request.demographics.items():
                    if key in machine_demographics:
                        # Machine has this demographic defined - must match
                        if key == "Age":
                            # Special handling for age range matching
                            if not _age_in_range(str(value), machine_demographics[key]):
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
                break
        
        if not matching_machine:
            # No matching state machine found
            error_msg = f"No matching state machine found for disease '{request.disease_name}'"
            if request.model_path:
                error_msg += f" with model path '{request.model_path}'"
            if request.demographics:
                error_msg += f" and demographics {request.demographics}"
            
            raise HTTPException(
                status_code=404,
                detail=error_msg
            )
        
        # Run simulation with the matching state machine
        states = matching_machine["states"]
        edges = matching_machine["edges"]
        
        # Convert graph to matrices
        matrices = convert_graph_to_matrices(states, edges)
        
        # Determine initial state
        initial_state_idx = 0
        if request.initial_state:
            if request.initial_state in states:
                initial_state_idx = states.index(request.initial_state)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Initial state '{request.initial_state}' not found in state machine states: {states}"
                )
        
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
            "simulation_id": f"sim_{matching_machine['id']}_{int(time.time())}",
            "model_path": matching_machine.get("model_path", "default"),
            "timeline": timeline,
            "total_duration": timeline[-1][1] if timeline else 0,
            "final_state": timeline[-1][0] if timeline else None,
            "states_visited": [entry[0] for entry in timeline],
            "state_machine": {
                "id": matching_machine["id"],
                "name": matching_machine["name"],
                "disease_name": matching_machine["disease_name"],
                "model_path": matching_machine.get("model_path", "default"),
                "demographics": matching_machine["demographics"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Add error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    print(f"Unhandled error: {str(exc)}")
    return {"detail": str(exc)} 