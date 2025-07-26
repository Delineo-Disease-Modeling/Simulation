import math 
from scipy.integrate import quad 

"""Delineo infection model"""

def probability_of_infection(disease, d, t_i, r, m_i, V, fv_list, p_list, t_room, t_close, a_filter, N_0 = 900): 
    """Calculates probablity of infection (equation 1 from paper)
    
    Args: 
        N_0: upper limit of virions to get infected (is 900 by default)
        
    Returns: 
        probability of infection 
    """
    N_c = total_virions_inhaled(disease, d, t_i, r, m_i, V, fv_list, p_list, t_room, t_close, a_filter); # N_c is the total virions inhaled by an individual 
    return 1 - math.exp(-N_c/N_0)

def total_virions_inhaled(disease, d, t_i, r, m_i, V, fv_list, p_list, t_room, t_close, a_filter): 
    """Calculates total virions inhaled (N_C) by an individual (equation 2 from paper)

    Args: 
        disease: maybe delta or omicron 
        d: particle degradation rate
        t_i: duration of exposure 
        c_v (list): concentration of virions in the air (derived in c_v_function())
        f_inh (float): fraction of virions inhaled 
        N_close (list): number of virions inhaled given the distance from the infected person 
        t_close (float): time spent within 2 meters of infected person
        m_filter(float): mask filter efficiency 
        a_filter(float): air filtering 

    Returns: 
        N_c (float): total virions inhaled by an individual 
    """

    if disease == 'delta': 
        r = ((3.563 * (10**3)) + (2.354 * (10**5))) / 2
    elif disease == 'omicron': 
        r = ((6.635 * (10**3)) + (7.796 * (10**5))) / 2


   # Room integral
    def room_integrand(t, d, t_i, r, m_i, V, fv_list, p_list): 
        return c_v_function(d, t_i, r, m_i, V) * f_inh_function(fv_list, p_list)

    # Note the lambda function to pass additional parameters
    room_integral, room_error = quad(lambda t: room_integrand(t, d, t_i, r, m_i, V, fv_list, p_list), 0, t_room)

    # Close-contact integral
    def close_integrand(t):
        return N_close_function(t)

    # close_integral = 0
    close_integral, close_error = quad(lambda t: close_integrand(t), 0, t_close)

    # Apply mask and air filtration
    return (room_integral + close_integral) * m_i * a_filter

def c_v_function(d, t_i, r_i, m_filter, V): 
    """Calculates the concentration of virions (particles per liter) in the air as a function of time t (equation 3 from paper)
    
    Args: 
        d: particle degradation rate 
        t_i: list of times since each infected person entered the facility 
        r_i: emission rates for each infected person (particles/minute)
        m_filter: list of mask filteration rates for each infected person 
        V: volume of the room in liters 
    
    Returns: 
        Concentration of virions in air at time t"""
    # assumption: only one infected person in the facility 
    numerator = (1 - math.exp(-1 * d * t_i)) * r_i * m_filter


    return numerator / (V * d)
    
    
def f_inh_function(fv_list, p_list): 
    """Calculates the fraction of virions inhaled 
    
    Args:
       fv_list: fraction of virus in each droplet size class 
       p_list: deposition probability of each droplet size class 
        
    Returns: 
        Fraction of virions inhaled at time t"""
    # assumption: there is only one infected person in the facility 
    return fv_list * (p_list / 100)

    # the below is for the case that there multiple infected people
    # return sum([fv_list[i] * (p_list[i] / 100) for i in range(len(fv_list))])

    
def N_close_function(distance): 
    """Calculates the number of virions inhaled per minute due to proximity with infected person as a function of distance 
    
    Args: 
        distance: distance from infected person (in meters)
    
    Returns: 
        Number of virions inhaled per minute (particles/min)"""

    if (distance <= 0.25):
        return 96.57; 
    elif (distance <= 0.5): 
        return 68.37; 
    elif (distance <= 0.75):
        return 32.68; 
    elif (distance <= 1):
        return 20.53; 
    elif (distance <= 1.25): 
        return 16.47; 
    elif (distance <= 1.5):
        return 13.39; 
    elif (distance <= 1.75): 
        return 11.18; 
    elif (distance <= 2): 
        return 10.82; 
    else: 
        return 0; 
    