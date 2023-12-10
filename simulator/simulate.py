from .pap import Person, Household, Facility, InfectionState, VaccinationState
from .infectionmgr import *
from io import StringIO
import pandas as pd
import json
import os

curdir = os.path.dirname(os.path.abspath(__file__))

# TODO: A way for users to call for interventions in the population
#   e.g: mask wearing, limit capacity, lockdowns/shutdowns, vaccinations
class InterventionManager:
    pass

# Putting it all together, simulates each timestep
# We can choose to only simulate areas with infected people
class DiseaseSimulator:
    def __init__(self, timestep=60, intervention_weights={}):
        self.timestep = timestep        # in minutes
        self.iv_weights = intervention_weights
        self.people = []
        self.households = []            # list of all houses
        self.facilities = []
    
    def add_person(self, person):
        self.people.append(person)
        
    def get_person(self, id):
        return next((p for p in self.people if p.id == id), None)
    
    def add_household(self, household):
        self.households.append(household)
    
    def get_household(self, id):
        return next((h for h in self.households if h.id == id), None)
    
    def add_facility(self, facility):
        self.facilities.append(facility)
    
    def get_facility(self, id):
        return next((f for f in self.facilities if f.id == id), None)

def move_people(simulator, items, is_household):
    for id, people in items:
        place = simulator.get_household(id) if is_household else simulator.get_facility(id)
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
                if at_capacity or hit_lockdown:
                    person.location.remove_member(person_id)
                    person.household.add_member(person)
                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            person.location = place

def run_simulator(matrices, interventions):
    with open(curdir + '/papdata.json') as file:
        pap = json.load(file)
    
    simulator = DiseaseSimulator(intervention_weights=interventions);
    
    for id, data in pap['homes'].items():
        simulator.add_household(Household(data['cbg'], id))

    for id, data in pap['places'].items():
        simulator.add_facility(Facility(id, data['cbg'], data['label'], data.get('capacity', -1)))

    for id, data in pap['people'].items():
        household = simulator.get_household(data['home'])
        if household is None:
            raise Exception(f"Person {id} is assigned to a house that does not exist ({data['home']})")
        person = Person(id, data['sex'], data['age'], household)
        
        if id == '160':
            person.states['delta'] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            person.timeline = {
                'delta': {
                    InfectionState.INFECTIOUS: InfectionTimeline(0, 4000)
                }
            }
        
        if id == '43':
            person.states['omicron'] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            person.timeline = {
                'omicron': {
                    InfectionState.INFECTIOUS: InfectionTimeline(0, 4000)
                }
            }
        
        # Assign masked and vaccination states
        # TODO: Meet with Wanli for these values
        if random.random() < simulator.iv_weights['mask']:
            person.set_masked(True)
        
        # Maryland: 90% at least one dose, 78.3% fully vaccinated
        if random.random() < simulator.iv_weights['vaccine']:
            person.set_vaccinated(VaccinationState(random.randint(1, 2)))
        
        simulator.add_person(person)
        household.add_member(person)
            
    
    # Check to see that all people are accounted for in each house
    #for house in simulator.households:
    #    print(house.id, house.total_count)
    
    matrices = (curdir + '/matrices.csv') if matrices is None else StringIO(matrices)
    infectionmgr = InfectionManager(pd.read_csv(matrices, header=None), people=simulator.people)
    
    # with open(curdir + '/patterns.json') as file:
    #     patterns = json.load(file)

    with open(curdir + '/pattern_simple.json') as file:
        patterns = json.load(file)

    last_timestep = 0
    timestamps = list(patterns.keys())
    
    result = {}
    deltaInfected = []
    omicronInfected = []

    while len(timestamps) > 0:
        print(f'Running movement simulator for timestep {last_timestep}')
        
        if last_timestep >= int(timestamps[0]):        
            data = patterns[timestamps[0]]
            
            # Move people to homes for this timestep
            move_people(simulator, data['homes'].items(), True)
            
            # Move people to facilities for this timestep
            move_people(simulator, data['places'].items(), False)
            
            timestamps.pop(0)
            #print(f'Completed movement for timestep {timestamps.pop(0)}')  
        
        infectionmgr.run_model(1, None, last_timestep, deltaInfected, omicronInfected)
        result[last_timestep] = {'delta': list(deltaInfected), 'omicron': list(omicronInfected) }
        last_timestep += simulator.timestep

    print("Delta Infected:")
    print(deltaInfected)
    print("Omicron Infected:")
    print(omicronInfected)

    with open('results.json', 'w') as file:
        json.dump(result, file, indent=4)

    return result

if __name__ == '__main__':
    run_simulator({
        'mask': 0.4,
        'vaccine': 0.2,
        'capacity': 1.0,
        'lockdown': 0.5
    })