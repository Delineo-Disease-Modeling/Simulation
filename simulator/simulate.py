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
from collections import defaultdict, deque
import csv 


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
    """Optimized logging system for simulation"""

    def __init__ (self, log_dir = "simulation_logs", enable_file_logging = True, buffer_size = 1000): 
        self.log_dir = log_dir 
        self.enable_file_logging = enable_file_logging
        self.buffer_size = buffer_size

        if self.enable_file_logging: 
            os.makedirs(log_dir, exist_ok=True)

        # Use deques for better append performance
        self.person_logs = deque(maxlen=buffer_size * 10)
        self.movement_logs = deque(maxlen=buffer_size * 5)
        self.infection_logs = deque(maxlen=buffer_size * 2)
        self.intervention_logs = deque(maxlen=buffer_size * 3)
        self.location_logs = deque(maxlen=buffer_size * 5)
        self.contact_logs = deque(maxlen=buffer_size * 20)
        self.exposure_logs = deque(maxlen=buffer_size * 5)

        # Cache frequently accessed data
        self.person_states = {}
        self.location_population = defaultdict(list)
        self.infection_chains = {}
        
        # Batch processing flags
        self._batch_person_logs = []
        self._batch_movement_logs = []
        self._batch_size = 100

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

    def _get_infection_status_cached(self, person, variants):
        """Cache infection status calculations"""
        person_id = person.id
        if person_id not in self.person_states:
            self.person_states[person_id] = {}
        
        cache = self.person_states[person_id]
        
        infection_status = {}
        infectious_variants = []
        symptomatic_variants = []

        for variant in variants: 
            if variant not in cache:
                state = person.states.get(variant, InfectionState.SUSCEPTIBLE)
                cache[variant] = {
                    'infected': bool(state & InfectionState.INFECTED),
                    'infectious': bool(state & InfectionState.INFECTIOUS),
                    'symptomatic': bool(state & InfectionState.SYMPTOMATIC), 
                    'recovered': bool(state & InfectionState.RECOVERED), 
                    'deceased': bool(state & InfectionState.REMOVED)
                }
            
            infection_status[variant] = cache[variant]
            
            if cache[variant]['infectious']:
                infectious_variants.append(variant)
            if cache[variant]['symptomatic']:
                symptomatic_variants.append(variant)
                
        return infection_status, infectious_variants, symptomatic_variants

    def log_person_demographics(self, person, timestep, variants=None):
        """Optimized person demographics logging with reduced frequency"""
        # Only log every 5th timestep to reduce overhead
        if timestep % 5 != 0:
            return
            
        if variants is None:
            variants = person.states.keys()
            
        # Use cached values where possible
        person_id = person.id
        if person_id in self.person_states and timestep - self.person_states[person_id].get('last_logged', 0) < 5:
            return  # Skip if recently logged
            
        vax_status = person.vaccination_state if person.vaccination_state else "Unvaccinated"        
        vax_doses = 0
        if hasattr(person, 'vaccination_state') and person.vaccination_state: 
            vax_doses = person.vaccination_state.value if hasattr(person.vaccination_state, 'value') else 0
            vax_status = f"Vaccinated ({vax_doses} doses)"

        infection_status, infectious_variants, symptomatic_variants = self._get_infection_status_cached(person, variants)
            
        location_id = person.location.id if person.location else None 
        location_type = "household" if isinstance(person.location, Household) else "facility" if isinstance(person.location, Facility) else "unknown"
        location_capacity = getattr(person.location, 'capacity', -1) if person.location else -1
        location_population = len(person.location.population) if person.location else 0 

        person_log = {
            'timestep': timestep, 
            'person_id': person_id,
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
        
        # Update last logged timestamp
        if person_id not in self.person_states:
            self.person_states[person_id] = {}
        self.person_states[person_id]['last_logged'] = timestep

    def log_movement(self, person, from_location, to_location, timestep, reason = "normal"):
        """Optimized movement logging"""
        # Cache infectious/symptomatic status
        is_infectious = any(person.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person.states.keys())
        is_symptomatic = any(person.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.SYMPTOMATIC for v in person.states.keys())
        
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
            'is_infectious': is_infectious,
            'is_symptomatic': is_symptomatic,
            'is_masked': getattr(person, 'masked', False),
            'from_occupancy': len(from_location.population) if from_location else 0,
            'to_occupancy': len(to_location.population) if to_location else 0, 
            'to_capacity': getattr(to_location, 'capacity', -1) if to_location else -1
        }

        self.movement_logs.append(movement_log)

    def log_infection_event(self, infected_person, infector_person, location, variant, timestep): 
        """Optimized infection event logging"""
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
        """Optimized intervention effect logging"""
        # Cache infectious/symptomatic status
        person_infectious = any(person.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person.states.keys())
        person_symptomatic = any(person.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.SYMPTOMATIC for v in person.states.keys())
        
        intervention_log = {
            'timestep': timestep,
            'person_id': person.id,
            'intervention_type': intervention_type, # for example, lockdown, capacity limit, self isolation, mask, vaccine 
            'effect': effect,
            'person_age': person.age, 
            'person_sex': person.sex, 
            'person_infectious': person_infectious,
            'person_symptomatic': person_symptomatic,
            'location_id': location.id if location else None,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'location_occupancy': len(location.population) if location else 0,
            'location_capacity': getattr(location, 'capacity', -1) if location else -1
        }

        self.intervention_logs.append(intervention_log)

    def log_location_state(self, location, timestep):
        """Optimized location state logging"""
        population = location.population if hasattr(location, 'population') else []
        if not population:
            return
            
        # Batch calculate statistics
        infectious_count = 0
        symptomatic_count = 0
        masked_count = 0
        vaccinated_count = 0
        ages = []
        male_count = 0
        female_count = 0
        
        for p in population:
            # Check infectious/symptomatic status once
            is_infectious = any(p.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in p.states.keys())
            is_symptomatic = any(p.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.SYMPTOMATIC for v in p.states.keys())
            
            if is_infectious:
                infectious_count += 1
            if is_symptomatic:
                symptomatic_count += 1
            if getattr(p, 'masked', False):
                masked_count += 1
            if hasattr(p, 'vaccination_state') and p.vaccination_state and p.vaccination_state.value > 0:
                vaccinated_count += 1
                
            ages.append(p.age)
            if p.sex == '0':
                male_count += 1
            else:
                female_count += 1

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
            'male_count': male_count,
            'female_count': female_count
        }

        self.location_logs.append(location_log)

    def log_contact_event(self, person1, person2, location, timestep, contact_duration = 1):
        """Optimized contact event logging"""
        # Cache infectious status
        p1_infectious = any(person1.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person1.states.keys())
        p2_infectious = any(person2.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person2.states.keys())
        p1_masked = getattr(person1, 'masked', False)
        p2_masked = getattr(person2, 'masked', False)
        
        contact_log = {
            'timestep': timestep,
            'person1_id': person1.id,
            'person2_id': person2.id,
            'location_id': location.id if location else None,
            'location_type': "household" if isinstance(location, Household) else "facility" if isinstance(location, Facility) else None,
            'contact_duration': contact_duration,  # in minutes
            'person1_infectious': p1_infectious,
            'person2_infectious': p2_infectious,
            'person1_masked': p1_masked,
            'person2_masked': p2_masked,
            'both_masked': p1_masked and p2_masked,
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
        infectious_count = sum(1 for p in population if any(p.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in p.states.keys()))

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
        p1_infection = any(person1.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person1.states.keys())
        p2_infection = any(person2.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.INFECTIOUS for v in person2.states.keys())

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
        """Optimized CSV export using batch processing"""
        if not self.enable_file_logging: 
            return 
        
        # Convert deques to lists only when exporting
        if self.person_logs: 
            df = pd.DataFrame(list(self.person_logs))
            df.to_csv(f'{self.log_dir}/person_logs.csv', index=False)

        if self.movement_logs:
            df = pd.DataFrame(list(self.movement_logs))
            df.to_csv(f'{self.log_dir}/movement_logs.csv', index=False)
        
        if self.infection_logs:
            df = pd.DataFrame(list(self.infection_logs))
            df.to_csv(f'{self.log_dir}/infection_logs.csv', index=False)

        if self.intervention_logs:
            df = pd.DataFrame(list(self.intervention_logs))
            df.to_csv(f'{self.log_dir}/intervention_logs.csv', index=False)

        if self.location_logs:
            df = pd.DataFrame(list(self.location_logs))
            df.to_csv(f'{self.log_dir}/location_logs.csv', index=False)
        
        if self.contact_logs:
            df = pd.DataFrame(list(self.contact_logs))
            df.to_csv(f'{self.log_dir}/contact_logs.csv', index=False)

        if self.infection_chains: 
            chains_df = pd.DataFrame.from_dict(self.infection_chains, orient='index')
            chains_df.reset_index(inplace=True)
            chains_df.rename(columns={'index': 'infected_person_id'}, inplace=True)
            chains_df.to_csv(f'{self.log_dir}/infection_chains.csv', index=False)


    def generate_summary_report(self):
        """Optimized summary report generation"""
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
            # Use defaultdict for faster counting
            intervention_counts = defaultdict(int)
            for log in self.intervention_logs:
                intervention_counts[log['intervention_type']] += 1
            
            report.append("\nIntervention Events:") 
            for intervention, count in intervention_counts.items():
                report.append(f"  {intervention}: {count} events")

        with open(f'{self.log_dir}/summary_report.txt', 'w') as f:
            f.write("\n".join(report))
            
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
    """Optimized people movement function"""
    for id, people in items:
        place = simulator.get_household(str(id)) if is_household else simulator.get_facility(str(id))
        if place is None:
            raise Exception(f"Place {id} was not found in the simulator data ({is_household})")

        # Cache capacity and intervention weights
        capacity_weight = simulator.iv_weights.get('capacity', 1.0)
        lockdown_weight = simulator.iv_weights.get('lockdown', 0.0)
        selfiso_weight = simulator.iv_weights.get('selfiso', 0.0)
        
        for person_id in people:
            person = simulator.get_person(person_id)
            if person is None:
                continue

            original_location = person.location 

            # Optimized intervention checks
            if not is_household:
                at_capacity = (place.capacity != -1 and 
                             place.total_count >= place.capacity * capacity_weight)
                hit_lockdown = (place != person.location and 
                              random.random() < lockdown_weight)
                
                # Cache symptomatic status check
                is_symptomatic = any(person.states.get(v, InfectionState.SUSCEPTIBLE) & InfectionState.SYMPTOMATIC 
                                   for v in person.states.keys())
                self_iso = is_symptomatic and random.random() < selfiso_weight
                
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

def run_simulator(location=None, max_length=None, interventions=None, save_file=False, enable_logging = True, log_dir = "simulation_logs"):
    """Optimized main simulation runner"""
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
    
    simulator = DiseaseSimulator(intervention_weights=interventions, enable_logging=enable_logging, log_dir=log_dir)
    
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

    # Cache intervention probabilities for faster access
    mask_prob = simulator.iv_weights.get('mask', 0.0)
    vaccine_prob = simulator.iv_weights.get('vaccine', 0.0)
    min_doses = SIMULATION["vaccination_options"]["min_doses"]
    max_doses = SIMULATION["vaccination_options"]["max_doses"]

    # Build people with optimized processing
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
            # logging initial infections at the beginning of the simulation
            if simulator.enable_logging and simulator.logger:
                simulator.logger.log_infection_event(person, None, person.household, variant, 0)

        # Assign masked state (optimized random check)
        if random.random() < mask_prob:
            person.set_masked(True)
            print(f"Person {person.id} assigned mask")
            if simulator.enable_logging and simulator.logger: 
                simulator.logger.log_intervention_effect(person, 'mask', 'complied', 0)

        # Assigning vaccination state (optimized)
        if random.random() < vaccine_prob:
            doses = random.randint(min_doses, max_doses)
            person.set_vaccinated(VaccinationState(doses))
            if simulator.enable_logging and simulator.logger: 
                simulator.logger.log_intervention_effect(person, 'vaccine', f'received_{doses}_doses', 0)

        simulator.add_person(person)
        household.add_member(person)
        people_added += 1

        if simulator.enable_logging and simulator.logger: 
            simulator.logger.log_person_demographics(person, 0, variants)
    
    print(f"Added {people_added} people")
    
    # Create infection manager with DMP API
    infectionmgr = InfectionManager({}, people=simulator.people.values())
    
    # Prepare simulation with optimized timestamp processing
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

    # Pre-cache log interval for performance
    log_interval = SIMULATION["log_interval"]

    # Main simulation loop with optimizations
    print("=== STARTING SIMULATION LOOP ===")
    iteration = 0
    while len(timestamps) > 0:
        iteration += 1
        
        if (last_timestep > max_length):
            print(f"Breaking: timestep {last_timestep} > max_length {max_length}")
            break
        
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
                        move_people(simulator, data['homes'].items(), True, current_timestamp)
                    if 'places' in data:
                        print(f"  Moving people to places: {len(data['places'])} locations")
                        move_people(simulator, data['places'].items(), False, current_timestamp)
                else:
                    print(f"  ERROR: Pattern data is not a dict: {data}")
            else:
                print(f"  ERROR: Timestamp {current_timestamp} not found in patterns")
            
            timestamps.pop(0)

            # Optimized logging with reduced frequency and batch processing
            if simulator.enable_logging and simulator.logger and last_timestep % 5 == 0: 
                # Log person demographics with variants passed for caching (reduced frequency)
                for person in simulator.people.values(): 
                    simulator.logger.log_person_demographics(person, last_timestep, variants)
                
                # Log only locations with population (performance optimization)
                for household in simulator.households.values(): 
                    if len(household.population) > 0: 
                        simulator.logger.log_location_state(household, last_timestep)

                for facility in simulator.facilities.values(): 
                    if len(facility.population) > 0: 
                        simulator.logger.log_location_state(facility, last_timestep)

                        # Optimized contact logging - only for facilities with multiple people and reduced frequency
                        population = list(facility.population)
                        if len(population) > 1 and len(population) < 50:  # Skip very large facilities
                            # Sample contacts instead of logging all pairs
                            max_contacts = min(20, len(population) * (len(population) - 1) // 2)
                            contact_pairs = [(population[i], population[j]) 
                                           for i in range(len(population)) 
                                           for j in range(i+1, len(population))]
                            sampled_pairs = random.sample(contact_pairs, min(max_contacts, len(contact_pairs)))
                            
                            for person1, person2 in sampled_pairs:
                                simulator.logger.log_contact_event(person1, person2, facility, last_timestep)
        
        # Optimized movement recording with dict comprehensions
        homes_with_people = {str(h.id): [p.id for p in h.population] 
                           for h in simulator.households.values() if h.population}
        places_with_people = {str(f.id): [p.id for p in f.population] 
                            for f in simulator.facilities.values() if f.population}
        
        movement_json[last_timestep] = {
            "homes": homes_with_people,
            "places": places_with_people
        }
        
        # Track movement data
        if homes_with_people or places_with_people:
            print(f"  Timestep {last_timestep}: {len(homes_with_people)} homes, {len(places_with_people)} places with people")
        
        # Run infection model with optimized error handling
        newlyInfected = {}
        try:
            # Pre-cache infection states for logging efficiency (only when needed)
            pre_infection_states = {}
            if simulator.enable_logging and simulator.logger and last_timestep % 5 == 0: 
                pre_infection_states = {
                    person.id: {
                        variant: person.states.get(variant, InfectionState.SUSCEPTIBLE) 
                        for variant in variants
                    }
                    for person in simulator.people.values()
                }
                
            infectionmgr.run_model(1, None, last_timestep, variantInfected, newlyInfected)
            
            # Process any pending timeline requests at the end of each timestep
            if hasattr(infectionmgr, '_pending_timeline_requests') and infectionmgr._pending_timeline_requests:
                infectionmgr._process_timeline_batch()

            # Optimized infection logging
            if simulator.enable_logging and simulator.logger and pre_infection_states: 
                for person in simulator.people.values(): 
                    person_id = person.id
                    for variant in variants: 
                        old_state = pre_infection_states[person_id][variant]
                        new_state = person.states.get(variant, InfectionState.SUSCEPTIBLE)
                        
                        # Ensure both states are InfectionState enums
                        if not isinstance(old_state, InfectionState):
                            old_state = InfectionState.SUSCEPTIBLE
                        if not isinstance(new_state, InfectionState):
                            new_state = InfectionState.SUSCEPTIBLE
                            
                        # Check for new infection
                        if not (old_state & InfectionState.INFECTED) and (new_state & InfectionState.INFECTED):
                            # Find infector efficiently
                            infector = None
                            location = person.location
                            
                            if location and hasattr(location, 'population'):
                                for potential_infector in location.population:
                                    if potential_infector == person:
                                        continue
                                    infector_state = potential_infector.states.get(variant, InfectionState.SUSCEPTIBLE)
                                    if not isinstance(infector_state, InfectionState):
                                        infector_state = InfectionState.SUSCEPTIBLE
                                        
                                    if infector_state & InfectionState.INFECTIOUS:
                                        infector = potential_infector
                                        break
                            simulator.logger.log_infection_event(person, infector, location, variant, last_timestep)
                        
        except Exception as e:
            print(f"Error during infection modeling at timestep {last_timestep}: {e}")
            newlyInfected = {}
        
        # Optimized result recording
        infectivity_json[last_timestep] = dict(newlyInfected)
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

    # Optimized logging export
    if simulator.enable_logging and simulator.logger: 
        print("=== EXPORTING LOGS ===")
        simulator.logger.export_logs_to_csv()
        simulator.logger.generate_summary_report()
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

    # Optimized final result processing
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
        # Optimized final result filtering
        final_result = {
            'result': {i: j for i, j in result.items() if i != 0},
            'movement': {i: j for i, j in movement_json.items() if i != 0}
        }
        print(f"Returning result with {len(final_result['result'])} result timesteps and {len(final_result['movement'])} movement timesteps")
        return final_result

    return result