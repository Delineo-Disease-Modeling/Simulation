from .pap import InfectionState, InfectionTimeline
from .infection_model import CAT
from dmp.user_input import process_dataframes
import random

class InfectionManager:
    def __init__(self, matrices_dict, timestep=15, people=[]):
        self.matrices_dict = matrices_dict  # This should now be a dictionary
        self.timestep = timestep
        self.multidisease = True
        self.infected = []
        
        for p in people:
            for v in p.states.values():
                if InfectionState.INFECTED in v:
                    self.infected.append(p)
    
    def run_model(self, num_timesteps=4, file=None, curtime=0, deltaInfected=[], omicronInfected=[]):
        if file != None:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            file.write(f'delta: {[i.id for i in self.infected if i.states.get("delta") != None]}\n')
            file.write(f'omicron: {[i.id for i in self.infected if i.states.get("omicron") != None]}\n')
            file.write(f"delta count: {len([i.id for i in self.infected if i.states.get('delta') != None])}\n")
            file.write(f"omicron count: {len([i.id for i in self.infected if i.states.get('omicron') != None])}\n")

        # keep an array of number of people infected at each time step
        for i in self.infected:
            if i.states.get('delta') != None and i.states['delta'] != InfectionState.SUSCEPTIBLE:
                deltaInfected[i.id] = int(i.states['delta'].value)
            elif i.states.get('omicron') != None and i.states['omicron'] != InfectionState.SUSCEPTIBLE:
                omicronInfected[i.id] = int(i.states['omicron'].value)
        
        for i in self.infected:
            i.update_state(curtime)
        
        for i in self.infected:
            if i.invisible == True:
                continue

            for p in i.location.population:
                if i == p or p.invisible == True:
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
                    if (disease == "delta" and CAT(p, True, num_timesteps, 7e4)) or (disease == "omicron" and CAT(p, True, num_timesteps, 7e4)):
                        new_infections.append(disease)
                        break
                
                for disease in new_infections:
                    # If a person is infected with more than one disease at the same time
                    # and the model does not support being infected with multiple diseases,
                    # this loop is used to remedy that case
                    
                    self.infected.append(p) # add to list of infected regardless
                    
                    # Set infection state if they were only infected once, or if multidisease is True
                    if len(new_infections) == 1 or self.multidisease == True:
                        p.states[disease] = InfectionState.INFECTED
                        self.create_timeline(p, disease, curtime)
                        
                        if file != None:
                            file.write(f'{i.id} infected {p.id} @ location {p.location.id} w/ {disease}\n')
                        continue
                    
                    # TODO: Handle case where a person is infected by multiple diseases at once
                    #p.state = InfectionState.INFECTED
                    print(f'{i.id} infected {p.id} @ location {p.location.id}')
            
            # print(len(all_p))


    # When will this person turn from infected to infectious? And later symptomatic? Hospitalized?
    def create_timeline(self, person, disease, curtime):
        #tl = process_dataframes([self.matrices], {})[0]
        # Select the correct matrix based on the disease variant
        #print(f"Creating timeline with variant: {disease}")  # Indicate which variant's matrix is used
        matrices = self.matrices_dict[disease]
        tl = process_dataframes([matrices], {})[0]
        
        mint = tl[min(tl, key=tl.get)]
        maxt = tl[max(tl, key=tl.get)]
        
        val = {
            disease: {
                # People are marked infected throughout everything
                InfectionState.INFECTED: InfectionTimeline(curtime + mint, curtime + maxt)
            }
        }
        
        str_to_state = {
            'Symptomatic': InfectionState.SYMPTOMATIC,
            'Infectious': InfectionState.INFECTIOUS,
            'Hospitalized': InfectionState.HOSPITALIZED,
            'Recovered': InfectionState.RECOVERED,
            'Removed': InfectionState.REMOVED
        }
        
        for str, state in str_to_state.items():
            if str in tl.keys():
                val[disease][state] = InfectionTimeline(curtime + tl[str], curtime + maxt)
                
        person.timeline = val