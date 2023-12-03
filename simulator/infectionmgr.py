from .pap import InfectionState, InfectionTimeline
from .infection_model import CAT
from dmp.user_input import get_disease_matrix
import random

class InfectionManager:
    def __init__(self, timestep=15, people=[]):
        self.timestep = timestep
        self.multidisease = True
        self.infected = []
        
        for p in people:
            for v in p.states.values():
                if InfectionState.INFECTED in v:
                    self.infected.append(p)
    
    def run_model(self, num_timesteps=1, file=None, curtime=0, deltaInfected=[], omicronInfected=[]):
        if file == None:
            print(f'infected: {[i.id for i in self.infected]}')
        else:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            file.write(f'delta: {[i.id for i in self.infected if i.states.get("delta") != None]}\n')
            file.write(f'omicron: {[i.id for i in self.infected if i.states.get("omicron") != None]}\n')
            file.write(f"delta count: {len([i.id for i in self.infected if i.states.get('delta') != None])}\n")
            file.write(f"omicron count: {len([i.id for i in self.infected if i.states.get('omicron') != None])}\n")

        # keep an array of number of people infected at each time step
        deltaInfected[:] = [i.id for i in self.infected if i.states.get('delta') != None]
        omicronInfected[:] = [i.id for i in self.infected if i.states.get('omicron') != None]
        
        for i in self.infected:
            i.update_state(curtime)
        
        for i in self.infected:
            # all_p = []
            # all_locations = []
            for p in i.location.population:
                # if p.location not in all_locations:
                #     all_locations.append(p.location)
                # if p not in all_p:
                #     all_p.append(p)

                if i == p or p.states.get("omicron") != None or p.states.get("delta") != None:
                    continue

                new_infections = []

                for disease, state in i.states.items():   
                    # Ignore those who cannot infect others
                    if InfectionState.INFECTIOUS not in state:
                        continue
                            
                    # Ignore those already infected, hospitalized, or recovered
                    if p.states.get(disease) != None and InfectionState.INFECTED in p.states[disease]:
                        continue
                    
                    # Repeat the probability the number of timesteps we passed over the interval
                    # for _ in range(num_timesteps):
                    if (disease == "delta" and CAT(p, True, num_timesteps, 3.237e5) == True) or (disease == "omicron" and CAT(p, True, num_timesteps, 3.2355e5) == True):
                        new_infections.append(disease)
                        p.states[disease] = InfectionState.INFECTED
                        self.infected.append(p)
                        break
                
                for disease in new_infections:
                    # If a person is infected with more than one disease at the same time
                    # and the model does not support being infected with multiple diseases,
                    # this loop is used to remedy that case
                    
                    # self.infected.append(p) # add to list of infected regardless
                    
                    # Set infection state if they were only infected once, or if multidisease is True
                    if len(new_infections) == 1 or self.multidisease == True:
                        p.states[disease] = InfectionState.INFECTED
                        self.create_timeline(p, disease, curtime)
                        
                        if file == None:
                            print(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}')
                        else:
                            file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')
                        continue
                    
                    # TODO: Handle case where a person is infected by multiple diseases at once
                    p.state = InfectionState.INFECTED
                    print(f'{i.id} infected {p.id} @ location {p.location.id}')
            
            # print(len(all_p))


    # When will this person turn from infected to infectious? And later symptomatic? Hospitalized?
    def create_timeline(self, person, disease, curtime):
        #print(str(person.id) + ': ' + str(get_disease_matrix(person)))
        
        person.timeline = {
            disease: {
                InfectionState.INFECTIOUS: InfectionTimeline(curtime, curtime + 4000)
            }
        }