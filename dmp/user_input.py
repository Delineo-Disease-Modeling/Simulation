import pandas as pd
from simulation_functions import run_simulation, default_initial_state
import os

def process_dataframes(dfs, demographic_info):
    # Define the labels for the matrices
    matrix_labels = ["Transition Matrix", "Distribution Type", "Mean", "Standard Deviation", "Min Cut-Off", "Max Cut-Off"]

    # Define the number of rows for each matrix
    matrix_rows = 7

    output_dicts = []

    for df in dfs:
        # Split the DataFrame into separate matrices
        matrices = [df[i:i + matrix_rows] for i in range(0, df.shape[0], matrix_rows)]

        # Assign each matrix to a label in a dictionary
        matrices_dict = {label: matrix.values.tolist() for label, matrix in zip(matrix_labels, matrices)}

        # Validate transition matrix
        transition_matrix = matrices_dict["Transition Matrix"]
        validate_transition_matrix(transition_matrix)

        validate_mean_and_std(matrices_dict["Mean"], matrices_dict["Standard Deviation"])

        validate_distribution_type(matrices_dict["Distribution Type"])

        validate_cutoffs(matrices_dict["Min Cut-Off"])
        validate_cutoffs(matrices_dict["Max Cut-Off"])

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

        output_dict = {}
        for state, total_time_steps in simulation_data:
            output_dict[state] = total_time_steps

        output_dicts.append(output_dict)

    return output_dicts


def validate_transition_matrix(matrix):
    if len(matrix) != 7:
        raise ValueError("Transition matrix must be 7x7")
    for row in matrix:
        if len(row) != 7:
            raise ValueError("Transition matrix must be 7x7")
        if not all(0 <= val <= 1 for val in row):
            raise ValueError("Transition matrix values must be between 0 and 1")
        if abs(sum(row) - 1) > 1e-6:
            raise ValueError("Each row of the transition matrix must sum up to 1")
def validate_mean_and_std(mean_matrix, std_matrix):
    for row in mean_matrix:
        if len(row) != 7 or not all(val > 0 for val in row):
            raise ValueError("Mean values must be a 7x7 matrix with all values greater than 0")
    for row in std_matrix:
        if len(row) != 7 or not all(val > 0 for val in row):
            raise ValueError("Standard deviation values must be a 7x7 matrix with all values greater than 0")
def validate_distribution_type_or_cutoffs(matrix, msg):
    if not all(len(row) == 7 and all(val.is_integer() and val >= (1 if msg == "Distribution Type" else 0) for val in row) for row in matrix):
        raise ValueError(f"Invalid {msg} matrix")
def validate_distribution_type(matrix):
    validate_distribution_type_or_cutoffs(matrix, "Distribution Type")
def validate_cutoffs(matrix):
    validate_distribution_type_or_cutoffs(matrix, "Cutoffs")

if __name__ == '__main__':
    # Read the first CSV file into a pandas DataFrame
    curdir = os.path.dirname(os.path.abspath(__file__))
    df = pd.read_csv(curdir + '/matrices.csv', header=None)

    # Read the second CSV file into another pandas DataFrame
    df2 = pd.read_csv(curdir + '/matrices2.csv', header=None)

    # Read the demographic info from the CSV file
    demo_cols = ["Sex", "Age", "Is_Vaccinated"]
    demographic_info = pd.read_csv(curdir + '/demographic_info.csv', names=demo_cols)

    # Split the dataframes into a list
    dataframes = [df, df2]

    result_dicts = process_dataframes(dataframes, demographic_info)

    # Print the result dictionaries
    for result_dict in result_dicts:
        print(result_dict)