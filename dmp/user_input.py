import pandas as pd
import numpy as np
from simulation_functions import run_simulation, default_initial_state
import os

def validate_matrix_shape(matrix, expected_shape=(7, 7), matrix_name="Matrix"):
    """
    Validates that the matrix has the correct shape.
    """
    if matrix.shape != expected_shape:
        raise ValueError(f"{matrix_name} must be of shape {expected_shape}. Current shape is {matrix.shape}.")

def validate_values_in_range(matrix, min_value, max_value, matrix_name="Matrix"):
    """
    Validates that all values in the matrix are within the specified range.
    """
    if not ((matrix >= min_value) & (matrix <= max_value)).all():
        raise ValueError(f"All values in {matrix_name} must be between {min_value} and {max_value}.")

def validate_row_sums(matrix, expected_sum=1, matrix_name="Transition Matrix"):
    """
    Validates that each row in the matrix sums to the expected value (default is 1).
    """
    row_sums = matrix.sum(axis=1)
    if not np.allclose(row_sums, expected_sum, atol=1e-6):
        raise ValueError(f"Each row in the {matrix_name} must sum to {expected_sum}. Row sums: {row_sums}")

def validate_distribution_type(matrix):
    """
    Validates that the distribution type matrix contains only valid integer types (1: Normal, 2: Exponential, 3: Uniform).
    """
    valid_types = [1, 2, 3]
    if not np.isin(matrix, valid_types).all():
        raise ValueError(f"Distribution Type matrix must contain only the values {valid_types}.")

def validate_matrices(transition_matrix, mean_matrix, std_dev_matrix, min_cutoff_matrix, max_cutoff_matrix, distribution_matrix):
    """
    Combines all validation functions to validate each matrix.
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

    # Validate cutoffs
    validate_matrix_shape(min_cutoff_matrix, matrix_name="Min Cutoff Matrix")
    validate_matrix_shape(max_cutoff_matrix, matrix_name="Max Cutoff Matrix")
    validate_values_in_range(min_cutoff_matrix, 0, float('inf'), matrix_name="Min Cutoff Matrix")
    validate_values_in_range(max_cutoff_matrix, 0, float('inf'), matrix_name="Max Cutoff Matrix")

    # Ensure that the max cutoff is greater than or equal to the min cutoff
    if not (max_cutoff_matrix >= min_cutoff_matrix).all():
        raise ValueError("Max Cutoff matrix must have values greater than or equal to Min Cutoff matrix.")

    # Validate distribution type matrix
    validate_matrix_shape(distribution_matrix, matrix_name="Distribution Type Matrix")
    validate_distribution_type(distribution_matrix)

def process_dataframes(demographic_info, combined_matrix_df):
    # Define the labels for the matrices
    matrix_labels = ["Transition Matrix", "Distribution Type", "Mean", "Standard Deviation", "Min Cut-Off", "Max Cut-Off"]

    # Define the number of rows for each matrix and the total number of rows for one matrix set
    matrix_rows = 7
    total_matrix_rows = matrix_rows * len(matrix_labels)  # 6 matrices, each 7x7

    output_dicts = []

    for _, individual in demographic_info.iterrows():
        # Get the matrix set for this individual
        matrix_set_index = int(individual['Matrix_Set']) - 1  # Assuming matrix sets are numbered starting from 1

        # Calculate the starting and ending row indices for this individual's matrix set
        start_row = matrix_set_index * total_matrix_rows
        end_row = start_row + total_matrix_rows

        # Extract the rows corresponding to the individual's matrix set
        matrix_set_df = combined_matrix_df[start_row:end_row]

        # Split the combined matrix set into individual 7x7 matrices and convert them to NumPy arrays
        matrices = [matrix_set_df[i:i + matrix_rows].to_numpy() for i in range(0, matrix_set_df.shape[0], matrix_rows)]

        # Assign each matrix to a label in a dictionary (keep them as NumPy arrays for validation)
        matrices_dict = {label: matrix for label, matrix in zip(matrix_labels, matrices)}

        # Validate matrices
        validate_matrices(
            transition_matrix=matrices_dict["Transition Matrix"],
            mean_matrix=matrices_dict["Mean"],
            std_dev_matrix=matrices_dict["Standard Deviation"],
            min_cutoff_matrix=matrices_dict["Min Cut-Off"],
            max_cutoff_matrix=matrices_dict["Max Cut-Off"],
            distribution_matrix=matrices_dict["Distribution Type"]
        )

        # Run the simulation for this individual using their specific matrix set
        simulation_data = run_simulation(
            matrices_dict["Transition Matrix"],
            matrices_dict["Mean"],
            matrices_dict["Standard Deviation"],
            matrices_dict["Min Cut-Off"],
            matrices_dict["Max Cut-Off"],
            matrices_dict["Distribution Type"],
            default_initial_state,
            20
        )

        # Add demographic info and simulation results
        output_dict = individual.to_dict()  # Convert individual demographic data to a dict
        for state, total_time_steps in simulation_data:
            output_dict[state] = total_time_steps

        output_dicts.append(output_dict)

    return output_dicts


if __name__ == '__main__':
    # Read the combined matrix file into a pandas DataFrame
    curdir = os.path.dirname(os.path.abspath(__file__))
    combined_matrix_df = pd.read_csv(curdir + '/use_case.csv', header=None)

    # Read the demographic info from the CSV file
    demographic_info = pd.read_csv(curdir + '/demographic_use_case.csv')

    # Process the dataframes with demographic info and the combined matrix file
    result_dicts = process_dataframes(demographic_info, combined_matrix_df)

    # Convert the result dictionaries to a DataFrame and save as CSV
    output_df = pd.DataFrame(result_dicts)
    output_df.to_csv('simulation_output.csv', index=False)

    # Print the result dictionaries
    for result_dict in result_dicts:
        print(result_dict)
