from pap import InfectionState, InfectionTimeline
from infection_model import CAT
import random

class InfectionManager:
    def __init__(self, timestep=15, people=[]):
        self.timestep = timestep
        self.multidisease = False
        self.infected = []
        
        for p in people:
            for v in p.states.values():
                if InfectionState.INFECTED in v:
                    self.infected.append(p)
    
    def run_model(self, num_timesteps=1, file=None, curtime=0):
        if file == None:
            print(f'infected: {[i.id for i in self.infected]}')
        else:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            file.write(f'delta: {[i.id for i in self.infected if i.states.get("delta") != None]}\n')
            file.write(f'omicron: {[i.id for i in self.infected if i.states.get("omicron") != None]}\n')
        
        for i in self.infected:
            i.update_state(curtime)
            
            stay = False
            for state in i.states.values():
                if InfectionState.INFECTED in state:
                    stay = True
                    break
            
            if stay == False:
                self.infected.remove(i)
        
        for i in self.infected:
            for p in i.location.population:
                if i == p or p.states.get("omicron") != None or p.states.get("delta") != None:
                    continue

                new_infections = []

                for disease, state in i.states.items():   
                    # Ignore those who cannot infect others
                    if InfectionState.INFECTIOUS not in state:
                        continue
                            
                    # Ignore those already infected, hospitalized, or recovered
                    if p.states.get(disease) != None:
                        if InfectionState.INFECTED in p.states[disease]:
                            continue
                    
                    # Repeat the probability the number of timesteps we passed over the interval
                    for _ in range(num_timesteps):
                        if random.random() < probability_model(i, p):
                            new_infections.append(disease)
                            break # We can't re-infect someone
                
                for disease in new_infections:
                    # If a person is infected with more than one disease at the same time
                    # and the model does not support being infected with multiple diseases,
                    # this loop is used to remedy that case
                    
                    self.infected.append(p) # add to list of infected regardless
                    
                    # Set infection state if they were only infected once
                    if len(new_infections) == 1:
                        p.states[disease] = InfectionState.INFECTED
                        self.create_timeline(p, disease, curtime)
                        continue
                    
                    if self.multidisease == False:
                        continue
                    
                    # TODO: Handle case where a person is infected by multiple diseases at once
                    p.state = InfectionState.INFECTED
        
        
    # When will this person turn from infected to infectious? And later symptomatic? Hospitalized?
    def create_timeline(self, person, disease, curtime):
        person.timeline = {
            disease: {
                InfectionState.INFECTIOUS: InfectionTimeline(curtime, curtime + 4000)
            }
        }