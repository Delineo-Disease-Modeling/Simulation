"""
Configuration settings for the Delineo simulation system.
This centralizes hardcoded values that were previously scattered across files.
"""
import os

# DMP API settings
DMP_API = {
    # HTTP fallback target, used only when the in-process DMP is unavailable.
    # Accept DMP_API_URL as an alias: the deploy compose sets DMP_API_URL, so
    # without this alias base_url would silently default to localhost:8000 (where
    # nothing listens inside the sim container) and the fallback would never reach
    # the real dmp service.
    "base_url": (
        os.environ.get("DMP_API_BASE_URL")
        or os.environ.get("DMP_API_URL")
        or "http://localhost:8000"
    ),
    "mode": os.environ.get("DMP_MODE", "auto"),
    "timeout_seconds": int(os.environ.get("DMP_API_TIMEOUT_SECONDS", "30")),
    # When true, resolve timelines via the in-process DMP (reads the local
    # state-machine DB directly, with a demographic cache) instead of the
    # per-infection HTTP call. Falls back to HTTP if the dmp package/DB can't
    # be loaded. Set DMP_INPROCESS=0 to force the HTTP path.
    "use_inprocess": os.environ.get("DMP_INPROCESS", "1").lower() in {"1", "true", "yes", "on"},
    "paths": {
        # Default paths for initialization
        # "matrices_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/combined_matrices.csv",
        # "mapping_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/demographic_mapping.csv",
        # "states_path": "/Users/jason/Documents/Academics/Research/Delineo/Simulation/simulator/config_data/custom_states.txt"
        "matrices_path": "/Users/navyamehrotra/Documents/Projects/Delineo/Simulation/simulator/config_data/combined_matrices.csv",
        "mapping_path": "/Users/navyamehrotra/Documents/Projects/Delineo/Simulation/simulator/config_data/demographic_mapping.csv",
        "states_path": "/Users/navyamehrotra/Documents/Projects/Delineo/Simulation/simulator/config_data/custom_states.txt"
    },
    # Mapping from DMP API state names to internal infection states
    "state_mapping": {
        "Infected": "INFECTED",
        "Infectious_Asymptomatic": "INFECTIOUS",
        # Symptomatic infection sets BOTH bits (infectious AND symptomatic) so the
        # SYMPTOMATIC compartment, self-isolation, and case-ascertainment work;
        # asymptomatic stays INFECTIOUS-only. A list value is OR-combined.
        "Infectious_Symptomatic": ["INFECTIOUS", "SYMPTOMATIC"],
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
    # Resolve per-location transmission with the O(n) aggregate Wells-Riley
    # kernel (sum infector quanta once per location/variant, then one infection
    # draw per susceptible) instead of the O(infectors x susceptibles) pairwise
    # kernel. Statistically equivalent per susceptible
    # (1 - prod_i exp(-lambda_i) == 1 - exp(-sum_i lambda_i)), but it consumes a
    # different RNG stream, so output is NOT byte-identical to the pairwise path
    # (validated by ensemble equivalence rather than the golden hash).
    # DEFAULT ON; set DELINEO_AGG_TRANSMISSION=0 to fall back to the pairwise
    # kernel, or override per run via the simdata "aggregate_transmission" field.
    "aggregate_transmission": os.environ.get("DELINEO_AGG_TRANSMISSION", "1").lower()
    in {"1", "true", "yes", "on"},
    # When true, derive the Wells-Riley ventilation term Q per-facility from its
    # physical floor area (Q = ventilation_coeff * clamp(area_m2)) instead of the
    # legacy fixed 150 m^3/hr. Makes transmission density-dependent: small crowded
    # POIs become higher-risk, large airy ones lower-risk, matching the inverse-
    # area scaling of Chang et al. 2021 (Nature). Facilities with no known area
    # fall back to Q=150. DEFAULT ON; set DELINEO_AREA_VENTILATION=0 to restore the
    # legacy fixed-Q behaviour, or override per run via the simdata
    # "area_aware_ventilation" field. NOTE: the transmission *level*
    # (ventilation_coeff) is a physical estimate, not yet calibrated to a target.
    "area_aware_ventilation": os.environ.get("DELINEO_AREA_VENTILATION", "1").lower()
    in {"1", "true", "yes", "on"},
    # Ventilation coefficient c (m^3/hr per m^2 of floor) used when
    # area_aware_ventilation is on: Q = c * area_m2. Physical default 9.0 ~= air
    # changes/hr (3) x ceiling height (3 m). This constant sets the overall
    # transmission *level* and is the single global knob to recalibrate later,
    # separate from the area *shape* it introduces.
    "ventilation_coeff": float(os.environ.get("DELINEO_VENTILATION_COEFF", "9.0")),
    # Floor-area clamp (m^2) before computing Q: winsorizes bad geometry (region
    # polygons recorded as one 200+ km^2 "POI") and sub-room areas. ~ p01..p99 of
    # the observed footprint distribution.
    "area_clamp_min": float(os.environ.get("DELINEO_AREA_CLAMP_MIN", "65.0")),
    "area_clamp_max": float(os.environ.get("DELINEO_AREA_CLAMP_MAX", "70000.0")),
    # External force-of-infection term (open-system coupling). ~85% of a POI's
    # real visitors live outside the simulated cluster; rather than simulate them,
    # they contribute a one-way background quanta source at each POI. The external
    # headcount is reconstructed from the already-simulated internal occupancy:
    # external = n_internal x (1 - f_j)/f_j, where f_j (catchment_fj, emitted by
    # popgen) is the in-cluster visitor share. Those externals act as extra
    # well-mixed infectors with probability external_prevalence of being infectious
    # (one-way: never simulated as agents, never susceptible, never rendered).
    # See docs/MOVEMENT_MODEL_REDESIGN.md (Algorithms) §10.
    # DEFAULT OFF (and external_prevalence defaults to 0, so even flagged-on it is
    # inert) -> golden run bit-identical until deliberately calibrated. Override
    # per run via the simdata "external_foi" / "external_prevalence" fields.
    "external_foi": os.environ.get("DELINEO_EXTERNAL_FOI", "0").lower()
    in {"1", "true", "yes", "on"},
    # P_ext: exogenous probability a given external visitor is infectious. A scalar
    # for now (calibrate against real case data; can grow into a time series). NOT
    # tied to the sim's own prevalence (that re-closes the system / feeds back).
    "external_prevalence": float(os.environ.get("DELINEO_EXTERNAL_PREVALENCE", "0.0")),
    # Average emission factor of an external visitor relative to an unmasked,
    # unvaccinated internal infector (community masking / behaviour). 1.0 = same.
    "external_emit_factor": float(os.environ.get("DELINEO_EXTERNAL_EMIT_FACTOR", "1.0")),
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
    "default_max_length": 72000,        # Default simulation length (50 days in minutes)
    "disease_name": "COVID-19",
    "default_initial_infected_count": 1,
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
        "randseed": True               # Whether to use random seed
    },
    "default_infected_ids": ['160', '43', '47', '4', '36', '9', '14', '19', '27', '22', '3', '5', '6', '7', '8', '10', '11', '12', '13', '15', '16', '17', '18', '20', '21', '23', '24', '25', '26'],
    "variants": ['Delta']               # Default disease variants
}

DELINEO = {
    "DB_URL": os.environ.get("DELINEO_DB_URL", "http://localhost:3000/api/")
}

# Server configuration
SERVER = {
    "host": "0.0.0.0",
    "port": 1870,
    "error_messages": {
        "bad_request": "Bad Request",
        "no_data": "No data sent"
    }
}
