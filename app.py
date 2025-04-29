from flask import Flask, request, jsonify, Response
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
import requests
import json

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
    
def simulation(cz_id, length, interventions):
    yield ''
    try:
        data = json.dumps(simulate.run_simulator(cz_id, length, interventions))
        
        # Upload generated data to DB
        if length == 10080:
            resp = requests.post('https://db.delineo.me/simdata', json={
                'czone_id': int(cz_id),
                'simdata': data
            })
            
            if resp.ok:
                print(f'Uploaded cached simulator data for #{cz_id}')
            else:
                print(f'Could not upload cached data for #{cz_id}')
                
        print('success!')
        
        yield data
    except Exception as e:
        print(e)
        yield '{}'

@app.route("/simulation/", methods=['POST'])
@cross_origin()
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    # Initialize DMP API before running simulation
    #initialize_dmp_api()

    # Get simulation length from request or use default
    length = request.json.get('length', SIMULATION["default_max_length"])
    cz_id = request.json.get('czone_id', 1)
        
    # Build interventions dict from request, using defaults for missing values
    interventions = {}
    for key in SIMULATION["default_interventions"]:
        interventions[key] = request.json.get(key, SIMULATION["default_interventions"][key])
        
    return Response(simulation(cz_id, length, interventions))


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
