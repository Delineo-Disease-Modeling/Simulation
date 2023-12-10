import pandas as pd
import numpy as np
import csv
from .simulation_functions import run_simulation, default_initial_state
import os

def process_dataframes(df, demographic_info):
    # Define the labels for the matrices
    matrix_labels = ["Transition Matrix", "Distribution Type", "Mean", "Standard Deviation", "Min Cut-Off", "Max Cut-Off"]

    # Define the number of rows for each matrix
    matrix_rows = 7

    # Split the DataFrame into separate matrices
    matrices = [df[i:i + matrix_rows] for i in range(0, df.shape[0], matrix_rows)]

    # Assign each matrix to a label in a dictionary
    matrices_dict = {label: matrix.values.tolist() for label, matrix in zip(matrix_labels, matrices)}

    # Print out all the matrices
    # for label, matrix in matrices_dict.items():
    #     print(label)
    #     print(matrix)

    # Define the column names for the demographic info
    demo_cols = ["Sex", "Age", "Is_Vaccinated"]

    # print('Demographic Info')
    # print(demographic_info)

    # print(matrices_dict["Mean"])
    simulation_data = run_simulation(
        matrices_dict["Transition Matrix"],
        matrices_dict["Mean"],
        matrices_dict["Standard Deviation"],
        matrices_dict["Min Cut-Off"],
        matrices_dict["Max Cut-Off"],
        matrices_dict["Distribution Type"],
        default_initial_state,
        20, 
        demographic_info["Age"].iloc[0], 
        demographic_info["Is_Vaccinated"].iloc[0]
    )

    output_dict = {}
    for state, total_time_steps in simulation_data:
        output_dict[state] = total_time_steps

    return output_dict

# Read the entire CSV file into a pandas DataFrame
curdir = os.path.dirname(os.path.abspath(__file__))
df = pd.read_csv(curdir + '/matrices.csv', header=None)

# Read the demographic info from the CSV file
demo_cols = ["Sex", "Age", "Is_Vaccinated"]
demographic_info = pd.read_csv('demographic_info.csv', names=demo_cols)
result_dict = process_dataframes(df, demographic_info)

# Print the result dictionary
print(result_dict)
