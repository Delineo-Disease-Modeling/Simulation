import streamlit as st
import pandas as pd
import numpy as np
from simulation_functions import run_simulation, default_initial_state, visualize_state_timeline, states
from user_input import validate_matrices  # Importing the validation function directly

# Reserve space at the top for potential error messages
error_placeholder = st.empty()
validation_failed = False  # Flag to check if validation failed

# Set parameters for initial state
initial_state = st.sidebar.selectbox("Select Initial State", states)

# File upload option for matrices
st.sidebar.subheader("Upload Input File")
uploaded_file = st.sidebar.file_uploader("Upload Combined Matrix CSV", type="csv")

# File upload option for demographic data
st.sidebar.subheader("Upload Demographic Data File")
demographic_file = st.sidebar.file_uploader("Upload Demographic CSV", type="csv")

# Define flags and matrices
file_uploaded = False
transition_matrix, distribution_type_matrix = [], []
mean_time_interval_matrix, std_dev_time_interval_matrix = [], []
min_cutoff_matrix, max_cutoff_matrix = [], []

# Process matrix file
if uploaded_file:
    combined_df = pd.read_csv(uploaded_file, header=None)
    file_uploaded = True

    def parse_combined_file(combined_df):
        matrix_rows = 7
        matrices = []
        for i in range(0, combined_df.shape[0], matrix_rows):
            matrices.append(combined_df.iloc[i:i+matrix_rows].to_numpy())
        return matrices

    (transition_matrix, distribution_type_matrix, mean_time_interval_matrix,
     std_dev_time_interval_matrix, min_cutoff_matrix, max_cutoff_matrix) = parse_combined_file(combined_df)

    # Editable matrices in main section
    st.subheader("Uploaded Matrices (Editable)")

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
                        key=f"prob_{i}_{j}"
                    )
                    row.append(probability)
                else:
                    row.append(0.0)
            transition_matrix_display.append(row)

    transition_matrix_display = np.array(transition_matrix_display)
    for i in range(len(transition_matrix_display)):
        row_sum = np.sum(transition_matrix_display[i])
        if row_sum > 0:
            transition_matrix_display[i] = transition_matrix_display[i] / row_sum

    # Mean and Standard Deviation matrices
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
                        key=f"mean_{i}_{j}"
                    )
                    std_dev_interval = st.slider(
                        f"Standard Deviation to {target_state} (days)",
                        min_value=0,
                        max_value=10,
                        value=int(std_dev_time_interval_matrix[i][j]),
                        step=1,
                        key=f"std_dev_{i}_{j}"
                    )
                    mean_row.append(mean_interval)
                    std_dev_row.append(std_dev_interval)
                else:
                    mean_row.append(0)
                    std_dev_row.append(0)
            mean_time_interval_matrix_display.append(mean_row)
            std_dev_time_interval_matrix_display.append(std_dev_row)

    mean_time_interval_matrix_display = np.array(mean_time_interval_matrix_display)
    std_dev_time_interval_matrix_display = np.array(std_dev_time_interval_matrix_display)

    # Distribution type matrix
    st.subheader("Distribution Type Matrix")
    distribution_type_matrix_display = []
    for i, state in enumerate(states):
        with st.expander(f"From {state}"):
            row = []
            for j, target_state in enumerate(states):
                if i != j:
                    dist_type = st.selectbox(
                        f"Distribution Type to {target_state}",
                        options=[0, 1, 2, 3, 4, 5],
                        format_func=lambda x: ["None", "Normal", "Exponential", "Uniform", "Gamma", "Beta"][x],
                        index=int(distribution_type_matrix[i][j]),
                        key=f"dist_type_{i}_{j}"
                    )
                    row.append(dist_type)
                else:
                    row.append(0)
            distribution_type_matrix_display.append(row)
    distribution_type_matrix_display = np.array(distribution_type_matrix_display)

    # Min and Max Cutoff matrices
    st.subheader("Min and Max Cutoff Matrices")
    min_cutoff_matrix_display = []
    max_cutoff_matrix_display = []
    for i, state in enumerate(states):
        with st.expander(f"From {state}"):
            min_row = []
            max_row = []
            for j, target_state in enumerate(states):
                if i != j:
                    min_cutoff = st.slider(
                        f"Min Cutoff to {target_state}",
                        min_value=0,
                        max_value=30,
                        value=int(min_cutoff_matrix[i][j]),
                        step=1,
                        key=f"min_cutoff_{i}_{j}"
                    )
                    max_cutoff = st.slider(
                        f"Max Cutoff to {target_state}",
                        min_value=0,
                        max_value=30,
                        value=int(max_cutoff_matrix[i][j]),
                        step=1,
                        key=f"max_cutoff_{i}_{j}"
                    )
                    min_row.append(min_cutoff)
                    max_row.append(max_cutoff)
                else:
                    min_row.append(0)
                    max_row.append(0)
            min_cutoff_matrix_display.append(min_row)
            max_cutoff_matrix_display.append(max_row)

    min_cutoff_matrix_display = np.array(min_cutoff_matrix_display)
    max_cutoff_matrix_display = np.array(max_cutoff_matrix_display)

    # Run validation and display any error at the top
    try:
        validate_matrices(
            transition_matrix_display,
            mean_time_interval_matrix_display,
            std_dev_time_interval_matrix_display,
            min_cutoff_matrix_display,
            max_cutoff_matrix_display,
            distribution_type_matrix_display
        )
    except ValueError as e:
        error_placeholder.error(f"Validation Error: {e}")
        validation_failed = True  # Set flag if validation fails

# Process demographic file
if demographic_file:
    demographic_df = pd.read_csv(demographic_file)
    st.subheader("Demographic Data")
    st.write(demographic_df)
    demographic_info = demographic_df.to_dict(orient="records")

# Main interface
st.title("Disease Modeling Platform")

if st.button("Run Simulation"):
    if validation_failed:
        error_placeholder.error("Cannot run simulation due to validation errors. Please correct them and try again.")
    else:
        # Run simulation if validation passed
        result_dicts = []
        for individual in demographic_info:
            simulation_data = run_simulation(
                transition_matrix_display, mean_time_interval_matrix_display, std_dev_time_interval_matrix_display, 
                min_cutoff_matrix_display, max_cutoff_matrix_display, distribution_type_matrix_display, 
                initial_state
            )

            # Store results
            output_dict = individual.copy()
            for state, time_step in simulation_data:
                output_dict[state] = time_step
            result_dicts.append(output_dict)
        
        # Display results
        st.write("Simulation Results for Each Individual")
        result_df = pd.DataFrame(result_dicts)
        st.write(result_df)
        
        # Visualize timeline for the last individual
        fig = visualize_state_timeline(simulation_data)
        st.pyplot(fig)
