import numpy as np
from typing import List, Tuple

def run_simulation(transition_matrix, mean_matrix, std_dev_matrix, 
                  min_cutoff_matrix, max_cutoff_matrix, distribution_matrix,
                  initial_state_idx, states: List[str]) -> List[Tuple[str, float]]:
    """Run a single simulation of disease progression
    
    Note: Input matrices contain times in days, but output timeline is in hours
    
    Args:
        transition_matrix: Matrix of transition probabilities
        mean_matrix: Matrix of mean transition times
        std_dev_matrix: Matrix of standard deviations
        min_cutoff_matrix: Matrix of minimum transition times
        max_cutoff_matrix: Matrix of maximum transition times
        distribution_matrix: Matrix of distribution types
        initial_state_idx: Index of initial state
        states: List of state names
    
    Returns:
        List of (state_name, time) tuples where time is in hours
    """
    HOURS_PER_DAY = 24  # Convert days to hours
    
    # Initialize current state with the provided index
    current_state = int(initial_state_idx)  # Ensure it's an integer
    timeline = [(states[current_state], 0.0)]  # Start at time 0
    total_time = 0.0
    max_iterations = 1000  # Add safety limit
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        # Get transition probabilities for current state
        transition_probs = transition_matrix[current_state]
        
        # If all transition probabilities are 0, we're in a terminal state
        if np.sum(transition_probs) == 0:
            break
            
        # Choose next state based on transition probabilities
        next_state = np.random.choice(len(states), p=transition_probs)
        
        # If we stay in the same state, increment counter but don't add to timeline
        if next_state == current_state:
            continue
            
        # Generate time for this transition (in days)
        time_days = generate_transition_time(
            mean_matrix[current_state][next_state],
            std_dev_matrix[current_state][next_state],
            min_cutoff_matrix[current_state][next_state],
            max_cutoff_matrix[current_state][next_state],
            distribution_matrix[current_state][next_state]
        )
        
        # Convert days to hours
        time_hours = time_days * HOURS_PER_DAY
        
        total_time += time_hours
        timeline.append((states[next_state], total_time))
        current_state = next_state
        
        # Check if we've reached a terminal state (Recovered or Deceased)
        if states[current_state] in ["Recovered", "Deceased"]:
            break
    
    if iteration >= max_iterations:
        print(f"Warning: Simulation stopped after {max_iterations} iterations")
    
    return timeline

def generate_transition_time(mean: float, std_dev: float, 
                           min_cutoff: float, max_cutoff: float, 
                           distribution_type: int) -> float:
    """Generate time for transitioning between states
    
    Args:
        mean: Mean time for transition
        std_dev: Standard deviation
        min_cutoff: Minimum allowed time
        max_cutoff: Maximum allowed time
        distribution_type: Type of distribution (0-4)
            0: Fixed (mean)
            1: Normal
            2: Uniform
            3: Log-normal
            4: Gamma
    
    Returns:
        float: Generated transition time
    """
    while True:
        if distribution_type == 0:  # Fixed time
            return mean
            
        elif distribution_type == 1:  # Normal
            time = np.random.normal(mean, std_dev)
            
        elif distribution_type == 2:  # Uniform
            time = np.random.uniform(mean - std_dev, mean + std_dev)
            
        elif distribution_type == 3:  # Log-normal
            # Convert mean and std_dev to log-normal parameters
            mu = np.log(mean**2 / np.sqrt(std_dev**2 + mean**2))
            sigma = np.sqrt(np.log(1 + (std_dev**2 / mean**2)))
            time = np.random.lognormal(mu, sigma)
            
        elif distribution_type == 4:  # Gamma
            # Convert mean and std_dev to gamma parameters
            shape = (mean / std_dev)**2
            scale = std_dev**2 / mean
            time = np.random.gamma(shape, scale)
            
        else:
            raise ValueError(f"Unknown distribution type: {distribution_type}")
            
        # Ensure time falls within allowed range
        if min_cutoff <= time <= max_cutoff:
            return time

def validate_matrices(transition_matrix, mean_matrix, std_dev_matrix,
                     min_cutoff_matrix, max_cutoff_matrix, distribution_matrix):
    """Validate all matrices have correct properties
    
    Args:
        transition_matrix: Matrix of transition probabilities
        mean_matrix: Matrix of mean transition times
        std_dev_matrix: Matrix of standard deviations
        min_cutoff_matrix: Matrix of minimum transition times
        max_cutoff_matrix: Matrix of maximum transition times
        distribution_matrix: Matrix of distribution types
    
    Raises:
        ValueError: If any matrix fails validation
    """
    # Check transition matrix properties
    if not np.all((transition_matrix >= 0) & (transition_matrix <= 1)):
        raise ValueError("Transition probabilities must be between 0 and 1")
        
    row_sums = np.sum(transition_matrix, axis=1)
    if not np.allclose(row_sums, 1.0) and not np.allclose(row_sums, 0.0):
        raise ValueError("Transition matrix rows must sum to 1 or 0")
    
    # Check other matrices
    if not np.all(mean_matrix >= 0):
        raise ValueError("Mean times must be non-negative")
        
    if not np.all(std_dev_matrix >= 0):
        raise ValueError("Standard deviations must be non-negative")
        
    if not np.all(min_cutoff_matrix <= max_cutoff_matrix):
        raise ValueError("Min cutoff must be less than or equal to max cutoff")
        
    if not np.all((distribution_matrix >= 0) & (distribution_matrix <= 4)):
        raise ValueError("Distribution types must be between 0 and 4") 