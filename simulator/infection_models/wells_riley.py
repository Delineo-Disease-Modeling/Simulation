from ..pap import InfectionState
import math
import random


def set_droplets_num(p, Rh):
    if p.age < 3:
        return 30
    elif p.age < 10 or p.age > 60:
        return 100
    return Rh

def set_viral_load(p, fvh):
    return fvh

def set_droplets_passed_mask(p, droplets=1, mask_already_applied=False):
    if mask_already_applied:
        return droplets
    if p.get_masked():
        filter_efficiency = random.uniform(0.3, 0.6)
        return droplets * (1 - filter_efficiency)
    return droplets

def set_frac_aerosol(p, fah):
    return fah

def calculate_droplets_transport(p, num_time_steps):
    average_fractions = []
    disease = ''
    for d, v in p.states.items():
        if InfectionState.INFECTED in v:
            disease = d
            break

    for _ in range(num_time_steps):
        total = 0
        for person in p.location.population:
            if person.invisible:
                continue
            if person.states.get(disease) and InfectionState.INFECTIOUS in person.states[disease]:
                if person.get_masked():
                    total += random.uniform(0.1, 0.4)
                else:
                    total += 1
        if p.location.total_count > 0:
            avg = total / (p.location.total_count * num_time_steps)
            average_fractions.append(math.exp(-avg))
    return sum(average_fractions)

def calculate_aerosol_transport():
    time_of_flight = random.uniform(3, 9)
    half_life = 1.1
    return math.exp(-time_of_flight / half_life)

def calculate_inhalation_rate(p, indoor):
    fis = random.uniform(0.05, 0.7)
    if p.sex == 1:
        fis *= 0.8
    if p.age < 18 or p.age > 60:
        fis *= 0.8
    if not indoor:
        fis *= 1.2
    return fis

def calculate_frac_filtered(p, mask_already_applied=False):
    if mask_already_applied:
        return 1.0
    if not p.get_masked():
        return 1.0
    filter_rate = random.uniform(0.1, 0.3)
    return 1.0 - filter_rate

def calculate_host_variables(p, Rh=250, fvh=0.37, fah=0.35, mask_already_applied=False):
    return (set_droplets_num(p, Rh)
            * set_viral_load(p, fvh)
            * set_droplets_passed_mask(p, droplets=1, mask_already_applied=mask_already_applied)
            * set_frac_aerosol(p, fah))

def calculate_environment_variables(p, num_time_steps):
    return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

def calculate_susceptible_variables(p, indoor, time, mask_already_applied=False):
    return (calculate_inhalation_rate(p, indoor)
            * calculate_frac_filtered(p, mask_already_applied=mask_already_applied)
            * time)

def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
    """
    Calculate transmission according to Wells-Riley:
    P = 1 - exp(- q·B·t / Q_effective )
    Here transmission_prob passed in is treated as (q·B / Q_eff) unit rate per time-step.
    """
    random.seed(0)
    if transmission_prob <= 0:
        return False

    # Total inhaled quanta over exposure period
    t = num_time_steps
    mean_quanta = transmission_prob * t

    # mask modifiers reduce source and receptor breaths
    mask_factor = 1.0
    if infector_masked and susceptible_masked:
        mask_factor *= (1 - 0.85)
    elif infector_masked:
        mask_factor *= (1 - 0.7)
    elif susceptible_masked:
        mask_factor *= (1 - 0.5)
    mean_quanta *= mask_factor

    # cap floor
    mean_quanta = max(mean_quanta, 0.0)

    # Probability of infection by Poisson:
    prob = 1.0 - math.exp(-mean_quanta)

    if hasattr(p, 'debug') and p.debug:
        print(f"CAT debug for person {getattr(p,'id',None)}:")
        print(f"  mean_quanta = {mean_quanta}")
        print(f"  mask_factor = {mask_factor}")
        print(f"  infection_prob = {prob}")

    return random.random() < prob
