from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
import requests
from dmp_functions import initialize_dmp, run_dmp_simulation, DMPContext
import os
import sys
import cProfile
import pstats
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

# === Prevent duplicate runs using a PID file ===
PID_FILE = "flask_app.pid"

if os.path.exists(PID_FILE):
    print("Another instance is already running. Exiting to avoid conflicts.")
    sys.exit(1)

with open(PID_FILE, 'w') as f:
    f.write(str(os.getpid()))

# === Profiling setup ===
PROFILE_DIR = "profiles"
os.makedirs(PROFILE_DIR, exist_ok=True)

def profile_function(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        profile_filename = f"{PROFILE_DIR}/{func.__name__}_{timestamp}.prof"
        text_filename = f"{PROFILE_DIR}/{func.__name__}_{timestamp}.txt"

        profiler = cProfile.Profile()
        profiler.enable()
        result = func(*args, **kwargs)
        profiler.disable()

        # Save .prof and .txt files
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.dump_stats(profile_filename)

        with open(text_filename, 'w') as f:
            stats = pstats.Stats(profiler, stream=f)
            stats.sort_stats('cumulative')
            stats.print_stats(30)

        print(f"Profile saved: {profile_filename} and {text_filename}")
        return result
    return wrapper

# === Initialize DMP API ===
def initialize_dmp_api():
    try:
        initialize_dmp(DMPContext, 
                       matrices_path=DMP_API["paths"]["matrices_path"],
                       mapping_path=DMP_API["paths"]["mapping_path"],
                       states_path=DMP_API["paths"]["states_path"])
        print("DMP API initialized successfully!")
        return True
    except Exception as e:
        print(f"Failed to initialize DMP API: {e}")
        return False

@app.route("/simulation/", methods=['POST', 'GET'])
@cross_origin()
@profile_function
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    initialize_dmp_api()
    length = request.json.get('length', SIMULATION["default_max_length"])
    location = request.json.get('location', SIMULATION["default_location"])

    interventions = {
        key: request.json.get(key, SIMULATION["default_interventions"][key])
        for key in SIMULATION["default_interventions"]
    }

    try:
        return simulate.run_simulator(location, length, interventions)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/", methods=['GET'])
@cross_origin()
@profile_function
def run_main():
    initialize_dmp_api()
    return simulate.run_simulator()

# === Main block ===
if __name__ == '__main__':
    try:
        initialize_dmp_api()
        app.run(debug=False, host=SERVER["host"], port=SERVER["port"])
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
            print("PID file cleaned up.")
