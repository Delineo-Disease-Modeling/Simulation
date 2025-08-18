# Wells Riley Model + modification to include vaccination effects 

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
    """
    Viral load can be reduced by vaccination status of the infected person
    """
    base_viral_load = fvh
    
    # Check if person is vaccinated and adjust viral load
    if hasattr(p, 'vaccination_status') and p.vaccination_status:
        # Vaccination reduces viral load in breakthrough infections
        vaccine_effectiveness_viral_load = getattr(p, 'vaccine_vl_reduction', 0.4)  # 40% reduction
        base_viral_load *= (1 - vaccine_effectiveness_viral_load)
    
    return base_viral_load

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

def get_vaccination_protection(p, protection_type='infection'):
    """
    Calculate vaccination protection factor
    
    Args:
        p: Person object
        protection_type: 'infection', 'transmission', or 'severity'
    
    Returns:
        float: Protection factor (0.0 = no protection, 1.0 = complete protection)
    """
    if not hasattr(p, 'vaccination_status') or not p.vaccination_status:
        return 0.0
    
    # Base vaccine effectiveness
    base_effectiveness = {
        'infection': getattr(p, 'vaccine_effectiveness_infection', 0.65),  # 65% against infection
        'transmission': getattr(p, 'vaccine_effectiveness_transmission', 0.40),  # 40% against transmission
        'severity': getattr(p, 'vaccine_effectiveness_severity', 0.85)  # 85% against severe disease
    }
    
    effectiveness = base_effectiveness.get(protection_type, 0.0)
    
    # Waning immunity - reduce effectiveness over time
    if hasattr(p, 'days_since_vaccination'):
        waning_factor = calculate_waning_immunity(p.days_since_vaccination)
        effectiveness *= waning_factor
    
    # Variant-specific effectiveness
    if hasattr(p, 'variant_effectiveness_modifier'):
        effectiveness *= p.variant_effectiveness_modifier
    
    return min(effectiveness, 1.0)

def calculate_waning_immunity(days_since_vaccination):
    """
    Calculate waning immunity factor based on time since vaccination
    
    Args:
        days_since_vaccination: Number of days since last vaccination
        
    Returns:
        float: Waning factor (1.0 = no waning, 0.0 = complete waning)
    """
    if days_since_vaccination <= 30:
        return 1.0  # Peak immunity for first month
    elif days_since_vaccination <= 180:
        # Linear decline from 100% to 70% over 5 months
        return 1.0 - 0.3 * (days_since_vaccination - 30) / 150
    else:
        # Slower decline after 6 months, stabilizing around 50%
        return max(0.5, 0.7 - 0.2 * (days_since_vaccination - 180) / 180)

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

def CAT(p, indoor, num_time_steps, transmission_prob, infector=None, infector_masked=False, susceptible_masked=False):
    """
    Calculate transmission according to Wells-Riley with vaccination effects:
    P = 1 - exp(- q·B·t / Q_effective )
    
    Enhanced to include:
    - Vaccination protection against infection (susceptible)
    - Vaccination effects on transmission (infector)
    - Waning immunity over time
    """
    random.seed(0)
    if transmission_prob <= 0:
        return False

    # Total inhaled quanta over exposure period
    t = num_time_steps
    mean_quanta = transmission_prob * t

    # Mask modifiers reduce source and receptor breaths
    mask_factor = 1.0
    if infector_masked and susceptible_masked:
        mask_factor *= (1 - 0.85)
    elif infector_masked:
        mask_factor *= (1 - 0.7)
    elif susceptible_masked:
        mask_factor *= (1 - 0.5)

    # Vaccination effects on transmission (source control)
    if infector is not None:
        transmission_reduction = get_vaccination_protection(infector, 'transmission')
        mask_factor *= (1 - transmission_reduction)

    # Apply combined mask and transmission factors
    mean_quanta *= mask_factor

    # Vaccination protection against infection (susceptible protection)
    infection_protection = get_vaccination_protection(p, 'infection')
    mean_quanta *= (1 - infection_protection)

    # Cap floor
    mean_quanta = max(mean_quanta, 0.0)

    # Probability of infection by Poisson distribution
    prob = 1.0 - math.exp(-mean_quanta)

    if hasattr(p, 'debug') and p.debug:
        print(f"CAT debug for person {getattr(p,'id',None)}:")
        print(f"  base_transmission_prob = {transmission_prob}")
        print(f"  mask_factor = {mask_factor}")
        print(f"  infection_protection = {infection_protection}")
        print(f"  mean_quanta = {mean_quanta}")
        print(f"  final_infection_prob = {prob}")

    return random.random() < prob


# Additional utility functions for vaccination management

def initialize_vaccination_status(person, vaccinated=False, vaccine_type='mRNA', doses=0, 
                                days_since_last_dose=0, variant_effectiveness=1.0):
    """
    Initialize vaccination status for a person
    
    Args:
        person: Person object
        vaccinated: Boolean vaccination status
        vaccine_type: Type of vaccine ('mRNA', 'viral_vector', 'protein')
        doses: Number of doses received
        days_since_last_dose: Days since last vaccination
        variant_effectiveness: Modifier for variant-specific effectiveness
    """
    person.vaccination_status = vaccinated
    person.vaccine_type = vaccine_type
    person.vaccine_doses = doses
    person.days_since_vaccination = days_since_last_dose
    person.variant_effectiveness_modifier = variant_effectiveness
    
    # Set vaccine effectiveness based on type and doses
    if vaccine_type == 'mRNA':
        if doses >= 2:
            person.vaccine_effectiveness_infection = 0.75
            person.vaccine_effectiveness_transmission = 0.50
            person.vaccine_effectiveness_severity = 0.90
            person.vaccine_vl_reduction = 0.5
        elif doses == 1:
            person.vaccine_effectiveness_infection = 0.50
            person.vaccine_effectiveness_transmission = 0.30
            person.vaccine_effectiveness_severity = 0.75
            person.vaccine_vl_reduction = 0.3
    elif vaccine_type == 'viral_vector':
        if doses >= 2:
            person.vaccine_effectiveness_infection = 0.65
            person.vaccine_effectiveness_transmission = 0.40
            person.vaccine_effectiveness_severity = 0.85
            person.vaccine_vl_reduction = 0.4
        elif doses == 1:
            person.vaccine_effectiveness_infection = 0.40
            person.vaccine_effectiveness_transmission = 0.25
            person.vaccine_effectiveness_severity = 0.65
            person.vaccine_vl_reduction = 0.2

def update_vaccination_time(person, days_elapsed):
    """
    Update the time since vaccination for waning immunity calculations
    
    Args:
        person: Person object
        days_elapsed: Number of days to add to vaccination time
    """
    if hasattr(person, 'days_since_vaccination'):
        person.days_since_vaccination += days_elapsed