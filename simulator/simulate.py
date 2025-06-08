from .pap import Person, Household, Facility, InfectionState, VaccinationState
from .infectionmgr import *
from .config import SIMULATION, INFECTION_MODEL
from io import StringIO
import pandas as pd
import json
import os
from .data_interface import stream_data
import requests

import random

curdir = os.path.dirname(os.path.abspath(__file__))

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
        self.people.append(person)
        
    def get_person(self, id):
        #return next((p for p in self.people if p.id == id), None)
        return self.people.get(id) 

    def add_household(self, household):
        #self.households.append(household)
        self.households[household.id] = household

    
    def get_household(self, id):
        #return next((h for h in self.households if h.id == id), None)
        return self.households.get(id)


    def add_facility(self, facility):
        #self.facilities.append(facility)
        self.facilities[facility.id] = facility

    
    def get_facility(self, id):
        #return next((f for f in self.facilities if f.id == id), None)
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
    
    # Merge provided interventions with defaults
    default_interventions = SIMULATION["default_interventions"].copy()
    if interventions:
        default_interventions.update(interventions)
    interventions = default_interventions
    
    # Set random seed if user specifies
    if not interventions['randseed']:
        random.seed(0)
    
    # Load people and places using the new streaming method
    data_stream = stream_data()
    
    
    # Extract initial data
    
    people_data = data_stream.get("people", {})
    homes_data = people_data.get("homes", {})
    places_data = people_data.get("places", {})
    

    """ patterns = data.get("data", {}).get("patterns", {})
    pap = data.get("data", {}).get("papdata", {})
    # people_data = pap['people']
    people_data = pap.get("people", {})

    homes_data = pap.get("homes", {})
    #places_data = pap['places']
    places_data = pap.get("places", {}) """
    
    simulator = DiseaseSimulator(intervention_weights=interventions)
    
    for id, data in homes_data.items():
        simulator.add_household(Household(data['cbg'], id))

    for id, data in places_data.items():
        simulator.add_facility(Facility(id, data['cbg'], data['label'], data.get('capacity', -1)))

    # Get default infected IDs and variants from config
    default_infected = SIMULATION["default_infected_ids"]
    variants = SIMULATION["variants"]
    
    # Ensure no more variants than infected individuals
    if len(variants) > len(default_infected):
        raise ValueError("Not enough infected IDs to assign each variant uniquely")

    # Randomly match infected IDs with variants
    random.shuffle(default_infected)
    variant_assignments = {id: variant for id, variant in zip(default_infected, variants)}

    for id, data in people_data.items():
        # if id == "181" or id == "182" or id == "193" or id == "199" or id == "209" or id == "229" or id == "232" or id == "242" or id == "255" or id == "265" or id == "272" or id == "285" or id == "295" or id == "304" or id == "309" or id == "314" or id == "329": 
            # Skip these people as they are not in the simulation
            # continue
        household = simulator.get_household(str(data['home']))
        if household is None:
            raise Exception(f"Person {id} is assigned to a house that does not exist ({data['home']})")
        person = Person(id, data['sex'], data['age'], household)
        
        # Infect person with a uniquely assigned variant
        if str(id) in variant_assignments:
            variant = variant_assignments[str(id)]
            person.states[variant] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            initial_duration = INFECTION_MODEL["initial_timeline"]["duration"]
            person.timeline = {
                variant: {
                    InfectionState.INFECTED: InfectionTimeline(0, initial_duration),
                    InfectionState.INFECTIOUS: InfectionTimeline(0, initial_duration)  # Initial timeline until DMP updates it
                }
            }
        
        # Assign masked and vaccination states
        if random.random() < simulator.iv_weights['mask']:
            person.set_masked(True)
        
        # Maryland: 90% at least one dose, 78.3% fully vaccinated
        if random.random() < simulator.iv_weights['vaccine']:
            min_doses = SIMULATION["vaccination_options"]["min_doses"]
            max_doses = SIMULATION["vaccination_options"]["max_doses"]
            person.set_vaccinated(VaccinationState(random.randint(min_doses, max_doses)))
        
        simulator.add_person(person)
        household.add_member(person)
    
    # Create infection manager with DMP API
    infectionmgr = InfectionManager({}, people=simulator.people)
    
    #with open(curdir + f'/{location}/patterns.json') as file:
        #patterns = json.load(file)
        
    last_timestep = 0
    timestamps = list(patterns.keys())
    
    result = {}
    variantInfected = {variant: {} for variant in variants}
    
    movement_json = {}
    infectivity_json = {}

    while len(timestamps) > 0:
        if (last_timestep > max_length):
            break
        
        log_interval = SIMULATION["log_interval"]
        if last_timestep % log_interval == 0:
            print(f'Running movement simulator for timestep {last_timestep}')
        
        if last_timestep >= int(timestamps[0]):        
            data = patterns[timestamps[0]]
            move_people(simulator, data['homes'].items(), True)
            move_people(simulator, data['places'].items(), False)
            timestamps.pop(0)
        
        movement_json[last_timestep] = {  \
            "homes": { str(h.id):[p.id for p in h.population] for h in simulator.households if len(h.population) > 0 }, 
            "places": { str(f.id):[p.id for p in f.population] for f in simulator.facilities if len(f.population) > 0 } }
        
        newlyInfected = {}
        
        try:
            infectionmgr.run_model(1, None, last_timestep, variantInfected, newlyInfected)
        except Exception as e:
            print(f"Error during infection modeling at timestep {last_timestep}: {e}")
            print("Continuing to next timestep...")
            newlyInfected = {}
        
        infectivity_json[last_timestep] = {i:j for i,j in newlyInfected.items()}
        
        result[last_timestep] = {variant: dict(infected) for variant, infected in variantInfected.items()}
        last_timestep += simulator.timestep

    if save_file:
        #Print results for each variant
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
        return {
            'result': {i:j for i,j in result.items() if i != 0},
            'movement': {i:j for i,j in movement_json.items() if i != 0}
        }

    return result
