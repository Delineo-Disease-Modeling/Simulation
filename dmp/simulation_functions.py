import random
import numpy as np
import matplotlib.pyplot as plt

# Define the states variable at the top level
states = ["Infected", "Infectious Asymptomatic", "Infectious Symptomatic", "Hospitalized", "ICU", "Removed", "Recovered"]

# Default initial state
default_initial_state = "Infected"

def run_simulation(transition_matrix, mean_time_interval_matrix, std_dev_time_interval_matrix, 
                   min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, 
                   initial_state, desired_iterations):
    current_state = states.index(initial_state)
    total_time_steps = 0
    simulation_data = []
    
    # Keep track of the timeline for the line graph
    simulation_data.append([initial_state, total_time_steps])

    def transition():
        nonlocal current_state
        next_state = random.choices(states, weights=transition_matrix[current_state])[0]
        current_state = states.index(next_state)
        return next_state

    def sample_time_interval(mean_matrix, std_dev_matrix, min_matrix, max_matrix, distribution_matrix, current_state_index, next_state_index):
        while True:
            if distribution_matrix[current_state_index][next_state_index] == 0:  # No transition
                return 0  # No time interval for this transition
            elif distribution_matrix[current_state_index][next_state_index] == 1:  # Normal distribution
                interval = int(random.normalvariate(mean_matrix[current_state_index][next_state_index], std_dev_matrix[current_state_index][next_state_index]))
            elif distribution_matrix[current_state_index][next_state_index] == 2:  # Exponential distribution
                interval = int(random.expovariate(1 / mean_matrix[current_state_index][next_state_index]))
            elif distribution_matrix[current_state_index][next_state_index] == 3:  # Uniform distribution
                interval = int(random.uniform(min_matrix[current_state_index][next_state_index], max_matrix[current_state_index][next_state_index]))
            elif distribution_matrix[current_state_index][next_state_index] == 4:  # Gamma distribution
                shape = (mean_matrix[current_state_index][next_state_index] / std_dev_matrix[current_state_index][next_state_index]) ** 2
                scale = std_dev_matrix[current_state_index][next_state_index] ** 2 / mean_matrix[current_state_index][next_state_index]
                interval = int(np.random.gamma(shape, scale))
            elif distribution_matrix[current_state_index][next_state_index] == 5:  # Beta distribution
                mean = mean_matrix[current_state_index][next_state_index]
                std_dev = std_dev_matrix[current_state_index][next_state_index]
                alpha = (mean * (mean * (1 - mean) / (std_dev ** 2)) - 1)
                beta = alpha * (1 - mean) / mean
                interval = int(np.random.beta(alpha, beta) * (max_matrix[current_state_index][next_state_index] - min_matrix[current_state_index][next_state_index]) + min_matrix[current_state_index][next_state_index])
            else:
                raise ValueError(f"Unsupported distribution type {distribution_matrix[current_state_index][next_state_index]}")
            
            if min_matrix[current_state_index][next_state_index] <= interval <= max_matrix[current_state_index][next_state_index]:
                return interval

    iterations = 0
    while iterations < desired_iterations:
        next_state = transition()
        next_state_index = states.index(next_state)
        
        if states[next_state_index] in ["Removed", "Recovered"]:
            simulation_data.append([states[next_state_index], total_time_steps])
            break  # Stop the simulation when reaching Recovered or Removed

        time_interval = sample_time_interval(mean_time_interval_matrix, std_dev_time_interval_matrix, min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, current_state, next_state_index) * 60 * 24
        total_time_steps += time_interval
        current_state_str = states[current_state]

        simulation_data.append([current_state_str, total_time_steps])

        current_state = next_state_index
        iterations += 1

    return simulation_data  # Return timeline of states and time

def visualize_state_timeline(simulation_data):
    # Extract the states and times from the simulation data
    timeline_states = [entry[0] for entry in simulation_data]
    timeline_times = [entry[1] for entry in simulation_data]

    # Create the line graph
    plt.figure(figsize=(10, 6))
    plt.plot(timeline_times, timeline_states, marker='o', color='skyblue', linestyle='-', linewidth=2)
    plt.xlabel('Time (minutes)')
    plt.ylabel('Disease States')
    plt.title('Timeline of Disease Progression')
    plt.grid(True)
    plt.tight_layout()
    plt.show()
