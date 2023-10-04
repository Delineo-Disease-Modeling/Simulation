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

# Simulate disease progression for an individual
for _ in range(10):
    print("Current state:", states[current_state])

    # Check if the current state is "Recovered" or "Removed" and stop the simulation
    if states[current_state] in ["Recovered", "Removed"]:
        print("Reached terminal state. Simulation stopped.")
        break

    next_state = transition()
    print()



