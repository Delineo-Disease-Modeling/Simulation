from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
import requests


app = Flask(__name__)

# Enable CORS
CORS(app)

# Initialize DMP API when the server starts
def initialize_dmp_api():
    BASE_URL = DMP_API["base_url"]
    init_payload = {
        "matrices_path": DMP_API["paths"]["matrices_path"],
        "mapping_path": DMP_API["paths"]["mapping_path"],
        "states_path": DMP_API["paths"]["states_path"]
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
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    # Initialize DMP API before running simulation
    initialize_dmp_api()

    # Get simulation length from request or use default
    length = request.json.get('length', SIMULATION["default_max_length"])
    location = request.json.get('location', SIMULATION["default_location"])
    
    # Build interventions dict from request, using defaults for missing values
    interventions = {}
    for key in SIMULATION["default_interventions"]:
        interventions[key] = request.json.get(key, SIMULATION["default_interventions"][key])

    try:
        return simulate.run_simulator(location, length, interventions)
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
    
    # Use default values from config
    return simulate.run_simulator()


if __name__ == '__main__':
    # Initialize DMP API when the server starts
    initialize_dmp_api()
    app.run(host=SERVER["host"], port=SERVER["port"])
