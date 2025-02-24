from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import pandas as pd
import os
import sys

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.simulation_functions import run_simulation

app = FastAPI()

# Global variables to store configuration
matrix_df = None
mapping_df = None
states = None

class InitConfig(BaseModel):
    matrices_path: str
    mapping_path: str
    states_path: Optional[str] = None

class Demographics(BaseModel):
    age: int
    sex: str
    vaccination_status: str
    variant: str

@app.post("/initialize")
async def initialize_dmp(config: InitConfig):
    """Initialize DMP with configuration files"""
    global matrix_df, mapping_df, states
    
    try:
        # Load matrices
        matrix_df = pd.read_csv(config.matrices_path, header=None)
        
        # Load mapping
        mapping_df = pd.read_csv(config.mapping_path, skipinitialspace=True)
        
        # Load states if provided, otherwise use defaults
        if config.states_path:
            with open(config.states_path, 'r') as f:
                states = [line.strip() for line in f if line.strip()]
        else:
            states = ["Infected", "Infectious_Asymptomatic", "Infectious_Symptomatic", 
                     "Hospitalized", "ICU", "Recovered", "Deceased"]
        
        return {
            "status": "success",
            "message": "DMP initialized successfully",
            "states": states,
            "available_demographics": get_available_demographics()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_available_demographics():
    """Get available demographic options from mapping file"""
    demographics = {}
    for col in mapping_df.columns:
        if col != "Matrix_Set":
            unique_values = mapping_df[col].unique()
            valid_values = [str(v).strip() for v in unique_values if v != "*" and pd.notna(v)]
            demographics[col] = valid_values
    return demographics

@app.post("/simulate")
async def run_dmp_simulation(demographics: Demographics):
    """Run a single simulation with given demographics"""
    global matrix_df, mapping_df, states
    
    if matrix_df is None or mapping_df is None or states is None:
        raise HTTPException(status_code=400, detail="DMP not initialized. Call /initialize first")
    
    try:
        # Find matching matrix set
        matching_set = find_matching_matrix_set(demographics)
        if not matching_set:
            raise ValueError("No matching matrix set found for given demographics")
            
        # Extract matrices for the matching set
        matrices = extract_matrices(matching_set, matrix_df, len(states))
        
        # Run simulation
        timeline = run_simulation(
            matrices["Transition Matrix"],
            matrices["Mean"],
            matrices["Standard Deviation"],
            matrices["Min Cut-Off"],
            matrices["Max Cut-Off"],
            matrices["Distribution Type"],
            states.index("Infected"),  # Initial state
            states
        )
        
        return {
            "status": "success",
            "timeline": timeline,
            "matrix_set": matching_set
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def find_matching_matrix_set(demographics: Demographics):
    """Find matching matrix set from mapping file"""
    for _, row in mapping_df.iterrows():
        if matches_demographics(row, demographics):
            return row["Matrix_Set"]
    return None

def matches_demographics(row, demographics: Demographics):
    """Check if row matches given demographics"""
    # Handle age ranges
    age_range = row["Age Range"]
    if age_range != "*":
        if age_range.endswith('+'):
            min_age = int(age_range[:-1])
            if demographics.age < min_age:
                return False
        else:
            start, end = map(int, age_range.split('-'))
            if not (start <= demographics.age <= end):
                return False
    
    # Check other demographics
    if (row["Sex"] != "*" and row["Sex"] != demographics.sex) or \
       (row["Vaccination Status"] != "*" and row["Vaccination Status"] != demographics.vaccination_status) or \
       (row["Variant"] != "*" and row["Variant"] != demographics.variant):
        return False
    
    return True

def extract_matrices(matrix_set: str, matrix_df: pd.DataFrame, num_states: int):
    """Extract matrices for given set"""
    matrix_set_id = int(matrix_set.split('_')[-1])
    start_row = (matrix_set_id - 1) * (num_states * 6)
    
    matrices = {}
    matrix_types = [
        "Transition Matrix",
        "Distribution Type",
        "Mean",
        "Standard Deviation",
        "Min Cut-Off",
        "Max Cut-Off"
    ]
    
    for i, matrix_type in enumerate(matrix_types):
        matrix_start = start_row + (i * num_states)
        matrix_end = matrix_start + num_states
        matrix = matrix_df.iloc[matrix_start:matrix_end, :num_states].values
        matrices[matrix_type] = matrix
    
    return matrices 