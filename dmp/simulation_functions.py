import random

# Define the states variable at the top level
states = ["Null", "Symptomatic", "Infectious", "Hospitalized", "ICU", "Removed", "Recovered"]

# Define other default values and transition matrix
default_mean_time_interval = 5
default_std_dev_time_interval = 2
default_initial_state = "Null"

# Define the transition matrix
transition_matrix = [
    [0.0, 0.5, 0.2, 0.0, 0.0, 0.0, 0],  # Transition from "Null" to "Symptomatic"
    [0.0, 0.0, 0.4, 0.1, 0.0, 0.0, 0.5],
    [0.0, 0.0, 0.0, 0.6, 0.0, 0.0, 0.4],
    [0.0, 0.0, 0.0, 0.0, 0.3, 0.0, 0.7],
    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0], 
    [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
]

def run_simulation(transition_matrix, mean_time_interval_matrix, std_dev_time_interval_matrix, initial_state, desired_iterations):
    current_state = states.index(initial_state)
    total_time_steps = 0
    simulation_data = []

    def transition():
        nonlocal current_state
        next_state = random.choices(states, weights=transition_matrix[current_state])[0]
        current_state = states.index(next_state)
        return next_state

    def sample_time_interval(mean_matrix, std_dev_matrix, current_state_index, next_state_index):
        while True:
            interval = int(random.normalvariate(mean_matrix[current_state_index][next_state_index], std_dev_matrix[current_state_index][next_state_index]))
            if interval >= 0:
                return interval

    iterations = 0
    while iterations < desired_iterations:
        next_state = transition()
        next_state_index = states.index(next_state)  # convert next_state to its index
        time_interval = sample_time_interval(mean_time_interval_matrix, std_dev_time_interval_matrix, current_state, next_state_index)
        total_time_steps += time_interval
        current_state_str = states[current_state]

        simulation_data.append([current_state_str, total_time_steps])

        if states[current_state] in ["Removed", "Recovered"]:
            break

        iterations += 1

    return simulation_data
