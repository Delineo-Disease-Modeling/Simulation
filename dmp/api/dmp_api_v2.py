from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import pandas as pd
import os
import sys
from pathlib import Path
import json

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
    variant_name: Optional[str] = Field(
        None,
        description="Variant name (optional)"
    )
    model_category: Optional[str] = Field(
        "default",
        description="Model category: 'default', 'variant', or 'vaccination'"
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
        print(f"Variant: {request.variant_name}")
        print(f"Model category: {request.model_category}")
        
        # Find matching state machine with model category-based hierarchical fallback
        saved_machines = db.list_state_machines()
        matching_machine = None
        best_match_score = -1
        
        for machine in saved_machines:
            machine_data = db.load_state_machine(machine[0])
            if not machine_data:
                continue
            
            # Check disease name
            if machine_data["disease_name"] != request.disease_name:
                continue
            
            # Check variant if specified
            if request.variant_name and machine_data.get("variant_name") != request.variant_name:
                continue
            
            # Check model category
            if request.model_category and machine_data.get("model_category") != request.model_category:
                continue
            
            # Model category-based hierarchical matching
            machine_demographics = machine_data["demographics"]
            match_score = 0
            demographics_match = True
            
            if machine_data.get("model_category") == "vaccination":
                # Vaccination models require vaccination status matching
                machine_name = machine_data.get("name", "")
                if "vaccination=" in machine_name:
                    vaccination_part = machine_name.split("vaccination=")[-1].split(" |")[0]
                    request_vaccination = request.demographics.get("Vaccination Status")
                    
                    if request_vaccination:
                        if vaccination_part == request_vaccination:
                            # Vaccination status matches - now check other demographics
                            match_score = 100  # Start with full score for vaccination match
                            
                            # Check other demographics (Age, Sex, etc.)
                            for key, value in request.demographics.items():
                                if key != "Vaccination Status" and key in machine_demographics:
                                    if key == "Age":
                                        # Special handling for age range matching
                                        if machine_demographics[key] == "*":
                                            pass  # Wildcard accepts any age
                                        elif not _age_in_range(str(value), machine_demographics[key]):
                                            # Age doesn't match range
                                            demographics_match = False
                                            break
                                    else:
                                        # Normal demographic matching for non-age fields
                                        if machine_demographics[key] != "*" and machine_demographics[key] != str(value):
                                            # Specific demographic doesn't match
                                            demographics_match = False
                                            break
                                elif key != "Vaccination Status":
                                    # Demographics not specified in machine - neutral
                                    pass
                            
                            # Score based on how many demographics are specified in the machine
                            specified_demographics = len([k for k in machine_demographics.keys() if k != "Vaccination Status"])
                            request_demographics = len([k for k in request.demographics.keys() if k != "Vaccination Status"])
                            
                            if request_demographics == 0:
                                # No demographics in request - prefer general models
                                if specified_demographics == 0:
                                    match_score = 100  # Perfect match: general request, general model
                                else:
                                    match_score = 50   # General request, specific model
                            else:
                                # Demographics in request - prefer specific models
                                if specified_demographics > 0:
                                    match_score = 100  # Specific request, specific model
                                else:
                                    match_score = 50   # Specific request, general model (fallback)
                        else:
                            # Vaccination status doesn't match - skip this machine
                            continue
                    else:
                        # No vaccination status in request - skip vaccination models
                        continue
                else:
                    # No vaccination status in machine name - skip
                    continue
            else:
                # Default models - vaccination status doesn't matter
                # Check demographics normally
                total_demographics = len([k for k in request.demographics.keys() if k != "Vaccination Status"])
                if total_demographics == 0:
                    match_score = 100  # No demographics to match
                else:
                    matched_demographics = 0
                    for key, value in request.demographics.items():
                        if key != "Vaccination Status":  # Ignore vaccination status for default models
                            if key in machine_demographics:
                                if key == "Age":
                                    # Special handling for age range matching
                                    if machine_demographics[key] == "*":
                                        matched_demographics += 0.5
                                    elif _age_in_range(str(value), machine_demographics[key]):
                                        matched_demographics += 1.0
                                    else:
                                        demographics_match = False
                                        break
                                else:
                                    # Normal demographic matching for non-age fields
                                    if machine_demographics[key] == "*":
                                        matched_demographics += 0.5
                                    elif machine_demographics[key] == str(value):
                                        matched_demographics += 1.0
                                    else:
                                        demographics_match = False
                                        break
                            else:
                                matched_demographics += 0.5
                    
                    if demographics_match:
                        match_score = (matched_demographics / total_demographics) * 100
            
            # Update best match if this machine has a higher score
            if demographics_match and match_score > best_match_score:
                matching_machine = machine_data
                best_match_score = match_score
                print(f"DEBUG: Selected machine '{machine_data.get('name')}' with score {match_score}")
            elif demographics_match:
                print(f"DEBUG: Skipped machine '{machine_data.get('name')}' with score {match_score} (best: {best_match_score})")
        
        if not matching_machine:
            raise HTTPException(
                status_code=404,
                detail=f"No matching state machine found for disease '{request.disease_name}' with the provided demographics"
            )
        
        # Convert graph to matrices
        matrices = convert_graph_to_matrices(
            matching_machine["states"], 
            matching_machine["edges"]
        )
        
        # Determine initial state
        initial_state_idx = 0
        if request.initial_state:
            if request.initial_state in matching_machine["states"]:
                initial_state_idx = matching_machine["states"].index(request.initial_state)
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Initial state '{request.initial_state}' not found in state machine"
                )
        
        # Run simulation
        simulation_data = run_simulation(
            transition_matrix=matrices["Transition Matrix"],
            mean_matrix=matrices["Mean Matrix"],
            std_dev_matrix=matrices["Standard Deviation Matrix"],
            min_cutoff_matrix=matrices["Min Cutoff Matrix"],
            max_cutoff_matrix=matrices["Max Cutoff Matrix"],
            distribution_matrix=matrices["Distribution Type Matrix"],
            initial_state_idx=initial_state_idx,
            states=matching_machine["states"]
        )
        
        # Format timeline for response
        timeline = [(state, time) for state, time in simulation_data]
        
        return {
            "status": "success",
            "timeline": timeline,
            "state_machine": {
                "id": matching_machine["id"],
                "name": matching_machine["name"],
                "disease_name": matching_machine["disease_name"],
                "variant_name": matching_machine.get("variant_name"),
                "model_category": matching_machine.get("model_category"),
                "demographics": matching_machine["demographics"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error during simulation: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error during simulation: {str(e)}"
        )

# Add error handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    print(f"Unhandled error: {str(exc)}")
    return {"detail": str(exc)} 