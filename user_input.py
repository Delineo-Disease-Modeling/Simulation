import sys
import os
import argparse
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

# Add the parent directory to the Python path more explicitly
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

# Import using the correct path
from simulation_functions import run_simulation, generate_transition_time, validate_matrices

# Path to default states file
DEFAULT_STATES_PATH = Path(parent_dir) / "data" / "default_states.txt"

# Define default states
default_states = ["Infected", "Infectious", "Symptomatic", "Severe", "Critical", "Deceased", "Recovered"]
default_initial_state = "Infected"

def parse_states_file(file_path):
    """Parse states from file"""
    try:
        with open(file_path, 'r') as f:
            states = [line.strip() for line in f if line.strip()]
        if not states:
            raise ValueError("States file is empty")
        return states
    except Exception as e:
        print(f"Error reading states file: {str(e)}")
        raise

def parse_args():
    """Parse command line arguments dynamically based on mapping file"""
    parser = argparse.ArgumentParser(description="Disease Modeling Platform")
    parser.add_argument("--matrices", required=True, help="Path to matrices CSV file")
    parser.add_argument("--mapping", required=True, help="Path to mapping CSV file")
    parser.add_argument("--states", help="Optional path to custom states file (default: data/default_states.txt)")
    parser.add_argument("--output", help="Optional path for output CSV file (default: results_TIMESTAMP.csv)")
    
    # First parse just the mapping file to get demographic categories
    initial_args, _ = parser.parse_known_args()
    mapping_df = pd.read_csv(initial_args.mapping, skipinitialspace=True)
    demographic_categories = [col.strip() for col in mapping_df.columns if col.strip() != "Matrix_Set"]
    
    # Add arguments dynamically based on mapping file
    for category in demographic_categories:
        # Convert category name to argument name
        arg_name = category.lower().replace(' ', '_')
        unique_values = mapping_df[category].unique()
        valid_values = [str(v).strip() for v in unique_values if v != "*" and pd.notna(v)]
        parser.add_argument(f"--{arg_name}", 
                          required=True, 
                          help=f"{category} value ({', '.join(valid_values)})")
    
    return parser.parse_args()

def visualize_state_timeline(timeline):
    """Visualize the state timeline"""
    print("\nDisease Progression Timeline:")
    for state, time in timeline:
        print(f"{time:>6.1f} minutes: {state}")

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
    """Parse mapping file and return mapping DataFrame and demographic categories"""
    try:
        # Read CSV file, skipping comment lines and handling whitespace
        mapping_df = pd.read_csv(
            mapping_file_path,
            comment='#',
            skipinitialspace=True
        )
        
        # Clean column names and get demographic categories
        mapping_df.columns = [col.strip() for col in mapping_df.columns]
        demographic_categories = [col for col in mapping_df.columns if col != "Matrix_Set"]
        
        return mapping_df, demographic_categories
    except Exception as e:
        print(f"Error reading mapping file: {str(e)}")
        raise

def extract_matrices(matrix_set, combined_matrix_df, num_states):
    """Extract matrices for a given matrix set from the combined DataFrame"""
    try:
        # Read CSV file if it's a path, otherwise use the DataFrame directly
        if isinstance(combined_matrix_df, (str, Path)):
            combined_matrix_df = pd.read_csv(
                combined_matrix_df,
                comment='#',
                skipinitialspace=True,
                header=None
            )
        
        # Calculate the block size for each matrix set
        block_size = 6 * num_states  # 6 matrices per set
        
        # Extract the matrix set number from the name (e.g., "Matrix_Set_14" -> 14)
        try:
            set_number = int(matrix_set.split('_')[-1]) - 1  # Convert to 0-based index
        except (ValueError, IndexError):
            # If we can't parse the number, use the first set
            set_number = 0
        
        # Calculate the start and end indices for this matrix set
        start_idx = set_number * block_size
        end_idx = start_idx + block_size
        
        # Extract each matrix
        matrices = {
            "Transition Matrix": combined_matrix_df.iloc[start_idx:start_idx + num_states].values,
            "Distribution Type": combined_matrix_df.iloc[start_idx + num_states:start_idx + 2*num_states].values,
            "Mean": combined_matrix_df.iloc[start_idx + 2*num_states:start_idx + 3*num_states].values,
            "Standard Deviation": combined_matrix_df.iloc[start_idx + 3*num_states:start_idx + 4*num_states].values,
            "Min Cut-Off": combined_matrix_df.iloc[start_idx + 4*num_states:start_idx + 5*num_states].values,
            "Max Cut-Off": combined_matrix_df.iloc[start_idx + 5*num_states:end_idx].values
        }
        
        return matrices
    except Exception as e:
        print(f"Error extracting matrices: {str(e)}")
        raise

def find_matching_matrix(demographics, mapping_df, demographic_categories):
    """Find the matrix set corresponding to the given demographics"""
    print(f"Input demographics: {demographics}")
    
    for idx, row in mapping_df.iterrows():
        match = True
        
        for category in demographic_categories:
            mapping_value = str(row[category]).strip()
            input_value = str(demographics[category]).strip()
            
            # Handle wildcard or blank cells
            if mapping_value in ("*", "") or input_value in ("*", ""):
                continue
                
            # Handle range-based matching
            if "-" in mapping_value:
                try:
                    range_start, range_end = map(int, mapping_value.split("-"))
                    input_num = int(input_value)
                    if not (range_start <= input_num <= range_end):
                        match = False
                        break
                except ValueError:
                    if mapping_value != input_value:
                        match = False
                        break
                    
            # Handle "N+" format
            elif "+" in mapping_value:
                try:
                    min_value = int(mapping_value.rstrip("+"))
                    input_num = int(input_value)
                    if input_num < min_value:
                        match = False
                        break
                except ValueError:
                    if mapping_value != input_value:
                        match = False
                        break
                        
            # Handle exact matches
            elif mapping_value != input_value:
                match = False
                break
                
        if match:
            print(f"\nFound matching set: {row['Matrix_Set']}")
            return row["Matrix_Set"]
            
    raise ValueError("No matching matrix set found for these demographics")


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
    states_path = states_file if states_file else DEFAULT_STATES_PATH
    if not os.path.exists(states_path):
        raise FileNotFoundError(f"States file not found: {states_path}")
    return parse_states_file(states_path)

def process_input(matrix_file_path, mapping_file_path, states_file_path=None, is_web=True):
    """Process input files for both web and CLI interfaces
    
    Args:
        matrix_file_path: Path or uploaded file for matrices
        mapping_file_path: Path or uploaded file for mapping
        states_file_path: Optional path or uploaded file for states
        is_web: Boolean indicating if this is web (True) or CLI (False)
    """
    try:
        # Load matrices with comment lines skipped
        if is_web:
            combined_matrix_df = pd.read_csv(matrix_file_path, comment='#')
        else:
            combined_matrix_df = pd.read_csv(matrix_file_path, comment='#')
            
        # Load mapping with comment lines skipped
        if is_web:
            mapping_df = pd.read_csv(mapping_file_path, comment='#', skipinitialspace=True)
        else:
            mapping_df = pd.read_csv(mapping_file_path, comment='#', skipinitialspace=True)
            
        # Load states from provided file or default file
        if states_file_path:
            states = parse_states_file(states_file_path)
        else:
            states = parse_states_file(DEFAULT_STATES_PATH)
            
        return combined_matrix_df, mapping_df, states
        
    except Exception as e:
        error_msg = f"Error processing input files: {str(e)}"
        if is_web:
            print(error_msg)
            return None, None, None
        else:
            print(f"Error: {error_msg}")
            return None, None, None

def save_results(timeline, demographics, output_path=None):
    """Save simulation results to CSV file"""
    # Create results directory if it doesn't exist
    results_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Generate default filename with timestamp if none provided
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(results_dir, f"results_{timestamp}.csv")
    
    # Convert timeline to DataFrame
    results_df = pd.DataFrame(timeline, columns=['State', 'Time'])
    
    # Add demographics to results
    for key, value in demographics.items():
        results_df[key] = value
    
    # Save to CSV
    results_df.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")

def main():
    args = parse_args()
    
    try:
        # Process input files
        print("\nLoading input files...")
        matrix_df = pd.read_csv(args.matrices, header=None, comment='#')
        mapping_df = pd.read_csv(args.mapping, skipinitialspace=True, comment='#')
        
        # Load states from file
        if args.states:
            with open(args.states, 'r') as f:
                states = [line.strip() for line in f if line.strip()]
        else:
            states = parse_states_file(DEFAULT_STATES_PATH)
        
        print(f"Using states: {states}")
        num_states = len(states)
        
        # Create demographics dictionary dynamically
        demographics = {}
        demographic_categories = [col.strip() for col in mapping_df.columns if col.strip() != "Matrix_Set"]
        for category in demographic_categories:
            arg_name = category.lower().replace(' ', '_')
            demographics[category] = getattr(args, arg_name)
        
        print(f"Demographics: {demographics}")
        
        # Find matching matrix set
        matching_set = find_matching_matrix(demographics, mapping_df, demographic_categories)
        
        # Extract matrices in correct order using num_states
        transition_matrix = matrix_df.iloc[0:num_states, 0:num_states].values
        distribution_matrix = matrix_df.iloc[num_states:2*num_states, 0:num_states].values
        mean_matrix = matrix_df.iloc[2*num_states:3*num_states, 0:num_states].values
        std_dev_matrix = matrix_df.iloc[3*num_states:4*num_states, 0:num_states].values
        min_cutoff_matrix = matrix_df.iloc[4*num_states:5*num_states, 0:num_states].values
        max_cutoff_matrix = matrix_df.iloc[5*num_states:6*num_states, 0:num_states].values
        
        # Validate matrices
        validate_matrices(transition_matrix, mean_matrix, std_dev_matrix,
                        min_cutoff_matrix, max_cutoff_matrix, distribution_matrix)
        
        # Run simulation
        print("\nRunning simulation...")
        initial_state_idx = states.index(default_initial_state)
        timeline = run_simulation(
            transition_matrix,
            mean_matrix,
            std_dev_matrix,
            min_cutoff_matrix,
            max_cutoff_matrix,
            distribution_matrix,
            initial_state_idx,
            states
        )
        
        # Print results to console
        print("\nDisease Progression Timeline:")
        for state, time in timeline:
            print(f"{time:>6.1f} hours: {state}")
        
        # Save results to file
        save_results(timeline, demographics, args.output)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()

