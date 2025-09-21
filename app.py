from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
import requests
import threading
import time


app = Flask(__name__)

# Enable CORS
CORS(app)

# Global variable to track DMP API initialization status
_dmp_initialized = False
_dmp_init_lock = threading.Lock()
_last_init_attempt = 0

# Initialize DMP API when the server starts
def initialize_dmp_api():
    global _dmp_initialized, _last_init_attempt
    
    # Avoid repeated initialization attempts within 60 seconds
    current_time = time.time()
    if _dmp_initialized or (current_time - _last_init_attempt) < 60:
        return _dmp_initialized
    
    with _dmp_init_lock:
        if _dmp_initialized:
            return True
            
        _last_init_attempt = current_time
        BASE_URL = DMP_API["base_url"]
        init_payload = {
            "matrices_path": DMP_API["paths"]["matrices_path"],
            "mapping_path": DMP_API["paths"]["mapping_path"],
            "states_path": DMP_API["paths"]["states_path"]
        }
        
        try:
            init_response = requests.post(f"{BASE_URL}/initialize", json=init_payload, timeout=10)
            init_response.raise_for_status()
            print("DMP API successfully initialized!")
            _dmp_initialized = True
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to initialize DMP API: {e}")
            _dmp_initialized = False
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

    # Initialize DMP API before running simulation (with caching)
    if not initialize_dmp_api():
        print("Warning: DMP API initialization failed, simulation will use fallback timelines")

    # Get simulation length from request or use default
    length = request.json.get('length', SIMULATION["default_max_length"])
    location = request.json.get('location', SIMULATION["default_location"])
    interventions = {}
    
    # Build interventions dict from request, using defaults for missing values
    if not request.json or not any(key in request.json for key in SIMULATION["default_interventions"]):
        for key in SIMULATION["default_interventions"]:
            interventions[key] = request.json.get(key, SIMULATION["default_interventions"][key])
        print("Using default interventions:", interventions)
    # if the interventions are provided from rerunner.py (AI-counterfactual-analysis repo/src/sparser/rerunner.py), use those 
    elif isinstance(request.json, dict):
        interventions = request.json
        print("Using provided interventions:", interventions)
        
    try:
        # Enable optimized logging for better performance
        result = simulate.run_simulator(
            location, 
            length, 
            interventions, 
            save_file=False,
            enable_logging=True,
            log_dir=f"simulation_logs_{int(time.time())}"
        )
        return result
    except Exception as e:
        print("Simulation error:", repr(e))
        return jsonify({"error": str(e)}), 400


@app.route("/", methods=['GET'])
@cross_origin()
def run_main():
    """
    Basic simulation endpoint for testing.
    """
    # Initialize DMP API before running simulation (with caching)
    if not initialize_dmp_api():
        print("Warning: DMP API initialization failed, simulation will use fallback timelines")
    
    # Use default values from config with optimizations
    return simulate.run_simulator(
        save_file=False,
        enable_logging=True,
        log_dir=f"simulation_logs_{int(time.time())}"
    )


if __name__ == '__main__':
    # Initialize DMP API when the server starts
    initialize_dmp_api()
    app.run(host=SERVER["host"], port=SERVER["port"])
