from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
import requests

app = Flask(__name__)

# Enable CORS
CORS(app)

# Initialize DMP API when the server starts
def initialize_dmp_api():
    BASE_URL = "http://localhost:8000"
    init_payload = {
        "matrices_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing_copy/combined_matrices_usecase.csv",
        "mapping_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing_copy/demographic_mapping_usecase.csv",
        "states_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/api_testing_copy/custom_states.txt"
        #"matrices_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing_copy/combined_matrices_usecase.csv",
        #"mapping_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing_copy/demographic_mapping_usecase.csv",
        #"states_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/api_testing_copy/custom_states.txt"
    }
    
    try:
        init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload)
        init_response.raise_for_status()
        print("DMP API successfully initialized!")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to initialize DMP API: {e}")
        return False

@app.route("/simulation/", methods=['POST', 'GET'])
@cross_origin()
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": "Bad Request"}), 400

    if not request.json:
        return jsonify({"error": "No data sent"}), 400

    # Initialize DMP API before running simulation
    initialize_dmp_api()

    # Simulation length in minutes
    length = request.json.get('length', 10080)

    try:
        return simulate.run_simulator(request.json.get('matrices'), request.json.get('location', 'barnsdall'), length, {
            'mask': request.json.get('mask', 0.4),
            'vaccine': request.json.get('vaccine', 0.2),
            'capacity': request.json.get('capacity', 1.0),
            'lockdown': request.json.get('lockdown', 0),
            'selfiso': request.json.get('selfiso', 0.5),
            'randseed': request.json.get('randseed', True)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/", methods=['GET'])
@cross_origin()
def run_main():
    """
    Basic simulation endpoint for testing.
    """
    # Initialize DMP API before running simulation
    initialize_dmp_api()
    
    return simulate.run_simulator(None, 'barnsdall', 10080, {
        'mask': 0.0,
        'vaccine': 0.0,
        'capacity': 1.0,
        'lockdown': 0,
        'selfiso': 0.0,
        'randseed': False
    })


if __name__ == '__main__':
    # Initialize DMP API when the server starts
    initialize_dmp_api()
    app.run(host='0.0.0.0', port=1880)
