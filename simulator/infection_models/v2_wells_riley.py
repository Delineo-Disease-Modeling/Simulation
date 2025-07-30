from ..pap import InfectionState
import math
import random


def set_droplets_num(p, Rh):
    """Number of respiratory droplets generated per unit time"""
    if p.age < 3:
        return 30
    elif p.age < 10 or p.age > 60:
        return 100
    return Rh

def set_viral_load(p, fvh):
    """Fraction of droplets containing viable virus"""
    return fvh

def set_droplets_passed_mask(p, droplets=1, mask_already_applied=False):
    """Apply source masking efficiency - reduces infectious quanta generation"""
    if mask_already_applied:
        return droplets
    if p.get_masked():
        # High-quality masks have 70-95% filtration efficiency for source control
        filter_efficiency = random.uniform(0.70, 0.95)
        return droplets * (1 - filter_efficiency)
    return droplets

def set_frac_aerosol(p, fah):
    """Fraction of droplets that become aerosols"""
    return fah

def calculate_droplets_transport(p, num_time_steps):
    """Calculate environmental transport - simplified for demonstration"""
    # In a proper Wells-Riley model, this would be based on ventilation rate
    # For now, return a constant transport efficiency
    return 0.8  # 80% of aerosols remain airborne and well-mixed

def calculate_aerosol_transport():
    """Calculate aerosol survival in air"""
    # Virus survival in aerosols - decay over time
    time_of_flight = random.uniform(3, 9)
    half_life = 1.1
    return math.exp(-time_of_flight / half_life)

def calculate_inhalation_rate(p, indoor):
    """Breathing rate in cubic meters per time step"""
    # Base breathing rate (m³/timestep)
    base_rate = 0.5  # Typical adult breathing rate
    
    # Age adjustments
    if p.age < 18:
        base_rate *= 0.7  # Children breathe less
    elif p.age > 60:
        base_rate *= 0.9  # Elderly slightly reduced
    
    # Sex adjustments  
    if p.sex == 1:  # Assuming 1 = female
        base_rate *= 0.85
    
    # Activity level (indoor vs outdoor as proxy)
    if not indoor:
        base_rate *= 1.3  # Higher activity outdoors
    
    return base_rate

def calculate_frac_filtered(p, mask_already_applied=False):
    """Calculate receptor masking - reduces inhalation of infectious particles"""
    if mask_already_applied:
        return 1.0
    if not p.get_masked():
        return 1.0
    
    # Receptor mask filtration efficiency
    filter_efficiency = random.uniform(0.50, 0.80)  # 50-80% for receptor protection
    return 1.0 - filter_efficiency

def calculate_quanta_generation_rate(infector, Rh=250, fvh=0.37, fah=0.35):
    """
    Calculate quanta generation rate (q) for an infected person
    Wells-Riley: q = (respiratory_rate * viral_load * fraction_aerosol * mask_reduction)
    """
    base_quanta_rate = 10.0  # Base quanta per time step for typical respiratory activity
    
    # Adjust for age-based respiratory differences
    if infector.age < 3:
        respiratory_factor = 0.3
    elif infector.age < 10:
        respiratory_factor = 0.6
    elif infector.age > 60:
        respiratory_factor = 0.8
    else:
        respiratory_factor = 1.0
    
    # Apply masking at source
    mask_reduction = 1.0
    if infector.get_masked():
        # Source masking is highly effective
        mask_efficiency = random.uniform(0.70, 0.95)
        mask_reduction = 1.0 - mask_efficiency
    
    quanta_rate = base_quanta_rate * respiratory_factor * fvh * fah * mask_reduction
    return max(quanta_rate, 0.0)

def calculate_effective_ventilation_rate(location, num_people):
    """
    Calculate effective ventilation rate Q (air changes per time step)
    In a real implementation, this would be based on room volume and HVAC
    """
    # Simple model: more people = relatively less effective ventilation per person
    base_ventilation = 5.0  # Base air changes per time step
    crowding_factor = max(0.1, 1.0 / math.sqrt(num_people)) if num_people > 0 else 1.0
    return base_ventilation * crowding_factor

def calculate_host_variables(p, Rh=250, fvh=0.37, fah=0.35, mask_already_applied=False):
    """Legacy function - maintained for compatibility"""
    return (set_droplets_num(p, Rh)
            * set_viral_load(p, fvh)
            * set_droplets_passed_mask(p, droplets=1, mask_already_applied=mask_already_applied)
            * set_frac_aerosol(p, fah))

def calculate_environment_variables(p, num_time_steps):
    """Legacy function - maintained for compatibility"""
    return calculate_droplets_transport(p, num_time_steps) * calculate_aerosol_transport()

def calculate_susceptible_variables(p, indoor, time, mask_already_applied=False):
    """Legacy function - maintained for compatibility"""
    return (calculate_inhalation_rate(p, indoor)
            * calculate_frac_filtered(p, mask_already_applied=mask_already_applied)
            * time)

def CAT(p, indoor, num_time_steps, transmission_prob, infector_masked=False, susceptible_masked=False):
    """
    Calculate transmission probability using Wells-Riley model:
    P = 1 - exp(-I * q * B * t / Q)
    
    Where:
    - I = number of infectious people
    - q = quanta generation rate per infectious person
    - B = breathing rate of susceptible person  
    - t = exposure time
    - Q = effective ventilation rate
    
    Parameters kept the same for compatibility with existing code.
    """
    random.seed(0)
    
    if transmission_prob <= 0:
        return False

    # Count infectious people in the location
    disease = ''
    for d, v in p.states.items():
        if InfectionState.INFECTED in v:
            disease = d
            break
    
    infectious_count = 0
    total_quanta_rate = 0.0
    
    for person in p.location.population:
        if person.invisible:
            continue
        if person.states.get(disease) and InfectionState.INFECTIOUS in person.states[disease]:
            infectious_count += 1
            # Calculate quanta generation for this infector
            infector_quanta_rate = calculate_quanta_generation_rate(person)
            total_quanta_rate += infector_quanta_rate

    if infectious_count == 0:
        return False

    # Wells-Riley calculation
    # B: breathing rate of susceptible person
    breathing_rate = calculate_inhalation_rate(p, indoor)
    
    # Apply receptor masking
    mask_protection = 1.0
    if susceptible_masked or p.get_masked():
        mask_efficiency = random.uniform(0.50, 0.80)
        mask_protection = 1.0 - mask_efficiency
    
    effective_breathing_rate = breathing_rate * mask_protection
    
    # Q: effective ventilation rate
    ventilation_rate = calculate_effective_ventilation_rate(p.location, len(p.location.population))
    
    # t: exposure time
    exposure_time = num_time_steps
    
    # Calculate mean inhaled quanta using Wells-Riley
    # Mean quanta = (total_quanta_rate * effective_breathing_rate * exposure_time) / ventilation_rate
    mean_quanta = (total_quanta_rate * effective_breathing_rate * exposure_time) / ventilation_rate
    
    # Add some baseline from transmission_prob parameter for compatibility
    baseline_risk = transmission_prob * exposure_time * 0.1  # Reduced weight
    mean_quanta += baseline_risk
    
    # Ensure non-negative
    mean_quanta = max(mean_quanta, 0.0)
    
    # Probability of infection (Poisson model)
    infection_probability = 1.0 - math.exp(-mean_quanta)
    
    # Cap probability at reasonable maximum
    infection_probability = min(infection_probability, 0.95)
    
    # Debug output
    if hasattr(p, 'debug') and p.debug:
        print(f"Wells-Riley CAT debug for person {getattr(p,'id',None)}:")
        print(f"  infectious_count = {infectious_count}")
        print(f"  total_quanta_rate = {total_quanta_rate:.3f}")
        print(f"  breathing_rate = {breathing_rate:.3f}")
        print(f"  mask_protection = {mask_protection:.3f}")
        print(f"  effective_breathing_rate = {effective_breathing_rate:.3f}")
        print(f"  ventilation_rate = {ventilation_rate:.3f}")
        print(f"  exposure_time = {exposure_time}")
        print(f"  mean_quanta = {mean_quanta:.3f}")
        print(f"  infection_probability = {infection_probability:.3f}")
        print(f"  susceptible_masked = {susceptible_masked or p.get_masked()}")
    
    return random.random() < infection_probability