from waitress import serve
from simulator.config import SERVER
import app

serve(app.app, host=SERVER["host"], port=SERVER["port"])
