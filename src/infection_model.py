import math 
from scipy.integrate import quad 
"""This program has the Delineo Infection Model"""

def probability_of_infection(N_c, N_0 = 900): 
    """Calculates probablity of infection (equation 1 from paper)
    
    Args: 
        N_c: inhaled virions by an individual (from total_virions_inhaled() function)
        N_0: upper limit of virions to get infected (is 900 by default)
        
    Returns: 
        probability of infection 
    """
    return 1 - math.exp(-N_c/N_0)

def total_virions_inhaled(disease, d, t_i, r, m_i, V, fv_list, p_list, t_room, t_close, m_filter, a_filter): 
    """Calculates total virions inhaled by an individual (equation 2 from paper)

    Args: 
        disease: maybe delta or omicron 
        d: particle degradation rate
        t_i: duration of exposure 
        c_v: concentration of virions in the air (derived in c_v_function())
        f_inh: fraction of virions inhaled 
        N_close: number of virions inhaled given the distance from the infected person 
        t_close: time spent within 2 meters of infected person
        m_filter: mask filter efficiency 
        a_filter: air filtering 

    Returns: 
        total virions inhaled by an individual 
    """

    if disease == 'delta': 
        r = ((3.563 * 10^3) + (2.354 * 10^5)) / 2
    else: 
        r = ((6.635 * 10^3) + (7.796 * 10^5)) / 2


    # Integrate for room virions inhaled
    room_integral = quad(c_v_function(d, t_i, r, m_i, V) * f_inh_function(fv_list, p_list), 0, t_room)

    # Integrate for close-contact virions inhaled
    close_integral = quad(N_close_function(t_i), 0, t_close)

    # Apply mask and air filtration
    return (room_integral + close_integral) * m_filter * a_filter

def c_v_function(d, t_i, r_i, m_i, V): 
    """Calculates the concentration of virions in the air as a function of time t (equation 3 from paper)
    
    Args: 
        d: particle degradation rate 
        t_i: list of times since each infected person entered the facility 
        r_i: emission rates for each infected person (particles/minute)
        m_i: list of mask filteration rates for each infected person 
        V: volume of the room in liters 
    
    Returns: 
        Concentration of virions in air at time t"""
    
    numerator = sum([(1 - math.exp(-1 * d * t_i[i])) * r_i * m_i[i] for i in range(len(t_i))])
    return numerator / (V * d)
    
    
def f_inh_function(fv_list, p_list): 
    """Calculates the fraction of virions inhaled 
    
    Args:
       fv_list: fraction of virus in each droplet size class 
       p_list: deposition probability of each droplet size class 
        
    Returns: 
        Fraction of virions inhaled at time t"""
    
    return sum([fv_list[i] * (p_list[i] / 100) for i in range(len(fv_list))])

    
def N_close_function(t): 
    #TODO: Implement 
    """Calculates the number of virions inhaled due to proximity with infected person as a function of time t
    
    Args: 
        t: Time
    
    Returns: 
        the virions inhaled due to proximity with infected person at time t"""