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
    [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0]
]

def run_simulation(transition_matrix, mean_time_interval, std_dev_time_interval, initial_state, desired_iterations, age, ethnicity, group_quarters, length_of_stay, num_under_5, mobile_home, origin):
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
    # Initialize flags for printing messages
    age_multiplier_applied = False
    ethnicity_multiplier_applied = False
    group_quarters_multiplier_applied = False
    length_of_stay_multiplier_applied = False
    num_under_5_multiplier_applied = False
    mobile_home_multiplier_applied = False
    origin_multiplier_applied = False

    while iterations < desired_iterations:
        time_interval = sample_time_interval(mean_time_interval, std_dev_time_interval)
        total_time_steps += time_interval
        current_state_str = states[current_state]

        simulation_data.append([current_state_str, total_time_steps])

        if states[current_state] in ["Removed", "Recovered"]:
            break

        # Adjust transition probabilities based on age
        age_multiplier = 1.0
        if age < 18 and not age_multiplier_applied:
            # Decrease the risk of being removed for individuals under 18
            age_multiplier = 0.8
            transition_matrix[states.index("Removed")][states.index("Removed")] *= age_multiplier
            print("Age multiplier applied")
            age_multiplier_applied = True

        # Adjust transition probabilities based on ethnicity
        ethnicity_multiplier = 1.0
        if ethnicity == "Asian" and not ethnicity_multiplier_applied:
            # Increase the risk of symptomatic, infectious, and removed for Asian individuals
            ethnicity_multiplier = 1.2
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= ethnicity_multiplier
            transition_matrix[states.index("Infectious")][states.index("Infectious")] *= ethnicity_multiplier
            transition_matrix[states.index("Removed")][states.index("Removed")] *= ethnicity_multiplier
            print("Ethnicity multiplier applied (Asian)")
            ethnicity_multiplier_applied = True
        elif ethnicity == "White" and not ethnicity_multiplier_applied:
            # Increase the risk of symptomatic and infectious for White individuals
            ethnicity_multiplier = 1.1
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= ethnicity_multiplier
            print("Ethnicity multiplier applied (White)")
            ethnicity_multiplier_applied = True

        # Adjust transition probabilities based on group_quarters
        group_quarters_multiplier = 1.0
        if group_quarters and not group_quarters_multiplier_applied:
            # Increase the risk of symptomatic and infectious for individuals in group quarters
            group_quarters_multiplier = 1.1
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= group_quarters_multiplier
            transition_matrix[states.index("Infectious")][states.index("Infectious")] *= group_quarters_multiplier
            print("Group Quarters multiplier applied")
            group_quarters_multiplier_applied = True

        # Adjust transition probabilities based on length_of_stay
        length_of_stay_multiplier = 1.0
        if length_of_stay > 1 and not length_of_stay_multiplier_applied:
            # Decrease the risk of symptomatic and infectious for individuals with a length of stay greater than 1 year
            length_of_stay_multiplier = 0.9
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= length_of_stay_multiplier
            transition_matrix[states.index("Infectious")][states.index("Infectious")] *= length_of_stay_multiplier
            print("Length of Stay multiplier applied")
            length_of_stay_multiplier_applied = True

        # Adjust transition probabilities based on the number of people under 5
        num_under_5_multiplier = 1.0
        if num_under_5 > 0 and not num_under_5_multiplier_applied:
            # Increase the risk of symptomatic, infectious, and removed for individuals with more people under 5
            num_under_5_multiplier = 1.2
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= num_under_5_multiplier
            transition_matrix[states.index("Infectious")][states.index("Infectious")] *= num_under_5_multiplier
            transition_matrix[states.index("Removed")][states.index("Removed")] *= num_under_5_multiplier
            print("Number of people under 5 multiplier applied")
            num_under_5_multiplier_applied = True

        # Adjust transition probabilities based on mobile home
        mobile_home_multiplier = 1.0
        if mobile_home and not mobile_home_multiplier_applied:
            # Increase the risk of removed for individuals living in a mobile home
            mobile_home_multiplier = 1.2
            transition_matrix[states.index("Removed")][states.index("Removed")] *= mobile_home_multiplier
            print("Mobile Home multiplier applied")
            mobile_home_multiplier_applied = True

        # Adjust transition probabilities based on origin
        origin_multiplier = 1.0
        if origin == "Foreign-born" and not origin_multiplier_applied:
            # Decrease the risk of symptomatic and infectious for foreign-born individuals
            origin_multiplier = 0.9
            transition_matrix[states.index("Symptomatic")][states.index("Symptomatic")] *= origin_multiplier
            transition_matrix[states.index("Infectious")][states.index("Infectious")] *= origin_multiplier
            print("Origin multiplier applied (Foreign-born)")
            origin_multiplier_applied = True

        # Use the adjusted transition matrix for the next state transition
        next_state = transition()
        iterations += 1

    return simulation_data
