import streamlit as st
import pandas as pd
import numpy as np
from simulation_functions import run_simulation, visualize_state_timeline, states, default_initial_state
from user_input import validate_matrices, find_matching_matrix, extract_matrices, parse_mapping_file

# Reserve space at the top for potential error messages
error_placeholder = st.empty()
validation_failed = False  # Flag to check if validation failed

# Set parameters for initial state
initial_state = st.sidebar.selectbox("Select Initial State", states)

# File upload options for matrices and demographics
st.sidebar.subheader("Upload Files")
uploaded_file = st.sidebar.file_uploader("Upload Combined Matrix CSV", type="csv")
demographic_file = st.sidebar.file_uploader("Upload Demographic Mapping CSV", type="csv")

# Main application title
st.title("Disease Modeling Platform")

# Add "Rules" section
with st.expander("Rules for Matrices"):
    st.markdown("""
    ### Validation Rules:
    - **General Rules:**
      - All matrices must be 7x7.
      - No values in any matrix can be negative.
      - Rows in the Transition Matrix can sum to 0 only for terminal states (e.g., "Removed" or "Recovered").
      - For active transitions (transition probability > 0):
        - Mean must fall within the Min-Max range.
        - Distribution Type must be non-zero.
      - For inactive transitions (transition probability = 0):
        - Values in other matrices (Mean, Std Dev, Min, Max, and Distribution Type) can remain zero but are not required to be.
    - **Transition Matrix:**
      - Values must be between 0 and 1.
      - Each row must sum to 1 or 0 (for terminal states).
    - **Distribution Type Matrix:**
      - Values must be one of [0, 1, 2, 3, 4, 5].
    - **Mean and Standard Deviation Matrices:**
      - Mean values must fall within the range defined by the Min and Max Cut-Off matrices (inclusive).
      - Standard Deviation can be 0 but cannot be negative.
    - **Min and Max Cut-Off Matrices:**
      - Min values must be less than or equal to Max values.
    - **Error Handling:**
      - For out-of-bounds or invalid values in any matrix, the simulation will fail validation and prompt corrections.
    """)

# Process uploaded files
transition_matrix, distribution_type_matrix = [], []
mean_time_interval_matrix, std_dev_time_interval_matrix = [], []
min_cutoff_matrix, max_cutoff_matrix = [], []

# Process combined matrix file
if uploaded_file:
    try:
        combined_df = pd.read_csv(uploaded_file, header=None)

        def parse_combined_file(combined_df):
            matrix_rows = 7
            num_matrices = 6  # Transition, Distribution Type, Mean, Std Dev, Min, Max
            num_rows = combined_df.shape[0]

            if num_rows % (matrix_rows * num_matrices) != 0:
                raise ValueError(
                    "The combined matrix file does not have the correct number of rows. Ensure it contains sets of 6 matrices, each 7x7."
                )

            matrices = []
            for i in range(0, num_rows, matrix_rows):
                matrices.append(combined_df.iloc[i:i + matrix_rows].to_numpy())

            return [
                np.array(matrices[j::num_matrices])  # Extract matrices by type
                for j in range(num_matrices)
            ]

        (
            transition_matrix,
            distribution_type_matrix,
            mean_time_interval_matrix,
            std_dev_time_interval_matrix,
            min_cutoff_matrix,
            max_cutoff_matrix,
        ) = parse_combined_file(combined_df)

        st.sidebar.success("Combined matrix file uploaded successfully.")

    except Exception as e:
        error_placeholder.error(f"Error reading combined matrix file: {e}")
        st.stop()

# Process demographic mapping file
if demographic_file:
    try:
        mapping_df, demographic_categories = parse_mapping_file(demographic_file)
        st.sidebar.success("Demographic mapping file uploaded successfully.")
    except Exception as e:
        error_placeholder.error(f"Error parsing demographic mapping file: {e}")
        st.stop()

# Input demographics
input_demographics = {}
if demographic_file:
    st.sidebar.subheader("Input Demographics")
    for category in demographic_categories:
        input_value = st.sidebar.text_input(f"Enter value for {category} (Leave blank for wildcard)")
        input_demographics[category] = input_value.strip() if input_value.strip() else "*"  # Treat blanks as wildcards

# Main interface
if st.button("Run Simulation"):
    if not uploaded_file or not demographic_file:
        error_placeholder.error("Please upload both the combined matrix and demographic mapping files.")
        st.stop()

    if validation_failed:
        error_placeholder.error("Cannot run simulation due to validation errors. Please correct them and try again.")
        st.stop()

    if not input_demographics:
        error_placeholder.error("Please provide input demographics.")
        st.stop()

    try:
        # Match input demographics to a matrix set
        matrix_set = find_matching_matrix(input_demographics, mapping_df, demographic_categories)
        matrices = extract_matrices(matrix_set, combined_df)

        # Validate matrices
        validate_matrices(
            matrices["Transition Matrix"],
            matrices["Mean"],
            matrices["Standard Deviation"],
            matrices["Min Cut-Off"],
            matrices["Max Cut-Off"],
            matrices["Distribution Type"],
        )

        # Run the simulation
        simulation_data = run_simulation(
            matrices["Transition Matrix"],
            matrices["Mean"],
            matrices["Standard Deviation"],
            matrices["Min Cut-Off"],
            matrices["Max Cut-Off"],
            matrices["Distribution Type"],
            initial_state,
        )

        # Display simulation results
        st.subheader("Simulation Results")
        st.write("Matched Matrix Set:", matrix_set)
        st.write("Input Demographics:", input_demographics)

        # Display simulation data in table format
        st.subheader("State Timeline")
        simulation_df = pd.DataFrame(simulation_data, columns=["State", "Time Step (minutes)"])
        st.table(simulation_df)

        # Visualize timeline
        fig = visualize_state_timeline(simulation_data)
        st.pyplot(fig)

    except ValueError as e:
        error_placeholder.error(f"Validation Error: {e}")
    except Exception as e:
        error_placeholder.error(f"Unexpected Error: {e}")
