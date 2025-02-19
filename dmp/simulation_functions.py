import random
import numpy as np
import matplotlib.pyplot as plt

# Define the states variable at the top level
states = ["Infected", "Infectious Asymptomatic", "Infectious Symptomatic", "Hospitalized", "ICU", "Removed", "Recovered"]

# Default initial state
default_initial_state = "Infected"

def run_simulation(transition_matrix, mean_matrix, std_matrix, min_cutoff, max_cutoff, dist_type_matrix, initial_state_idx):
    """
    Run the simulation with the given parameters
    
    Args:
        transition_matrix: numpy array of transition probabilities
        mean_matrix: numpy array of mean times
        std_matrix: numpy array of standard deviations
        min_cutoff: numpy array of minimum cutoff times
        max_cutoff: numpy array of maximum cutoff times
        dist_type_matrix: numpy array of distribution types
        initial_state_idx: integer index of the initial state
    """
    current_state = initial_state_idx
    current_time = 0
    timeline = [(current_state, current_time)]
    
    # Keep track of the timeline for the line graph
    print(f"Starting simulation with initial state: {states[current_state]}")

    def transition():
        nonlocal current_state
        # Filter out zero-probability transitions
        non_zero_states = [s for s, prob in zip(states, transition_matrix[current_state]) if prob > 0]
        non_zero_weights = [prob for prob in transition_matrix[current_state] if prob > 0]

        # Debugging output to show current state, probabilities, and next state options
        print(f"Transitioning from {states[current_state]}. Available states and probabilities: {dict(zip(non_zero_states, non_zero_weights))}")
        
        # Select the next state based on non-zero probabilities
        next_state = random.choices(non_zero_states, weights=non_zero_weights)[0]
        next_state_index = states.index(next_state)

        # Debugging output for selected transition
        print(f"Transitioned to {next_state}")

        return next_state

    def sample_time_interval(mean_matrix, std_dev_matrix, min_matrix, max_matrix, distribution_matrix, current_state_index, next_state_index):
        # Sample time interval based on the specified distribution type
        dist_type = distribution_matrix[current_state_index][next_state_index]

        if dist_type == 1:  # Normal distribution
            interval = int(random.normalvariate(mean_matrix[current_state_index][next_state_index], std_dev_matrix[current_state_index][next_state_index]))
        elif dist_type == 2:  # Exponential distribution
            interval = int(random.expovariate(1 / mean_matrix[current_state_index][next_state_index]))
        elif dist_type == 3:  # Uniform distribution
            interval = int(random.uniform(min_matrix[current_state_index][next_state_index], max_matrix[current_state_index][next_state_index]))
        elif dist_type == 4:  # Gamma distribution
            shape = (mean_matrix[current_state_index][next_state_index] / std_dev_matrix[current_state_index][next_state_index]) ** 2
            scale = std_dev_matrix[current_state_index][next_state_index] ** 2 / mean_matrix[current_state_index][next_state_index]
            interval = int(np.random.gamma(shape, scale))
        elif dist_type == 5:  # Beta distribution
            mean = mean_matrix[current_state_index][next_state_index]
            std_dev = std_dev_matrix[current_state_index][next_state_index]
            alpha = (mean * (mean * (1 - mean) / (std_dev ** 2)) - 1)
            beta = alpha * (1 - mean) / mean
            interval = int(np.random.beta(alpha, beta) * (max_matrix[current_state_index][next_state_index] - min_matrix[current_state_index][next_state_index]) + min_matrix[current_state_index][next_state_index])
        else:
            raise ValueError(f"Unsupported distribution type {dist_type}")
        
        # Ensure the interval falls within the min and max bounds; otherwise, resample
        if min_matrix[current_state_index][next_state_index] <= interval <= max_matrix[current_state_index][next_state_index]:
            print(f"Sampled interval: {interval} for transition from {states[current_state_index]} to {states[next_state_index]} using distribution type {dist_type}")
            return interval
        else:
            print(f"Resampling interval for out-of-bounds value: {interval} for transition from {states[current_state_index]} to {states[next_state_index]}")
            return sample_time_interval(mean_matrix, std_dev_matrix, min_matrix, max_matrix, distribution_matrix, current_state_index, next_state_index)

    # Simulation loop continues until reaching a terminal state or hitting the max iteration limit
    while True:
        next_state = transition()
        next_state_index = states.index(next_state)

        # Calculate time interval for transition
        time_interval = sample_time_interval(mean_matrix, std_matrix, min_cutoff, max_cutoff, dist_type_matrix, 
                                             current_state, next_state_index) * 60 * 24
        current_time += time_interval
        timeline.append((next_state_index, current_time))

        print(f"Current timeline: {timeline}")

        current_state = next_state_index

        # Stop if reaching a terminal state after spending time in the last state
        if states[current_state] in ["Removed", "Recovered"]:
            print(f"Ending simulation at terminal state: {states[current_state]}")
            break

    return timeline  # Return timeline of states and time

def visualize_state_timeline(simulation_data):
    # Extract the states and times from the simulation data
    timeline_states = [states[state_idx] for state_idx, _ in simulation_data]
    timeline_times = [time for _, time in simulation_data]

    # Create the line graph
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(timeline_times, timeline_states, marker='o', linestyle='-', linewidth=2)
    ax.set_xlabel('Time (minutes)')
    ax.set_ylabel('Disease States')
    ax.set_title('Timeline of Disease Progression')
    ax.grid(True)
    plt.tight_layout()

    # Return the figure to be displayed in Streamlit
    return fig
