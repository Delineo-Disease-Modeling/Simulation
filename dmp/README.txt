Overview:
This project consists of two Python files: user_input.py and simulation_functions.py. 
The purpose of this project is to simulate a dynamic system with multiple states and transitions, utilizing provided transition matrices and demographic information. 
The simulation tracks the progression of individuals through various states over time.

How the Code Works:
user_input.py:
The process_dataframes function in user_input.py reads input data from CSV files, validates the data, 
and then calls the run_simulation function from simulation_functions.py to perform the simulation.
The input data includes transition matrices, mean, standard deviation, min and max cutoff matrices for time intervals, 
a distribution type matrix, and demographic information.
The code validates the input data to ensure it meets certain requirements, such as matrix dimensions and valid values.
After processing the data, the simulation is run with the provided parameters.

simulation_functions.py
This file contains the core simulation logic.
It defines the states of the system, transition functions, and time interval sampling.
The run_simulation function iterates through desired iterations, transitioning individuals between states based on probabilities
and sampling time intervals from distributions.

Assumptions About the Input:
Transition matrices must be square matrices with dimensions 7x7.
Each row in the transition matrix must add up to 1 and each value must be between 0 and 1. 
The distribution type matrix should be a 7x7 matrix where each cell contains a number indicating the distribution type to be used for that transition.
A value of 1 in a cell indicates a normal distribution should be used for that transition.
A value of 2 indicates an exponential distribution.
A value of 3 indicates a uniform distribution.
Mean and standard deviation values can be decimals, but cannot be negative.
Distribution, min-cutoff, and max-cutoff values must be positive whole numbers. 
Demographic information is assumed to be provided in a CSV file with columns for sex, age, and vaccination status.

Below is a simplified diagram of the transition matrix:

          Infected  Symptomatic  Infectious  Hospitalized  ICU  Removed  Recovered
Infected     0.0        0.7          0.3         0.0       0.0    0.0      0.0
Symptomatic  0.0        0.0          0.5         0.2       0.1    0.0      0.2
Infectious   0.0        0.0          0.0         0.4       0.2    0.0      0.4
Hospitalized 0.0        0.0          0.0         0.0       0.7    0.0      0.3
ICU          0.0        0.0          0.0         0.0       0.0    0.4      0.6
Removed      0.0        0.0          0.0         0.0       0.0    1.0      0.0
Recovered    0.0        0.0          0.0         0.0       0.0    0.0      1.0

Each box indicates the probability of going from the row to the column state.

To run the code:

Ensure Python 3.x is installed on your system.
Place your input CSV files (matrices.csv and demographic_info.csv) in the same directory as the Python files.
Execute user_input.py using a Python interpreter.
The simulation results will be printed to the console.