"""
Configuration settings for the Delineo simulation system.
This centralizes hardcoded values that were previously scattered across files.
"""

# DMP API settings
DMP_API = {
    "base_url": "http://localhost:8000",
    "paths": {
        # Default paths for initialization
        # "matrices_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/combined_matrices.csv",
        # "mapping_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/demographic_mapping.csv",
        # "states_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/custom_states.txt"
        "matrices_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/config_data/combined_matrices_usecase.csv",
        "mapping_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/config_data/demographic_mapping_usecase.csv",
        "states_path": "/Users/navyamehrotra/Documents/Projects/Classes_Semester_2/Delineo/Simulation/simulator/config_data/custom_states.txt"
    },
    # Mapping from DMP API state names to internal infection states
    "state_mapping": {
        "Infected": "INFECTED",
        "Infectious_Asymptomatic": "INFECTIOUS",
        "Infectious_Symptomatic": "INFECTIOUS",
        "Hospitalized": "HOSPITALIZED",
        "ICU": "HOSPITALIZED",
        "Recovered": "RECOVERED",
        "Deceased": "REMOVED"
    },
    # Time conversion factor from API time units to simulation time units
    "time_conversion_factor": 60
}

# Infection model parameters
INFECTION_MODEL = {
    # Fallback transmission rate used in CAT function when primary calculation method fails
    "transmission_rate": 7e3,
    # Whether multiple diseases can infect the same person simultaneously
    "allow_multidisease": True,
    # Default timestep for infection manager (minutes)
    "default_timestep": 15,
    # Fallback timeline values used only when DMP API fails to provide a timeline
    "fallback_timeline": {
        "infected_duration": 1440,      # 24 hours in minutes (fallback value)
        "infectious_delay": 240,        # 4 hours in minutes (fallback value)
        "recovery_duration": 10080      # 7 days in minutes (fallback value)
    },
    # Initial timeline values for newly infected people before DMP updates
    "initial_timeline": {
        "duration": 10800  # 180 hours in minutes
    }
}

# Simulation defaults
SIMULATION = {
    "default_timestep": 60,             # Default timestep in minutes
    "default_location": "barnsdall",    # Default location for simulation
    "default_max_length": 10080,        # Default simulation length (7 days in minutes)
    "log_interval": 6000,               # Interval for printing progress logs
    "vaccination_options": {
        "min_doses": 1,                 # Minimum number of vaccine doses
        "max_doses": 2                  # Maximum number of vaccine doses
    },
    "default_interventions": {
        "mask": 0.0,                    # Proportion of population wearing masks
        "vaccine": 0.0,                 # Proportion of population vaccinated
        "capacity": 1.0,                # Capacity multiplier for facilities
        "lockdown": 0,                  # Probability of lockdown enforcement
        "selfiso": 0.0,                 # Probability of self-isolation when symptomatic
        "randseed": False               # Whether to use random seed
    },
    "default_infected_ids": ['160', '43', '47', '4', '36', '9', '14', '19', '27', '22'],
    "variants": ['Delta', 'Omicron']    # Available disease variants
}

# Server configuration
SERVER = {
    "host": "0.0.0.0",
    "port": 1880,
    "error_messages": {
        "bad_request": "Bad Request",
        "no_data": "No data sent"
    }
} 