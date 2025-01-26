from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from dmp.user_input import validate_matrices, find_matching_matrix, extract_matrices, parse_mapping_file
import pandas as pd
from io import StringIO
import numpy as np

app = Flask(__name__)

# Enable CORS
CORS(app)

@app.route("/simulation/", methods=['POST', 'GET'])
@cross_origin()
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": "Bad Request"}), 400

    if not request.json:
        return jsonify({"error": "No data sent"}), 400

    # Simulation length in minutes
    length = request.json.get('length', 10080)

    try:
        return simulate.run_simulator(request.json.get('matrices'), request.json.get('location', 'barnsdall'), length, {
            'mask': request.json.get('mask', 0.4),
            'vaccine': request.json.get('vaccine', 0.2),
            'capacity': request.json.get('capacity', 1.0),
            'lockdown': request.json.get('lockdown', 0),
            'selfiso': request.json.get('selfiso', 0.5),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/dmp/", methods=['POST'])
@cross_origin()
def run_dmp_simulation_endpoint():
    """
    Endpoint to run Disease Modeling Platform (DMP) simulation.
    """
    try:
        # Force JSON parsing
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": "Bad Request"}), 400

    if not request.json:
        return jsonify({"error": "No data sent"}), 400

    try:
        # Parse input parameters
        demographic_mapping = request.json.get('demographic_mapping')
        combined_matrices = request.json.get('combined_matrices')
        demographics = request.json.get('demographics', {})
        initial_state = request.json.get('initial_state', default_initial_state)

        # Convert string CSVs to pandas DataFrame
        mapping_df = pd.read_csv(StringIO(demographic_mapping))
        combined_matrix_df = pd.read_csv(StringIO(combined_matrices), header=None)

        # Ensure 'Matrix_Set' column exists in the demographic mapping file
        if "Matrix_Set" not in mapping_df.columns:
            return jsonify({"error": "'Matrix_Set' column missing in demographic mapping"}), 400

        # Extract demographic categories
        demographic_categories = [col for col in mapping_df.columns if col != "Matrix_Set"]

        # Find matching matrix set and extract matrices
        matrix_set = find_matching_matrix(demographics, mapping_df, demographic_categories)
        matrices = extract_matrices(matrix_set, combined_matrix_df)

        # Validate matrices
        validate_matrices(
            transition_matrix=matrices["Transition Matrix"],
            mean_matrix=matrices["Mean"],
            std_dev_matrix=matrices["Standard Deviation"],
            min_cutoff_matrix=matrices["Min Cut-Off"],
            max_cutoff_matrix=matrices["Max Cut-Off"],
            distribution_matrix=matrices["Distribution Type"]
        )

        # Run the simulation using positional arguments
        simulation_data = run_simulation(
            matrices["Transition Matrix"],  # Positional argument 1
            matrices["Mean"],               # Positional argument 2
            matrices["Standard Deviation"], # Positional argument 3
            matrices["Min Cut-Off"],        # Positional argument 4
            matrices["Max Cut-Off"],        # Positional argument 5
            matrices["Distribution Type"],  # Positional argument 6
            initial_state                   # Positional argument 7
        )

        # Return the simulation results as JSON
        return jsonify({"status": "success", "simulation_data": simulation_data})

    except Exception as e:
        return jsonify({"error": f"Error during DMP simulation: {e}"}), 400

# Define the states variable at the top level
states = ["Infected", "Infectious Asymptomatic", "Infectious Symptomatic", "Hospitalized", "ICU", "Removed", "Recovered"]

# Default initial state
default_initial_state = "Infected"

def run_simulation(transition_matrix, mean_time_interval_matrix, std_dev_time_interval_matrix, 
                   min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, 
                   initial_state, max_iterations=1000):
    current_state = states.index(initial_state)
    total_time_steps = 0
    simulation_data = []
    iteration_count = 0  # Track the number of iterations
    
    # Keep track of the timeline for the line graph
    simulation_data.append([initial_state, total_time_steps])
    print(f"Starting simulation with initial state: {initial_state}")

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
    while iteration_count < max_iterations:
        next_state = transition()
        next_state_index = states.index(next_state)

        # Calculate time interval for transition
        time_interval = sample_time_interval(mean_time_interval_matrix, std_dev_time_interval_matrix, 
                                             min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, 
                                             current_state, next_state_index) * 60 * 24
        total_time_steps += time_interval
        simulation_data.append([states[next_state_index], total_time_steps])

        print(f"Current timeline: {simulation_data}")

        current_state = next_state_index
        iteration_count += 1

        # Stop if reaching a terminal state after spending time in the last state
        if states[current_state] in ["Removed", "Recovered"]:
            print(f"Ending simulation at terminal state: {states[current_state]}")
            break

    # Handle max iteration limit reached
    if iteration_count >= max_iterations:
        print(f"Max iterations ({max_iterations}) reached. Forcing transition to Recovered.")
        simulation_data.append(["Recovered", total_time_steps])

    return simulation_data  # Return timeline of states and time

@app.route("/", methods=['GET'])
@cross_origin()
def run_main():
    """
    Basic simulation endpoint for testing.
    """
    return simulate.run_simulator(None, 'barnsdall', 10080, {
        'mask': 0.0,
        'vaccine': 0.0,
        'capacity': 1.0,
        'lockdown': 0,
        'selfiso': 0.0
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000)
