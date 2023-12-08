from .pap import InfectionState
import random
import math

def set_droplets_num(p, Rh):
    #droplets per timestamp if speaking
    if p.age < 3:
        Rh = 30
    # Adjust for children below 10
    elif p.age < 10 or p.age > 60:
        Rh = 100
    return Rh

def set_viral_load(p, fvh):
    # fvh = fraction of viral load in droplets
    return fvh

def set_droplets_passed_mask(p, droplets=1):
    # droplets passed through mask
    # self.interventions = {
    #         'mask': False,
    #         'vaccine': VaccinationState.NONE
    #     }
    if p.get_masked() == True:
        filter_efficiency = random.uniform(0.3, 0.6)
        droplets = droplets * filter_efficiency
    return droplets

def set_frac_aerosol(p, fah):
    # fraction of droplets that become aerosol (smaller than 10 microns)
    return fah

def calculate_droplets_transport(p, num_time_steps): 
        #fat: fraction of droplets with viable virons
        average_fractions = []
        num_time_steps = num_time_steps
        
        disease = ''
        for d, v in p.states.items():
            if InfectionState.INFECTED in v:
                disease = d

        #Iterate over each time step within p's timeline
        for t in range(num_time_steps):
            total_infectious_people = 0

            # Iterate over each person in the location at time step t
            for person in p.location.population:
                # Check if the person has an infectious state at time t
                if person.states.get(disease) != None and InfectionState.INFECTIOUS in person.states.get(disease):
                    # Calculate the total number of infectious people at time t
                    # if the infected person is wearing a mask
                    if person.get_masked() == True:
                        filtered_droplets = random.uniform(0.3, 0.9)
                        total_infectious_people += filtered_droplets
                    else:
                        total_infectious_people += 1

            # Calculate the average fraction at time step t and add it to the list
            average_fraction = total_infectious_people / p.location.total_count
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
    fms = random.uniform(0.1, 0.3)
    if p.get_masked() == False:
        fms = 1
    return fms


def calculate_host_variables(p, Rh = 250, fvh=0.37, fah=0.35):
    # print(f"droplets {set_droplets_num(p, Rh)}")
    # print(f"viral load {set_viral_load(p, fvh)}")
    # print(f"droplets passed mask {set_droplets_passed_mask(p)}")
    # print(f"frac aerosol {set_frac_aerosol(p, fah)}")
    return set_droplets_num(p, Rh) * set_viral_load(p, fvh) * set_droplets_passed_mask(p) * set_frac_aerosol(p, fah)

def calculate_environment_variables(p, num_time_steps):
    return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

def calculate_susceptible_variables(p, indoor, time):
    # print(f"inhale {calculate_inhalation_rate(p, indoor)}")
    # print(f"frac {calculate_frac_filtered(p)}")
    # print(f"time {time}")
    return calculate_inhalation_rate(p, indoor) * calculate_frac_filtered(p) * time

# times all the left side of the equation
def CAT (p, indoor, num_time_steps, Nid):
    left = calculate_host_variables(p) * calculate_environment_variables(p, num_time_steps) * calculate_susceptible_variables(p, indoor, num_time_steps)
    # print(f"host {calculate_host_variables(p)}")
    # print(f"env {calculate_environment_variables(p, num_time_steps)}")
    # print(f"sus {calculate_susceptible_variables(p, indoor, num_time_steps)}")
    # print(f"left {left}")
    # print(f"right {Nid}")
    if left <= Nid: # threhold for infection
        return False
    else:
        return True

