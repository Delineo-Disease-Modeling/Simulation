from flask import Flask, request
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate

app = Flask(__name__)

# CORS
cors = CORS(app)

@app.route("/simulation/", methods=['POST', 'GET'])
@cross_origin()
def run_simulation():
    try:
        request.get_json(force=True)
    except BadRequest:
        return 'Bad Request'
    
    if not request.json:
        return 'Nothing Sent'
    
    try:
        return simulate.run_simulator({
            'mask': request.json['mask'],
            'vaccine': request.json['vaccine'],
            'capacity': request.json['capacity'],
            'lockdown': request.json['lockdown']
        })

    except KeyError:
        return 'Missing required intervention metric'

# This is for testing purposes
@app.route("/", methods=['GET'])
@cross_origin()
def run_main():
    return simulate.run_simulator({
            'mask': 0.4,
            'vaccine': 0.2,
            'capacity': 1.0,
            'lockdown': 0
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0')