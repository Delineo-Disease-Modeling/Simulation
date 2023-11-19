import pandas as pd
import numpy as np
import csv
from simulation_functions import run_simulation, states, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, transition_matrix

# Read the entire CSV file into a pandas DataFrame
df = pd.read_csv('matrices.csv', header=None)

# Define the labels for the matrices
matrix_labels = ["Transition Matrix", "Distribution Type", "Mean", "Standard Deviation", "Min Cut-Off", "Max Cut-Off"]

# Define the number of rows for each matrix
matrix_rows = 7

# Split the DataFrame into separate matrices
matrices = [df[i:i+matrix_rows] for i in range(0, df.shape[0], matrix_rows)]

# Assign each matrix to a label in a dictionary
matrices_dict = {label: matrix.values.tolist() for label, matrix in zip(matrix_labels, matrices)}

# Print out all the matrices
for label, matrix in matrices_dict.items():
    print(label)
    print(matrix)


# Define the column names for the demographic info
demo_cols = ["Sex", "Age", "Comorbidity"]

# Read the demographic info from the CSV file
demographic_info = pd.read_csv('demographic_info.csv', names=demo_cols)

print('Demographic Info')
print(demographic_info)
print(matrices_dict["Mean"])
simulation_data = run_simulation(matrices_dict["Transition Matrix"], matrices_dict["Mean"], matrices_dict["Standard Deviation"], matrices_dict["Min Cut-Off"], matrices_dict["Max Cut-Off"], matrices_dict["Distribution Type"], default_initial_state, 20)
output_file = "simulation_parameters_results.csv"
with open(output_file, "w", newline='') as file:
      writer = csv.writer(file)
      writer.writerow(["State", "Time Step"])
      writer.writerows(simulation_data)