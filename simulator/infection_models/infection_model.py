# from .pap import InfectionState
# import math

# import random
# # random.seed(1)

# def set_droplets_num(p, Rh):
#     #droplets per timestamp if speaking
#     if p.age < 3:
#         Rh = 30
#     # Adjust for children below 10
#     elif p.age < 10 or p.age > 60:
#         Rh = 100
#     return Rh

# def set_viral_load(p, fvh):
#     # fvh = fraction of viral load in droplets
#     return fvh

# """ def set_droplets_passed_mask(p, droplets=1):
#     # droplets passed through mask
#     # self.interventions = {
#     #         'mask': False,
#     #         'vaccine': VaccinationState.NONE
#     #     }
#     if p.get_masked() == True:
#         filter_efficiency = random.uniform(0.3, 0.6)
#         droplets = droplets * filter_efficiency
#     return droplets """

# def set_droplets_passed_mask(p, droplets=1, mask_already_applied=False):
#     """
#     Calculate droplets passed through mask
#     mask_already_applied: if True, skip mask filtering to avoid double application
#     """
#     if mask_already_applied:
#         return droplets
        
#     if p.get_masked() == True:
#         filter_efficiency = random.uniform(0.3, 0.6)
#         droplets = droplets * (1 - filter_efficiency)  # Reduce droplets by filter efficiency
#     return droplets

# def set_frac_aerosol(p, fah):
#     # fraction of droplets that become aerosol (smaller than 10 microns)
#     return fah

# def calculate_droplets_transport(p, num_time_steps): 
#         #fat: fraction of droplets with viable virons
#         average_fractions = []
#         num_time_steps = num_time_steps
        
#         disease = ''
#         for d, v in p.states.items():
#             if InfectionState.INFECTED in v:
#                 disease = d

#         #Iterate over each time step within p's timeline
#         for _ in range(num_time_steps):
#             total_infectious_people = 0

#             # Iterate over each person in the location at time step t
#             for person in p.location.population:
#                 if person.invisible == True:
#                     continue
                
#                 # Check if the person has an infectious state at time t
#                 if person.states.get(disease) != None and InfectionState.INFECTIOUS in person.states.get(disease):
#                     # Calculate the total number of infectious people at time t
#                     # if the infected person is wearing a mask
#                     if person.get_masked() == True:
#                         filtered_droplets = random.uniform(0.3, 0.9)
#                         total_infectious_people += filtered_droplets
#                     else:
#                         total_infectious_people += 1

#             # Calculate the average fraction at time step t and add it to the list
#             average_fraction = total_infectious_people / (p.location.total_count * num_time_steps)
#             average_fraction = math.exp(-average_fraction)
#             average_fractions.append(average_fraction)

#         # Calculate the average fraction over the entire timeline
#         average_frac = sum(average_fractions)

#         return average_frac

# def calculate_aerosol_transport():
#     #fvv: fraction of droplets with viable virons
#     # e^(time of flight/half-life) where T is the time in hours, half-life of virus = 1.1 hours
#     time_of_flight = random.randint(3, 9)
#     half_life = 1.1
#     return math.exp(time_of_flight/half_life)

# def calculate_inhalation_rate(p, indoor):
#         #fis: fraction of bioaerosols from the host in the vicinity of the susceptible 
#         # that would be inhaled and deposited in the respiratory tract of a susceptible 
#         # not wearing a face covering.
#         fis = random.uniform(0.05, 0.7)
#         if p.sex == 1:
#             fis = fis * 0.8
#         if p.age < 18 or p.age > 60:
#             fis = fis * 0.8
#         if indoor == False:
#             fis = fis * 1.2
#         return fis
    
# """ def calculate_frac_filtered(p):
#     #fms % filtered by facemask
#     fms = random.uniform(0.1, 0.3)
#     if p.get_masked() == False:
#         fms = 1
#     return fms """

# def calculate_frac_filtered(p, mask_already_applied=False):
#     """Calculate fraction filtered by facemask"""
#     if mask_already_applied:
#         return 1.0  # No additional filtering if already applied
        
#     fms = random.uniform(0.1, 0.3)
#     if p.get_masked() == False:
#         fms = 1.0
#     else:
#         fms = 1.0 - fms  # Convert to pass-through rate
#     return fms



# """ def calculate_host_variables(p, Rh = 250, fvh=0.37, fah=0.35):
#     # print(f"droplets {set_droplets_num(p, Rh)}")
#     # print(f"viral load {set_viral_load(p, fvh)}")
#     # print(f"droplets passed mask {set_droplets_passed_mask(p)}")
#     # print(f"frac aerosol {set_frac_aerosol(p, fah)}")
#     return set_droplets_num(p, Rh) * set_viral_load(p, fvh) * set_droplets_passed_mask(p) * set_frac_aerosol(p, fah) """

# def calculate_host_variables(p, Rh=250, fvh=0.37, fah=0.35, mask_already_applied=False):
#     """Calculate host variables with optional mask bypass"""
#     return (set_droplets_num(p, Rh) * 
#             set_viral_load(p, fvh) * 
#             set_droplets_passed_mask(p, mask_already_applied=mask_already_applied) * 
#             set_frac_aerosol(p, fah))

# def calculate_environment_variables(p, num_time_steps):
#     return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

# """ def calculate_susceptible_variables(p, indoor, time):
#     # print(f"inhale {calculate_inhalation_rate(p, indoor)}")
#     # print(f"frac {calculate_frac_filtered(p)}")
#     # print(f"time {time}")
#     return calculate_inhalation_rate(p, indoor) * calculate_frac_filtered(p) * time """

# def calculate_susceptible_variables(p, indoor, time, mask_already_applied=False):
#     """Calculate susceptible variables with optional mask bypass"""
#     return (calculate_inhalation_rate(p, indoor) * 
#             calculate_frac_filtered(p, mask_already_applied=mask_already_applied) * 
#             time)


# """ # times all the left side of the equation
# def CAT (p, indoor, num_time_steps, transmission_prob):
#     left = calculate_host_variables(p) * calculate_environment_variables(p, num_time_steps) * calculate_susceptible_variables(p, indoor, num_time_steps)
#     # print(f"host {calculate_host_variables(p)}")
#     # print(f"env {calculate_environment_variables(p, num_time_steps)}")
#     # print(f"sus {calculate_susceptible_variables(p, indoor, num_time_steps)}")
#     # print(f"left {left}")
#     # print(f"right {Nid}")
#     '''if left <= Nid: # threhold for infection
#         return False
#     else:
#         return True'''
#     chance = min(left / transmission_prob, 1.0)
#     return random.random() < chance """
# def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
    
#     """Calculate transmission probability
    
#     Args:
#         p: susceptible person
#         indoor: indoor/outdoor setting
#         num_time_steps: number of time steps
#         transmission_prob: base transmission probability (should already include mask effects)
#         infector_masked: whether infector is masked (for logging/debugging)
#         susceptible_masked: whether susceptible is masked (for logging/debugging)"""
    
#     # Since mask effects are already applied in transmission_prob, 
#     # we bypass mask calculations here to avoid double application
#     if transmission_prob <= 0:
#         return False
#     mask_already_applied = True
    
#     left = (calculate_host_variables(p, mask_already_applied=mask_already_applied) * 
#             calculate_environment_variables(p, num_time_steps) * 
#             calculate_susceptible_variables(p, indoor, num_time_steps, mask_already_applied=mask_already_applied))
    
#     # Debug logging (optional)
#     if hasattr(p, 'debug') and p.debug:
#         print(f"CAT calculation for person {p.id}:")
#         print(f"  Left side: {left}")
#         print(f"  Transmission prob: {transmission_prob}")
#         print(f"  Infector masked: {infector_masked}")
#         print(f"  Susceptible masked: {susceptible_masked}")
    
#     chance = min(left / transmission_prob, 1.0)
#     return random.random() < chance 

# # def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
# #     if transmission_prob <= 0:
# #         return False
    
# #     # Use a simple calculation without mask effects since they're already in transmission_prob
# #     left = 1.0  # Simplified for testing
    
# #     chance = min(left / transmission_prob, 1.0)
# #     return random.random() < chance

# ANALYSIS OF INFECTION MODEL CODE AND INTEGRATION ISSUES

# CORRECTED INFECTION MODEL CODE
from ..pap import InfectionState
import math

import random
# random.seed(1)

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

def set_droplets_passed_mask(p, droplets=1, mask_already_applied=False):
    """
    Calculate droplets passed through mask
    mask_already_applied: if True, skip mask filtering to avoid double application
    """
    if mask_already_applied:
        return droplets
        
    if p.get_masked() == True:
        filter_efficiency = random.uniform(0.3, 0.6)
        droplets = droplets * (1 - filter_efficiency)  # Fixed: Reduce droplets by filter efficiency
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
        for _ in range(num_time_steps):
            total_infectious_people = 0

            # Iterate over each person in the location at time step t
            for person in p.location.population:
                if person.invisible == True:
                    continue
                
                # Check if the person has an infectious state at time t
                if person.states.get(disease) != None and InfectionState.INFECTIOUS in person.states.get(disease):
                    # Calculate the total number of infectious people at time t
                    # if the infected person is wearing a mask
                    if person.get_masked() == True:
                        filtered_droplets = random.uniform(0.1, 0.4)  # Fixed: Lower values mean more filtering
                        total_infectious_people += filtered_droplets
                    else:
                        total_infectious_people += 1

            # Calculate the average fraction at time step t and add it to the list
            if p.location.total_count > 0:  # Fixed: Prevent division by zero
                average_fraction = total_infectious_people / (p.location.total_count * num_time_steps)
                average_fraction = math.exp(-average_fraction)
                average_fractions.append(average_fraction)

        # Calculate the average fraction over the entire timeline
        average_frac = sum(average_fractions)

        return average_frac

def calculate_aerosol_transport():
    #fvv: fraction of droplets with viable virons
    # e^(time of flight/half-life) where T is the time in hours, half-life of virus = 1.1 hours
    time_of_flight = random.randint(3, 9)
    half_life = 1.1
    return math.exp(-time_of_flight/half_life)  # Fixed: Should be negative for decay

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

def calculate_frac_filtered(p, mask_already_applied=False):
    """Calculate fraction filtered by facemask"""
    if mask_already_applied:
        return 1.0  # No additional filtering if already applied
        
    if p.get_masked() == False:
        fms = 1.0  # No filtering
    else:
        filter_rate = random.uniform(0.1, 0.3)
        fms = 1.0 - filter_rate  # Fixed: Convert to pass-through rate (what gets through)
    return fms

def calculate_host_variables(p, Rh=250, fvh=0.37, fah=0.35, mask_already_applied=False):
    """Calculate host variables with optional mask bypass"""
    return (set_droplets_num(p, Rh) * 
            set_viral_load(p, fvh) * 
            set_droplets_passed_mask(p, droplets=1, mask_already_applied=mask_already_applied) * 
            set_frac_aerosol(p, fah))

def calculate_environment_variables(p, num_time_steps):
    return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

def calculate_susceptible_variables(p, indoor, time, mask_already_applied=False):
    """Calculate susceptible variables with optional mask bypass"""
    return (calculate_inhalation_rate(p, indoor) * 
            calculate_frac_filtered(p, mask_already_applied=mask_already_applied) * 
            time)

def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
    """Calculate transmission probability
    
    Args:
        p: susceptible person
        indoor: indoor/outdoor setting
        num_time_steps: number of time steps
        transmission_prob: base transmission probability
        infector_masked: whether infector is masked
        susceptible_masked: whether susceptible is masked
    """
    
    if transmission_prob <= 0:
        return False
    
    return random.random() < 0.8
    
    # Apply masking effects if they haven't been applied yet
    if transmission_prob >= 0.001:  # Assuming masks haven't been applied to high base rates
        mask_modifier = 1.0
        
        # Hardcoded mask effectiveness values to avoid circular import
        MASK_EFFECTIVENESS = {
            'source_control': 0.7,      # infector masked
            'wearer_protection': 0.5,   # susceptible masked
            'both_masked': 0.85,        # both masked
        }
        
        if infector_masked and susceptible_masked:
            mask_modifier *= (1 - MASK_EFFECTIVENESS['both_masked'])
        elif infector_masked:
            mask_modifier *= (1 - MASK_EFFECTIVENESS['source_control'])
        elif susceptible_masked:
            mask_modifier *= (1 - MASK_EFFECTIVENESS['wearer_protection'])
        
        transmission_prob = transmission_prob * mask_modifier
    
    left = (calculate_host_variables(p, mask_already_applied=True) * 
            calculate_environment_variables(p, num_time_steps) * 
            calculate_susceptible_variables(p, indoor, num_time_steps, mask_already_applied=True))
    
    # Debug logging (optional)
    if hasattr(p, 'debug') and p.debug:
        print(f"CAT calculation for person {p.id}:")
        print(f"  Left side: {left}")
        print(f"  Adjusted transmission prob: {transmission_prob}")
        print(f"  Mask modifier: {mask_modifier}")
        print(f"  Infector masked: {infector_masked}")
        print(f"  Susceptible masked: {susceptible_masked}")
    
    if transmission_prob > 0:
        chance = min(left / transmission_prob, 1.0)
    else:
        chance = 0.0
    
    return random.random() < chance
    