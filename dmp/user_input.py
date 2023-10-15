import random
from simulation_functions import run_simulation, states, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, transition_matrix
import csv

csv_file_path = "dmp/simulation_results.csv"

def get_user_input():
    use_default_values = input("Use default values for parameters? (y/n): ").lower()

    if use_default_values == "n":
        mean_time_interval = float(input("Enter the mean time interval: "))
        std_dev_time_interval = float(input("Enter the standard deviation of time interval: "))
    else:
        # Use default values
        mean_time_interval = default_mean_time_interval
        std_dev_time_interval = default_std_dev_time_interval
        initial_state = default_initial_state  # Set the initial state to "Symptomatic"

    desired_iterations = 20

    simulation_data = run_simulation(transition_matrix, mean_time_interval, std_dev_time_interval, initial_state, desired_iterations)

    with open(csv_file_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["State", "Time Step"])
        writer.writerows(simulation_data)

    return simulation_data

if __name__ == "__main__":
    simulation_data = get_user_input()
    print("Simulation completed. Results:")
    for state, time_step in simulation_data:
        print(f"State: {state}, Time Step: {time_step}")
    print("Results saved to", csv_file_path)
