from waitress import serve
from simulator.config import SERVER
# Entry module is `server` (NOT `app`): importing the Flask server as a top-level
# module named `app` shadows the dmp/app package and silently disables the
# in-process DMP (forcing the slow per-infection HTTP fallback).
import server

serve(server.app, host=SERVER["host"], port=SERVER["port"])
