from .pap import Person, Household, Facility, InfectionState, VaccinationState
from .infectionmgr import *
from io import StringIO
import pandas as pd
import json
import os

curdir = os.path.dirname(os.path.abspath(__file__))

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

def run_simulator(matrices_dict, location, interventions):
    with open(curdir + f'/{location}/papdata.json') as file:
        pap = json.load(file)
    
    simulator = DiseaseSimulator(intervention_weights=interventions);
    
    for id, data in pap['homes'].items():
        simulator.add_household(Household(data['cbg'], id))

    for id, data in pap['places'].items():
        simulator.add_facility(Facility(id, data['cbg'], data['label'], data.get('capacity', -1)))

    default_infected = ['160', '43', '47', '4', '36', '9', '14', '19', '27', '22']

    default_matrices_dict = {
        'delta': pd.read_csv(curdir + '/matrices.csv', header=None),
        'omicron': pd.read_csv(curdir + '/matrices2.csv', header=None)
    }

    if not matrices_dict:
        matrices_dict = default_matrices_dict
    else:
        matrices_dict = {i:pd.read_csv(StringIO(j), header=None) for i,j in matrices_dict.items()}

    # Ensure no more variants than infected individuals
    if len(matrices_dict) > len(default_infected):
        raise ValueError("Not enough infected IDs to assign each variant uniquely")

    # Randomly match infected IDs with variants
    random.shuffle(default_infected)
    variant_assignments = dict(zip(default_infected, matrices_dict.keys()))

    for id, data in pap['people'].items():
        household = simulator.get_household(str(data['home']))
        if household is None:
            raise Exception(f"Person {id} is assigned to a house that does not exist ({data['home']})")
        person = Person(id, data['sex'], data['age'], household)
        
        #TODO create list of people and infect each one with variant one by one
        # if id == '160':
        #     person.states['alpha'] = InfectionState.INFECTED | InfectionState.INFECTIOUS
        #     person.timeline = {
        #         'alpha': {
        #             InfectionState.INFECTIOUS: InfectionTimeline(0, 4000)
        #         }
        #     }
        
        # if id == '43':
        #     person.states['omicron'] = InfectionState.INFECTED | InfectionState.INFECTIOUS
        #     person.timeline = {
        #         'omicron': {
        #             InfectionState.INFECTIOUS: InfectionTimeline(0, 4000)
        #         }
        #     }

        # Infect person with a uniquely assigned variant
        if id in variant_assignments:
            variant = variant_assignments[id]
            person.states[variant] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            person.timeline = {
                variant: {
                    InfectionState.INFECTIOUS: InfectionTimeline(0, 4000)  # Customize duration as needed
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
    
    #matrices = (curdir + '/matrices.csv') if matrices is None else StringIO(matrices)
    #infectionmgr = InfectionManager(pd.read_csv(matrices, header=None), people=simulator.people)

        # Instead of a single matrix, prepare a dictionary of matrices

    infectionmgr = InfectionManager(matrices_dict, people=simulator.people)

    
    # Pass the dictionary to InfectionManager
    #infectionmgr = InfectionManager(matrices_dict, people=simulator.people)
    
    # with open(curdir + '/patterns.json') as file:
    #     patterns = json.load(file)

    with open(curdir + f'/{location}/patterns.json') as file:
        patterns = json.load(file)
        
    # with open(curdir + '/patterns_alg.json') as file:
    #     patterns = json.load(file)

    last_timestep = 0
    timestamps = list(patterns.keys())
    
    # result = {}
    # deltaInfected = {}
    # omicronInfected = {}

    # while len(timestamps) > 0:
    #     print(f'Running movement simulator for timestep {last_timestep}')
        
    #     if last_timestep >= int(timestamps[0]):        
    #         data = patterns[timestamps[0]]
            
    #         # Move people to homes for this timestep
    #         move_people(simulator, data['homes'].items(), True)
            
    #         # Move people to facilities for this timestep
    #         move_people(simulator, data['places'].items(), False)
            
    #         timestamps.pop(0)
    #         #print(f'Completed movement for timestep {timestamps.pop(0)}')  
        
    #     infectionmgr.run_model(1, None, last_timestep, deltaInfected, omicronInfected)
    #     result[last_timestep] = {'delta': dict(deltaInfected), 'omicron': dict(omicronInfected) }
    #     last_timestep += simulator.timestep

    # print("Delta Infected:")
    # print(deltaInfected)
    # print("Omicron Infected:")
    # print(omicronInfected)

    # with open('results.json', 'w') as file:
    #     json.dump(result, file, indent=4)

    # return result

    result = {}
    variantInfected = {variant: {} for variant in matrices_dict.keys()}

    while len(timestamps) > 0:
        if last_timestep % 6000 == 0:
            print(f'Running movement simulator for timestep {last_timestep}')
        
        if last_timestep >= int(timestamps[0]):        
            data = patterns[timestamps[0]]
            move_people(simulator, data['homes'].items(), True)
            move_people(simulator, data['places'].items(), False)
            timestamps.pop(0)
        
        infectionmgr.run_model(1, None, last_timestep, variantInfected)
        result[last_timestep] = {variant: dict(infected) for variant, infected in variantInfected.items()}
        last_timestep += simulator.timestep

    # Print results for each variant
    for variant in variantInfected.keys():
        print(f"{variant} Infected:")
        print(variantInfected[variant])

    with open('results.json', 'w') as file:
        json.dump(result, file, indent=4)

    return result
if __name__ == '__main__':
    run_simulator({
        'mask': 0.4,
        'vaccine': 0.2,
        'capacity': 1.0,
        'lockdown': 0.5,
        'selfiso': 0.5
    })