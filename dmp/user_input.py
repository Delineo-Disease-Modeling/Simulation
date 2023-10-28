import argparse
import csv
import os
from simulation_functions import run_simulation, states, default_mean_time_interval, default_std_dev_time_interval, default_initial_state, transition_matrix

def read_parameters_from_csv(csv_filename):
    try:
        with open(csv_filename, mode="r", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                return row  # Return the first row found in the CSV
        print("CSV file is empty or does not contain valid parameters.")
        return None
    except FileNotFoundError:
        print("CSV file not found.")
        return None

def get_output_csv_path(csv_filename):
    base_filename = os.path.splitext(csv_filename)[0]
    return f"{base_filename}_results.csv"

def get_user_input():
    use_default_values = input("Use default values for parameters? (y/n): ").lower()

    if use_default_values == "n":
        parameters = read_parameters_from_csv(args.csv_file)
        if parameters:
            mean_time_interval = float(parameters.get("Mean Time Interval", default_mean_time_interval))
            std_dev_time_interval = float(parameters.get("Standard Deviation", default_std_dev_time_interval))
            initial_state = parameters.get("Initial State", default_initial_state)
            desired_iterations = int(parameters.get("Desired Iterations", 20))

            # Age input validation
            age = int(parameters.get("Age", 0))
            if age < 0 or age > 120:
                print("Age should be between 0 and 120. Using default value.")
                age = 0

            ethnicity = parameters.get("Ethnicity", "")
            group_quarters = parameters.get("Group Quarters", "no").lower() == "yes"

            # Length of Stay input validation
            length_of_stay = int(parameters.get("Length of Stay", 0))
            if length_of_stay < 0:
                print("Length of Stay should be a positive integer. Using default value.")
                length_of_stay = 0

            # Number of People Under 5 input validation
            num_under_5 = int(parameters.get("Number of People Under 5", 0))
            if num_under_5 < 0:
                print("Number of People Under 5 should be a non-negative integer. Using default value.")
                num_under_5 = 0

            mobile_home = parameters.get("Mobile Home", "no").lower() == "yes"
            origin = parameters.get("Origin", "")
            print("Loaded parameters from CSV file.")
        else:
            # If the CSV file is not found or doesn't contain valid parameters, use defaults.
            mean_time_interval = default_mean_time_interval
            std_dev_time_interval = default_std_dev_time_interval
            initial_state = default_initial_state
            desired_iterations = 20
            age = 0
            ethnicity = ""
            group_quarters = False
            length_of_stay = 0
            num_under_5 = 0
            mobile_home = False
            origin = ""
            print("Using default parameters.")
    else:
        # Use default values
        mean_time_interval = default_mean_time_interval
        std_dev_time_interval = default_std_dev_time_interval
        initial_state = default_initial_state
        desired_iterations = 20
        age = 0
        ethnicity = ""
        group_quarters = False
        length_of_stay = 0
        num_under_5 = 0
        mobile_home = False
        origin = ""
        print("Using default parameters.")

    output_csv_path = get_output_csv_path(args.csv_file)
    simulation_data = run_simulation(transition_matrix, mean_time_interval, std_dev_time_interval, initial_state, desired_iterations, age, ethnicity, group_quarters, length_of_stay, num_under_5, mobile_home, origin)

    with open(output_csv_path, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["State", "Time Step"])
        writer.writerows(simulation_data)

    return simulation_data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Disease Simulation")
    parser.add_argument("--csv_file", type=str, help="CSV file containing simulation parameters")
    args = parser.parse_args()

    if not args.csv_file:
        print("Please provide a CSV file with simulation parameters using the --csv_file argument.")
    else:
        simulation_data = get_user_input()
        print("Simulation completed. Results:")
        for state, time_step in simulation_data:
            print(f"State: {state}, Time Step: {time_step}")
        print(f"Results saved to {get_output_csv_path(args.csv_file)}")
