import pandas as pd
import numpy as np
from dmp.simulation_functions import run_simulation, default_initial_state, visualize_state_timeline, states
import os

def validate_matrix_shape(matrix, expected_shape=(7, 7), matrix_name="Matrix"):
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

def parse_mapping_file(mapping_file):
    mapping_df = pd.read_csv(mapping_file)
    print("Columns in Mapping File:", mapping_df.columns.tolist())

    if "Matrix_Set" not in mapping_df.columns:
        raise ValueError("The mapping file must include a 'Matrix_Set' column.")
    demographic_categories = [col for col in mapping_df.columns if col != "Matrix_Set"]
    return mapping_df, demographic_categories

def extract_matrices(matrix_set, combined_matrix_df):
    matrix_set_index = int(matrix_set.split("_")[-1]) - 1
    matrix_rows = 7
    total_matrix_rows = matrix_rows * 6
    start_row = matrix_set_index * total_matrix_rows
    end_row = start_row + total_matrix_rows
    matrix_block = combined_matrix_df.iloc[start_row:end_row].to_numpy()
    matrices = {
        "Transition Matrix": matrix_block[:matrix_rows],
        "Distribution Type": matrix_block[matrix_rows:matrix_rows*2],
        "Mean": matrix_block[matrix_rows*2:matrix_rows*3],
        "Standard Deviation": matrix_block[matrix_rows*3:matrix_rows*4],
        "Min Cut-Off": matrix_block[matrix_rows*4:matrix_rows*5],
        "Max Cut-Off": matrix_block[matrix_rows*5:matrix_rows*6],
    }
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
    matrices = extract_matrices(matrix_set, combined_matrix_df)
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

if __name__ == '__main__':
    import os

    curdir = os.path.dirname(os.path.abspath(__file__))
    mapping_file = input("Enter the path to the demographic mapping CSV file: ").strip()
    combined_matrix_file = input("Enter the path to the combined matrices CSV file: ").strip()

    # Parse mapping and combined matrix files
    mapping_df, demographic_categories = parse_mapping_file(mapping_file)
    combined_matrix_df = pd.read_csv(combined_matrix_file, header=None)

    print("\nPress Ctrl+C to exit the simulation at any time.")

    # Loop for repeated demographic input
    while True:
        try:
            # Prompt for demographic input
            input_demographics = get_user_input(demographic_categories)

            # Run the simulation
            simulation_results, timeline_fig = process_demographic_input(
                input_demographics, mapping_df, combined_matrix_df, demographic_categories
            )

            # Display simulation results
            print("\nSimulation Results:")
            for state, time in simulation_results:
                print(f"  {state}: {time}")
            timeline_fig.show()

        except ValueError as e:
            print(f"Error: {e}")
        except KeyboardInterrupt:
            print("\nExiting the simulation.")
            break

