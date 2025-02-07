from infection_model import *
"""File to test and implement infection model"""

# Example inputs
d = 0.1  # virus degradation rate
t = [10, 20]  # times since infected people entered (minutes)
r_list = [1000, 2000]  # emission rates (particles/min)
m_list = [0.1, 0.2]  # mask filtration rates (e.g., surgical masks)
V = 50000  # room volume (liters)
fv_list = [0.5, 0.3, 0.2]  # fraction of virions in droplet size classes
p_list = [90, 70, 50]  # deposition probabilities for droplet sizes (%)
t_room = 60  # time spent in the room (minutes)
n_close = 50  # virions inhaled per minute due to proximity
t_close = 15  # time spent close to infected person (minutes)
m_filter = 0.01  # mask filtration rate for the individual
a_filter = 0.5  # air filtration rate
N0 = 900  # threshold virions for infection

# Step 1: Calculate virus concentration
cv = c_v_function(d, t, r_list, m_list, V)

# Step 2: Calculate fraction of virions inhaled
finh = f_inh_function(fv_list, p_list)

# Step 3: Calculate total virions inhaled
Nc = total_virions_inhaled(cv, finh, t_room, n_close, t_close, m_filter, a_filter)

# Step 4: Calculate probability of infection
P_infected = probability_of_infection(Nc, N0)

print(f"Virus Concentration (cv): {cv:.4f} particles/liter")
print(f"Fraction of Virions Inhaled (f_inh): {finh:.4f}")
print(f"Total Virions Inhaled (Nc): {Nc:.2f}")
print(f"Probability of Infection (P_infected): {P_infected:.2%}")
