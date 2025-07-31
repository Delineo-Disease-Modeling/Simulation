from ..pap import InfectionState
import math
import random


def calculate_quanta_generation_rate(p, base_quanta_rate=10.0):
    """
    Calculate quanta generation rate (q) based on person characteristics.
    Wells-Riley model: q represents infectious doses breathed out per unit time.
    """
    # Much more variable base quanta generation
    quanta_rate = base_quanta_rate * random.uniform(0.3, 2.5)
    
    # Age adjustments with more variation
    if p.age < 3:
        quanta_rate *= random.uniform(0.2, 0.8)  # Very young children - high variation
    elif p.age < 10:
        quanta_rate *= random.uniform(0.4, 1.2)  # Children - moderate variation
    elif p.age > 60:
        quanta_rate *= random.uniform(0.8, 2.0)  # Elderly - can be much higher
    else:
        quanta_rate *= random.uniform(0.6, 1.8)  # Adults - normal range
    
    # Add disease severity variation (some people are super-spreaders)
    severity_factor = random.lognormvariate(0, 0.8)  # Log-normal for realistic spread
    quanta_rate *= severity_factor
    
    # Activity level - much more dramatic effects
    activity_multiplier = random.choice([
        random.uniform(0.3, 0.7),   # Quiet/resting
        random.uniform(0.8, 1.2),   # Normal talking
        random.uniform(1.5, 3.0),   # Loud talking/singing
        random.uniform(2.0, 5.0)    # Shouting/exercising
    ])
    quanta_rate *= activity_multiplier
    
    return max(quanta_rate, 0.1)


def calculate_breathing_rate(p, indoor=True):
    """
    Calculate breathing rate (p) in m³/hour with high stochasticity.
    """
    # Base breathing rate with much more variation
    base_rate = random.uniform(0.3, 0.8)
    
    # Age adjustments with overlapping ranges
    if p.age < 3:
        base_rate *= random.uniform(0.2, 0.5)
    elif p.age < 10:
        base_rate *= random.uniform(0.4, 0.8)
    elif p.age < 18:
        base_rate *= random.uniform(0.7, 1.1)
    elif p.age > 60:
        base_rate *= random.uniform(0.6, 1.0)
    else:
        base_rate *= random.uniform(0.8, 1.3)
    
    # Sex with more variation
    if p.sex == 1:  # Male
        base_rate *= random.uniform(1.0, 1.4)
    else:
        base_rate *= random.uniform(0.8, 1.2)
    
    # Indoor vs outdoor with significant difference
    if not indoor:
        base_rate *= random.uniform(1.3, 2.0)  # Much higher outdoors
    
    # Random individual variation (some people just breathe differently)
    individual_factor = random.lognormvariate(0, 0.3)
    base_rate *= individual_factor
    
    return max(base_rate, 0.05)


def calculate_ventilation_rate(location, base_ventilation=3.0):
    """
    Calculate effective ventilation rate with high variability.
    """
    # Much more variable base ventilation
    ventilation_rate = base_ventilation * random.uniform(0.2, 3.0)
    
    # Occupancy effects with non-linear relationships
    if location.total_count > 50:
        ventilation_rate *= random.uniform(0.8, 1.8)  # Could be better or worse
    elif location.total_count > 20:
        ventilation_rate *= random.uniform(0.6, 1.4)
    elif location.total_count < 5:
        ventilation_rate *= random.uniform(0.3, 0.9)  # Small spaces often poorly ventilated
    
    # Random building quality factor
    building_factor = random.choice([
        random.uniform(0.1, 0.4),   # Poor ventilation (old buildings, crowded spaces)
        random.uniform(0.5, 1.0),   # Average ventilation
        random.uniform(1.0, 2.0),   # Good ventilation
        random.uniform(2.0, 5.0)    # Excellent ventilation (hospitals, labs)
    ])
    ventilation_rate *= building_factor
    
    return max(ventilation_rate, 0.1)


def calculate_mask_effectiveness(infector_masked=False, susceptible_masked=False):
    """
    Calculate mask effectiveness with realistic variability and dramatic effects.
    """
    effectiveness = 1.0
    
    if infector_masked:
        # Source control varies ENORMOUSLY by mask type and fit
        mask_quality = random.choice([
            random.uniform(0.20, 0.40),  # Poor mask/fit (cloth, loose)
            random.uniform(0.50, 0.70),  # Average surgical mask
            random.uniform(0.75, 0.90),  # Good surgical mask, well-fitted
            random.uniform(0.85, 0.95)   # N95/FFP2, properly fitted
        ])
        effectiveness *= (1 - mask_quality)
    
    if susceptible_masked:
        # Protection effectiveness also highly variable
        protection_quality = random.choice([
            random.uniform(0.15, 0.35),  # Poor protection
            random.uniform(0.40, 0.60),  # Average protection
            random.uniform(0.65, 0.80),  # Good protection
            random.uniform(0.80, 0.95)   # Excellent protection
        ])
        effectiveness *= (1 - protection_quality)
    
    return max(effectiveness, 0.001)  # Always some small risk remains


def calculate_environmental_decay(exposure_time_hours):
    """
    Calculate environmental factors with high variability.
    """
    # Viral half-life varies enormously by conditions
    half_life = random.choice([
        random.uniform(0.3, 1.0),   # Poor conditions for virus (UV, dry, hot)
        random.uniform(1.0, 2.0),   # Average conditions
        random.uniform(2.0, 4.0),   # Good conditions for virus (cool, humid)
        random.uniform(4.0, 8.0)    # Excellent conditions (cold, humid, dark)
    ])
    
    # Decay with some random variation
    base_decay = math.exp(-0.693 * exposure_time_hours / half_life)
    
    # Add environmental noise
    environmental_factor = random.uniform(0.7, 1.3)
    
    return max(base_decay * environmental_factor, 0.01)


def count_infectors_in_location(location, disease):
    """
    Count infectors with individual quanta generation rates.
    """
    infector_count = 0
    total_quanta_rate = 0
    
    for person in location.population:
        if person.invisible:
            continue
        if (person.states.get(disease) and 
            InfectionState.INFECTIOUS in person.states[disease]):
            infector_count += 1
            # Each person gets their own random quanta rate
            personal_quanta = calculate_quanta_generation_rate(person)
            total_quanta_rate += personal_quanta
    
    return infector_count, total_quanta_rate


def wells_riley_infection_probability(susceptible_person, location, exposure_time_hours, 
                                     disease, infector_masked=False, susceptible_masked=False,
                                     indoor=True):
    """
    Highly stochastic Wells-Riley probability calculation.
    """
    # Count infectors and total quanta generation
    infector_count, total_quanta_rate = count_infectors_in_location(location, disease)
    
    if infector_count == 0:
        return 0.0
    
    # All parameters are now stochastic
    breathing_rate = calculate_breathing_rate(susceptible_person, indoor)
    
    # Room volume estimation with high variability
    base_volume_per_person = random.uniform(20, 100)  # Huge range
    estimated_volume = max(location.total_count * base_volume_per_person, 50)
    
    # Add random room characteristics
    room_factor = random.uniform(0.3, 3.0)  # Some rooms are just different
    estimated_volume *= room_factor
    
    ventilation_ach = calculate_ventilation_rate(location)
    ventilation_rate = ventilation_ach * estimated_volume / 1000  # Convert to m³/hour
    
    # Mask effectiveness with high impact
    mask_factor = calculate_mask_effectiveness(infector_masked, susceptible_masked)
    
    # Environmental decay
    decay_factor = calculate_environmental_decay(exposure_time_hours)
    
    # Add proximity effects (not in original Wells-Riley but important)
    proximity_factor = random.uniform(0.5, 2.0)
    if location.total_count < 5:  # Small groups = closer proximity
        proximity_factor *= random.uniform(1.5, 4.0)
    
    # Wells-Riley equation with all stochastic parameters
    exponent = (total_quanta_rate * breathing_rate * exposure_time_hours * 
               mask_factor * decay_factor * proximity_factor / max(ventilation_rate, 0.1))
    
    # Add final random variation to account for individual susceptibility
    susceptibility_factor = random.lognormvariate(0, 0.5)  # Some people more/less susceptible
    exponent *= susceptibility_factor
    
    exponent = max(exponent, 0.0)
    probability = 1.0 - math.exp(-exponent)
    
    return min(probability, 0.999)


def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
    """
    Highly stochastic Wells-Riley transmission with dramatic masking effects.
    """
    # Remove the fixed seed to make it truly stochastic!
    # random.seed(0)  # REMOVED - this was making everything deterministic!
    
    if transmission_prob <= 0:
        return False
    
    # Find disease
    disease = ''
    for d, v in p.states.items():
        if InfectionState.INFECTED in v:
            disease = d
            break
    
    if not disease:
        return False
    
    # More variable time step conversion
    time_step_hours = random.uniform(0.05, 0.2)  # 3-12 minutes per step
    exposure_time_hours = num_time_steps * time_step_hours
    
    # Calculate Wells-Riley probability (now highly stochastic)
    wells_riley_prob = wells_riley_infection_probability(
        p, p.location, exposure_time_hours, disease, 
        infector_masked, susceptible_masked, indoor
    )
    
    # Scaling factor now also variable
    base_scaling = transmission_prob * random.uniform(5, 20)
    
    # Add interaction effects between transmission_prob and Wells-Riley
    if transmission_prob > 0.5:
        base_scaling *= random.uniform(1.2, 2.0)  # High base transmission amplifies
    
    scaling_factor = min(base_scaling, 3.0)
    final_probability = wells_riley_prob * scaling_factor
    
    # Add final random boost/reduction
    final_random_factor = random.uniform(0.3, 1.8)
    final_probability *= final_random_factor
    
    final_probability = max(0.0, min(final_probability, 0.99))
    
    # Debug information
    if hasattr(p, 'debug') and p.debug:
        print(f"Stochastic Wells-Riley CAT debug for person {getattr(p,'id',None)}:")
        print(f"  exposure_time_hours = {exposure_time_hours:.2f}")
        print(f"  wells_riley_prob = {wells_riley_prob:.4f}")
        print(f"  scaling_factor = {scaling_factor:.4f}")
        print(f"  final_probability = {final_probability:.4f}")
        print(f"  infector_masked = {infector_masked}")
        print(f"  susceptible_masked = {susceptible_masked}")
        print(f"  indoor = {indoor}")
    
    # Make the final decision
    return random.random() < final_probability


# Legacy functions - now also more stochastic for compatibility
def set_droplets_num(p, Rh):
    """Legacy function with added stochasticity"""
    base = Rh * random.uniform(0.5, 1.8)
    if p.age < 3:
        return int(base * random.uniform(0.1, 0.6))
    elif p.age < 10 or p.age > 60:
        return int(base * random.uniform(0.6, 1.4))
    return int(base)

def set_viral_load(p, fvh):
    """Legacy function with variation"""
    return fvh * random.uniform(0.3, 2.0)

def set_droplets_passed_mask(p, droplets=1, mask_already_applied=False):
    """Legacy function with realistic mask variation"""
    if mask_already_applied:
        return droplets
    if p.get_masked():
        # Much more variable mask effectiveness
        filter_efficiency = random.choice([
            random.uniform(0.1, 0.3),   # Poor mask
            random.uniform(0.3, 0.6),   # Average mask  
            random.uniform(0.6, 0.8),   # Good mask
            random.uniform(0.8, 0.95)   # Excellent mask
        ])
        return droplets * (1 - filter_efficiency)
    return droplets

def set_frac_aerosol(p, fah):
    """Legacy function with variation"""
    return fah * random.uniform(0.5, 1.8)

def calculate_droplets_transport(p, num_time_steps):
    """Legacy function - now properly stochastic"""
    # Much more variable transport
    base_transport = random.uniform(0.05, 0.95)
    
    # Add time-dependent effects
    time_factor = random.uniform(0.7, 1.3) ** num_time_steps
    
    return base_transport * time_factor

def calculate_aerosol_transport():
    """Legacy function with more variation"""
    time_of_flight = random.uniform(1, 15)  # Much wider range
    half_life = random.uniform(0.5, 3.0)    # Variable half-life
    return math.exp(-time_of_flight / half_life)

def calculate_inhalation_rate(p, indoor):
    """Legacy function using Wells-Riley breathing rate"""
    return calculate_breathing_rate(p, indoor)

def calculate_frac_filtered(p, mask_already_applied=False):
    """Legacy function with realistic mask variation"""
    if mask_already_applied:
        return 1.0
    if not p.get_masked():
        return 1.0
    # Much more variable filtration
    filter_rate = random.choice([
        random.uniform(0.05, 0.2),   # Poor filtration
        random.uniform(0.2, 0.4),    # Average filtration
        random.uniform(0.4, 0.7),    # Good filtration
        random.uniform(0.7, 0.9)     # Excellent filtration
    ])
    return 1.0 - filter_rate

def calculate_host_variables(p, Rh=250, fvh=0.37, fah=0.35, mask_already_applied=False):
    """Legacy function - now stochastic"""
    return (set_droplets_num(p, Rh)
            * set_viral_load(p, fvh)
            * set_droplets_passed_mask(p, droplets=1, mask_already_applied=mask_already_applied)
            * set_frac_aerosol(p, fah))

def calculate_environment_variables(p, num_time_steps):
    """Legacy function - now stochastic"""
    return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

def calculate_susceptible_variables(p, indoor, time, mask_already_applied=False):
    """Legacy function - now stochastic"""
    return (calculate_inhalation_rate(p, indoor)
            * calculate_frac_filtered(p, mask_already_applied=mask_already_applied)
            * time * random.uniform(0.6, 1.4))  # Added final variation