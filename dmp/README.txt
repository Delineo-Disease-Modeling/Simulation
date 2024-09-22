Overview:
This project simulates the progression of individuals through various stages of a disease, based on transition probabilities, time intervals, and demographic information. The system is designed to model how people move through health states such as being infected, hospitalized, and recovered, and it can accommodate a wide range of disease progression scenarios using customizable transition matrices and time intervals.

The simulation is particularly useful for understanding how different demographic groups (e.g., age, sex, vaccination status) may experience different disease timelines. For example, it can help answer questions like:
How long does it take for a vaccinated person to recover compared to an unvaccinated person?
What is the probability that an elderly individual moves from infection to hospitalization versus recovery?
How does the average time spent in the ICU differ across demographic groups?

Each individual's progression through disease states (e.g., Infected, Hospitalized, ICU, Recovered, etc.) is determined by predefined transition probabilities and time intervals, which can be drawn from a variety of statistical distributions (e.g., Normal, Exponential, Gamma, Beta). These distributions allow for flexibility in modeling real-world scenarios, where disease progression may not follow a strict timeline but varies based on individual characteristics and external factors.

Example Disease Timeline:
Stage 1: An individual starts in the Infected state.
Stage 2: They may transition to Infectious Symptomatic (IS) or Infectious Asymptomatic (IA) after a certain number of days.
Stage 3: If they are symptomatic, they could move to Hospitalized after a predefined time interval.
Stage 4: From the Hospitalized state, the individual may either recover or require intensive care (ICU).
Stage 5: Finally, the individual may either be Removed (due to death) or Recovered based on the simulation's transition rules.

This project allows you to explore the impact of various factors on the timeline, such as:
Demographics: Age, vaccination status, or pre-existing conditions.
Transition Probabilities: The likelihood of moving between disease states.
Time Intervals: How long an individual stays in each state, based on different statistical distributions.
By running multiple simulations, you can analyze trends and make predictions about how different populations might respond to an epidemic or treatment intervention.

Running a Custom Simulation:
The system is fully customizable, allowing users to define:
Transition Matrices: Control the probabilities of moving between disease states.
Time Intervals: Sampled from statistical distributions (Normal, Exponential, Uniform, Gamma, or Beta) to model the duration spent in each state.
Demographic Factors: Assign specific transition matrices to different demographic groups to study how disease progression varies by population.
The simulation outputs a CSV file that captures each individual's complete disease timeline, from infection to recovery or removal, along with their demographic details.



How the Code Works:
user_input.py:
The process_dataframes function in user_input.py reads input data from CSV files (transition matrices, demographic info, and time interval parameters). It validates the data and then calls the run_simulation function from simulation_functions.py to perform the simulation.

The input data includes:
Transition matrices
Mean and standard deviation matrices for time intervals
Minimum and maximum cutoff matrices
A distribution type matrix (which specifies the distribution for each transition)
Demographic information

The code validates the input data to ensure it meets the necessary requirements (matrix dimensions, valid values, etc.). After validation, the simulation is run with the provided parameters.

simulation_functions.py:
This file contains the core simulation logic. It defines the states of the system, the transition functions, and the time interval sampling logic.
The run_simulation function iterates through each simulation step for the desired number of iterations, transitioning individuals between states based on the probabilities provided in the transition matrices and sampling time intervals from specified distributions.

The available distributions for time intervals are:
Normal distribution (Type 1)
Exponential distribution (Type 2)
Uniform distribution (Type 3)
Gamma distribution (Type 4)
Beta distribution (Type 5)

Assumptions About the Input:
Transition Matrices:
These matrices must be square with dimensions 7x7.
Each row in the transition matrix represents probabilities of moving from one state to another.
Each row must sum to 1, and all values must be between 0 and 1.
Distribution Type Matrix:
A 7x7 matrix where each cell contains a number indicating the distribution type to be used for the corresponding state transition.
1: Normal distribution
2: Exponential distribution
3: Uniform distribution
4: Gamma distribution
5: Beta distribution

Mean and Standard Deviation Matrices:
These matrices provide the mean and standard deviation for time intervals between transitions (in cases where Normal, Gamma, or Beta distributions are used).

Min and Max Cutoff Matrices:
These define the range for the Uniform and Beta distributions and provide lower and upper bounds for sampled time intervals.

Demographic Information:
Demographic data must be provided in a CSV file. The file should have columns for various demographic factors (e.g., Sex, Age, Is_Vaccinated, and Matrix_Set).

Below is a simplified diagram of the transition matrix:

          Infected      IS             IA      Hospitalized  ICU  Removed  Recovered
Infected     0.0        0.7          0.3         0.0       0.0    0.0      0.0
IS           0.0        0.0          0.5         0.2       0.1    0.0      0.2
IA           0.0        0.0          0.0         0.4       0.2    0.0      0.4
Hospitalized 0.0        0.0          0.0         0.0       0.7    0.0      0.3
ICU          0.0        0.0          0.0         0.0       0.0    0.4      0.6
Removed      0.0        0.0          0.0         0.0       0.0    1.0      0.0
Recovered    0.0        0.0          0.0         0.0       0.0    0.0      1.0

Each box indicates the probability of going from the row to the column state.

To run the code:

Ensure Python 3.x is installed on your system.
Place your input CSV files (combined_matrices.csv and demographic_info.csv) in the same directory as the Python files.
Execute user_input.py using a Python interpreter.
The simulation results will be printed to the console.