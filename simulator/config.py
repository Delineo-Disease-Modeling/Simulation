"""
Configuration settings for the Delineo simulation system.
This centralizes hardcoded values that were previously scattered across files.
Now parameterized via environment variables to support Docker and deployments.
"""

import os
from pathlib import Path

# Base directory for repo-relative defaults
_BASE_DIR = Path(__file__).resolve().parent
_CONFIG_DATA_DIR = _BASE_DIR / "config_data"

# DMP API settings
DMP_API = {
    "base_url": os.getenv("DMP_BASE_URL", "http://dmp:8000"),  # default to docker service name
    "paths": {
        # Default paths for initialization; can be overridden with env vars
        "matrices_path": os.getenv(
            "DMP_MATRICES_PATH", str(_CONFIG_DATA_DIR / "combined_matrices.csv")
        ),
        "mapping_path": os.getenv(
            "DMP_MAPPING_PATH", str(_CONFIG_DATA_DIR / "demographic_mapping.csv")
        ),
        "states_path": os.getenv(
            "DMP_STATES_PATH", str(_CONFIG_DATA_DIR / "custom_states.txt")
        ),
    },
    # Mapping from DMP API state names to internal infection states
    "state_mapping": {
        "Infected": "INFECTED",
        "Infectious_Asymptomatic": "INFECTIOUS",
        "Infectious_Symptomatic": "INFECTIOUS",
        "Hospitalized": "HOSPITALIZED",
        "ICU": "HOSPITALIZED",
        "Recovered": "RECOVERED",
        "Deceased": "REMOVED",
    },
    # Time conversion factor from API time units to simulation time units
    "time_conversion_factor": int(os.getenv("DMP_TIME_FACTOR", "60")),
}

# Infection model parameters
INFECTION_MODEL = {
    # Fallback transmission rate used in CAT function when primary calculation method fails
    "transmission_rate": float(os.getenv("INFECTION_TRANSMISSION_RATE", "7000")),
    # Whether multiple diseases can infect the same person simultaneously
    "allow_multidisease": os.getenv("ALLOW_MULTIDISEASE", "true").lower() == "true",
    # Default timestep for infection manager (minutes)
    "default_timestep": int(os.getenv("INFECTION_DEFAULT_TIMESTEP", "15")),
    # Fallback timeline values used only when DMP API fails to provide a timeline
    "fallback_timeline": {
        "infected_duration": int(os.getenv("FALLBACK_INFECTED_DURATION", "1440")),
        "infectious_delay": int(os.getenv("FALLBACK_INFECTIOUS_DELAY", "240")),
        "recovery_duration": int(os.getenv("FALLBACK_RECOVERY_DURATION", "10080")),
    },
    # Initial timeline values for newly infected people before DMP updates
    "initial_timeline": {
        "duration": int(os.getenv("INITIAL_TIMELINE_DURATION", "10800"))
    },
}

# Simulation defaults
SIMULATION = {
    "default_timestep": int(os.getenv("SIM_DEFAULT_TIMESTEP", "60")),  # minutes
    "default_location": os.getenv("SIM_DEFAULT_LOCATION", "barnsdall"),
    "default_max_length": int(os.getenv("SIM_DEFAULT_MAX_LENGTH", "72000")),
    "log_interval": int(os.getenv("SIM_LOG_INTERVAL", "6000")),
    "vaccination_options": {
        "min_doses": int(os.getenv("SIM_VAX_MIN_DOSES", "1")),
        "max_doses": int(os.getenv("SIM_VAX_MAX_DOSES", "2")),
    },
    "default_interventions": {
        "mask": float(os.getenv("SIM_DEFAULT_MASK", "0.0")),
        "vaccine": float(os.getenv("SIM_DEFAULT_VACCINE", "0.0")),
        "capacity": float(os.getenv("SIM_DEFAULT_CAPACITY", "1.0")),
        "lockdown": int(os.getenv("SIM_DEFAULT_LOCKDOWN", "0")),
        "selfiso": float(os.getenv("SIM_DEFAULT_SELFISO", "0.0")),
        "randseed": os.getenv("SIM_DEFAULT_RANDSEED", "true").lower() == "true",
    },
    "default_infected_ids": [
        "160",
        "43",
        "47",
        "4",
        "36",
        "9",
        "14",
        "19",
        "27",
        "22",
        "3",
        "5",
    ],
    "variants": ["Delta", "Omicron"],
}

# Server configuration
SERVER = {
    "host": os.getenv("SERVER_HOST", "0.0.0.0"),
    "port": int(os.getenv("SERVER_PORT", "1880")),
    "error_messages": {
        "bad_request": "Bad Request",
        "no_data": "No data sent",
    },
}
 