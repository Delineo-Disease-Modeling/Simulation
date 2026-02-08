from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from werkzeug.exceptions import BadRequest
from simulator import simulate
from simulator.config import DMP_API, SERVER, SIMULATION
from datetime import datetime, timedelta
import requests
import traceback
from run_report import RunReport


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

@app.route("/simulation/legacy", methods=['POST', 'GET'])
@cross_origin()
def run_simulation_endpoint():
    """
    Legacy simulation endpoint - use /simulation/ with start_date/end_date for multi-month.
    This endpoint is kept for backward compatibility with older clients.
    """
    try:
        request.get_json(force=True)
    except BadRequest as e:
        print(f"Bad request error: {e}")
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        print("No JSON data in request")
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    print(f"Received request JSON: {request.json}")

    # Get simulation parameters
    length = request.json.get('length', SIMULATION["default_max_length"])
    location = request.json.get('location', SIMULATION["default_location"])
    initial_infected_count = request.json.get('initial_infected_count', None)
    initial_infected_ids = request.json.get('initial_infected_ids', None)
    czone_id = request.json.get('czone_id')
    
    # Build interventions dict from request
    interventions_array = request.json.get('interventions', None)
    if interventions_array and isinstance(interventions_array, list) and len(interventions_array) > 0:
        first_intervention = interventions_array[0]
        interventions = {}
        for key in SIMULATION["default_interventions"]:
            interventions[key] = first_intervention.get(key, request.json.get(key, SIMULATION["default_interventions"][key]))
    else:
        interventions = {}
        for key in SIMULATION["default_interventions"]:
            interventions[key] = request.json.get(key, SIMULATION["default_interventions"][key])
    
    # Create run report
    report = RunReport(
        run_type="simulation",
        name=f"Simulation: {location}" + (f" (CZ #{czone_id})" if czone_id else ""),
        parameters={
            'location': location,
            'length': length,
            'interventions': interventions,
            'initial_infected_count': initial_infected_count,
            'czone_id': czone_id,
        },
        czone_id=czone_id,
    )
    
    # Initialize DMP API before running simulation
    report.info("Initializing DMP API...")
    dmp_ok = initialize_dmp_api()
    if dmp_ok:
        report.info("DMP API initialized successfully")
    else:
        report.warn("DMP API not available, using fallback timelines")

    report.info(f"Starting simulation: location={location}, length={length} minutes")
    report.info(f"Interventions: mask={interventions.get('mask')}, vaccine={interventions.get('vaccine')}, capacity={interventions.get('capacity')}")

    try:
        sim_result = simulate.run_simulator(
            location,
            length,
            interventions,
            initial_infected_count=initial_infected_count,
            initial_infected_ids=initial_infected_ids,
            czone_id=czone_id,
            report=report,  # Pass report to simulator
        )
        
        # Extract summary stats from result
        summary = {
            'total_timesteps': len(sim_result.get('result', {})),
        }
        if 'result' in sim_result and sim_result['result']:
            last_key = max(sim_result['result'].keys(), key=int)
            last_state = sim_result['result'][last_key]
            summary['final_susceptible'] = last_state.get('susceptible', 0)
            summary['final_infected'] = last_state.get('infected', 0)
            summary['final_recovered'] = last_state.get('recovered', 0)
            summary['final_removed'] = last_state.get('removed', 0)
        
        # Save simdata to DB server and get an ID back
        sim_id = None
        if czone_id:
            try:
                report.info("Saving simulation results to database...")
                db_response = requests.post('http://localhost:1890/simdata', json={
                    'czone_id': czone_id,
                    'name': f"Simulation {czone_id}",
                    'simdata': sim_result
                })
                if db_response.ok:
                    db_data = db_response.json()
                    sim_id = db_data.get('data', {}).get('id')
                    report.info(f"Results saved with ID: {sim_id}")
                else:
                    report.warn(f"Failed to save to DB: HTTP {db_response.status_code}")
            except Exception as db_error:
                report.warn(f"Error saving to DB: {db_error}")
        
        report.complete(summary=summary)
        return jsonify({'data': {'id': sim_id}, 'simdata': sim_result})
        
    except Exception as e:
        report.capture_exception()
        print("Simulation error:", repr(e))
        traceback.print_exc()
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


@app.route("/simulation/multi-month", methods=['POST'])
@app.route("/simulation/", methods=['POST'])
@cross_origin()
def run_multi_month_simulation():
    """
    Run a simulation across a date range using monthly pattern files.
    
    This is the default simulation endpoint. Automatically uses the appropriate
    monthly pattern files for each month in the specified date range.
    
    Request JSON:
    {
        "start_date": "2019-01-15",     # Required: simulation start date (YYYY-MM-DD)
        "end_date": "2019-02-20",       # Required: simulation end date (YYYY-MM-DD)
        "state": "OK",                   # Required: state code for pattern files
        "location": "barnsdall",         # Optional: location name (default: barnsdall)
        "patterns_folder": "./data/OK",  # Optional: folder with YYYY-MM-{STATE}.csv files
        "initial_infected_count": 5,     # Optional: starting infections (default: 5)
        "interventions": {...},          # Optional: intervention parameters
        "czone_id": 1                    # Optional: convenience zone ID
    }
    
    Pattern files should be organized in location-based folders:
        data/OK/2019-01-OK.csv, data/OK/2019-02-OK.csv, etc.
    
    If patterns_folder is not provided, it defaults to:
        ../Algorithms/server/data/{state}/
    """
    import os
    import sys
    import json
    from simulator.state_manager import save_simulation_state, load_simulation_state, restore_people_state
    from monthly_patterns import (
        MonthlyPatternsManager, get_month_boundaries, parse_month_key,
        parse_date, date_to_month_key, get_simulation_minutes_for_month
    )
    
    # Add Algorithms/server to path for gen_patterns import
    ALGORITHMS_SERVER_PATH = os.path.join(os.path.dirname(__file__), '../Algorithms/server')
    if ALGORITHMS_SERVER_PATH not in sys.path:
        sys.path.insert(0, ALGORITHMS_SERVER_PATH)
    from patterns import gen_patterns
    
    # Base data folder (relative to Simulation/)
    ALGORITHMS_DATA_FOLDER = os.path.join(os.path.dirname(__file__), '../Algorithms/server/data')
    
    try:
        request.get_json(force=True)
    except BadRequest as e:
        return jsonify({"error": SERVER["error_messages"]["bad_request"]}), 400

    if not request.json:
        return jsonify({"error": SERVER["error_messages"]["no_data"]}), 400

    # Required parameters - accept either date format or month format
    start_date_str = request.json.get('start_date')
    end_date_str = request.json.get('end_date')
    start_month = request.json.get('start_month')  # Legacy support
    end_month = request.json.get('end_month')      # Legacy support
    
    # Parse dates
    if start_date_str and end_date_str:
        try:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
            start_month = date_to_month_key(start_date)
            end_month = date_to_month_key(end_date)
        except ValueError as e:
            return jsonify({"error": f"Invalid date format. Use YYYY-MM-DD: {e}"}), 400
    elif start_month and end_month:
        # Legacy month-based format - use full month boundaries
        start_year, start_m = parse_month_key(start_month)
        end_year, end_m = parse_month_key(end_month)
        start_date, _ = get_month_boundaries(start_year, start_m)
        _, end_date = get_month_boundaries(end_year, end_m)
    else:
        return jsonify({
            "error": "Missing required parameters: start_date and end_date (YYYY-MM-DD format)"
        }), 400
    
    # State is required when using date-based simulation
    state_filter = request.json.get('state')
    if not state_filter:
        return jsonify({"error": "Missing required parameter: state (e.g., 'OK')"}), 400
    
    # Optional parameters
    location = request.json.get('location', SIMULATION["default_location"])
    initial_infected_count = request.json.get('initial_infected_count', 5)
    czone_id = request.json.get('czone_id')
    
    # Determine patterns_folder with smart defaults
    # Priority: explicit patterns_folder > data/{state}/ > data/
    patterns_folder = request.json.get('patterns_folder')
    if not patterns_folder:
        if state_filter:
            # Try state-based subfolder first (e.g., data/OK/)
            state_folder = os.path.join(ALGORITHMS_DATA_FOLDER, state_filter)
            if os.path.isdir(state_folder):
                patterns_folder = state_folder
            else:
                # Fallback to main data folder
                patterns_folder = ALGORITHMS_DATA_FOLDER
        else:
            patterns_folder = ALGORITHMS_DATA_FOLDER
    
    # State save folder - organized by location/state
    default_state_folder = './simulation_states'
    if state_filter:
        default_state_folder = f'./simulation_states/{state_filter}'
    state_save_folder = request.json.get('state_save_folder', default_state_folder)
    
    # Build interventions
    interventions = {}
    for key in SIMULATION["default_interventions"]:
        interventions[key] = request.json.get(key, SIMULATION["default_interventions"][key])
    
    # Create report
    report = RunReport(
        run_type="simulation",
        name=f"Simulation: {start_date_str or start_month} to {end_date_str or end_month}" + (f" ({state_filter})" if state_filter else ""),
        parameters={
            'location': location,
            'patterns_folder': patterns_folder,
            'start_date': start_date_str or start_month,
            'end_date': end_date_str or end_month,
            'state': state_filter,
            'interventions': interventions,
            'initial_infected_count': initial_infected_count,
        },
        czone_id=czone_id,
    )
    
    try:
        # Initialize patterns manager
        print(f"[SIMULATION] ========================================")
        print(f"[SIMULATION] Starting simulation")
        print(f"[SIMULATION] Patterns folder: {patterns_folder}")
        print(f"[SIMULATION] State: {state_filter}")
        print(f"[SIMULATION] Date range: {start_date} to {end_date}")
        print(f"[SIMULATION] Months: {start_month} to {end_month}")
        print(f"[SIMULATION] State save folder: {state_save_folder}")
        print(f"[SIMULATION] CZone ID: {czone_id}")
        print(f"[SIMULATION] ========================================")
        
        manager = MonthlyPatternsManager(patterns_folder, state_filter)
        
        # Validate coverage
        is_valid, missing = manager.validate_range(start_month, end_month)
        if not is_valid:
            report.fail(f"Missing pattern files for months: {missing}")
            return jsonify({"error": f"Missing pattern files: {missing}"}), 400
        
        report.info(f"Found {len(manager.files)} monthly files")
        
        # Initialize DMP API
        report.info("Initializing DMP API...")
        dmp_ok = initialize_dmp_api()
        if dmp_ok:
            report.info("DMP API initialized successfully")
        else:
            report.warn("DMP API not available, using fallback timelines")
        
        # Load papdata - prefer DB (czone_id) over local files
        # DB papdata has placekeys needed for pattern matching
        papdata = None
        
        # Try DB first if we have a czone_id
        if czone_id:
            try:
                db_resp = requests.get(f'http://localhost:1890/patterns/{czone_id}')
                if db_resp.ok:
                    # The endpoint streams papdata on first line, then patterns
                    # We only need the first line (papdata)
                    text = db_resp.text
                    first_line = text.split('\n')[0] if '\n' in text else text
                    if first_line:
                        papdata = json.loads(first_line)
                        # Response format: either {papdata: {...}} or papdata directly
                        if 'papdata' in papdata:
                            papdata = papdata['papdata']
                        if papdata and 'people' in papdata:
                            report.info(f"Loaded papdata from DB (czone {czone_id}): {len(papdata.get('people', {}))} people, {len(papdata.get('places', {}))} places")
                        else:
                            papdata = None
            except Exception as e:
                report.warn(f"Could not load papdata from DB: {e}")
        
        # Fallback to local files if DB didn't work
        if not papdata:
            location_folder = os.path.join(os.path.dirname(__file__), f'simulator/{location}')
            papdata_path = os.path.join(location_folder, 'papdata.json')
            
            if os.path.exists(papdata_path):
                with open(papdata_path, 'r') as f:
                    papdata = json.load(f)
                report.info(f"Loaded papdata from {location}: {len(papdata.get('people', {}))} people")
            else:
                # Fallback to barnsdall
                fallback_path = os.path.join(os.path.dirname(__file__), 'simulator/barnsdall/papdata.json')
                if os.path.exists(fallback_path):
                    with open(fallback_path, 'r') as f:
                        papdata = json.load(f)
                    report.warn(f"Using barnsdall papdata as fallback ({len(papdata.get('people', {}))} people)")
                else:
                    report.fail("Could not load papdata - no local file found")
                    return jsonify({"error": "Could not load papdata"}), 400
        
        # Results for each month
        monthly_results = {}
        previous_state_file = None
        previous_month_start_dt = None
        
        # Run simulation for each month
        for month, patterns_csv_file in manager.iter_months(start_month, end_month):
            # Calculate simulation minutes and actual segment boundaries for this month
            length_minutes = get_simulation_minutes_for_month(month, start_date, end_date)
            duration_hours = length_minutes // 60
            
            print(f"[SIMULATION] ----------------------------------------")
            print(f"[SIMULATION] MONTH: {month}")
            print(f"[SIMULATION] Simulating {length_minutes} minutes ({duration_hours} hours, {length_minutes // 1440} days)")
            print(f"[SIMULATION] Patterns CSV file: {patterns_csv_file}")
            print(f"[SIMULATION] File exists: {os.path.exists(patterns_csv_file)}")
            if os.path.exists(patterns_csv_file):
                file_size = os.path.getsize(patterns_csv_file) / (1024*1024)
                print(f"[SIMULATION] File size: {file_size:.2f} MB")
            print(f"[SIMULATION] Previous state file: {previous_state_file}")
            print(f"[SIMULATION] ----------------------------------------")
            report.info(f"=== Starting simulation for month: {month} ===")
            report.info(f"Using patterns CSV: {patterns_csv_file}")
            report.info(f"Simulating {length_minutes} minutes ({length_minutes // 1440} days)")
            
            # Generate patterns from SafeGraph CSV -> patterns.json format
            year, m = parse_month_key(month)
            month_start_dt, month_end_dt = get_month_boundaries(year, m)
            segment_start_dt = max(month_start_dt, datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0))
            segment_end_dt = min(month_end_dt, datetime(end_date.year, end_date.month, end_date.day, 23, 59, 59))
            report.info(f"Generating patterns from CSV (this may take a moment)...")
            
            patterns_data = gen_patterns(
                papdata,
                start_time=segment_start_dt,
                duration=duration_hours,
                patterns_file=patterns_csv_file
            )
            report.info(f"Generated {len(patterns_data)} timestep patterns")
            
            # Determine initial infections
            # First month: use initial_infected_count
            # Subsequent months: restore from previous state (infections persist)
            current_initial_infected = None
            restore_state_from = None
            restore_time_offset = None
            
            if previous_state_file and os.path.exists(previous_state_file):
                report.info(f"[MONTH-CHAIN] Restoring state from: {previous_state_file}")
                restore_state_from = previous_state_file
                if previous_month_start_dt:
                    delta_minutes = int((segment_start_dt - previous_month_start_dt).total_seconds() / 60)
                    restore_time_offset = max(0, delta_minutes)
                    report.info(f"[MONTH-CHAIN] Time offset between months: {restore_time_offset} minutes")
                # Log the state file contents for debugging
                try:
                    with open(previous_state_file, 'r') as f:
                        state_data = json.load(f)
                        infected_count = 0
                        for p in state_data.get('people', {}).values():
                            for state_val in p.get('states', {}).values():
                                if state_val & 1:
                                    infected_count += 1
                                    break
                        report.info(f"[MONTH-CHAIN] Previous state has {infected_count} infected people")
                except Exception as e:
                    report.warn(f"[MONTH-CHAIN] Could not read previous state: {e}")
            else:
                current_initial_infected = initial_infected_count
                report.info(f"[MONTH-CHAIN] Initial month - starting with {initial_infected_count} infected")
            
            # Run the simulation for this month with pre-generated patterns
            sim_result = simulate.run_simulator(
                location,
                length_minutes,
                interventions,
                initial_infected_count=current_initial_infected,
                czone_id=czone_id,
                report=report,
                restore_state_file=restore_state_from,
                restore_time_offset=restore_time_offset,
                patterns_data=patterns_data,
                papdata=papdata,
            )
            
            # Calculate days in this simulation segment
            days_simulated = length_minutes // 1440
            
            monthly_results[month] = {
                'patterns_csv_file': patterns_csv_file,
                'days': days_simulated,
                'minutes': length_minutes,
                'result': sim_result,
            }
            
            # Save state for next month
            state_file = os.path.join(state_save_folder, f'state_{month}.json')
            os.makedirs(state_save_folder, exist_ok=True)
            
            # Extract final state from simulation result and save it
            if 'people_state' in sim_result:
                save_simulation_state(
                    sim_result['people_state'],
                    state_file,
                    metadata={
                        'month': month,
                        'patterns_csv_file': patterns_csv_file,
                        'interventions': interventions,
                        'start_time': segment_start_dt.isoformat(),
                        'end_time': segment_end_dt.isoformat(),
                        'length_minutes': length_minutes,
                    }
                )
                report.info(f"State saved to: {state_file}")
                previous_state_file = state_file
                previous_month_start_dt = segment_start_dt
            else:
                report.warn("No people_state in result, cannot save state for next month")
            
            # Extract summary for this month
            if 'result' in sim_result and sim_result['result']:
                last_key = max(sim_result['result'].keys(), key=int)
                last_state = sim_result['result'][last_key]
                report.info(f"Month {month} final: susceptible={last_state.get('susceptible', 0)}, "
                           f"infected={last_state.get('infected', 0)}, "
                           f"recovered={last_state.get('recovered', 0)}")
        
        # Build combined results
        combined_result = {
            'months': list(monthly_results.keys()),
            'monthly_results': monthly_results,
            'summary': {
                'start_month': start_month,
                'end_month': end_month,
                'total_months': len(monthly_results),
            }
        }
        
        report.complete(summary=combined_result['summary'])
        return jsonify({'data': combined_result})
        
    except Exception as e:
        report.capture_exception()
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400


if __name__ == '__main__':
    # Initialize DMP API when the server starts
    initialize_dmp_api()
    app.run(host=SERVER["host"], port=SERVER["port"])
