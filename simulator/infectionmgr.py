from pap import InfectionState, InfectionTimeline
from infection_model import probability_model
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

    def calculate_host_variables(self, p, Rh = 250, fvh=0.37, fah=0.35):
        
        def set_droplets_num(p, Rh = Rh):
            #droplets per minute if speaking
            if p.age < 3:
                Rh = 0
            # Adjust for children below 10
            elif p.age < 10 or p.age > 60:
                Rh = 100
            return Rh
        
        def set_viral_load(p, fvh):
            # fvh = fraction of viral load in droplets
            Rh = set_droplets_num(p)
            viral_load = Rh * fvh
            return viral_load
        
        def set_droplets_passed_mask(p, droplets=1):
            # droplets passed through mask
            if p.masked == True:
                droplets = droplets * 0.2
            return droplets
        
        def set_frac_aerosol(p, fah=0.35):
            # fraction of droplets that become aerosol (smaller than 10 microns)
            return fah

        return set_viral_load(p, fvh) * set_droplets_passed_mask(p) * set_frac_aerosol(p, fah)


    def calculate_accumulated_droplets(self, p, curtime, fat=0.01):
        acccumulated_droplets = self.calculate_host_variables(self, p)
        for i in self.infected:
            if i != p and i.location == p.location:
                fat = 0.01 # rate of droplets transport near the susceptible

                exposure_duration = 0

                if InfectionState.INFECTIOUS in i.states:
                    exposure_duration += i.states[InfectionState.INFECTIOUS].end - curtime

                acccumulated_droplets = fat * exposure_duration
        
        return acccumulated_droplets


    
    
    def run_model(self, num_timesteps=1, file=None, curtime=0):
        if file == None:
            print(f'infected: {[i.id for i in self.infected]}')
        else:
            file.write(f'====== TIMESTEP {curtime} ======\n')
            file.write(f'delta: {[i.id for i in self.infected if i.states.get("delta") != None]}\n')
            file.write(f'omicron: {[i.id for i in self.infected if i.states.get("omicron") != None]}\n')
        
        for i in self.infected:
            i.update_state(curtime)
        
        for i in self.infected:
            for p in i.location.population:
                if i == p:
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
                    for _ in range(num_timesteps):
                        if random.random() < probability_model(i, p):
                            new_infections.append(disease)
                            break # We can't re-infect someone
                
                for disease in new_infections:
                    # If a person is infected with more than one disease at the same time
                    # and the model does not support being infected with multiple diseases,
                    # this loop is used to remedy that case
                    
                    self.infected.append(p) # add to list of infected regardless
                    
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

        
    # When will this person turn from infected to infectious? And later symptomatic? Hospitalized?
    def create_timeline(self, person, disease, curtime):
        person.timeline = {
            disease: {
                InfectionState.INFECTIOUS: InfectionTimeline(curtime, curtime + 4000)
            }
        }