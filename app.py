from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from Simulation.dmp.core.simulation_functions import run_simulation, states, default_initial_state
from Simulation.dmp.cli.user_input import validate_matrices, find_matching_matrix, extract_matrices, parse_mapping_file
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
