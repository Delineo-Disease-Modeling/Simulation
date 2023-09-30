import random
import math

def calculate_host_variables(p, Rh = 250, fvh=0.37, fah=0.35):
        
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
        return fvh
    
    def set_droplets_passed_mask(p, droplets=1):
        # droplets passed through mask
        if p.masked == True:
            filter_efficiency = random.uniform(0.3, 0.6)
            droplets = droplets * filter_efficiency
        return droplets
    
    def set_frac_aerosol(p, fah):
        # fraction of droplets that become aerosol (smaller than 10 microns)
        return fah

    return set_droplets_num(p, Rh) * set_viral_load(p, fvh) * set_droplets_passed_mask(p) * set_frac_aerosol(p, fah)

def calculate_environment_variables(p):

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


def calculate_susceptible_variables(p, indoor, time):

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
        #fms % filtered by facemask
        fms = random.uniform(0.3, 0.6)
        if p.masked == False:
            fms = 0
        return fms
    
    return calculate_inhalation_rate(p, indoor) * calculate_frac_filtered(p) * time

# times all the left side of the equation
def CAT (self, p, indoor, time):
    left = self.calculate_host_variables(p) * self.calculate_environment_variables(p) * self.calculate_susceptible_variables(p, indoor, time)
    #TODO: Nid
    Nid = 30
    if left <= Nid:
        return False
    else:
        return True

