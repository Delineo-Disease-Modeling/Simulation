from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS, cross_origin
from jsonschema import validate
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.jobs import start_simulation_job, stream_sse_messages
from simulator.config import SERVER
import os
import queue

app = Flask(__name__)

# Enable CORS
CORS(app,
  origins=['http://localhost:3000', 'http://localhost:5173', 'https://coviddev.isi.jhu.edu', 'http://coviddev.isi.jhu.edu', 'https://covidweb.isi.jhu.edu', 'http://covidweb.isi.jhu.edu', 'https://covidmod.isi.jhu.edu', 'http://covidweb.isi.jhu.edu'],
  methods=['GET', 'HEAD', 'PUT', 'PATCH', 'POST', 'DELETE'],
  allow_headers=['Content-Type', 'Authorization'],
  expose_headers=['Set-Cookie'],
  supports_credentials=True
)

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
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not data:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400
    
    try:
        validate(instance=data, schema=simulation_schema)
    except:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400
        
    msg_queue = queue.Queue()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    start_simulation_job(data, msg_queue, base_dir)
    return Response(
        stream_with_context(stream_sse_messages(msg_queue)),
        mimetype='text/event-stream',
    )


@app.route("/", methods=['GET'])
@cross_origin()
def run_main():
    """
    Basic simulation endpoint for testing.
    """
    # Use default values from config
    return simulate.run_simulator()


if __name__ == '__main__':
    app.run(host=SERVER["host"], port=SERVER["port"], threaded=True)
