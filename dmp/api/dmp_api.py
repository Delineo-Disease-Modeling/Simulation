from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import pandas as pd
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

from core.simulation_functions import run_simulation
from cli.user_input import find_matching_matrix, parse_mapping_file, extract_matrices

app = FastAPI()

# Global variables to store configuration
matrix_df = None
mapping_df = None
states = None
demographic_categories = None

# Path to default states file
DEFAULT_STATES_PATH = Path(parent_dir) / "data" / "default_states.txt"

class InitConfig(BaseModel):
    matrices_path: str
    mapping_path: str
    states_path: Optional[str] = None

class SimulationRequest(BaseModel):
    demographics: Dict[str, str] = Field(
        ..., 
        description="Dictionary of demographic values matching the mapping file columns"
    )

@app.post("/initialize")
async def initialize_dmp(config: InitConfig):
    """Initialize DMP with configuration files"""
    global matrix_df, mapping_df, states, demographic_categories
    
    try:
        print(f"Initializing DMP with:")
        print(f"Matrices path: {config.matrices_path}")
        print(f"Mapping path: {config.mapping_path}")
        print(f"States path: {config.states_path or DEFAULT_STATES_PATH}")
        
        # Verify files exist
        if not os.path.exists(config.matrices_path):
            raise FileNotFoundError(f"Matrix file not found: {config.matrices_path}")
        if not os.path.exists(config.mapping_path):
            raise FileNotFoundError(f"Mapping file not found: {config.mapping_path}")
        
        # Load matrices with explicit delimiter, no header, and skip comment lines
        matrix_df = pd.read_csv(config.matrices_path, header=None, sep=',', skipinitialspace=True, comment='#')
        print(f"Loaded matrix file with shape: {matrix_df.shape}")
        
        # Load mapping and get demographic categories using existing function
        mapping_df, demographic_categories = parse_mapping_file(config.mapping_path)
        print(f"Loaded mapping file with categories: {demographic_categories}")
        
        # Load states from file (custom or default)
        states_path = config.states_path if config.states_path else DEFAULT_STATES_PATH
        if not os.path.exists(states_path):
            raise FileNotFoundError(f"States file not found: {states_path}")
            
        with open(states_path, 'r') as f:
            states = [line.strip() for line in f if line.strip()]
        
        if not states:
            raise ValueError("States file is empty")
            
        print(f"Using states from {states_path}: {states}")
        
        # Get available demographics using the mapping DataFrame
        available_demographics = {
            category: mapping_df[category].unique().tolist()
            for category in demographic_categories
        }
        
        return {
            "status": "success", 
            "states": states,
            "demographics": available_demographics
        }
        
    except Exception as e:
        print(f"Error during initialization: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Error during initialization: {str(e)}"
        )

@app.post("/simulate")
async def run_dmp_simulation(request: SimulationRequest):
    """Run simulation with provided demographics"""
    if matrix_df is None or mapping_df is None or states is None:
        raise HTTPException(status_code=400, detail="DMP not initialized. Call /initialize first")
    
    try:
        print(f"Running simulation with demographics: {request.demographics}")
        
        # Find matching matrix set using existing function
        try:
            matching_set = find_matching_matrix(request.demographics, mapping_df, demographic_categories)
            if not matching_set:
                # If no match found, use Matrix_Set_1 as default
                matching_set = "Matrix_Set_1"
                print(f"No matching matrix set found, using default: {matching_set}")
        except ValueError:
            # If error occurs during matching, use Matrix_Set_1 as default
            matching_set = "Matrix_Set_1"
            print(f"Error during matrix matching, using default: {matching_set}")
            
        print(f"Using matrix set: {matching_set}")
        
        # Extract matrices using existing function
        matrices = extract_matrices(matching_set, matrix_df, len(states))
        
        # Run simulation
        initial_state_idx = 0  # Assuming first state is always the initial state
        simulation_data = run_simulation(
            matrices["Transition Matrix"],
            matrices["Mean"],
            matrices["Standard Deviation"],
            matrices["Min Cut-Off"],
            matrices["Max Cut-Off"],
            matrices["Distribution Type"],
            initial_state_idx,
            states
        )
        
        # Format timeline for response
        timeline = [(state, time) for state, time in simulation_data]
        
        # Print simple timeline in hours
        print("\nTimeline (hours):")
        for state, time in timeline:
            hours = time
            print(f"{hours:.2f} hours: {state}")
        
        return {
            "status": "success",
            "timeline": timeline,
            "matrix_set": matching_set
        }
        
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