import os
import pandas as pd
from pathlib import Path

from simulation_functions import run_simulation
from user_input import find_matching_matrix, parse_mapping_file, extract_matrices

DEFAULT_STATES_PATH = Path(__file__).resolve().parent / ".." / "data" / "default_states.txt"

class DMPContext:
    def __init__(self):
        self.matrix_df = None
        self.mapping_df = None
        self.states = None
        self.demographic_categories = None

def initialize_dmp(context: DMPContext, matrices_path: str, mapping_path: str, states_path: str = None):
    print(f"Initializing DMP:")
    print(f"Matrices path: {matrices_path}")
    print(f"Mapping path: {mapping_path}")
    print(f"States path: {states_path or DEFAULT_STATES_PATH}")
    
    if not os.path.exists(matrices_path):
        raise FileNotFoundError(f"Matrix file not found: {matrices_path}")
    if not os.path.exists(mapping_path):
        raise FileNotFoundError(f"Mapping file not found: {mapping_path}")
    
    context.matrix_df = pd.read_csv(matrices_path, header=None, sep=',', skipinitialspace=True, comment='#')
    print(f"Loaded matrix file with shape: {context.matrix_df.shape}")
    
    context.mapping_df, context.demographic_categories = parse_mapping_file(mapping_path)
    
    states_path = states_path or DEFAULT_STATES_PATH
    if not os.path.exists(states_path):
        raise FileNotFoundError(f"States file not found: {states_path}")
    
    with open(states_path, 'r') as f:
        context.states = [line.strip() for line in f if line.strip()]
    
    if not context.states:
        raise ValueError("States file is empty")
    
    available_demographics = {
        category: context.mapping_df[category].unique().tolist()
        for category in context.demographic_categories
    }

    return {
        "status": "success",
        "states": context.states,
        "demographics": available_demographics
    }

def run_dmp_simulation(context: DMPContext, demographics: dict):
    if context.matrix_df is None or context.mapping_df is None or context.states is None:
        raise ValueError("DMP not initialized. Please call `initialize_dmp` first.")
    
    print(f"Running simulation with demographics: {demographics}")
    
    try:
        matching_set = find_matching_matrix(demographics, context.mapping_df, context.demographic_categories)
        if not matching_set:
            matching_set = "Matrix_Set_1"
            print(f"No matching matrix set found. Using default: {matching_set}")
    except ValueError:
        matching_set = "Matrix_Set_1"
        print(f"Error during matrix matching. Using default: {matching_set}")
    
    matrices = extract_matrices(matching_set, context.matrix_df, len(context.states))
    
    simulation_data = run_simulation(
        matrices["Transition Matrix"],
        matrices["Mean"],
        matrices["Standard Deviation"],
        matrices["Min Cut-Off"],
        matrices["Max Cut-Off"],
        matrices["Distribution Type"],
        0,
        context.states
    )
    
    timeline = [(state, time) for state, time in simulation_data]
    
    print("\nTimeline (hours):")
    for state, time in timeline:
        print(f"{time:.2f} hours: {state}")
    
    return {
        "status": "success",
        "timeline": timeline,
        "matrix_set": matching_set
    }
