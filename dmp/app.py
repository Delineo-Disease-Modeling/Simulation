import streamlit as st
import pandas as pd
import numpy as np
from simulation_functions import run_simulation, default_initial_state, visualize_state_timeline

# Define states
states = ["Infected", "Infectious Asymptomatic", "Infectious Symptomatic", "Hospitalized", "ICU", "Removed", "Recovered"]

# Set parameters for initial state
initial_state = st.sidebar.selectbox("Select Initial State", states)

# File upload option for matrices
st.sidebar.subheader("Upload Input File")
uploaded_file = st.sidebar.file_uploader("Upload Combined Matrix CSV", type="csv")

# File upload option for demographic data
st.sidebar.subheader("Upload Demographic Data File")
demographic_file = st.sidebar.file_uploader("Upload Demographic CSV", type="csv")

# Define a flag to check if the file was uploaded
file_uploaded = False
transition_matrix, distribution_type_matrix = [], []
mean_time_interval_matrix, std_dev_time_interval_matrix = [], []
min_cutoff_matrix, max_cutoff_matrix = [], []

# Check if a matrix file is uploaded
if uploaded_file:
    # Load combined matrix file and parse it
    combined_df = pd.read_csv(uploaded_file, header=None)
    file_uploaded = True

    def parse_combined_file(combined_df):
        # Split into 7x7 matrices
        matrix_rows = 7
        matrices = []
        for i in range(0, combined_df.shape[0], matrix_rows):
            matrices.append(combined_df.iloc[i:i+matrix_rows].to_numpy())
        return matrices

    # Unpack matrices from uploaded file
    (transition_matrix, distribution_type_matrix, mean_time_interval_matrix,
     std_dev_time_interval_matrix, min_cutoff_matrix, max_cutoff_matrix) = parse_combined_file(combined_df)

    # Display matrices for verification and editing in the main section
    st.subheader("Uploaded Matrices (Editable)")

    # Transition probabilities setup with unique keys
    st.subheader("Transition Probabilities")
    transition_matrix_display = []
    for i, state in enumerate(states):
        with st.expander(f"From {state}"):
            row = []
            for j, target_state in enumerate(states):
                if i != j:
                    probability = st.slider(
                        f"Probability to {target_state}",
                        min_value=0.0,
                        max_value=1.0,
                        value=float(transition_matrix[i][j]),
                        step=0.01,
                        key=f"prob_{i}_{j}"  # Unique key for each transition probability slider
                    )
                    row.append(probability)
                else:
                    row.append(0.0)
            transition_matrix_display.append(row)

    # Normalize transition probabilities
    transition_matrix_display = np.array(transition_matrix_display)
    for i in range(len(transition_matrix_display)):
        row_sum = np.sum(transition_matrix_display[i])
        if row_sum > 0:
            transition_matrix_display[i] = transition_matrix_display[i] / row_sum

    # Controls for mean and standard deviation of time intervals with unique keys
    st.subheader("Mean Time Intervals and Standard Deviations")
    mean_time_interval_matrix_display = []
    std_dev_time_interval_matrix_display = []
    for i, state in enumerate(states):
        with st.expander(f"From {state}"):
            mean_row = []
            std_dev_row = []
            for j, target_state in enumerate(states):
                if i != j:
                    mean_interval = st.slider(
                        f"Mean Interval to {target_state} (days)",
                        min_value=0,
                        max_value=30,
                        value=int(mean_time_interval_matrix[i][j]),
                        step=1,
                        key=f"mean_{i}_{j}"  # Unique key for each mean time slider
                    )
                    std_dev_interval = st.slider(
                        f"Standard Deviation to {target_state} (days)",
                        min_value=0,
                        max_value=10,
                        value=int(std_dev_time_interval_matrix[i][j]),
                        step=1,
                        key=f"std_dev_{i}_{j}"  # Unique key for each standard deviation slider
                    )
                    mean_row.append(mean_interval)
                    std_dev_row.append(std_dev_interval)
                else:
                    mean_row.append(0)
                    std_dev_row.append(0)
            mean_time_interval_matrix_display.append(mean_row)
            std_dev_time_interval_matrix_display.append(std_dev_row)

    # Convert lists to numpy arrays for compatibility with run_simulation
    transition_matrix_display = np.array(transition_matrix_display)
    mean_time_interval_matrix_display = np.array(mean_time_interval_matrix_display)
    std_dev_time_interval_matrix_display = np.array(std_dev_time_interval_matrix_display)

# Check if a demographic file is uploaded
if demographic_file:
    # Load demographic data
    demographic_df = pd.read_csv(demographic_file)
    st.subheader("Demographic Data")
    st.write(demographic_df)

    # Store demographics for each individual and set up for multiple simulations if needed
    demographic_info = demographic_df.to_dict(orient="records")

# Main interface
st.title("Disease Modeling Simulation")

if st.button("Run Simulation"):
    # Run the simulation with the adjusted parameters
    result_dicts = []
    for individual in demographic_info:
        simulation_data = run_simulation(
            transition_matrix_display, mean_time_interval_matrix_display, std_dev_time_interval_matrix_display, 
            min_cutoff_matrix, max_cutoff_matrix, distribution_type_matrix, 
            initial_state
        )
        
        # Store the result for each individual
        output_dict = individual.copy()
        for state, time_step in simulation_data:
            output_dict[state] = time_step
        result_dicts.append(output_dict)
    
    # Display the simulation timeline
    st.write("Simulation Results for Each Individual")
    result_df = pd.DataFrame(result_dicts)
    st.write(result_df)
    
    # Visualize the timeline for the last individual as an example
    fig = visualize_state_timeline(simulation_data)
    st.pyplot(fig)
