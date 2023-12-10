import random
import numpy as np

# Define the states variable at the top level
states = ["Infected", "Symptomatic", "Infectious", "Hospitalized", "ICU", "Removed", "Recovered"]

# # Define other default values and transition matrix
# default_mean_time_interval = 5
# default_std_dev_time_interval = 2
default_initial_state = "Infected"

# # Define the transition matrix
# transition_matrix = [
#     [0.0, 0.7, 0.3, 0.0, 0.0, 0.0, 0],  # Transition from "Infected" to "Symptomatic"
#     [0.0, 0.0, 0.5, 0.2, 0.1, 0.0, 0.2],
#     [0.0, 0.0, 0.0, 0.4, 0.2, 0.0, 0.4],
#     [0.0, 0.0, 0.0, 0.0, 0.7, 0.0, 0.3],
#     [0.0, 0.0, 0.0, 0.0, 0.0, 0.4, 0.6],
#     [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0], 
#     [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
# ]

# # Define the distribution type matrix
# distribution_type_matrix = [
#     [1, 2, 1, 1, 1, 1, 1],  # Distribution types for transitions from "Infected"
#     [1, 1, 2, 1, 1, 1, 1],
#     [1, 1, 1, 2, 1, 1, 1],
#     [1, 1, 1, 1, 2, 1, 1],
#     [1, 1, 1, 1, 1, 2, 1],
#     [1, 1, 1, 1, 1, 1, 2], 
#     [1, 1, 1, 1, 1, 1, 1]
# ]

def run_simulation(transition_matrix, mean_time_interval_matrix, std_dev_time_interval_matrix, min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, initial_state, desired_iterations, age, vaccination_status):
    current_state = states.index(initial_state)
    total_time_steps = 0
    simulation_data = []
    
    simulation_data.append([initial_state, total_time_steps])

    def transition():
        nonlocal current_state
        age_multiplier = 1 + (age / 100)

        # Adjust transition weights based on age and vaccination status
        if vaccination_status == "Yes":
            vaccination_multiplier = 0.8
        else:
            vaccination_multiplier = 1.0

        original_weights = transition_matrix[current_state]
        weighted_transition = [weight * age_multiplier * vaccination_multiplier for weight in original_weights]
        
        # Normalize the weights to ensure they sum up to 1
        sum_weights = sum(weighted_transition)
        normalized_weights = [weight / sum_weights for weight in weighted_transition]

        next_state = random.choices(states, weights=normalized_weights)[0]

        current_state = states.index(next_state)
        return next_state

    def sample_time_interval(mean_matrix, std_dev_matrix, min_matrix, max_matrix, distribution_matrix, current_state_index, next_state_index):
        age_multiplier = 1 + (age / 100)

        # Adjust time interval based on age and vaccination status
        if vaccination_status == "Yes":
            vaccination_multiplier = 0.8
        else:
            vaccination_multiplier = 1.0
        while True:
            if distribution_matrix[current_state_index][next_state_index] == 1:  # Normal distribution
                interval = int(random.normalvariate(
                    mean_matrix[current_state_index][next_state_index] * age_multiplier * vaccination_multiplier,
                    std_dev_matrix[current_state_index][next_state_index]
                ))
            elif distribution_matrix[current_state_index][next_state_index] == 2:  # Exponential distribution
                interval = int(random.expovariate(
                    1 / (mean_matrix[current_state_index][next_state_index] * age_multiplier * vaccination_multiplier)
                ))
            elif distribution_matrix[current_state_index][next_state_index] == 3:  # Uniform distribution
                interval = int(random.uniform(
                    min_matrix[current_state_index][next_state_index] * age_multiplier * vaccination_multiplier,
                    max_matrix[current_state_index][next_state_index] * age_multiplier * vaccination_multiplier
                ))
            else:
                raise ValueError(f"Unsupported distribution type {distribution_matrix[current_state_index][next_state_index]}")
            
            if min_matrix[current_state_index][next_state_index] <= interval <= max_matrix[current_state_index][next_state_index]:
                return interval

    iterations = 0
    while iterations < desired_iterations:
        next_state = transition()
        next_state_index = states.index(next_state)  # convert next_state to its index
        time_interval = sample_time_interval(mean_time_interval_matrix, std_dev_time_interval_matrix, min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, current_state, next_state_index) * 60 * 24
        total_time_steps += time_interval
        current_state_str = states[current_state]

        simulation_data.append([current_state_str, total_time_steps])

        if states[current_state] in ["Removed", "Recovered"]:
            break

        iterations += 1

    return simulation_data
