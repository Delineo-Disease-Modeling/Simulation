from .pap import InfectionState, InfectionTimeline
from .infection_model import CAT
from dmp.user_input import process_dataframes
import random

class InfectionManager:
    def __init__(self, matrices, timestep=15, people=[]):
        self.matrices = matrices
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
                    if (disease == "delta" and CAT(p, True, num_timesteps, 100)) or (disease == "omicron" and CAT(p, True, num_timesteps, 100)):
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
        tl = process_dataframes(self.matrices, {
            "Age": person.age,
            "Is_Vaccinated": "Yes" if person.get_vaccinated() != None else "No"
        })
        
        mint = tl[min(tl, key=tl.get)]
        maxt = tl[max(tl, key=tl.get)]
        
        val = {
            disease: {
                # People are marked infected throughout everything
                InfectionState.INFECTED: InfectionTimeline(mint, maxt)
            }
        }
        
        if 'Symptomatic' in tl.keys():
            val[disease][InfectionState.SYMPTOMATIC] = InfectionTimeline(tl['Symptomatic'], maxt)
        
        if 'Infectious' in tl.keys():
            val[disease][InfectionState.INFECTIOUS] = InfectionTimeline(tl['Infectious'], maxt)
            
        if 'Hospitalized' in tl.keys():
            val[disease][InfectionState.HOSPITALIZED] = InfectionTimeline(tl['Hospitalized'], maxt)

        if 'Recovered' in tl.keys():
            val[disease][InfectionState.RECOVERED] = InfectionTimeline(tl['Recovered'], maxt)
        
        if 'Removed' in tl.keys():
            val[disease][InfectionState.REMOVED] = InfectionTimeline(tl['Removed'], maxt)

        person.timeline = val