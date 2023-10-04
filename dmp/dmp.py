import random;

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

# Initialize the initial state (e.g., a person starts as "Infectious")
current_state = states.index("Symptomatic")

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

# Set parameters for time intervals (mean and standard deviation)
mean_time_interval = 5  
std_dev_time_interval = 2 

total_time_steps = 0



# Simulate disease progression for an individual
while True:
    time_interval = sample_time_interval(mean_time_interval, std_dev_time_interval)
    total_time_steps += time_interval
    print(f"Current state:", states[current_state], "|  Time step:", total_time_steps)

    # Check if the current state is "Recovered" or "Removed" and stop the simulation
    if states[current_state] in ["Recovered", "Removed"]:
        print("Reached terminal state. Simulation stopped.")
        break

    next_state = transition()
    print()



