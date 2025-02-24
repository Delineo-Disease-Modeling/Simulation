import pandas as pd
import numpy as np
from Simulation.dmp.core.simulation_functions import run_simulation, default_initial_state, visualize_state_timeline, states
import os
import streamlit as st

def validate_matrix_shape(matrix, expected_shape=None, matrix_name="Matrix"):
    """Validates matrix shape against number of states"""
    if expected_shape is None:
        return  # Skip validation if no shape specified
    if matrix.shape != expected_shape:
        raise ValueError(f"{matrix_name} must be of shape {expected_shape}. Current shape is {matrix.shape}.")

def validate_values_in_range(matrix, min_value, max_value, matrix_name="Matrix"):
    if not ((matrix >= min_value) & (matrix <= max_value)).all():
        raise ValueError(f"All values in {matrix_name} must be between {min_value} and {max_value}.")

def validate_row_sums(matrix, expected_sum=1, matrix_name="Transition Matrix"):
    row_sums = matrix.sum(axis=1)
    for i, row_sum in enumerate(row_sums):
        if not (np.isclose(row_sum, expected_sum, atol=1e-6) or np.isclose(row_sum, 0, atol=1e-6)):
            raise ValueError(f"Each row in the {matrix_name} must sum to {expected_sum} or be 0 for terminal states. Row sums: {row_sums}")

def validate_distribution_type(matrix):
    valid_types = [0, 1, 2, 3, 4, 5]
    if not np.isin(matrix, valid_types).all():
        raise ValueError(f"Distribution Type matrix must contain only the values {valid_types}.")

def validate_matrices(transition_matrix, mean_matrix, std_dev_matrix, min_cutoff_matrix, max_cutoff_matrix, distribution_matrix):
    """
    Validates all the matrices with the updated rule that if a transition probability is 0,
    corresponding values in other matrices are allowed to be 0 but not required to be.
    """

    # Validate transition matrix
    validate_matrix_shape(transition_matrix, matrix_name="Transition Matrix")
    validate_values_in_range(transition_matrix, 0, 1, matrix_name="Transition Matrix")
    validate_row_sums(transition_matrix)

    # Validate mean and standard deviation matrices
    validate_matrix_shape(mean_matrix, matrix_name="Mean Matrix")
    validate_matrix_shape(std_dev_matrix, matrix_name="Standard Deviation Matrix")
    validate_values_in_range(mean_matrix, 0, float('inf'), matrix_name="Mean Matrix")
    validate_values_in_range(std_dev_matrix, 0, float('inf'), matrix_name="Standard Deviation Matrix")

    # Validate cutoff matrices
    validate_matrix_shape(min_cutoff_matrix, matrix_name="Min Cutoff Matrix")
    validate_matrix_shape(max_cutoff_matrix, matrix_name="Max Cutoff Matrix")
    validate_values_in_range(min_cutoff_matrix, 0, float('inf'), matrix_name="Min Cutoff Matrix")
    validate_values_in_range(max_cutoff_matrix, 0, float('inf'), matrix_name="Max Cutoff Matrix")
    if not (max_cutoff_matrix >= min_cutoff_matrix).all():
        raise ValueError("Max Cutoff matrix must have values greater than or equal to Min Cutoff matrix.")

    # Validate distribution type matrix
    validate_matrix_shape(distribution_matrix, matrix_name="Distribution Type Matrix")
    validate_distribution_type(distribution_matrix)

    # Check consistency for active transitions
    for i in range(len(transition_matrix)):
        for j in range(len(transition_matrix[i])):
            if transition_matrix[i][j] > 0:
                # For active transitions, validate that other matrices pass their respective checks
                if not (min_cutoff_matrix[i][j] <= mean_matrix[i][j] <= max_cutoff_matrix[i][j]):
                    raise ValueError(
                        f"For active transition from {states[i]} to {states[j]}, Mean must be within Min and Max Cutoff. "
                        f"Got Mean: {mean_matrix[i][j]}, Min: {min_cutoff_matrix[i][j]}, Max: {max_cutoff_matrix[i][j]}"
                    )
                if std_dev_matrix[i][j] < 0:
                    raise ValueError(
                        f"For active transition from {states[i]} to {states[j]}, Standard Deviation cannot be negative. "
                        f"Got Std Dev: {std_dev_matrix[i][j]}"
                    )
                if distribution_matrix[i][j] == 0:
                    raise ValueError(
                        f"For active transition from {states[i]} to {states[j]}, Distribution Type must be non-zero. "
                        f"Got Distribution Type: {distribution_matrix[i][j]}"
                    )
            # If transition probability is 0, skip validation for other matrices
            else:
                continue

def parse_mapping_file(mapping_file_path):
    """Parse demographic mapping file and extract categories
    
    Args:
        mapping_file_path (str): Path to the mapping CSV file
    
    Returns:
        tuple: (DataFrame of mappings, list of demographic categories)
    """
    try:
        mapping_df = pd.read_csv(mapping_file_path)
        print("Columns in Mapping File:", mapping_df.columns.tolist())

        if "Matrix_Set" not in mapping_df.columns:
            raise ValueError("The mapping file must include a 'Matrix_Set' column.")
            
        demographic_categories = [col for col in mapping_df.columns if col != "Matrix_Set"]
        return mapping_df, demographic_categories
        
    except Exception as e:
        raise ValueError(f"Error reading mapping file: {str(e)}")

def extract_matrices(matrix_set, combined_matrix_df, num_states):
    """
    Extract matrices for a given set ID from the combined matrix dataframe
    
    Args:
        matrix_set: str, the matrix set identifier (e.g., "Matrix_Set_1")
        combined_matrix_df: pandas DataFrame containing all matrices
        num_states: int, number of states in the model
    """
    # Extract the numeric ID from the matrix set string
    matrix_set_id = int(matrix_set.split('_')[-1])
    
    matrices = {}
    matrix_types = [
        "Transition Matrix",
        "Distribution Type",
        "Mean",
        "Standard Deviation",
        "Min Cut-Off",
        "Max Cut-Off"
    ]
    
    # Each matrix set contains 6 matrices of size num_states x num_states
    # Each matrix takes up num_states rows in the CSV
    start_row = (matrix_set_id - 1) * (num_states * 6)
    
    for i, matrix_type in enumerate(matrix_types):
        # Get the rows for this matrix
        matrix_start = start_row + (i * num_states)
        matrix_end = matrix_start + num_states
        
        # Extract and convert matrix values
        matrix_data = combined_matrix_df.iloc[matrix_start:matrix_end].values
        
        # Convert string values to float, handling any trailing commas
        matrix = np.array([[float(str(val).strip(',')) for val in row[:num_states]] for row in matrix_data])
        
        matrices[matrix_type] = matrix
    
    return matrices

def find_matching_matrix(demographics, mapping_df, demographic_categories):
    """
    Find the matrix set corresponding to the given demographics, supporting wildcards,
    range-based matching, and optional categories.
    """
    print("\nInput Demographics:")
    for key, value in demographics.items():
        print(f"  {key}: {value}")

    for idx, row in mapping_df.iterrows():
        match = True
        print(f"\nChecking Row {idx}:")
        print(row.to_string(index=False))

        for category in demographic_categories:
            mapping_value = str(row[category]).strip()
            input_value = str(demographics.get(category, "")).strip()

            # Handle wildcard or blank cells in the mapping file
            if mapping_value in ("*", ""):
                continue

            # Handle wildcard or blank cells in the user input
            if input_value in ("*", ""):
                continue

            # Handle range-based matching
            if "-" in mapping_value and category == "Age Range":
                try:
                    range_start, range_end = map(int, mapping_value.split("-"))
                    if not (range_start <= int(input_value) <= range_end):
                        print(f"  Mismatch in {category}: {input_value} not in range {mapping_value}")
                        match = False
                        break
                except ValueError:
                    raise ValueError(f"Invalid range format in mapping file: {mapping_value}")

            # Handle "61+" or similar conditions
            elif mapping_value.endswith("+") and category == "Age Range":
                try:
                    min_value = int(mapping_value[:-1])  # Extract the numeric part
                    if int(input_value) < min_value:
                        print(f"  Mismatch in {category}: {input_value} is less than {mapping_value}")
                        match = False
                        break
                except ValueError:
                    raise ValueError(f"Invalid format for '61+' in mapping file: {mapping_value}")

            # Handle exact matches
            elif mapping_value != input_value:
                print(f"  Mismatch in {category}: {input_value} != {mapping_value}")
                match = False
                break

        if match:
            print("\nMatched Demographic Set:")
            print(row.to_string(index=False))
            return row["Matrix_Set"]

    # If no match, raise an error
    raise ValueError("No matching matrix set found for the given demographics.")


def get_user_input(demographic_categories):
    print("\nEnter demographic parameters. Use '*' for any value (wildcard).")
    demographics = {}
    for category in demographic_categories:
        value = input(f"{category}: ").strip()
        demographics[category] = value if value else "*"
    return demographics

def process_demographic_input(demographics, mapping_df, combined_matrix_df, demographic_categories):
    matrix_set = find_matching_matrix(demographics, mapping_df, demographic_categories)
    matrices = extract_matrices(matrix_set, combined_matrix_df, num_states)
    
    validate_matrices(
        transition_matrix=matrices["Transition Matrix"],
        mean_matrix=matrices["Mean"],
        std_dev_matrix=matrices["Standard Deviation"],
        min_cutoff_matrix=matrices["Min Cut-Off"],
        max_cutoff_matrix=matrices["Max Cut-Off"],
        distribution_matrix=matrices["Distribution Type"]
    )
    
    simulation_data = run_simulation(
        matrices["Transition Matrix"],
        matrices["Mean"],
        matrices["Standard Deviation"],
        matrices["Min Cut-Off"],
        matrices["Max Cut-Off"],
        matrices["Distribution Type"],
        default_initial_state
    )
    fig = visualize_state_timeline(simulation_data)
    return simulation_data, fig

def validate_states_format(states):
    """Validates the format of user-defined states"""
    if not isinstance(states, list):
        raise ValueError("States must be provided as a list")
    if len(states) < 2:
        raise ValueError("At least 2 states are required")
    if len(set(states)) != len(states):
        raise ValueError("State names must be unique")
    if not all(isinstance(s, str) for s in states):
        raise ValueError("All states must be strings")

def process_states_input(states_file=None):
    """Process user-defined states from file or use defaults"""
    if states_file:
        try:
            with open(states_file, 'r') as f:
                states = [line.strip() for line in f if line.strip()]
            validate_states_format(states)
            return states
        except FileNotFoundError:
            raise ValueError(f"States file not found: {states_file}")
    return default_states  # Fall back to default states if no file provided

def process_input(matrix_file_path, mapping_file_path, states_file_path=None, is_web=True):
    """Process input files for both web and CLI interfaces
    
    Args:
        matrix_file_path: Path or uploaded file for matrices
        mapping_file_path: Path or uploaded file for mapping
        states_file_path: Optional path or uploaded file for states
        is_web: Boolean indicating if this is web (True) or CLI (False)
    """
    try:
        # Load matrices
        if is_web:
            combined_matrix_df = pd.read_csv(matrix_file_path)
        else:
            combined_matrix_df = pd.read_csv(matrix_file_path)
            
        # Load mapping
        if is_web:
            mapping_df = pd.read_csv(mapping_file_path)
        else:
            mapping_df = pd.read_csv(mapping_file_path)
            
        # Load states if provided
        if states_file_path:
            if is_web:
                states = parse_states_file(states_file_path)
            else:
                with open(states_file_path, 'r') as f:
                    states = parse_states_file(f)
        else:
            states = default_states
            
        return combined_matrix_df, mapping_df, states
        
    except Exception as e:
        error_msg = f"Error processing input files: {str(e)}"
        if is_web:
            st.error(error_msg)
            return None, None, None
        else:
            print(f"Error: {error_msg}")
            return None, None, None

def run_cli():
    """Command-line interface for DMP"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Disease Modeling Platform")
    parser.add_argument("--matrices", required=True, help="Path to matrices CSV file")
    parser.add_argument("--mapping", required=True, help="Path to mapping CSV file")
    parser.add_argument("--states", help="Optional path to states file")
    
    # First read the mapping file to get demographic categories
    mapping_df, demographic_categories = parse_mapping_file(args.mapping)
    
    # Add arguments dynamically based on mapping file
    for category in demographic_categories:
        if category == "Age Range":
            parser.add_argument(f"--{category.lower().replace(' ', '_')}", 
                              type=int, required=True,
                              help=f"{category} of person")
        else:
            parser.add_argument(f"--{category.lower().replace(' ', '_')}", 
                              help=f"{category} of person")
    
    args = parser.parse_args()
    
    # Create demographics dictionary from provided arguments
    demographics = {}
    for category in demographic_categories:
        arg_name = category.lower().replace(' ', '_')
        value = getattr(args, arg_name)
        if value is not None:
            demographics[category] = value
    
    # Process input files
    matrix_df, mapping_df, states = process_input(
        args.matrices, 
        args.mapping, 
        args.states,
        is_web=False
    )
    
    if matrix_df is None:
        return
    
    # Initialize DMP and run simulation
    try:
        dmp = DiseaseModelingPlatform(
            matrix_file_path=args.matrices,
            mapping_file_path=args.mapping,
            states_file_path=args.states
        )
        
        timeline = dmp.get_disease_timeline(demographics)
        
        print("\nDisease Progression Timeline:")
        for state, time in timeline:
            print(f"{time:>6.1f} minutes: {state}")
            
    except Exception as e:
        print(f"Error running simulation: {str(e)}")

if __name__ == "__main__":
    run_cli()

