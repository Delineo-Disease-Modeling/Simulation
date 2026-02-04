from io import BytesIO
import json
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from jsonschema import validate, ValidationError, SchemaError
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DELINEO, DMP_API, SERVER
import requests

app = Flask(__name__)

# Enable CORS
CORS(app,
  origins=['http://localhost:5173', 'https://coviddev.isi.jhu.edu', 'http://coviddev.isi.jhu.edu', 'https://covidweb.isi.jhu.edu', 'http://covidweb.isi.jhu.edu'],
  methods=['GET', 'HEAD', 'PUT', 'PATCH', 'POST', 'DELETE'],
  allow_headers=['Content-Type', 'Authorization'],
  expose_headers=['Set-Cookie'],
  supports_credentials=True
)

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
    
simulation_schema = {
    "type": "object",
    "properties": {
        "czone_id": { "type": "integer", "minimum": 1 },
        "length": { "type": "integer", "minimum": 1 },
        "randseed": { "type": "boolean" },
        "interventions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "time": { "type": "integer", "minimum": 0 },
                    "mask": { "type": "number", "minimum": 0, "maximum": 1 },
                    "vaccine": { "type": "number", "minimum": 0, "maximum": 1 },
                    "capacity": { "type": "number", "minimum": 0, "maximum": 1 },
                    "lockdown": { "type": "number", "minimum": 0, "maximum": 1 },
                    "selfiso": { "type": "number", "minimum": 0, "maximum": 1 },
                },
                "required": [ "time", "mask", "vaccine", "capacity", "lockdown", "selfiso" ]
            }
        }
    },
    "required": [ "czone_id", "length", "interventions" ]
}

@app.route("/simulation/", methods=['POST'])
@cross_origin()
def run_simulation_endpoint():
    try:
        request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400
    
    try:
        validate(instance=request.json, schema=simulation_schema)
    except:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400
        
    # Initialize DMP API before running simulation
    initialize_dmp_api()

    try:
        final_result = simulate.run_simulator(request.json, enable_logging=False)
        
        print('sending data...')

        resp = requests.post(f'{DELINEO["DB_URL"]}simdata', data={
            'czone_id': int(request.json['czone_id']),
        }, files={
            'simdata': ('simdata.json', BytesIO(json.dumps(final_result['result']).encode()), 'text/plain'),
            'patterns': ('patterns.json', BytesIO(json.dumps(final_result['movement']).encode()), 'text/plain')
        })
        
        if resp.ok:
            print('sent!')
        else:
            print(f'error sending data... {resp.status_code}')
            return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400
        
        return jsonify({ "data": { 'id': resp.json()['data']['id'] } })

    except Exception as e:
        print("Simulation error:", repr(e))
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
