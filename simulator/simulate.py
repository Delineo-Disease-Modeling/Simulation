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


curdir = os.path.dirname(os.path.abspath(__file__))

class SimulationLogger: 
    """Logging system for simulation"""

    def __init__ (self, log_dir = "simulation_logs", enable_file_logging = True): 
        self.log_dir = log_dir 
        self.enable_file_logging = enable_file_logging

        if self.enable_file_logging: 
            os.makedirs(log_dir, exist_ok=True)

        self.person_logs = []
        self.movement_logs = []
        self.infection_logs = []
        self.intervention_logs = []
        self.location_logs = []
        self.contact_logs = []
        self.exposure_logs = []

        self.person_states = {}
        self.location_occupancy = defaultdict(list)
        self.infection_chains = {}

        self.setup_logging()
    
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
        """Log person demographics and current state"""
        vax_status = person.vaccination_status if person.vaccination_status else "Unvaccinated"
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
                'deceased': bool(state & InfectionState.DECEASED)
            }

            if state & InfectionState.INFECTIOUS:
                infectious_variants.append(variant)
            if state & InfectionState.SYMPTOMATIC:
                symptomatic_variants.append(variant)
            
            location_id = person.location.id if person.location else None 
            location_type = "household" if isinstance(person.location, Household) else "facility" if isinstance(person.location, Facility) else "unknown"
            location_capacity = getattr(person.location, 'capacity', -1) if person.location else -1
            location_occupancy = len(person.location.population) if person.location else 0 

            person_log = {
                'timestep': timestep, 
                'person_id': person.id,
                'age': person.age,
                'sex': person.sex, 
                'household_id': person.household.id if person.household else None,
                'current_location_id': location_id,
                'current_location_type': location_type,
                'location_capacity': location_capacity,
                'location_occupancy': location_occupancy,
                'location_utilization': location_occupancy / location_capacity if location_capacity > 0 else 0,
                'is_masked': getattr(person, 'masked', False), 
                'vaccination_status': vax_status,
                'vaccination_doses': vax_doses,
                'infectious_variants': infectious_variants,
                'symptomatic_variants': symptomatic_variants,
                'total_variants_infected': len([v for v in infection_status.values() if v['infected']]),
                'infection_status': infection_status
            }

            self.person_logs.append(person_log)
            self.person_states[person.id] = person_log.copy()

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

        self.movement_logs.append(movement_log)

    def log_infection_event(self, infected_person, infector_person, location, variant, timestep): 
        """Log an infection event"""
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
            'transmission_risk_score': self.calculate_transmission_risk(infected_person, infector_person, location)
        }
        self.infection_logs.append(infection_log)

        # tracking infection chains 
        if infector_person: 
            self.infection_chains[infected_person.id] = {
                'infector_id': infector_person.id,
                'location_id': location.id if location else None,
                'variant': variant,
                'timestep': timestep
            }
    
    def log_intervention_effect(self, person, intervention_type, effect, timestep, location=None): 
        """Log when interventions affect person behavior"""
        intervention_log = {
            'timestep': timestep,
            'person_id': person.id,
            'intervention_type': intervention_type, # for example, lockdown, capacity limit, self isolation, mask, vaccine 
            'effect': effect,
            'person_age': person.age, 
            'person_sex': person.sex, 
        }

# Putting it all together, simulates each timestep
# We can choose to only simulate areas with infected people
class DiseaseSimulator:
    def __init__(self, timestep=None, intervention_weights={}):
        self.timestep = timestep or SIMULATION["default_timestep"]  # in minutes
        self.iv_weights = intervention_weights
        self.people = {}
        self.households = {}          # list of all houses
        self.facilities = {}
    
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

def move_people(simulator, items, is_household):
    for id, people in items:
        place = simulator.get_household(str(id)) if is_household else simulator.get_facility(str(id))
        if place is None:
            raise Exception(f"Place {id} was not found in the simulator data ({is_household})")

        for person_id in people:
            person = simulator.get_person(person_id)
            if person is None:
                raise Exception(f"Person {person_id} was not found in the simulator data")

            # If we hit capacity limit, then we are going to send the person home instead
            # Otherwise, if we are enforcing a lockdown, they may randomly decide to head home
            if not is_household:
                at_capacity = place.total_count >= place.capacity * simulator.iv_weights['capacity'] if place.capacity != -1 else False
                hit_lockdown = place != person.location and random.random() < simulator.iv_weights['lockdown']
                self_iso = person.get_state(InfectionState.SYMPTOMATIC) and random.random() < simulator.iv_weights['selfiso']
                if at_capacity or hit_lockdown or self_iso:
                    person.location.remove_member(person_id)
                    person.household.add_member(person)
                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            person.location = place

def run_simulator(location=None, max_length=None, interventions=None, save_file=False):
    location = location or SIMULATION["default_location"]
    max_length = max_length or SIMULATION["default_max_length"]
    
    print(f"=== SIMULATION DEBUG START ===")
    print(f"max_length: {max_length}")
    print(f"save_file: {save_file}")
    
    # Merge provided interventions with defaults
    default_interventions = SIMULATION["default_interventions"].copy()
    if interventions:
        default_interventions.update(interventions)
    interventions = default_interventions
    
    # Set random seed if user specifies
    if not interventions['randseed']:
        random.seed(0)
    
    # Load people and places using the new streaming method
    data_stream = StreamDataLoader.stream_data("https://db.delineo.me/patterns/1?stream=true")
    
    # Extract initial data from the stream
    people_data = {}
    homes_data = {}
    places_data = {}
    patterns = {}
    with open('simulator/barnsdall/patterns.json', 'r') as file:
        patterns = json.load(file)
        print(f"Loaded {len(patterns)} patterns from pattern_simple.json")
    print("=== LOADING DATA FROM STREAM ===")
    chunk_count = 0
    for data in data_stream:
        chunk_count += 1
        print(f"Chunk {chunk_count} - Keys: {list(data.keys())}")
        
        # Merge data from each chunk
        if "people" in data:
            people_data.update(data["people"])
            print(f"  People: {len(data['people'])} items")
        if "homes" in data:
            homes_data.update(data["homes"])
            print(f"  Homes: {len(data['homes'])} items")
        if "places" in data:
            places_data.update(data["places"])
            print(f"  Places: {len(data['places'])} items")
        if "patterns" in data:
            patterns.update(data["patterns"])
            print(f"  Patterns: {len(data['patterns'])} items")
    
    print(f"=== FINAL DATA LOADED ===")
    print(f"Total people: {len(people_data)}")
    print(f"Total homes: {len(homes_data)}")
    print(f"Total places: {len(places_data)}")
    print(f"Total patterns: {len(patterns)}")
    
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
        elif isinstance(data, dict):
            cbg = data.get('cbg')
            label = data.get('label', f"Place_{id}")
            capacity = data.get('capacity', -1)
        else:
            cbg = data
            label = f"Place_{id}"
            capacity = -1
        
        if isinstance(capacity, str):
            try:
                capacity = int(capacity)
            except ValueError:
                capacity = -1
        
        simulator.add_facility(Facility(id, cbg, label, capacity))
    print(f"Added {len(simulator.facilities)} facilities")

    # Get default infected IDs and variants from config
    default_infected = SIMULATION["default_infected_ids"]
    variants = SIMULATION["variants"]
    
    print(f"=== INFECTION SETUP ===")
    print(f"Default infected IDs: {default_infected}")
    print(f"Variants: {variants}")
    
    # Ensure no more variants than infected individuals
    if len(variants) > len(default_infected):
        raise ValueError("Not enough infected IDs to assign each variant uniquely")

    # Randomly match infected IDs with variants
    random.shuffle(default_infected)
    variant_assignments = {id: variant for id, variant in zip(default_infected, variants)}
    print(f"Variant assignments: {variant_assignments}")

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
            person.timeline = {
                variant: {
                    InfectionState.INFECTED: InfectionTimeline(0, initial_duration),
                    InfectionState.INFECTIOUS: InfectionTimeline(0, initial_duration)
                }
            }
            print(f"Infected person {id} with variant {variant}")
        
        # Assign masked and vaccination states
        if random.random() < simulator.iv_weights['mask']:
            person.set_masked(True)
        
        if random.random() < simulator.iv_weights['vaccine']:
            min_doses = SIMULATION["vaccination_options"]["min_doses"]
            max_doses = SIMULATION["vaccination_options"]["max_doses"]
            person.set_vaccinated(VaccinationState(random.randint(min_doses, max_doses)))
        
        simulator.add_person(person)
        household.add_member(person)
        people_added += 1
    
    print(f"Added {people_added} people")
    
    # Create infection manager with DMP API
    infectionmgr = InfectionManager({}, people=simulator.people.values())
    
    # Prepare simulation
    last_timestep = 0
    timestamps = sorted([int(k) for k in patterns.keys() if k.isdigit()])
    print(f"=== SIMULATION PREPARATION ===")
    print(f"Sorted timestamps: {timestamps[:10]}...")  # First 10
    print(f"Starting timestep: {last_timestep}")
    print(f"Max length: {max_length}")
    
    result = {}
    variantInfected = {variant: {} for variant in variants}
    
    movement_json = {}
    infectivity_json = {}

    # Main simulation loop
    print("=== STARTING SIMULATION LOOP ===")
    iteration = 0
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
            print(f"Processing timestamp {current_timestamp}")
            
            if current_timestamp in patterns:
                data = patterns[current_timestamp]
                print(f"  Pattern data type: {type(data)}")
                
                if isinstance(data, dict):
                    if 'homes' in data:
                        print(f"  Moving people to homes: {len(data['homes'])} locations")
                        move_people(simulator, data['homes'].items(), True)
                    if 'places' in data:
                        print(f"  Moving people to places: {len(data['places'])} locations")
                        move_people(simulator, data['places'].items(), False)
                else:
                    print(f"  ERROR: Pattern data is not a dict: {data}")
            else:
                print(f"  ERROR: Timestamp {current_timestamp} not found in patterns")
            
            timestamps.pop(0)
        
        # Record movement
        movement_json[last_timestep] = {
            "homes": {str(h.id): [p.id for p in h.population] for h in simulator.households.values() if len(h.population) > 0},
            "places": {str(f.id): [p.id for p in f.population] for f in simulator.facilities.values() if len(f.population) > 0}
        }
        
        # Track movement data
        homes_with_people = len(movement_json[last_timestep]["homes"])
        places_with_people = len(movement_json[last_timestep]["places"])
        if homes_with_people > 0 or places_with_people > 0:
            print(f"  Timestep {last_timestep}: {homes_with_people} homes, {places_with_people} places with people")
        
        # Run infection model
        newlyInfected = {}
        try:
            infectionmgr.run_model(1, None, last_timestep, variantInfected, newlyInfected)
        except Exception as e:
            print(f"Error during infection modeling at timestep {last_timestep}: {e}")
            newlyInfected = {}
        
        infectivity_json[last_timestep] = {i: j for i, j in newlyInfected.items()}
        result[last_timestep] = {variant: dict(infected) for variant, infected in variantInfected.items()}
        
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
        final_result = {
            'result': {i: j for i, j in result.items() if i != 0},
            'movement': {i: j for i, j in movement_json.items() if i != 0}
        }
        print(f"Returning result with {len(final_result['result'])} result timesteps and {len(final_result['movement'])} movement timesteps")
        return final_result

    return result