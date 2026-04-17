from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS, cross_origin
from jsonschema import validate
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DELINEO, SERVER
import requests
import tempfile
import shutil
import os
import threading
import queue
import json
import time

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
        # If content-type is not json, try force
        data = request.get_json(force=True)
    except BadRequest:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not data:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400
    
    try:
        validate(instance=data, schema=simulation_schema)
    except:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400
        
    # Create a queue for communication
    msg_queue = queue.Queue()

    def run_sim_thread(sim_data):
        # Use a local temp directory for visibility/debugging
        base_dir = os.path.dirname(os.path.abspath(__file__))
        local_temp = os.path.join(base_dir, 'sim_temp')
        os.makedirs(local_temp, exist_ok=True)
        
        temp_dir = tempfile.mkdtemp(dir=local_temp)
        print(f'Created temp dir: {temp_dir}')

        last_progress = [-1]
        last_message = [None]
        def progress_callback(current_step, max_steps, message=None):
            progress = int((current_step / max_steps) * 100)
            msg_changed = message is not None and message != last_message[0]
            progress_changed = progress != last_progress[0]
            if msg_changed or progress_changed:
                last_progress[0] = progress
                if message is not None:
                    last_message[0] = message
                msg_queue.put({"type": "progress", "value": progress, "message": last_message[0]})

        try:
            # Pass output_dir to run_simulator so it writes files directly
            file_paths = simulate.run_simulator(sim_data, enable_logging=False, output_dir=temp_dir, progress_callback=progress_callback)
            
            msg_queue.put({"type": "progress", "value": 100, "message": "Uploading results..."})

            if "error" in file_paths:
                shutil.rmtree(temp_dir)
                msg_queue.put({"type": "error", "message": file_paths["error"]})
                return

            # Upload results with bounded retries. Transient truncation of the
            # storage response (e.g. flaky proxy) used to surface as a raw
            # Python JSONDecodeError in the UI; retry once, then fall back to a
            # clear message.
            sim_id = None
            last_error = None
            for attempt in range(2):
                with open(file_paths['simdata'], 'rb') as f_sim, open(file_paths['patterns'], 'rb') as f_pat:
                    try:
                        resp = requests.post(f'{DELINEO["DB_URL"]}simdata', data={
                            'czone_id': int(sim_data['czone_id']),
                            'length': int(sim_data['length'])
                        }, files={
                            'simdata': ('simdata.json.gz', f_sim, 'application/gzip'),
                            'patterns': ('patterns.json.gz', f_pat, 'application/gzip')
                        }, timeout=600)
                    except requests.RequestException as req_err:
                        last_error = f"Network error uploading results: {req_err}"
                        print(f"[attempt {attempt + 1}] {last_error}")
                        time.sleep(1)
                        continue

                if not resp.ok:
                    last_error = f"Storage returned {resp.status_code}"
                    print(f"[attempt {attempt + 1}] {last_error}")
                    time.sleep(1)
                    continue

                try:
                    sim_id = resp.json()['data']['id']
                except (json.JSONDecodeError, ValueError, KeyError, TypeError) as parse_err:
                    body_len = len(resp.content or b'')
                    last_error = (
                        f"Storage response was not valid JSON "
                        f"(status {resp.status_code}, {body_len} bytes): {parse_err}"
                    )
                    print(f"[attempt {attempt + 1}] {last_error}")
                    time.sleep(1)
                    continue

                break

            if sim_id is not None:
                print('Sent successfully!')
                msg_queue.put({"type": "result", "data": {'id': sim_id}})
            else:
                msg_queue.put({
                    "type": "error",
                    "message": f"Failed to save simulation results. {last_error or 'unknown error'}",
                })
            
            # Cleanup
            shutil.rmtree(temp_dir)

        except Exception as e:
            print("Simulation error:", repr(e))
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            msg_queue.put({"type": "error", "message": str(e)})
        finally:
            msg_queue.put(None) # Signal end

    # Start the thread
    thread = threading.Thread(target=run_sim_thread, args=(data,))
    thread.start()

    def generate():
        while True:
            msg = msg_queue.get()
            if msg is None:
                break
            yield f"data: {json.dumps(msg)}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


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
