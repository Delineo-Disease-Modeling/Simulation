import argparse
import csv
import os
from simulation_functions import run_simulation, states, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, transition_matrix

# def read_parameters_from_csv(csv_filename):
#     try:
#         with open(csv_filename, mode="r", newline="") as file:
#             reader = csv.reader(file)
#             return list(reader)  # Return all rows in the CSV as a list of lists
#     except FileNotFoundError:
#         print("CSV file not found.")
#         return None



# def get_output_csv_path(csv_filename):
#     base_filename = os.path.splitext(csv_filename)[0]
#     return f"{base_filename}_results.csv"

# def get_user_input(args):
#     if not args.csv_file:
#         print("Please provide a CSV file with simulation parameters using the --csv_file argument.")
#         return None

#     use_default_values = input("Use default values for parameters? (y/n): ").lower()

#     if use_default_values == "n":
#         parameters = read_parameters_from_csv(args.csv_file)
#         if not parameters:
#             return None

#         simulation_data = []
#         for row in parameters:
#             if len(row) >= 3:  # Ensure the row has enough elements for unpacking
#                 sex, age, comorbidity = row[0].split(", ")[:3]  # Limit to 3 elements
#                 transition_matrix_2 = [list(map(float, entry.split(", "))) for entry in row[1:]]
#                 result = run_simulation(transition_matrix_2, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, 20)
#                 simulation_data.append(result)
#             else:
#                 print("Insufficient data in the row:", row)

#     else:
#         print("Using default parameters.")
#         simulation_data = run_simulation(transition_matrix, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, 20)

#     output_csv_path = get_output_csv_path(args.csv_file)
#     with open(output_csv_path, mode="w", newline="") as file:
#         writer = csv.writer(file)
#         writer.writerow(["State", "Time Step"])
#         writer.writerows(simulation_data)

#     return simulation_data

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Disease Simulation")
#     parser.add_argument("--csv_file", type=str, help="CSV file containing simulation parameters")
#     args = parser.parse_args()

#     simulation_data = get_user_input(args)  # Pass 'args' as an argument

#     if not args.csv_file:
#         print("Please provide a CSV file with simulation parameters using the --csv_file argument.")
#     else:
#         simulation_data = get_user_input()
#         print("Simulation completed. Results:")
#         for state, time_step in simulation_data:
#             print(f"State: {state}, Time Step: {time_step}")
#         print(f"Results saved to {get_output_csv_path(args.csv_file)}")

import pandas as pd
import numpy as np

# Read the input file
with open('simulation_parameters.csv', 'r') as file:
    sample_data = file.readline().strip()  # Read the first line (strip to remove newline character)

# Split the sample data by comma
split_data = sample_data.split(', ')

# Extract sex, age, and comorbidity
sex = split_data[0]
age = int(split_data[1])
comorbidity = split_data[2]

# Extract the transition matrix values as a 6x7 array
transition_values = np.array([float(value) for value in split_data[3:]])

# Reshape the transition values into a 6x7 matrix
transition_matrix = transition_values.reshape(6, 7)

# Create a DataFrame combining sex, age, and comorbidity with the transition matrix
data = pd.DataFrame(transition_matrix)

simulation_data = run_simulation(transition_matrix, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, 20)
output_file = "simulation_parameters_results.csv"
with open(output_file, "w", newline='') as file:
      writer = csv.writer(file)
      writer.writerow(["State", "Time Step"])
      writer.writerows(simulation_data)

# Display the extracted information and transition matrix
print("Sex:", sex)
print("Age:", age)
print("Comorbidity:", comorbidity)
print("\nTransition Matrix:")
print(data)
