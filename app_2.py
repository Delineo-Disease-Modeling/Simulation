from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
import cProfile
import pstats
import io
import os
from datetime import datetime
from functools import wraps

# Import the DMP functions directly
# Replace these imports with the actual module paths to your DMP functions
from dmp_functions import initialize_dmp, run_dmp_simulation  # Replace with actual DMP function imports

app = Flask(__name__)

# Enable CORS
CORS(app)

# Initialize DMP directly when the server starts
def initialize_dmp_direct():
    matrices_path = DMP_API["paths"]["matrices_path"]
    mapping_path = DMP_API["paths"]["mapping_path"]
    states_path = DMP_API["paths"]["states_path"]
    
    try:
        # Call the DMP initialization function directly
        initialize_dmp(matrices_path=matrices_path, mapping_path=mapping_path, states_path=states_path)
        print("DMP successfully initialized!")
        return True
    except Exception as e:
        print(f"Failed to initialize DMP: {e}")
        return False

def profile_decorator(func):
    """
    Decorator to profile a function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Create a new Profile instance for this function call
        pr = cProfile.Profile()
        pr.enable()
        
        # Execute the function
        result = func(*args, **kwargs)
        
        pr.disable()
        
        # Save and print profiling stats
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_dir = "profiles"
        os.makedirs(profile_dir, exist_ok=True)
        
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        
        profile_filename = f"{profile_dir}/{func.__name__}_{timestamp}.txt"
        with open(profile_filename, "w") as f:
            f.write(s.getvalue())
        
        print(f"Profile for {func.__name__} saved to {profile_filename}")
        print(s.getvalue())
        
        return result
    
    return wrapper

@app.route("/simulation/", methods=['POST', 'GET'])
@cross_origin()
@profile_decorator
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    # Initialize DMP directly before running simulation
    initialize_dmp_direct()

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
@profile_decorator
def run_main():
    """
    Basic simulation endpoint for testing.
    """
    # Initialize DMP directly before running simulation
    initialize_dmp_direct()
    
    # Use default values from config
    return simulate.run_simulator()


# Also profile the run_simulator function directly
@profile_decorator
def profiled_run_simulator(*args, **kwargs):
    return simulate.run_simulator(*args, **kwargs)

# Monkey patch the original function to use our profiled version
simulate.run_simulator = profiled_run_simulator

if __name__ == '__main__':
    # Initialize DMP directly when the server starts
    initialize_dmp_direct()
    
    # Run the Flask app normally
    app.run(host=SERVER["host"], port=SERVER["port"])