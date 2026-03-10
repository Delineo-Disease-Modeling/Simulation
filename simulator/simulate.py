from .pap import Person, Household, Facility, InfectionState, VaccinationState
from .infectionmgr import *
from .config import DELINEO, SIMULATION, INFECTION_MODEL
import pandas as pd
import json
import os
import gzip
from .data_interface import StreamDataLoader
import random 
import logging 
from collections import defaultdict
from math import ceil
from . import agentstats as ast

curdir = os.path.dirname(os.path.abspath(__file__))

class IncrementalJSONWriter:
    def __init__(self, filename):
        self.filename = filename
        # Use gzip.open for compressed writing
        self.f = gzip.open(filename, 'wt', encoding='utf-8')
        self.f.write('{')
        self.first = True

    def add(self, key, value):
        if not self.first:
            self.f.write(',')
        else:
            self.first = False
        
        # We manually structure the key-value pair to avoid dumping a huge wrapper dict
        self.f.write(f'"{key}":')
        json.dump(value, self.f)

    def close(self):
        self.f.write('}')
        self.f.close()

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
        self.location_population = defaultdict(list)
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
                'location_utilization': location_population / location_capacity if location_capacity > 0 else 0,
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
            'person_infectious': any(person.states[v] & InfectionState.INFECTIOUS for v in person.states.keys()),
            'person_symptomatic': any(person.states[v] & InfectionState.SYMPTOMATIC for v in person.states.keys()),
            'location_id': location.id if location else None,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'location_occupancy': len(location.population) if location else 0,
            'location_capacity': getattr(location, 'capacity', -1) if location else -1
        }

        self.intervention_logs.append(intervention_log.copy())

    def log_location_state(self, location, timestep):
        population = location.population if hasattr(location, 'population') else []
        infectious_count = sum(1 for p in population if any(p.states[v] & InfectionState.INFECTIOUS for v in p.states.keys()))
        symptomatic_count = sum(1 for p in population if any(p.states[v] & InfectionState.SYMPTOMATIC for v in p.states.keys()))
        masked_count = sum(1 for p in population if getattr(p, 'masked', False))
        vaccinated_count = sum(1 for p in population if hasattr(p, 'vaccination_state') and p.vaccination_state and p.vaccination_state.value > 0)

        ages = [p.age for p in population]
        avg_age = sum(ages) / len(ages) if ages else 0

        location_log = {
            'timestep': timestep,
            'location_id': location.id,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'capacity': getattr(location, 'capacity', -1),
            'occupancy': len(population),
            'utilization_rate': len(population) / getattr(location, 'capacity', 1),  # Avoid division by zero
            'infectious_count': infectious_count,
            'symptomatic_count': symptomatic_count,
            'masked_count': masked_count,
            'vaccinated_count': vaccinated_count,
            'avg_age': avg_age,
            'male_count': sum(1 for p in population if p.sex == '0'),
            'female_count': sum(1 for p in population if p.sex == '1')
        }

        self.location_logs.append(location_log)

    def log_contact_event(self, person1, person2, location, timestep, contact_duration = 1): 
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
        
        self.contact_logs.append(contact_log)

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
        infectious_count = sum(1 for p in population if any(p.states[v] & InfectionState.INFECTIOUS for v in p.states.keys()))

        if infectious_count == 0:
            return 0
        
        risk = infectious_count / len(population)  # Basic risk based on infectious individuals
        if hasattr(location, 'capacity') and location.capacity > 0:
            utilization = len(population) / location.capacity
            risk *= (1 + utilization)

        masked_rate = sum(1 for p in population if getattr(p, 'masked', False)) / len(population)

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
        if not self.enable_file_logging: 
            return 
        
        if self.person_logs: 
            df = pd.DataFrame(self.person_logs)
            df.to_csv(f'{self.log_dir}/person_logs.csv', index=False)

        if self.movement_logs:
            df = pd.DataFrame(self.movement_logs)
            df.to_csv(f'{self.log_dir}/movement_logs.csv', index=False)
        
        if self.infection_logs:
            df = pd.DataFrame(self.infection_logs)
            df.to_csv(f'{self.log_dir}/infection_logs.csv', index=False)

        if self.intervention_logs:
            df = pd.DataFrame(self.intervention_logs)
            df.to_csv(f'{self.log_dir}/intervention_logs.csv', index=False)

        if self.location_logs:
            df = pd.DataFrame(self.location_logs)
            df.to_csv(f'{self.log_dir}/location_logs.csv', index=False)
        
        if self.contact_logs:
            df = pd.DataFrame(self.contact_logs)
            df.to_csv(f'{self.log_dir}/contact_logs.csv', index=False)

        if self.infection_chains: 
            chains_df = pd.DataFrame.from_dict(self.infection_chains, orient='index')
            chains_df.reset_index(inplace=True)
            chains_df.rename(columns={'index': 'infected_person_id'}, inplace=True)
            chains_df.to_csv(f'{self.log_dir}/infection_chains.csv', index=False)


    def generate_summary_report(self):
        if not self.enable_file_logging:
            return 

        report = []
        report.append("=== Simulation Summary Report ===\n")

        total_people = len(set(log['person_id'] for log in self.person_logs))
        total_infections = len(self.infection_logs)
        total_movements = len(self.movement_logs)

        report.append(f"Total people: {total_people}") 
        report.append(f"Total infections: {total_infections}")
        report.append(f"Total movements: {total_movements}")

        if self.intervention_logs: 
            interventions = pd.DataFrame(self.intervention_logs)
            intervention_summary = interventions.groupby('intervention_type').size()
            report.append("\nIntervention Events:") 
            for intervention, count in intervention_summary.items():
                report.append(f"  {intervention}: {count} events")

        with open(f'{self.log_dir}/summary_report.txt', 'w') as f:
            f.write("\n".join(report))
    
    def graphic_analysis(self):
        if not self.enable_file_logging or not self.infection_logs:
            return 0
        
        #construct graph
        start = ast.Node(-1,-1,None)
        ast.build_agent_graph_nodupes(start, f'{self.log_dir}/infection_logs.csv')

        #run analysis
        report = []
        ast.calculate_all_harmonic(start)
        ast.check_sse(start, report)
        ast.location_impact(start, report)
        ast.time_gates(start, report)
        ast.time_impact(start, report)

        with open(f'{self.log_dir}/graph_report.txt', 'w') as f:
            f.write("\n".join(report))

        return 1
            
# Putting it all together, simulates each timestep
# We can choose to only simulate areas with infected people
class DiseaseSimulator:
    def __init__(self, timestep=None, intervention_weights=[], enable_logging = True, log_dir = "simulation_logs"):
        self.timestep = timestep or SIMULATION["default_timestep"]  # in minutes
        self.iv_weights = intervention_weights
        self.people = {}
        self.households = {}          # list of all houses
        self.facilities = {}
        self.logger = SimulationLogger(log_dir, enable_logging) if enable_logging else None
        self.enable_logging = enable_logging 
        
    def get_interventions(self, curtime: int):
        best_time = 0
        weights = self.iv_weights[0]
        
        for w in self.iv_weights:
            # Mult by 60 because interventions are sent back in hours
            if w['time'] * 60 < int(curtime) and best_time < w['time']:
                best_time = w['time']
                weights = w
        
        return weights
    
    def add_person(self, person: Person):
        self.people[str(person.id)] = person  
        
    def get_person(self, id) -> Person:
        return self.people.get(str(id)) 

    def add_household(self, household: Household):
        self.households[str(household.id)] = household

    def get_household(self, id) -> Household:
        return self.households.get(str(id))

    def add_facility(self, facility: Facility):
        self.facilities[str(facility.id)] = facility
    
    def get_facility(self, id) -> Facility:
        return self.facilities.get(str(id))

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
            
            interventions = simulator.get_interventions(current_timestep)

            # If we hit capacity limit, then we are going to send the person home instead
            # Otherwise, if we are enforcing a lockdown, they may randomly decide to head home
            if not is_household:
                at_capacity = place.total_count >= place.capacity * interventions['capacity'] if place.capacity != -1 else False
                hit_lockdown = place != person.location and random.random() < interventions['lockdown']
                self_iso = person.get_state(InfectionState.SYMPTOMATIC) and random.random() < interventions['selfiso']
                
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

                    if simulator.enable_logging and simulator.logger and original_location.id != person.household.id: 
                        reason = 'capacity_limit' if at_capacity else ('lockdown' if hit_lockdown else 'self_isolation')
                        simulator.logger.log_movement(person, original_location, person.household, current_timestep, reason)

                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            
            if simulator.enable_logging and simulator.logger and original_location.id != place.id: 
                simulator.logger.log_movement(person, original_location, place, current_timestep, 'normal')

            person.location = place


def run_simulator(simdata, save_file=False, enable_logging = True, log_dir = "simulation_logs", output_dir=None, progress_callback=None):
    print(f"=== SIMULATION DEBUG START ===")
    print(f"max_length: {simdata['length']}")
    
    # Set random seed if user specifies
    if not simdata['randseed']:
        random.seed(0)
    
    # Load people and places using the new streaming method
    # This generator yields standard dicts that we can consume sequentially
    url = f"{DELINEO['DB_URL']}patterns/{simdata['czone_id']}?length={simdata['length']}"
    data_stream = StreamDataLoader.stream_data(url, timeout=360)
    stream_iterator = iter(data_stream)
    
    # --- PHASE 1: Load Static Data (PapData) ---
    # We expect the first chunk to contain the bulk of static data (people, homes, places)
    # The server sends: papdata_file_content \n pattern_chunk_1 \n pattern_chunk_2 ...
    
    people_data = {}
    homes_data = {}
    places_data = {}
    patterns_buffer = {}
    
    try:
        print("=== WAITING FOR STATIC DATA ===")
        first_chunk = next(stream_iterator)
        
        if "people" in first_chunk: people_data = first_chunk["people"]
        if "homes" in first_chunk: homes_data = first_chunk["homes"]
        if "places" in first_chunk: places_data = first_chunk["places"]
        if "patterns" in first_chunk: patterns_buffer.update(first_chunk["patterns"])
        
        print(f"Loaded static data: {len(people_data)} people, {len(homes_data)} homes, {len(places_data)} places")

    except StopIteration:
        print("ERROR: Stream is empty!")
        return {"error": "No data received from server"}
    except Exception as e:
        print(f"ERROR: Failed to load static data: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

    # Initialize Simulator
    simulator = DiseaseSimulator(timestep=60, enable_logging=enable_logging, intervention_weights=simdata['interventions'])
    
    # Build households
    for id, data in homes_data.items():
        if isinstance(data, list):
            cbg = data[0] if len(data) > 0 else None
        elif isinstance(data, dict):
            cbg = data.get("cbg")
        else:
            cbg = data
        simulator.add_household(Household(cbg, str(id)))
        
    # Build facilities
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
        
        simulator.add_facility(Facility(str(id), cbg, label, capacity))

    # Initialize Variants
    variants = SIMULATION["variants"]
    default_infected = random.sample(list(people_data.keys()), min(len(people_data), len(variants)))
    variant_assignments = {id: variant for id, variant in zip(default_infected, variants)}
    
    # Build people
    iv_threshold = [ceil((100.0 * i) / len(people_data)) / 100.0 for i in range(len(people_data))]
    
    for id, data in people_data.items():
        household = simulator.get_household(str(data['home']))
        if household is None:
            continue
        
        person = Person(id, data['sex'], data['age'], household)
        
        # Infect person if selected
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
            if simulator.enable_logging and simulator.logger:
                simulator.logger.log_infection_event(person, None, person.household, variant, 0)
                        
        person.iv_threshold = random.choice(iv_threshold)
        iv_threshold.remove(person.iv_threshold)
        
        simulator.add_person(person)
        household.add_member(person)
        
        if simulator.enable_logging and simulator.logger: 
            simulator.logger.log_person_demographics(person, 0)
            
    # Create infection manager
    infectionmgr = InfectionManager(infected_ids=[p.id for p in simulator.people.values() for d in variants if p.states.get(d, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE])

    # --- PHASE 2: Simulation Loop (Interleaved with Streaming) ---
    
    # Initialize JSON Writers
    simdata_writer = None
    patterns_writer = None
    simdata_json = {} if not output_dir else None
    patterns_json = {} if not output_dir else None

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        simdata_writer = IncrementalJSONWriter(os.path.join(output_dir, 'simdata.json.gz'))
        patterns_writer = IncrementalJSONWriter(os.path.join(output_dir, 'patterns.json.gz'))

    variantInfected = {variant: {} for variant in variants}
    
    last_timestep = 0
    iteration = 0
    max_len = simdata['length']
    
    print("=== STARTING INTERLEAVED SIMULATION LOOP ===")

    while last_timestep <= max_len:
        if progress_callback:
            progress_callback(last_timestep, max_len)

        iteration += 1
        current_ts_str = str(last_timestep)
        
        # Ensure we have movement data for this timestep
        # If we don't have it in buffer, keep reading from stream until we find it or stream ends
        while current_ts_str not in patterns_buffer:
            try:
                chunk = next(stream_iterator)
                if "patterns" in chunk:
                    patterns_buffer.update(chunk["patterns"])
            except StopIteration:
                # Stream finished
                break
        
        if last_timestep % SIMULATION["log_interval"] == 0:
            print(f"Processing timestep {last_timestep} (Buffered patterns: {len(patterns_buffer)})")

        # Process movement
        if current_ts_str in patterns_buffer:
            data = patterns_buffer[current_ts_str]
            
            interventions = simulator.get_interventions(current_ts_str)
            
            # Apply interventions per person
            for (id, person_data) in simulator.people.items():
                simulator.people[id].update_state(current_ts_str, variants)
                
                if person_data.iv_threshold <= interventions['mask']:
                    if simulator.enable_logging and simulator.logger and not simulator.people[id].is_masked(): 
                        simulator.logger.log_intervention_effect(simulator.people[id], 'mask', f'complied', current_ts_str)
                    simulator.people[id].set_masked(True)
                
                if person_data.iv_threshold <= interventions['vaccine']:
                    min_doses = SIMULATION["vaccination_options"]["min_doses"]
                    max_doses = SIMULATION["vaccination_options"]["max_doses"]
                    doses = random.randint(min_doses, max_doses)
                    if simulator.enable_logging and simulator.logger and simulator.people[id].get_vaccinated() == VaccinationState.NONE: 
                        simulator.logger.log_intervention_effect(simulator.people[id], 'vaccine', f'received_{doses}_doses', current_ts_str)
                    simulator.people[id].set_vaccinated(VaccinationState(doses))

            if isinstance(data, dict):
                if 'homes' in data:
                    move_people(simulator, data['homes'].items(), True, current_ts_str)
                if 'places' in data:
                    move_people(simulator, data['places'].items(), False, current_ts_str)
            
            # Remove processed pattern to free memory
            del patterns_buffer[current_ts_str]

        # Log demographics/contacts
        if simulator.enable_logging and simulator.logger: 
            for person in simulator.people.values(): 
                simulator.logger.log_person_demographics(person, last_timestep)
            for household in simulator.households.values(): 
                if len(household.population) > 0: 
                    simulator.logger.log_location_state(household, last_timestep)
            for facility in simulator.facilities.values(): 
                if len(facility.population) > 0: 
                    simulator.logger.log_location_state(facility, last_timestep)
                    population = list(facility.population)
                    for i, person1 in enumerate(population): 
                        for person2 in population[i+1:]: 
                            simulator.logger.log_contact_event(person1, person2, facility, last_timestep)

        # Record movement snapshot
        movement_step = {
            "homes": {str(h.id): [p.id for p in h.population] for h in simulator.households.values() if len(h.population) > 0},
            "places": {str(f.id): [p.id for p in f.population] for f in simulator.facilities.values() if len(f.population) > 0}
        }
        
        if patterns_writer:
            patterns_writer.add(current_ts_str, movement_step)
        else:
            patterns_json[current_ts_str] = movement_step

        # Run infection model
        newlyInfected = {}
        try:
            pre_infection_states = {}
            if simulator.enable_logging and simulator.logger: 
                 for person in simulator.people.values(): 
                    pre_infection_states[person.id] = {
                        variant: person.states.get(variant, InfectionState.SUSCEPTIBLE) 
                        for variant in variants
                    }

            infectionmgr.run_model(simulator, last_timestep, variantInfected, newlyInfected, None)
            
            if simulator.enable_logging and simulator.logger: 
                for person in simulator.people.values(): 
                    for variant in variants: 
                        old_state = pre_infection_states[person.id][variant]
                        new_state = person.states.get(variant, InfectionState.SUSCEPTIBLE) 
                        if not isinstance(old_state, InfectionState): old_state = InfectionState.SUSCEPTIBLE
                        if not isinstance(new_state, InfectionState): new_state = InfectionState.SUSCEPTIBLE
                        if not (old_state & InfectionState.INFECTED) and (new_state & InfectionState.INFECTED):
                            simulator.logger.log_infection_event(person, None, person.location, variant, last_timestep)

        except Exception as e:
            print(f"Error during infection modeling at timestep {last_timestep}: {e}")
            newlyInfected = {}

        result_step = {variant: dict(infected) for variant, infected in variantInfected.items()}
        
        if simdata_writer:
            simdata_writer.add(current_ts_str, result_step)
        else:
            simdata_json[current_ts_str] = result_step

        last_timestep += simulator.timestep

    print(f"=== SIMULATION COMPLETE ===")
    
    if simdata_writer: simdata_writer.close()
    if patterns_writer: patterns_writer.close()
    
    if simulator.enable_logging and simulator.logger: 
        print("=== EXPORTING LOGS ===")
        simulator.logger.export_logs_to_csv()
        simulator.logger.generate_summary_report()
        simulator.logger.graphic_analysis()
    
    if output_dir:
        return {
            "simdata": os.path.join(output_dir, 'simdata.json.gz'),
            "patterns": os.path.join(output_dir, 'patterns.json.gz')
        }
    else:
        print(f"Logs exported to {log_dir}/")
        print(f"Generated files:")
        print(f"  - person_logs.csv: {len(simulator.logger.person_logs)} records")
        print(f"  - movement_logs.csv: {len(simulator.logger.movement_logs)} records")
        print(f"  - infection_logs.csv: {len(simulator.logger.infection_logs)} records")
        print(f"  - intervention_logs.csv: {len(simulator.logger.intervention_logs)} records")
        print(f"  - location_logs.csv: {len(simulator.logger.location_logs)} records")
        print(f"  - contact_logs.csv: {len(simulator.logger.contact_logs)} records")
        print(f"  - infection_chains.csv: Chain data for {len(simulator.logger.infection_chains)} infections")
        print(f"  - simulation_summary.txt: Summary report")
        return {"movement": patterns_json, "result": simdata_json}

    
    # Debug final results
    non_empty_results = {k: v for k, v in result.items() if v and any(v.values())}
    non_empty_movement = {k: v for k, v in movement_json.items() if v and (v.get('homes') or v.get('places'))}
    
    print(f"Non-empty results: {len(non_empty_results)}")
    print(f"Non-empty movement: {len(non_empty_movement)}")
    
    if non_empty_movement:
        sample_timestep = list(non_empty_movement.keys())[1]
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