from .pap import Person, Household, Facility, InfectionState, VaccinationState
from .infectionmgr import *
from .config import SIMULATION, INFECTION_MODEL
from io import StringIO
import pandas as pd
import json
import os
from .data_interface import StreamDataLoader
import requests
import random 
import logging 
from datetime import datetime, timedelta 
from collections import defaultdict
import csv 
from . import agentstats as ast


curdir = os.path.dirname(os.path.abspath(__file__))

class Maskingeffects: 
    
    MASK_EFFECTIVENESS = {
        'source_control' : 0.7, # what should these values be?
        'wearer_protection': 0.5, 
        'both_masked' : 0.85, 
    }

    @staticmethod
    def calculate_mask_transmission_modifier(infector, susceptible): 
        base_modifier = 1.0 
        infector_masked = getattr(infector, 'masked', False)
        susceptible_masked = getattr(susceptible, 'masked', False)

        if infector_masked and susceptible_masked: 
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['both_masked'])
        elif infector_masked: 
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['source_control'])
        elif susceptible_masked: 
            base_modifier *= (1 - Maskingeffects.MASK_EFFECTIVENESS['wearer_protection'])
        return base_modifier
        
    @staticmethod
    def update_mask_effectiveness(source_control=None, wearer_protection=None, both_masked=None):
        """Allow dynamic updating of mask effectiveness values"""
        if source_control is not None:
            Maskingeffects.MASK_EFFECTIVENESS['source_control'] = source_control
        if wearer_protection is not None:
            Maskingeffects.MASK_EFFECTIVENESS['wearer_protection'] = wearer_protection
        if both_masked is not None:
            Maskingeffects.MASK_EFFECTIVENESS['both_masked'] = both_masked


class SimulationLogger: 
    """Logging system for simulation - streams directly to disk to minimize RAM usage"""

    def __init__ (self, log_dir = "simulation_logs", enable_file_logging = True): 
        self.log_dir = log_dir 
        self.enable_file_logging = enable_file_logging
        
        # Counters for summary (instead of storing all logs in memory)
        self.person_log_count = 0
        self.movement_log_count = 0
        self.infection_log_count = 0
        self.intervention_log_count = 0
        self.location_log_count = 0
        self.contact_log_count = 0
        
        # Only keep infection chains in memory (small relative to other logs)
        self.infection_chains = {}
        
        # Track unique people seen (for summary)
        self._unique_people = set()
        
        # CSV writers for streaming to disk
        self._csv_files = {}
        self._csv_writers = {}
        self._headers_written = {}

        if self.enable_file_logging: 
            os.makedirs(log_dir, exist_ok=True)
            self._init_csv_writers()

        self.setup_logging()
    
    def _init_csv_writers(self):
        """Initialize CSV file handles for streaming writes"""
        log_types = ['person_logs', 'movement_logs', 'infection_logs', 
                     'intervention_logs', 'location_logs', 'contact_logs']
        for log_type in log_types:
            filepath = f'{self.log_dir}/{log_type}.csv'
            self._csv_files[log_type] = open(filepath, 'w', newline='', buffering=8192)
            self._csv_writers[log_type] = None  # Will create on first write with headers
            self._headers_written[log_type] = False
    
    def _write_log(self, log_type, log_dict):
        """Write a single log entry to the appropriate CSV file"""
        if not self.enable_file_logging:
            return
        
        if self._csv_writers.get(log_type) is None:
            # First write - create writer and write headers
            self._csv_writers[log_type] = csv.DictWriter(
                self._csv_files[log_type], 
                fieldnames=list(log_dict.keys()),
                extrasaction='ignore'
            )
            if not self._headers_written[log_type]:
                self._csv_writers[log_type].writeheader()
                self._headers_written[log_type] = True
        
        self._csv_writers[log_type].writerow(log_dict)
    
    def setup_logging(self):
        logging.basicConfig(
            level = logging.INFO, 
            format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
            handlers = [
                logging.StreamHandler(),  
                logging.FileHandler(f'{self.log_dir}/simulation.log' if self.enable_file_logging else logging.NullHandler())
            ]
        )
        self.logger = logging.getLogger('DiseaseSimulator')

    def log_person_demographics(self, person, timestep):
        """Log person demographics and current state - streams to disk"""
        vax_status = person.vaccination_state if person.vaccination_state else "Unvaccinated"        
        vax_doses = 0
        if hasattr(person, 'vaccination_state') and person.vaccination_state: 
            vax_doses = person.vaccination_state.value if hasattr(person.vaccination_state, 'value') else 0
            vax_status = f"Vaccinated ({vax_doses} doses)"

        infection_status = {}
        infectious_variants = []
        symptomatic_variants = []

        for variant in person.states.keys(): 
            state = person.states[variant]
            infection_status[variant] = {
                'infected': bool(state & InfectionState.INFECTED),
                'infectious': bool(state & InfectionState.INFECTIOUS),
                'symptomatic': bool(state & InfectionState.SYMPTOMATIC), 
                'recovered': bool(state & InfectionState.RECOVERED), 
                'deceased': bool(state & InfectionState.REMOVED)
            }

            if state & InfectionState.INFECTIOUS:
                infectious_variants.append(variant)
            if state & InfectionState.SYMPTOMATIC:
                symptomatic_variants.append(variant)
            
        location_id = person.location.id if person.location else None 
        location_type = "household" if isinstance(person.location, Household) else "facility" if isinstance(person.location, Facility) else "unknown"
        location_capacity = getattr(person.location, 'capacity', -1) if person.location else -1
        location_population = len(person.location.population) if person.location else 0 

        person_log = {
            'timestep': timestep, 
            'person_id': person.id,
            'age': person.age,
            'sex': person.sex, 
            'household_id': person.household.id if person.household else None,
            'current_location_id': location_id,
            'current_location_type': location_type,
            'location_capacity': location_capacity,
            'location_occupancy': location_population, 
            'location_utilization': (location_population / location_capacity) if location_capacity > 0 else 0,
            'is_masked': getattr(person, 'masked', False), 
            'vaccination_status': vax_status,
            'vaccination_doses': vax_doses,
            'infectious_variants': ','.join(infectious_variants),
            'symptomatic_variants': ','.join(symptomatic_variants),
            'total_variants_infected': len([v for v in infection_status.values() if v['infected']]),
            'infection_status': str(infection_status)
        }

        self._write_log('person_logs', person_log)
        self.person_log_count += 1
        self._unique_people.add(person.id)

    def log_movement(self, person, from_location, to_location, timestep, reason = "normal") :
        movement_log = {
            'timestep': timestep,
            'person_id': person.id,
            'from_location_id': from_location.id if from_location else None,
            'from_location_type': "household" if isinstance(from_location, Household) else "facility" if isinstance(from_location, Facility) else None,
            'to_location_id': to_location.id if to_location else None,
            'to_location_type': "household" if isinstance(to_location, Household) else "facility" if isinstance(to_location, Facility) else None,
            'movement_reason': reason,
            'person_age': person.age, 
            'person_sex': person.sex, 
            'is_infectious': any(person.states[v] & InfectionState.INFECTIOUS for v in person.states.keys()),
            'is_symptomatic': any(person.states[v] & InfectionState.SYMPTOMATIC for v in person.states.keys()),
            'is_masked': getattr(person, 'masked', False),
            'from_occupancy': len(from_location.population) if from_location else 0,
            'to_occupancy': len(to_location.population) if to_location else 0, 
            'to_capacity': getattr(to_location, 'capacity', -1) if to_location else -1
        }

        self._write_log('movement_logs', movement_log)
        self.movement_log_count += 1

    def log_infection_event(self, infected_person, infector_person, location, variant, timestep): 
        """Log an infection event - streams to disk"""
        infection_log = {
            'timestep': timestep,
            'infected_person_id': infected_person.id,
            'infected_age': infected_person.age,
            'infected_sex': infected_person.sex, 
            'infected_masked': getattr(infected_person, 'masked', False),
            'infected_vaccination_doses': getattr(infected_person.vaccination_state, 'value', 0) if hasattr(infected_person, 'vaccination_state') and infected_person.vaccination_state else 0, 
            'infector_person_id': infector_person.id if infector_person else None,
            'infector_age': infector_person.age if infector_person else None,
            'infector_sex': infector_person.sex if infector_person else None, 
            'infector_masked': getattr(infector_person, 'masked', False) if infector_person else False,
            'infector_vaccination_doses': getattr(infector_person.vaccination_state, 'value', 0) if hasattr(infector_person, 'vaccination_state') and infector_person.vaccination_state else 0 if infector_person else 0,
            'infection_location_id': location.id if location else None,
            'infection_location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'location_occupancy': len(location.population) if location else 0,
            'location_capacity': getattr(location, 'capacity', -1) if location else -1,
            'variant': variant,
            'transmission_pair_age_diff': abs(infected_person.age - infector_person.age) if infector_person else None,
        }
        self._write_log('infection_logs', infection_log)
        self.infection_log_count += 1

        # tracking infection chains (kept in memory - small data)
        if infector_person: 
            self.infection_chains[infected_person.id] = {
                'infector_id': infector_person.id,
                'location_id': location.id if location else None,
                'variant': variant,
                'timestep': timestep
            }
    
    def log_intervention_effect(self, person, intervention_type, effect, timestep, location=None): 
        """Log when interventions affect person behavior - streams to disk"""
        intervention_log = {
            'timestep': timestep,
            'person_id': person.id,
            'intervention_type': intervention_type, # for example, lockdown, capacity limit, self isolation, mask, vaccine 
            'effect': effect,
            'person_age': person.age, 
            'person_sex': person.sex, 
            'person_infectious': any(person.states[v] & InfectionState.INFECTIOUS for v in person.states.keys()),
            'person_symptomatic': any(person.states[v] & InfectionState.SYMPTOMATIC for v in person.states.keys()),
            'location_id': location.id if location else None,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'location_occupancy': len(location.population) if location else 0,
            'location_capacity': getattr(location, 'capacity', -1) if location else -1
        }

        self._write_log('intervention_logs', intervention_log)
        self.intervention_log_count += 1

    def log_location_state(self, location, timestep):
        """Log location state - streams to disk"""
        population = location.population if hasattr(location, 'population') else []
        infectious_count = sum(1 for p in population if any(p.states[v] & InfectionState.INFECTIOUS for v in p.states.keys()))
        symptomatic_count = sum(1 for p in population if any(p.states[v] & InfectionState.SYMPTOMATIC for v in p.states.keys()))
        masked_count = sum(1 for p in population if getattr(p, 'masked', False))
        vaccinated_count = sum(1 for p in population if hasattr(p, 'vaccination_state') and p.vaccination_state and p.vaccination_state.value > 0)

        ages = [p.age for p in population]
        avg_age = sum(ages) / len(ages) if ages else 0

        capacity = getattr(location, 'capacity', -1)
        location_log = {
            'timestep': timestep,
            'location_id': location.id,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'capacity': capacity,
            'occupancy': len(population),
            'utilization_rate': len(population) / capacity if capacity > 0 else 0,
            'infectious_count': infectious_count,
            'symptomatic_count': symptomatic_count,
            'masked_count': masked_count,
            'vaccinated_count': vaccinated_count,
            'avg_age': avg_age,
            'male_count': sum(1 for p in population if p.sex == '0'),
            'female_count': sum(1 for p in population if p.sex == '1'),
            'label': 'None' if isinstance(location, Household) else location.label,
            'latitude': 'None' if isinstance(location, Household) else location.latitude,
            'longitude': 'None' if isinstance(location, Household) else location.longitude,
            'street_address': 'None' if isinstance(location, Household) else location.street_address
        }

        self._write_log('location_logs', location_log)
        self.location_log_count += 1

    def log_contact_event(self, person1, person2, location, timestep, contact_duration = 1): 
        """Log contact between two people - streams to disk"""
        contact_log = {
            'timestep': timestep,
            'person1_id': person1.id,
            'person2_id': person2.id,
            'location_id': location.id if location else None,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'contact_duration': contact_duration,  # in minutes
            'person1_infectious': any(person1.states[v] & InfectionState.INFECTIOUS for v in person1.states.keys()),
            'person2_infectious': any(person2.states[v] & InfectionState.INFECTIOUS for v in person2.states.keys()),
            'person1_masked': getattr(person1, 'masked', False),
            'person2_masked': getattr(person2, 'masked', False),
            'both_masked': getattr(person1, 'masked', False) and getattr(person2, 'masked', False),
            'age_diff': abs(person1.age - person2.age) if person1 and person2 else None,
            'same_household': person1.household.id == person2.household.id if person1 and person2 else False,
        }
        
        self._write_log('contact_logs', contact_log)
        self.contact_log_count += 1

    def calculate_transmission_risk(self, infected_person, infector_person, location): 
        if not infector_person or not location: 
            return 0
        
        risk = 1.0 

        if getattr(infected_person, 'masked', False): 
            risk *= 0.5
        if getattr(infector_person, 'masked', False):
            risk *= 0.5

        if hasattr(location, 'capacity') and location.capacity > 0:
            utilization = len(location.population) / location.capacity
            risk *= (1 + utilization)
        
        return risk

    def calculate_location_risk(self, location): 
        if not hasattr(location, 'population') or not location.population:
            return 0

        population = location.population
        pop_count = len(population)
        if pop_count == 0:
            return 0
            
        infectious_count = sum(1 for p in population if any(p.states[v] & InfectionState.INFECTIOUS for v in p.states.keys()))

        if infectious_count == 0:
            return 0
        
        risk = infectious_count / pop_count  # Basic risk based on infectious individuals
        if hasattr(location, 'capacity') and location.capacity > 0:
            utilization = pop_count / location.capacity
            risk *= (1 + utilization)

        masked_rate = sum(1 for p in population if getattr(p, 'masked', False)) / pop_count

        risk *= (1-masked_rate * 0.3)  # Reduce risk based on masking rate

        return risk
    
    def calculate_contact_risk(self, person1, person2, location): 
        p1_infection = any(person1.states[v] & InfectionState.INFECTIOUS for v in person1.states.keys())
        p2_infection = any(person2.states[v] & InfectionState.INFECTIOUS for v in person2.states.keys())

        if not p1_infection and not p2_infection:
            return 0
        
        risk = 1.0 

        if getattr(person1, 'masked', False):
            risk *= 0.7
        if getattr(person2, 'masked', False):
            risk *= 0.7

        if hasattr(location, 'capacity') and location.capacity > 0:
            utilization = len(location.population) / location.capacity
            risk *= (1 + utilization * 0.5)

        return risk
    
    def export_logs_to_csv(self): 
        """Close CSV file handles and write infection chains"""
        if not self.enable_file_logging: 
            return 
        
        # Close all CSV file handles
        for log_type, file_handle in self._csv_files.items():
            if file_handle and not file_handle.closed:
                file_handle.close()

        # Write infection chains (only data kept in memory)
        if self.infection_chains: 
            chains_df = pd.DataFrame.from_dict(self.infection_chains, orient='index')
            chains_df.reset_index(inplace=True)
            chains_df.rename(columns={'index': 'infected_person_id'}, inplace=True)
            chains_df.to_csv(f'{self.log_dir}/infection_chains.csv', index=False)

    def graphic_analysis(self):
        if not self.enable_file_logging:
            return 0

        #construct graph
        start = ast.Node(-1,-1,None)
        ast.build_agent_graph_nodupes(start, f'{self.log_dir}/infection_logs.csv', f'{self.log_dir}/location_logs.csv')

        #run analysis
        report = []
        ast.calculate_all_harmonic(start)
        ast.check_sse(start, report, f'{self.log_dir}/person_logs.csv')
        ast.location_impact(start, report, f'{self.log_dir}/location_logs.csv')
        ast.time_gates(start, report, f'{self.log_dir}/location_logs.csv')
        ast.time_impact(start, report, f'{self.log_dir}/location_logs.csv')
            
        with open(f'{self.log_dir}/graph_report.txt', 'w') as f:
            f.write("\n".join(report))
        
        return 1

    def generate_summary_report(self):
        if not self.enable_file_logging:
            return 

        report = []
        report.append("=== Simulation Summary Report ===\n")

        report.append(f"Total unique people tracked: {len(self._unique_people)}") 
        report.append(f"Total infections logged: {self.infection_log_count}")
        report.append(f"Total movements logged: {self.movement_log_count}")
        report.append(f"Total person state logs: {self.person_log_count}")
        report.append(f"Total location state logs: {self.location_log_count}")
        report.append(f"Total contact logs: {self.contact_log_count}")
        report.append(f"Total intervention logs: {self.intervention_log_count}")
        report.append(f"Infection chains tracked: {len(self.infection_chains)}")

        with open(f'{self.log_dir}/summary_report.txt', 'w') as f:
            f.write("\n".join(report))
    
    def close(self):
        """Ensure all file handles are closed"""
        self.export_logs_to_csv()
            
# Putting it all together, simulates each timestep
# We can choose to only simulate areas with infected people
class DiseaseSimulator:
    def __init__(self, timestep=None, intervention_weights={}, enable_logging = True, log_dir = "simulation_logs"):
        self.timestep = timestep or SIMULATION["default_timestep"]  # in minutes
        self.iv_weights = intervention_weights
        self.people = {}
        self.households = {}          # list of all houses
        self.facilities = {}
        self.logger = SimulationLogger(log_dir, enable_logging) if enable_logging else None
        self.enable_logging = enable_logging 
    
    def add_person(self, person):
        self.people[person.id] = person  
        
    def get_person(self, id):
        return self.people.get(id) 

    def add_household(self, household):
        self.households[household.id] = household

    
    def get_household(self, id):
        return self.households.get(id)


    def add_facility(self, facility):
        self.facilities[facility.id] = facility

    
    def get_facility(self, id):
        return self.facilities.get(id)

def move_people(simulator, items, is_household, current_timestep):
    for id, people in items:
        place = simulator.get_household(str(id)) if is_household else simulator.get_facility(str(id))
        if place is None:
            raise Exception(f"Place {id} was not found in the simulator data ({is_household})")

        for person_id in people:
            person = simulator.get_person(person_id)
            if person is None:
                #raise Exception(f"Person {person_id} was not found in the simulator data")
                continue

            original_location = person.location 

            # If we hit capacity limit, then we are going to send the person home instead
            # Otherwise, if we are enforcing a lockdown, they may randomly decide to head home
            if not is_household:
                # Treat capacity 0 or -1 as unlimited
                at_capacity = place.total_count >= place.capacity * simulator.iv_weights['capacity'] if place.capacity > 0 else False
                hit_lockdown = place != person.location and random.random() < simulator.iv_weights['lockdown']
                self_iso = person.get_state(InfectionState.SYMPTOMATIC) and random.random() < simulator.iv_weights['selfiso']
                
                if simulator.enable_logging and simulator.logger: 
                    if at_capacity: 
                        simulator.logger.log_intervention_effect(person, 'capacity_limit', 'redirected_home',current_timestep, place)
                    if hit_lockdown: 
                        simulator.logger.log_intervention_effect(person, 'lockdown', 'stayed_home', current_timestep, place)
                    if self_iso: 
                        simulator.logger.log_intervention_effect(person, 'self_isolation', 'stayed_home', current_timestep, place)
                if at_capacity or hit_lockdown or self_iso:
                    person.location.remove_member(person_id)
                    person.household.add_member(person)

                    if simulator.enable_logging and simulator.logger: 
                        reason = 'capacity_limit' if at_capacity else ('lockdown' if hit_lockdown else 'self_isolation')
                        simulator.logger.log_movement(person, original_location, person.household, current_timestep, reason)

                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            

            if simulator.enable_logging and simulator.logger: 
                simulator.logger.log_movement(person, original_location, place, current_timestep, 'normal')

            person.location = place

def run_simulator(
    location=None,
    max_length=None,
    interventions=None,
    save_file=False,
    enable_logging=True,
    log_dir="simulation_logs",
    initial_infected_count=None,
    initial_infected_ids=None,
    czone_id=None,
    report=None,  # Optional RunReport instance for structured logging
    patterns_file=None,  # Optional specific patterns CSV file for multi-month simulation
    restore_state_file=None,  # Optional state file to restore from (for multi-month continuity)
    restore_time_offset=None,  # Optional time offset (minutes) between previous and current simulation start
    patterns_data=None,  # Pre-generated patterns dict (from gen_patterns), takes priority over patterns_file
    papdata=None,  # Pre-loaded papdata dict, avoids reloading for each month
):
    print(f"[RUN_SIMULATOR] RECEIVED max_length (before default): {max_length}")
    location = location or SIMULATION["default_location"]
    max_length = max_length or SIMULATION["default_max_length"]
    print(f"[RUN_SIMULATOR] EFFECTIVE max_length (after default): {max_length}")
    
    # Log patterns_file if provided (multi-month simulation)
    if patterns_file:
        print(f"[RUN_SIMULATOR] ========================================")
        print(f"[RUN_SIMULATOR] patterns_file: {patterns_file}")
        print(f"[RUN_SIMULATOR] restore_state_file: {restore_state_file}")
        print(f"[RUN_SIMULATOR] ========================================")
    
    # Helper to log to both report and console
    def log_info(msg):
        print(msg)
        if report:
            report.info(msg)
    
    def log_warn(msg):
        print(f"Warning: {msg}")
        if report:
            report.warn(msg)

    def count_infected_people(people_dict):
        count = 0
        for person in people_dict.values():
            for state in getattr(person, 'states', {}).values():
                try:
                    if state.value & 1:
                        count += 1
                        break
                except AttributeError:
                    if int(state) & 1:
                        count += 1
                        break
        return count
    
    log_info(f"=== SIMULATION DEBUG START ===")
    log_info(f"max_length: {max_length}")
    log_info(f"save_file: {save_file}")
    
    # Merge provided interventions with defaults
    default_interventions = SIMULATION["default_interventions"].copy()
    if interventions:
        default_interventions.update(interventions)
    interventions = default_interventions
    
    # Set random seed if user specifies
    if not interventions['randseed']:
        random.seed(0)
    
    # Initialize data containers
    people_data = {}
    homes_data = {}
    places_data = {}
    patterns = {}
    data_loaded = False
    
    # Strategy 0: Use pre-loaded papdata and patterns_data if provided (multi-month optimization)
    # if papdata and patterns_data:
    #     log_info(f"Strategy 0: Using pre-loaded papdata and patterns_data")
    #     people_data = papdata.get('people', {})
    #     homes_data = papdata.get('homes', {})
    #     places_data = papdata.get('places', {})
    #     patterns = patterns_data
    #     log_info(f"Pre-loaded: {len(people_data)} people, {len(homes_data)} homes, {len(places_data)} places, {len(patterns)} patterns")
    #     data_loaded = True
    
    # Helper function to fetch from DB API
    def fetch_from_db_api(cz_id):
        """Fetch patterns and papdata from the DB API for a convenience zone."""
        import requests
        try:
            # Fetch papdata (people, homes, places) from dedicated endpoint
            papdata_response = requests.get(f'http://localhost:1890/papdata/{cz_id}', timeout=30)
            if not papdata_response.ok:
                print(f"Warning: Could not fetch papdata from DB API for CZ {cz_id}: {papdata_response.status_code}")
                return None, None, None, None
            
            papdata = papdata_response.json().get('data', {})
            ppl = papdata.get('people', {})
            hms = papdata.get('homes', {})
            plcs = papdata.get('places', {})
            
            # Fetch patterns from streaming endpoint
            # The endpoint streams: papdata JSON (first line) then {"patterns": {timestep: data}} per line
            patterns_response = requests.get(f'http://localhost:1890/patterns/{cz_id}', timeout=60, stream=True)
            if not patterns_response.ok:
                print(f"Warning: Could not fetch patterns from DB API for CZ {cz_id}: {patterns_response.status_code}")
                return None, None, None, None
            
            ptns = {}
            first_line = True
            for line in patterns_response.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if first_line:
                        # First line is papdata, skip it (we already have it)
                        first_line = False
                        continue
                    try:
                        chunk = json.loads(line_str)
                        if 'patterns' in chunk:
                            ptns.update(chunk['patterns'])
                    except json.JSONDecodeError:
                        continue
            
            print(f"Loaded from DB API (CZ {cz_id}): {len(ppl)} people, {len(hms)} homes, {len(plcs)} places, {len(ptns)} patterns")
            return ppl, hms, plcs, ptns
        except Exception as e:
            print(f"Warning: Error fetching from DB API for CZ {cz_id}: {e}")
        return None, None, None, None
    
    # Helper function to lookup CZ by name/description
    def lookup_czone_id(location_name):
        """Look up convenience zone ID by name or description."""
        import requests
        try:
            response = requests.get('http://localhost:1890/convenience-zones', timeout=10)
            if response.ok:
                czones = response.json().get('data', [])
                for cz in czones:
                    if cz.get('description', '').lower() == location_name.lower() or \
                       cz.get('name', '').lower() == location_name.lower():
                        print(f"Found CZ for '{location_name}': ID {cz['id']}")
                        return cz['id']
        except Exception as e:
            print(f"Warning: Could not lookup CZ by name: {e}")
        return None
    
    # Strategy 1: If czone_id is provided, fetch from DB API
    # if not data_loaded and czone_id:
    if czone_id:
        log_info(f"Fetching data from DB API for czone_id={czone_id}")
        people_data, homes_data, places_data, patterns = fetch_from_db_api(czone_id)
        if people_data:
            data_loaded = True
    
    # Strategy 2: Try to load from local files
    if not data_loaded:
        location_folder = f'simulator/{location}'
        try:
            with open(f'{location_folder}/patterns.json', 'r') as file:
                patterns = json.load(file)
                log_info(f"Loaded {len(patterns)} patterns from {location}/patterns.json")
            with open(f'{location_folder}/papdata.json', 'r') as file:
                local_papdata = json.load(file)
                people_data = local_papdata.get('people', {})
                homes_data = local_papdata.get('homes', {})
                places_data = local_papdata.get('places', {})
                log_info(f"Loaded papdata from {location}: {len(people_data)} people, {len(homes_data)} homes, {len(places_data)} places")
            data_loaded = True
        except FileNotFoundError as e:
            log_warn(f"Could not load local data for location '{location}': {e}")
    
    # Strategy 3: Try to lookup CZ by location name and fetch from DB
    if not data_loaded:
        log_info(f"Strategy 3: Looking up CZ by location name '{location}'")
        cz_id = lookup_czone_id(location)
        if cz_id:
            log_info(f"Found CZ ID {cz_id} for location '{location}', fetching data...")
            people_data, homes_data, places_data, patterns = fetch_from_db_api(cz_id)
            if people_data:
                data_loaded = True
        else:
            log_warn(f"No CZ found for location '{location}'")
    
    # Strategy 4: Fall back to barnsdall as last resort
    if not data_loaded:
        log_warn("Falling back to barnsdall data")
        with open('simulator/barnsdall/patterns.json', 'r') as file:
            patterns = json.load(file)
            log_info(f"Loaded {len(patterns)} patterns from barnsdall/patterns.json")
        with open('simulator/barnsdall/papdata.json', 'r') as file:
            papdata = json.load(file)
            people_data = papdata.get('people', {})
            homes_data = papdata.get('homes', {})
            places_data = papdata.get('places', {})
            log_info(f"Loaded papdata from barnsdall: {len(people_data)} people, {len(homes_data)} homes, {len(places_data)} places")
    
    log_info(f"=== DATA LOADED ===")
    log_info(f"Total people: {len(people_data)}")
    log_info(f"Total homes: {len(homes_data)}")
    log_info(f"Total places: {len(places_data)}")
    log_info(f"Total patterns: {len(patterns)}")
    
    # Debug patterns structure
    if patterns:
        pattern_keys = sorted(patterns.keys(), key=lambda x: int(x) if x.isdigit() else float('inf'))
        print(f"Pattern timestamps: {pattern_keys[:10]}...")  # First 10
        
        # Check first pattern structure
        first_key = pattern_keys[0]
        first_pattern = patterns[first_key]
        print(f"First pattern ({first_key}): {type(first_pattern)}")
        if isinstance(first_pattern, dict):
            print(f"  Keys: {list(first_pattern.keys())}")
            if "homes" in first_pattern:
                print(f"  Homes in pattern: {len(first_pattern['homes'])}")
            if "places" in first_pattern:
                print(f"  Places in pattern: {len(first_pattern['places'])}")
    else:
        print("ERROR: No patterns data found!")
        return {"movement": {}, "result": {}}
    
    simulator = DiseaseSimulator(intervention_weights=interventions)
    
    # Build households
    print("=== BUILDING HOUSEHOLDS ===")
    for id, data in homes_data.items():
        if isinstance(data, list):
            cbg = data[0] if len(data) > 0 else None
        elif isinstance(data, dict):
            cbg = data.get("cbg")
        else:
            cbg = data
        simulator.add_household(Household(cbg, id))
    print(f"Added {len(simulator.households)} households")

    # Build facilities
    print("=== BUILDING FACILITIES ===")
    for id, data in places_data.items():
        if isinstance(data, list) and len(data) >= 2:
            cbg = data[0] if len(data) > 0 else None
            label = data[1] if len(data) > 1 else None
            capacity = data[2] if len(data) > 2 else -1
            latitude = 0
            longitude = 0
            top_category = 'Other'
            placekey = ''
            postal_code = 0
            street_address = ''
        elif isinstance(data, dict):
            cbg = data.get('cbg')
            label = data.get('label', f"Place_{id}")
            capacity = data.get('capacity', -1)
            latitude = data.get('latitude', 0)
            longitude = data.get('longitude', 0)
            top_category = data.get('top_category', 'Other')
            placekey = data.get('placekey', '')
            postal_code = data.get('postal_code', 0)
            street_address = data.get('street_address', 'None')
        else:
            cbg = data
            label = f"Place_{id}"
            capacity = -1
            latitude = 0
            longitude = 0
            top_category = 'Other'
            placekey = ''
            postal_code = 0
            street_address = ''
        
        if isinstance(capacity, str):
            try:
                capacity = int(capacity)
            except ValueError:
                capacity = -1
        
        simulator.add_facility(Facility(id, cbg, label, capacity, latitude, longitude, top_category, placekey, postal_code, street_address))
    print(f"Added {len(simulator.facilities)} facilities")

    # Get default infected IDs and variants from config
    default_infected_pool = list(SIMULATION["default_infected_ids"])
    variants = list(SIMULATION["variants"])
    
    print(f"=== INFECTION SETUP ===")
    print(f"Default infected IDs: {default_infected_pool}")
    print(f"Variants: {variants}")
    print(f"restore_state_file: {restore_state_file}")

    # Determine which people start infected.
    # - Default behavior (when unset) is 1 initial infection per variant.
    # - If `initial_infected_ids` is provided, it wins.
    # - If `initial_infected_count` is provided, infect that many people total.
    # - If `restore_state_file` is provided, skip initial infections (we'll restore state later)
    
    if restore_state_file:
        # Skip initial infection setup - we'll restore state from previous month
        print(f"[INIT] Skipping initial infections - will restore from state file: {restore_state_file}")
        variant_assignments = {}
        infected_ids = []
    elif initial_infected_ids is not None:
        if not isinstance(initial_infected_ids, list):
            raise ValueError("initial_infected_ids must be a JSON list")
        requested_ids = [str(x) for x in initial_infected_ids]
        infected_ids = [pid for pid in requested_ids if pid in people_data]
    else:
        if initial_infected_count is None:
            initial_infected_count = len(variants)
        try:
            initial_infected_count = int(initial_infected_count)
        except (TypeError, ValueError):
            raise ValueError("initial_infected_count must be an integer")
        if initial_infected_count < 0:
            raise ValueError("initial_infected_count must be >= 0")

        infected_pool = [pid for pid in default_infected_pool if pid in people_data]
        random.shuffle(infected_pool)

        # If caller asks for more than the default pool contains, extend with other people IDs.
        if initial_infected_count > len(infected_pool):
            extra_ids = [str(pid) for pid in people_data.keys() if str(pid) not in set(infected_pool)]
            random.shuffle(extra_ids)
            infected_pool.extend(extra_ids)

        infected_ids = infected_pool[:initial_infected_count]

    if not variants or not infected_ids:
        variant_assignments = {}
    else:
        # Assign a variant to each infected person (cycle variants if count > variants).
        variant_assignments = {
            pid: variants[i % len(variants)] for i, pid in enumerate(infected_ids)
        }

    print(f"Initial infected count: {len(variant_assignments)}")
    print(f"Variant assignments (sample): {dict(list(variant_assignments.items())[:10])}")

    # Build people
    print("=== BUILDING PEOPLE ===")
    people_added = 0
    for id, data in people_data.items():
        household = simulator.get_household(str(data['home']))
        if household is None:
            print(f"ERROR: Person {id} assigned to non-existent house {data['home']}")
            continue
        
        person = Person(id, data['sex'], data['age'], household)
        
        # Infect person with a uniquely assigned variant
        if str(id) in variant_assignments:
            variant = variant_assignments[str(id)]
            person.states[variant] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            initial_duration = INFECTION_MODEL["initial_timeline"]["duration"]
            recovery_duration = INFECTION_MODEL["fallback_timeline"]["recovery_duration"]
            person.timeline = {
                variant: {
                    InfectionState.INFECTED: InfectionTimeline(0, initial_duration),
                    InfectionState.INFECTIOUS: InfectionTimeline(0, initial_duration),
                    InfectionState.RECOVERED: InfectionTimeline(initial_duration, initial_duration + recovery_duration)
                }
            }
            print(f"Infected person {id} with variant {variant}")
            # logging initial infections at the beginning of the simulation
            if simulator.enable_logging and simulator.logger:
                simulator.logger.log_infection_event(person, None, person.household, variant, 0)

        # Assign masked state
        if random.random() < simulator.iv_weights['mask']:
            person.set_masked(True)
            #print(f"Person {person.id} assigned mask")
            if simulator.enable_logging and simulator.logger: 
                simulator.logger.log_intervention_effect(person, 'mask', 'complied', 0)


        # Assigning vaccination state
        if random.random() < simulator.iv_weights['vaccine']:
            min_doses = SIMULATION["vaccination_options"]["min_doses"]
            max_doses = SIMULATION["vaccination_options"]["max_doses"]
            doses = random.randint(min_doses, max_doses)
            person.set_vaccinated(VaccinationState(random.randint(min_doses, max_doses)))
            if simulator.enable_logging and simulator.logger: 
                simulator.logger.log_intervention_effect(person, 'vaccine', f'received_{doses}_doses', 0)

        simulator.add_person(person)
        household.add_member(person)
        people_added += 1

        if simulator.enable_logging and simulator.logger: 
            simulator.logger.log_person_demographics(person, 0)
    
    print(f"Added {people_added} people")
    
    # Restore state from previous simulation phase (for multi-month simulations)
    if restore_state_file:
        print(f"[STATE_RESTORE] ========================================")
        print(f"[STATE_RESTORE] Restoring from: {restore_state_file}")
        print(f"[STATE_RESTORE] File exists: {os.path.exists(restore_state_file) if 'os' in dir() else 'unknown'}")
        print(f"[STATE_RESTORE] ========================================")
        try:
            from .state_manager import load_simulation_state, restore_people_state
            saved_state = load_simulation_state(restore_state_file)
            print(f"[STATE_RESTORE] Loaded state with {len(saved_state.get('people', {}))} people")
            print(f"[STATE_RESTORE] State metadata: {saved_state.get('metadata', {})}")
            
            # Get the time offset (minutes) between previous and current simulation starts.
            # Prefer explicit restore_time_offset (supports overlapping months), fall back to saved end_time.
            time_offset = restore_time_offset
            if time_offset is None:
                meta = saved_state.get('metadata', {})
                time_offset = meta.get('length_minutes')
                if time_offset is None:
                    time_offset = meta.get('end_time', 0)
            try:
                time_offset = int(time_offset) if time_offset is not None else 0
            except (TypeError, ValueError):
                time_offset = 0
            print(f"[STATE_RESTORE] Time offset from previous sim: {time_offset}")
            
            restored_count = restore_people_state(simulator.people, saved_state.get('people', {}), time_offset=time_offset)
            restored_infected = count_infected_people(simulator.people)
            print(f"[STATE_RESTORE] Infected immediately after restore: {restored_infected}")
            if report:
                report.info(f"[STATE_RESTORE] Infected immediately after restore: {restored_infected}")
            print(f"[STATE_RESTORE] Restored state for {restored_count} people")
            if report:
                report.info(f"Restored state for {restored_count} people from {restore_state_file}")
            
            # Clear initial infections since we're continuing from saved state
            # (people who were infected will already have their states restored)
            variant_assignments.clear()
            print(f"[STATE_RESTORE] Cleared variant_assignments (continuing from saved state)")
            
        except Exception as e:
            print(f"[STATE_RESTORE] ERROR: Could not restore state: {e}")
            import traceback
            traceback.print_exc()
            if report:
                report.warn(f"Could not restore state from {restore_state_file}: {e}")
    
    # Create infection manager with DMP API
    infectionmgr = InfectionManager({}, people=simulator.people.values())
    
    # Debug: Log infection manager state
    print(f"[INFMGR] InfectionManager created with {len(infectionmgr.infected)} infected people")
    if restore_state_file:
        # Count how many people have INFECTIOUS state
        infectious_count = 0
        for p in simulator.people.values():
            for state in p.states.values():
                if isinstance(state, InfectionState) and (state & InfectionState.INFECTIOUS):
                    infectious_count += 1
                    break
        print(f"[INFMGR] Total people with INFECTIOUS state: {infectious_count}")
        print(f"[INFMGR] InfectionManager.infected has: {len(infectionmgr.infected)} people")
        # if infectious_count > 0 and len(infectionmgr.infected) == 0:
        if infectious_count > len(infectionmgr.infected):
            print(f"[INFMGR] BUG DETECTED: People are infectious but not in infected list!")
    
    # Prepare simulation
    last_timestep = 0
    timestamps = sorted([int(k) for k in patterns.keys() if k.isdigit()])
    print(f"=== SIMULATION PREPARATION ===")
    print(f"Sorted timestamps: {timestamps[:10]}...")  # First 10
    print(f"Starting timestep: {last_timestep}")
    print(f"Max length: {max_length}")
    
    result = {}
    variantInfected = {variant: {} for variant in variants}
    
    # Populate variantInfected with existing infection states from people
    # This is needed both for state restoration AND for initial infections
    print(f"[INIT] Populating variantInfected from people states...")
    initial_infected_count_tracked = 0
    for pid, person in simulator.people.items():
        for variant in variants:
            if variant in person.states:
                state = person.states[variant]
                if isinstance(state, InfectionState):
                    state_value = state.value
                else:
                    state_value = int(state)
                # If person has any infection-related state (not just susceptible)
                if state_value != 0:
                    variantInfected[variant][str(pid)] = state_value
                    if state_value & 1:  # INFECTED bit
                        initial_infected_count_tracked += 1
    print(f"[INIT] Populated variantInfected: {initial_infected_count_tracked} currently infected")
    for variant in variants:
        print(f"[INIT]   {variant}: {len(variantInfected[variant])} people with states")
    
    movement_json = {}
    infectivity_json = {}

    # Main simulation loop
    print("=== STARTING SIMULATION LOOP ===")
    print(f"[LOOP-START] variantInfected totals: {[(v, len(d)) for v, d in variantInfected.items()]}")
    iteration = 0
    first_result_logged = False
    while len(timestamps) > 0:
        iteration += 1
        
        if (last_timestep > max_length):
            print(f"Breaking: timestep {last_timestep} > max_length {max_length}")
            break
        
        log_interval = SIMULATION["log_interval"]
        if last_timestep % log_interval == 0:
            print(f'Running movement simulator for timestep {last_timestep} (iteration {iteration})')
        
        # Process movement if we've reached the next timestamp
        if len(timestamps) > 0 and last_timestep >= timestamps[0]:
            current_timestamp = str(timestamps[0])
            # Only log every 10th pattern for performance
            if int(current_timestamp) % 600 == 0:
                print(f"Processing timestamp {current_timestamp}")
            
            if current_timestamp in patterns:
                data = patterns[current_timestamp]
                
                if isinstance(data, dict):
                    if 'homes' in data:
                        move_people(simulator, data['homes'].items(), True, current_timestamp)
                    if 'places' in data:
                        move_people(simulator, data['places'].items(), False, current_timestamp)
                else:
                    print(f"  ERROR: Pattern data is not a dict: {data}")
            else:
                print(f"  ERROR: Timestamp {current_timestamp} not found in patterns")
            
            timestamps.pop(0)

            if simulator.enable_logging and simulator.logger: 
                for person in simulator.people.values(): 
                    simulator.logger.log_person_demographics(person, last_timestep)
                
                for household in simulator.households.values(): 
                    if len(household.population) > 0: 
                        simulator.logger.log_location_state(household, last_timestep)

                for facility in simulator.facilities.values(): 
                    if len(facility.population) > 0: 
                        simulator.logger.log_location_state(facility, last_timestep)

                        # Only log contacts for infectious situations to avoid O(n²) explosion
                        # Skip contact logging if no one is infectious
                        population = list(facility.population)
                        has_infectious = any(
                            any(p.states[v] & InfectionState.INFECTIOUS for v in p.states.keys()) 
                            for p in population
                        )
                        if has_infectious and len(population) <= 50:  # Only log if facility is small enough
                            for i, person1 in enumerate(population): 
                                for person2 in population[i+1:]: 
                                    simulator.logger.log_contact_event(person1, person2, facility, last_timestep)

            
        
        # Record movement
        # Note: Convert person IDs to strings to match the result data format (JSON serializes int keys as strings)
        movement_json[last_timestep] = {
            "homes": {str(h.id): [str(p.id) for p in h.population] for h in simulator.households.values() if len(h.population) > 0},
            "places": {str(f.id): [str(p.id) for p in f.population] for f in simulator.facilities.values() if len(f.population) > 0}
        }
        
        # Track movement data
        homes_with_people = len(movement_json[last_timestep]["homes"])
        places_with_people = len(movement_json[last_timestep]["places"])
        if homes_with_people > 0 or places_with_people > 0:
            print(f"  Timestep {last_timestep}: {homes_with_people} homes, {places_with_people} places with people")
        
        # Run infection model
        newlyInfected = {}
        try:
            pre_infection_states = {}
            if simulator.enable_logging and simulator.logger: 
                for person in simulator.people.values(): 
                    # pre_infection_states[person.id] = {variant: person.states.get(variant, 0) for variant in variants}
                    pre_infection_states[person.id] = {
                        variant: person.states.get(variant, InfectionState.SUSCEPTIBLE) 
                        for variant in variants
                    }
                
            infectionmgr.run_model(1, None, last_timestep, variantInfected, newlyInfected)

            if simulator.enable_logging and simulator.logger: 
                for person in simulator.people.values(): 
                    for variant in variants: 
                        old_state = pre_infection_states[person.id][variant]
                        new_state = person.states.get(variant, InfectionState.SUSCEPTIBLE)  # Use enum default
                        
                        # Ensure both states are InfectionState enums
                        if not isinstance(old_state, InfectionState):
                            old_state = InfectionState.SUSCEPTIBLE
                        if not isinstance(new_state, InfectionState):
                            new_state = InfectionState.SUSCEPTIBLE
                            
                        if not (old_state & InfectionState.INFECTED) and (new_state & InfectionState.INFECTED):
                            # Try to identify the infector (simplified - could be enhanced)
                            infector = None
                            location = person.location
                            
                            # Look for infectious people in the same location
                            if location and hasattr(location, 'population'):
                                for potential_infector in location.population:
                                    infector_state = potential_infector.states.get(variant, InfectionState.SUSCEPTIBLE)
                                    if not isinstance(infector_state, InfectionState):
                                        infector_state = InfectionState.SUSCEPTIBLE
                                        
                                    if (potential_infector != person and 
                                        infector_state & InfectionState.INFECTIOUS):
                                        infector = potential_infector
                                        break
                            simulator.logger.log_infection_event(person, infector, location, variant, last_timestep)

                        
        except Exception as e:
            print(f"Error during infection modeling at timestep {last_timestep}: {e}")
            newlyInfected = {}
        
        infectivity_json[last_timestep] = {i: j for i, j in newlyInfected.items()}
        result[last_timestep] = {variant: dict(infected) for variant, infected in variantInfected.items()}
        
        # Debug: Log first few results
        if not first_result_logged or last_timestep % 1000 == 0:
            total_entries = sum(len(v) for v in result[last_timestep].values())
            # Count how many have INFECTED bit set vs just RECOVERED
            infected_bit_count = 0
            recovered_only_count = 0
            sample_states = []
            for variant, people in result[last_timestep].items():
                for pid, state in people.items():
                    if state & 1:  # INFECTED bit
                        infected_bit_count += 1
                    elif state == 16 or state == 32:  # RECOVERED or REMOVED only
                        recovered_only_count += 1
                    if len(sample_states) < 5:
                        sample_states.append((pid, variant, state))
            print(f"[RESULT-DEBUG] ts={last_timestep}: {total_entries} total, {infected_bit_count} with INFECTED bit, {recovered_only_count} recovered/removed only")
            print(f"[RESULT-DEBUG]   sample states: {sample_states}")
            if total_entries == 0 and iteration > 1:
                print(f"[RESULT-DEBUG]   WARNING: 0 entries at ts={last_timestep}!")
                print(f"[RESULT-DEBUG]   variantInfected totals: {[(v, len(d)) for v, d in variantInfected.items()]}")
            first_result_logged = True
        
        last_timestep += simulator.timestep
        
        # Safety break
        if iteration > 10000:
            print("Breaking: too many iterations")
            break

    print(f"=== SIMULATION COMPLETE ===")
    print(f"Total iterations: {iteration}")
    print(f"Final timestep: {last_timestep}")
    print(f"Result timesteps: {len(result)}")
    print(f"Movement timesteps: {len(movement_json)}")

    if simulator.enable_logging and simulator.logger: 
        print("=== EXPORTING LOGS ===")
        simulator.logger.export_logs_to_csv()
        simulator.logger.generate_summary_report()
        simulator.logger.graphic_analysis()
        print(f"Logs exported to {log_dir}/")
        print(f"Generated files (streamed to disk):")
        print(f"  - person_logs.csv: {simulator.logger.person_log_count} records")
        print(f"  - movement_logs.csv: {simulator.logger.movement_log_count} records")
        print(f"  - infection_logs.csv: {simulator.logger.infection_log_count} records")
        print(f"  - intervention_logs.csv: {simulator.logger.intervention_log_count} records")
        print(f"  - location_logs.csv: {simulator.logger.location_log_count} records")
        print(f"  - contact_logs.csv: {simulator.logger.contact_log_count} records")
        print(f"  - infection_chains.csv: Chain data for {len(simulator.logger.infection_chains)} infections")
        print(f"  - summary_report.txt: Summary report")

    
    # Debug final results
    non_empty_results = {k: v for k, v in result.items() if v and any(v.values())}
    non_empty_movement = {k: v for k, v in movement_json.items() if v and (v.get('homes') or v.get('places'))}
    
    print(f"Non-empty results: {len(non_empty_results)}")
    print(f"Non-empty movement: {len(non_empty_movement)}")
    
    if non_empty_movement:
        sample_timestep = list(non_empty_movement.keys())[0]
        sample_movement = non_empty_movement[sample_timestep]
        print(f"Sample movement (timestep {sample_timestep}):")
        print(f"  Homes: {len(sample_movement.get('homes', {}))}")
        print(f"  Places: {len(sample_movement.get('places', {}))}")

    if save_file:
        # Print results for each variant
        for variant in variantInfected.keys():
            print(f"{variant} Infected:")
            print(variantInfected[variant])
    
        with open('results.json', 'w') as file:
            json.dump(result, file, indent=4)
            
        with open('results_movement.json', 'w') as file:
            json.dump(movement_json, file, indent=4)
            
        with open('results_infections.json', 'w') as file:
            json.dump(infectivity_json, file, indent=4)
    else:
        # Build papdata for frontend
        papdata = {
            'people': {str(p.id): {'sex': p.sex, 'age': p.age, 'home': str(p.household.id) if p.household else None} for p in simulator.people.values()},
            'homes': {str(h.id): {'cbg': getattr(h, 'cbg', ''), 'members': len(h.population)} for h in simulator.households.values()},
            'places': {str(f.id): {
                'placekey': getattr(f, 'placekey', ''),
                'label': getattr(f, 'label', f'Place {f.id}'),
                'latitude': getattr(f, 'latitude', 0),
                'longitude': getattr(f, 'longitude', 0),
                'top_category': getattr(f, 'top_category', 'Other'),
                'postal_code': getattr(f, 'postal_code', 0),
                'street_address': getattr(f, 'street_address', '')
            } for f in simulator.facilities.values()}
        }
        
        # Build people state for multi-month simulation continuity
        people_state = {}
        non_zero_states_count = 0
        sample_non_zero = []
        for pid, person in simulator.people.items():
            if hasattr(person, 'to_dict'):
                people_state[str(pid)] = person.to_dict()
            else:
                # Fallback: just store basic state
                people_state[str(pid)] = {
                    'id': pid,
                    'states': {k: v.value if hasattr(v, 'value') else int(v) for k, v in getattr(person, 'states', {}).items()},
                    'masked': getattr(person, 'masked', False),
                    'vaccination_state': getattr(person, 'vaccination_state', 0),
                }
            
            # Debug: Count states being saved
            for variant, state in getattr(person, 'states', {}).items():
                state_val = state.value if hasattr(state, 'value') else int(state)
                if state_val != 0:
                    non_zero_states_count += 1
                    if len(sample_non_zero) < 10:
                        sample_non_zero.append((pid, variant, state_val, str(state)))
        
        print(f"[SIM_END] Non-zero states in people objects: {non_zero_states_count}")
        print(f"[SIM_END] Sample non-zero states: {sample_non_zero}")
        
        end_infected = count_infected_people(simulator.people)
        print(f"[SIM_END] Infected at end of simulation: {end_infected}")
        if report:
            report.info(f"[SIM_END] Infected at end of simulation: {end_infected}")
        if end_infected != len(infectionmgr.infected):
            print("ERROR! Unequal infected in simulator than infectionmgr!")

        final_result = {
            'result': {i: j for i, j in result.items() if i != 0},
            'movement': {i: j for i, j in movement_json.items() if i != 0},
            'papdata': papdata,
            'people_state': people_state,  # For multi-month simulation state persistence
        }
        print(f"Returning result with {len(final_result['result'])} result timesteps and {len(final_result['movement'])} movement timesteps")
        return final_result

    return result