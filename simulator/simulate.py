from pap import Person, Household, Facility, InfectionState
from infectionmgr import *
import json

# TODO: A way for users to call for interventions in the population
#   e.g: mask wearing, limit capacity, lockdowns/shutdowns, vaccinations
class InterventionManager:
    pass

# Putting it all together, simulates each timestep
# We can choose to only simulate areas with infected people
class DiseaseSimulator:
    def __init__(self, timestep=60):
        self.timestep = timestep        # in minutes
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
            
            #print(f'person {person_id}: {person.location.id} -> {place.id} ({is_household})')
            
            person.location.remove_member(person_id)
            place.add_member(person)
            person.location = place

        
if __name__ == '__main__':
    with open('papdata.json') as file:
        pap = json.load(file)
    
    simulator = DiseaseSimulator()
    
    for id, data in pap['homes'].items():
        simulator.add_household(Household(data['cbg'], id))

    for id, data in pap['places'].items():
        facility = simulator.add_facility(Facility(id, data['cbg'], data['label']))

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
        
        simulator.add_person(person)
        household.add_member(person)
    
    # Check to see that all people are accounted for in each house
    #for house in simulator.households:
    #    print(house.id, house.total_count)
    
    infectionmgr = InfectionManager(people=simulator.people)
    
    with open('patterns.json') as file:
        patterns = json.load(file)

    last_timestep = 0
    timestamps = list(patterns.keys())
    
    with open('simulator_results.txt', 'w') as file:
        while len(timestamps) > 0:
            #print(f'Running movement simulator for timestep {last_timestep}')
            
            if last_timestep >= int(timestamps[0]):        
                data = patterns[timestamps[0]]
                
                # Move people to homes for this timestep
                move_people(simulator, data['homes'].items(), True)
                
                # Move people to facilities for this timestep
                move_people(simulator, data['places'].items(), False)
                
                infectionmgr.run_model(file, last_timestep)
                
                timestamps.pop(0)
                #print(f'Completed movement for timestep {timestamps.pop(0)}')  
                        
            last_timestep += simulator.timestep
      