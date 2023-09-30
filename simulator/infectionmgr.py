from pap import InfectionState, InfectionTimeline
from infection_model import probability_model
import random
import math

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
        
        def set_droplets_num(p, Rh):
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
                filter_efficiency = random.uniform(0.3, 0.6)
                droplets = droplets * filter_efficiency
            return droplets
        
        def set_frac_aerosol(p, fah):
            # fraction of droplets that become aerosol (smaller than 10 microns)
            return fah

        return set_viral_load(p, fvh) * set_droplets_passed_mask(p) * set_frac_aerosol(p, fah)
    
    def calculate_environment_variables(self, p):
    
        def calculate_droplets_transport(p): 
            #fat: fraction of droplets with viable virons
            average_fractions = []
            num_time_steps = p.timeline_end - p.timeline_start #TODO replace

            # TODO: Iterate over each time step within p's timeline
            for t in range(p.timeline_start, p.timeline_end):
                total_infectious_people = 0

                # Iterate over each person in the location at time step t
                for person in p.location.population:
                    # Check if the person has an infectious state at time t
                    if "infectious" in person.states and person.states["infectious"].start <= t <= person.states["infectious"].end:
                        # Calculate the total number of infectious people at time t
                        # if the infected person is wearing a mask
                        if person.masked == True:
                            filtered_droplets = random.uniform(0.3, 0.9)
                            total_infectious_people += filtered_droplets
                        else:
                            total_infectious_people += 1

                # Calculate the average fraction at time step t and add it to the list
                average_fraction = total_infectious_people / p.location.capacity
                average_fraction = math.exp(-average_fraction)
                average_fractions.append(average_fraction)

            # Calculate the average fraction over the entire timeline
            average_frac = sum(average_fractions) / num_time_steps

            return average_frac
        
        def calculate_aerosol_transport():
            #fvv: fraction of droplets with viable virons
            # e^(time of flight/half-life) where T is the time in hours, half-life of virus = 1.1 hours
            time_of_flight = random.randint(3, 9)
            half_life = 1.1
            return math.exp(time_of_flight/half_life)
        
        return calculate_droplets_transport(p) * calculate_aerosol_transport()

    
    def calculate_susceptible_variables(self, p, indoor):

        def calculate_inhalation_rate(p, indoor):
            #fis: fraction of bioaerosols from the host in the vicinity of the susceptible 
            # that would be inhaled and deposited in the respiratory tract of a susceptible 
            # not wearing a face covering.
            fis = random.uniform(0.05, 0.7)
            if p.sex == 1:
                fis = fis * 0.8
            if p.age < 18 or p.age > 60:
                fis = fis * 0.8
            if indoor == False:
                fis = fis * 1.2
            return fis
        
        def calculate_frac_filtered(p):
            #fms
            ff = random.uniform(0.3, 0.6)
            if p.masked == False:
                ff = 0
            return ff
        
        return calculate_inhalation_rate(p, indoor)

    

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