# Wells-Riley Model v6

import math
import random


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
        'infection': getattr(p, 'vaccine_effectiveness_infection', 0.65),
        'transmission': getattr(p, 'vaccine_effectiveness_transmission', 0.40),
        'severity': getattr(p, 'vaccine_effectiveness_severity', 0.85)
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
    Calculate waning immunity factor based on time since vaccination.

    Returns:
        float: Waning factor (1.0 = no waning, 0.0 = complete waning)
    """
    if days_since_vaccination <= 30:
        return 1.0
    elif days_since_vaccination <= 180:
        # Linear decline from 100% to 70% over 5 months
        return 1.0 - 0.3 * (days_since_vaccination - 30) / 150
    else:
        # Slower decline after 6 months, stabilizing around 50%
        return max(0.5, 0.7 - 0.2 * (days_since_vaccination - 180) / 180)


def CAT(p, indoor, num_time_steps, infector=None, infector_masked=False, susceptible_masked=False):
    """
    Calculate transmission probability using the Wells-Riley equation
    with vaccination effects:

        P = 1 - exp(- I * q * p * t / Q)

    Where:
        I = number of infectors (always 1 per call)
        q = quanta generation rate (quanta/hr)
        p = pulmonary ventilation rate (m³/hr)
        t = exposure time (hours)
        Q = room ventilation rate (m³/hr)

    Args:
        p: susceptible Person object
        indoor: whether the location is indoors
        num_time_steps: number of timesteps of co-location (each = 1 hour)
        infector: infector Person object (for vaccination checks)
        infector_masked: whether the infector is wearing a mask
        susceptible_masked: whether the susceptible is wearing a mask

    Returns:
        bool: True if transmission occurs
    """
    # Wells-Riley parameters
    quanta_rate = 20.0        # quanta/hr
    breathing_rate = 0.5      # m³/hr
    ventilation_rate = 150.0  # m³/hr

    if not indoor:
        # Outdoor
        ventilation_rate *= 20.0

    # Exposure time in hours
    t = num_time_steps

    # Wells-Riley: mean inhaled quanta = I * q * p * t / Q
    mean_quanta = (quanta_rate * breathing_rate * t) / ventilation_rate

    # Mask modifiers reduce quanta reaching susceptible
    mask_factor = 1.0
    if infector_masked and susceptible_masked:
        mask_factor *= (1 - 0.85)
    elif infector_masked:
        mask_factor *= (1 - 0.7)
    elif susceptible_masked:
        mask_factor *= (1 - 0.5)

    # Vaccination effects on transmission
    if infector is not None:
        transmission_reduction = get_vaccination_protection(infector, 'transmission')
        mask_factor *= (1 - transmission_reduction)

    mean_quanta *= mask_factor

    # Vaccination protection against infection (susceptible)
    infection_protection = get_vaccination_protection(p, 'infection')
    mean_quanta *= (1 - infection_protection)

    mean_quanta = max(mean_quanta, 0.0)

    # Probability of infection (Poisson process)
    prob = 1.0 - math.exp(-mean_quanta)

    if hasattr(p, 'debug') and p.debug:
        print(f"CAT debug for person {getattr(p, 'id', None)}:")
        print(f"  quanta_rate={quanta_rate}, breathing_rate={breathing_rate}, ventilation_rate={ventilation_rate}")
        print(f"  mask_factor = {mask_factor}")
        print(f"  infection_protection = {infection_protection}")
        print(f"  mean_quanta = {mean_quanta}")
        print(f"  final_infection_prob = {prob}")

    return random.random() < prob


# Vaccination utility functions (carried over from v5)

def initialize_vaccination_status(person, vaccinated=False, vaccine_type='mRNA', doses=0,
                                days_since_last_dose=0, variant_effectiveness=1.0):
    """Initialize vaccination status for a person."""
    person.vaccination_status = vaccinated
    person.vaccine_type = vaccine_type
    person.vaccine_doses = doses
    person.days_since_vaccination = days_since_last_dose
    person.variant_effectiveness_modifier = variant_effectiveness

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
    """Update the time since vaccination for waning immunity calculations."""
    if hasattr(person, 'days_since_vaccination'):
        person.days_since_vaccination += days_elapsed
