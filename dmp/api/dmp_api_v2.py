from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import pandas as pd
from pathlib import Path
import json
import time

from dmp.core.simulation_functions import run_simulation
from dmp.app.state_machine.state_machine_db import StateMachineDB
from dmp.app.state_machine.utils.graph_utils import convert_graph_to_matrices
from dmp.app.state_machine.state_machine_matching import find_matching_state_machine

app = FastAPI(
    title="Disease Modeling Platform API v2.0",
    description="API for state machine database-based disease modeling",
    version="2.0.0"
)

# Initialize database connection
db = StateMachineDB()


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
        
        # Find the matching state machine (shared with the in-process engine path
        # so the two cannot diverge); a None result becomes the 404 below.
        matching_machine = find_matching_state_machine(
            db, request.disease_name, request.demographics, request.model_path
        )

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
