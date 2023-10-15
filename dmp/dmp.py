import random
import csv

# Define states
states = ["Symptomatic", "Infectious", "Hospitalized", "ICU", "Removed", "Recovered"]

# Create a transition matrix with transition probabilities
transition_matrix = [
    # Symptomatic  Infectious  Hospitalized   ICU      Removed    Recovered
    [0.0,          0.5,        0.2,          0.0,     0.0,      0.3],   # Symptomatic
    [0.0,          0.0,        0.4,          0.1,     0.0,      0.5],   # Infectious
    [0.0,          0.0,        0.0,          0.6,     0.0,      0.4],   # Hospitalized
    [0.0,          0.0,        0.0,          0.0,     0.3,      0.7],   # ICU
    [0.0,          0.0,        0.0,          0.0,     1.0,      0.0],   # Removed
    [0.0,          0.0,        0.0,          0.0,     0.0,      1.0]    # Recovered
]

# Set default values
default_mean_time_interval = 5
default_std_dev_time_interval = 2
default_initial_state = "Symptomatic"

# Get user input for parameters
use_default_values = input("Use default values for parameters? (y/n): ").lower()

if use_default_values == "n":
    mean_time_interval = float(input("Enter the mean time interval: "))
    std_dev_time_interval = float(input("Enter the standard deviation of time interval: "))
    
    while True:
        initial_state = input("Enter the initial state (e.g., Symptomatic): ")
        
        # Check if the provided initial state is valid
        if initial_state in states:
            break
        else:
            print("Invalid initial state. Please choose from:", states)
else:
    mean_time_interval = default_mean_time_interval
    std_dev_time_interval = default_std_dev_time_interval
    initial_state = default_initial_state

# Initialize the initial state based on user input
current_state = states.index(initial_state)

total_time_steps = 0

# Create a list to store simulation data
simulation_data = []

# Set the desired number of iterations
desired_iterations = 20

# Function to transition to the next state based on probabilities
def transition():
    global current_state
    next_state = random.choices(states, weights=transition_matrix[current_state])[0]
    current_state = states.index(next_state)
    return next_state

# Function to sample time intervals from a normal distribution
def sample_time_interval(mean, std_dev):
    while True:
        interval = int(random.normalvariate(mean, std_dev))
        if interval >= 0:
            return interval

# Simulate disease progression for an individual
iterations = 0
while iterations < desired_iterations:
    time_interval = sample_time_interval(mean_time_interval, std_dev_time_interval)
    total_time_steps += time_interval
    current_state_str = states[current_state]

    # Append data to the list for data storage
    simulation_data.append([current_state_str, total_time_steps])

    print(f"Current state:", current_state_str, "| Time step:", total_time_steps)

    # Check if the current state is "Recovered" or "Removed" and stop the simulation
    if states[current_state] in ["Recovered", "Removed"]:
        print("Reached terminal state. Simulation stopped.")
        break

    next_state = transition()
    print()
    
    iterations += 1

# Write the data to a CSV file
csv_file_path = "dmp/simulation_results.csv"
with open(csv_file_path, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["State", "Time Step"])  # Write a header row
    writer.writerows(simulation_data)
