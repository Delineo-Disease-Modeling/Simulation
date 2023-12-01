import pandas as pd
import numpy as np
import csv
import os
from .simulation_functions import run_simulation, states, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, transition_matrix

curdir = os.path.dirname(os.path.abspath(__file__))

# Read the entire CSV file into a pandas DataFrame
df = pd.read_csv(curdir + '/matrices.csv', header=None)

# Define the labels for the matrices
matrix_labels = ["Transition Matrix", "Distribution Type", "Mean", "Standard Deviation", "Min Cut-Off", "Max Cut-Off"]

# Define the number of rows for each matrix
matrix_rows = 7

# Split the DataFrame into separate matrices
matrices = [df[i:i+matrix_rows] for i in range(0, df.shape[0], matrix_rows)]

# Assign each matrix to a label in a dictionary
matrices_dict = {label: matrix.values.tolist() for label, matrix in zip(matrix_labels, matrices)}

# Define the column names for the demographic info
demo_cols = ["Sex", "Age", "Comorbidity"]

if __name__ == '__main__':
    # Print out all the matrices
    for label, matrix in matrices_dict.items():
        print(label)
        print(matrix)

    print('Demographic Info')
    print(matrices_dict["Mean"])



def get_disease_matrix(person):
    demographic_info = [ person.sex, person.age, person.get_vaccinated() ]
    #demographic_info = pd.read_csv('demographic_info.csv', names=demo_cols)

    simulation_data = run_simulation(matrices_dict["Transition Matrix"], matrices_dict["Mean"], matrices_dict["Standard Deviation"], matrices_dict["Min Cut-Off"], matrices_dict["Max Cut-Off"], matrices_dict["Distribution Type"], default_initial_state, 20)

    return simulation_data