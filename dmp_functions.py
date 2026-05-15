import io
import os
import pandas as pd
from pathlib import Path

from simulation_functions import run_simulation
from user_input import find_matching_matrix, parse_mapping_file, extract_matrices

DEFAULT_STATES_PATH = Path(__file__).resolve().parent / ".." / "data" / "default_states.txt"
_BUNDLED_STATES_PATH = Path(__file__).resolve().parent / "simulator" / "config_data" / "custom_states.txt"
_BUNDLED_MAPPING_PATH = Path(__file__).resolve().parent / "simulator" / "config_data" / "demographic_mapping.csv"

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


def initialize_dmp_from_string(context: DMPContext, matrix_csv_content: str, states_path: str = None):
    """Initialize a DMPContext from an in-memory CSV string.

    Comment lines (starting with #) are parsed as demographic headers in the form:
        # Age, Vaccination Status, Sex, Variant
    One comment per matrix block; these are used to build an in-memory mapping.
    If no comment headers are present the bundled demographic_mapping.csv is used.
    """
    lines = matrix_csv_content.split('\n')
    comments = []
    data_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            parts = [p.strip() for p in stripped[1:].split(',')]
            if len(parts) >= 4:
                comments.append(parts[:4])
        elif stripped:
            data_lines.append(line)

    if not data_lines:
        raise ValueError("CSV content contains no data rows.")

    context.matrix_df = pd.read_csv(
        io.StringIO('\n'.join(data_lines)),
        header=None,
        skipinitialspace=True
    )

    resolved_states_path = states_path or (
        str(_BUNDLED_STATES_PATH) if _BUNDLED_STATES_PATH.exists() else str(DEFAULT_STATES_PATH)
    )
    if not os.path.exists(resolved_states_path):
        raise FileNotFoundError(f"States file not found: {resolved_states_path}")

    with open(resolved_states_path, 'r') as f:
        context.states = [line.strip() for line in f if line.strip()]

    if not context.states:
        raise ValueError("States file is empty.")

    if comments:
        rows = [
            {
                'Age': p[0],
                'Vaccination Status': p[1],
                'Sex': p[2],
                'Variant': p[3],
                'Matrix_Set': f'Matrix_Set_{i + 1}'
            }
            for i, p in enumerate(comments)
        ]
        context.mapping_df = pd.DataFrame(rows)
        context.demographic_categories = ['Age', 'Vaccination Status', 'Sex', 'Variant']
    else:
        if not _BUNDLED_MAPPING_PATH.exists():
            raise FileNotFoundError(f"Default mapping file not found: {_BUNDLED_MAPPING_PATH}")
        context.mapping_df, context.demographic_categories = parse_mapping_file(str(_BUNDLED_MAPPING_PATH))
