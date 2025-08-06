# Delineo Infection Simulator

This repository contains a simulation framework for modeling infection spread and profiling different scenarios across regions. It includes tools for simulation setup, data interface, profiling, and visualization.

## Directory Structure

### `dmp/`
Handles Disease Modelling Platform (DMP) functionality, including interfacing with APIs or structured data layers. DMP uses matrices to predict the infection trajectory of an individual. 

### `profiles/`
Contains profiling data (e.g., `.prof`, `.txt`) to analyze performance of key functions like `run_main` and `initialize_dmp_api` as well as `app.py`

### `profiling_results/`
Stores simulation profiling outputs for various dataset sizes (`100`, `1000`, `10000`) to benchmark runtime performance.

### `simulator/`
Main simulation logic and configuration files.

#### Subdirectories:
- `api_testing/`, `api_testing_copy/`: For testing API functionality, with different configurations.
- `barnsdall/`, `hagerstown/`: Regional datasets/configurations.

#### Key Files:
- `config.py`: Contains default simulation configuration settings.
- `data_interface.py`: Manages loading and formatting of external datasets (CSV, JSON, YAML).
- `generate_pattern.py`: Generates movement patterns used in simulations.
- `infection_model.py`: Based on Wells-Reilly model to predict infection probability.
- `infectionmgr.py`: Manages infection state across simulation steps.
- `pap_places.json`, `pap_places.py`: Contains predefined place-based datasets and associated logic.
- `pattern_simple.json`, `patterns_alg.json`: Pattern configuration files.
- `population_info.yaml`: Metadata about the population used in simulations.
- `simulate.py`: Main simulation logic
- `test_loading_data.py`: Unit test or utility to check data loading.
- `visualize.ipynb`: Jupyter Notebook for visualizing simulation outputs.
- `cbg_populations.csv`, `clusters.csv`, `facility_data.json`: Input datasets.

## Root-Level Files

- `app_3.py`, `app_profiling.py`, `app.py`: Simulation applications with various configurations.
- `dmp_functions.py`: Functions supporting DMP operations.
- `simulation_functions.py`: Core functions used across simulation runs.
- `simulator_results.txt`, `simulator_results_1.txt`: Text-based output logs of simulation runs.
- `user_input.py`: Likely processes user configurations or interactive inputs.
- `stream_debug.log`: Debug log for streaming or runtime operations.
- `README.md`, `README_v0.md`: Documentation for project usage and structure.
- `.gitignore`, `LICENSE`: Standard project configuration files.

---

## Getting Started

To run a simulation:

```bash
python app.py
