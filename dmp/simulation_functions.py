import random

# Define the states variable at the top level
states = ["Symptomatic", "Infectious", "Hospitalized", "ICU", "Removed", "Recovered"]

# Define other default values and transition matrix
default_mean_time_interval = 5
default_std_dev_time_interval = 2
default_initial_state = "Symptomatic"

# Define the transition matrix
transition_matrix = [
    [0.0, 0.5, 0.2, 0.0, 0.0, 0.3],
    [0.0, 0.0, 0.4, 0.1, 0.0, 0.5],
    [0.0, 0.0, 0.0, 0.6, 0.0, 0.4],
    [0.0, 0.0, 0.0, 0.0, 0.3, 0.7],
    [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
]

def run_simulation(transition_matrix, mean_time_interval, std_dev_time_interval, initial_state, desired_iterations):
    states = ["Symptomatic", "Infectious", "Hospitalized", "ICU", "Removed", "Recovered"]

    current_state = states.index(initial_state)
    total_time_steps = 0

    simulation_data = []

    def transition():
        nonlocal current_state
        next_state = random.choices(states, weights=transition_matrix[current_state])[0]
        current_state = states.index(next_state)
        return next_state

    def sample_time_interval(mean, std_dev):
        while True:
            interval = int(random.normalvariate(mean, std_dev))
            if interval >= 0:
                return interval

    iterations = 0
    while iterations < desired_iterations:
        time_interval = sample_time_interval(mean_time_interval, std_dev_time_interval)
        total_time_steps += time_interval
        current_state_str = states[current_state]

        simulation_data.append([current_state_str, total_time_steps])

        if states[current_state] in ["Recovered", "Removed"]:
            break

        next_state = transition()
        iterations += 1

    return simulation_data
