import streamlit as st
import numpy as np
import pandas as pd
from Simulation.dmp.core.simulation_functions import run_simulation, visualize_state_timeline

def create_initial_state_vector(num_states, initial_state_name, states_list):
    """Create initial state vector with 1 in the initial state and 0 elsewhere"""
    initial_vector = np.zeros(num_states)
    initial_vector[states_list.index(initial_state_name)] = 1
    return initial_vector

def find_matching_matrix_set(simulation_demographics):
    """Find a matrix set that matches the given demographics"""
    for set_name, matrix_set in st.session_state.matrix_sets.items():
        matches = True
        for demo_name, demo_value in simulation_demographics.items():
            if demo_name == "Age":
                # Handle age range matching
                matrix_age_range = matrix_set["demographics"].get("Age Range")
                if matrix_age_range and matrix_age_range != "*":
                    try:
                        start, end = map(int, matrix_age_range.split("-"))
                        if not (start <= demo_value <= end):
                            matches = False
                            break
                    except ValueError:
                        matches = False
                        break
            else:
                # Direct match for other demographics
                matrix_value = matrix_set["demographics"].get(demo_name)
                if matrix_value != "*" and matrix_value != demo_value:
                    matches = False
                    break
        
        if matches:
            return set_name
    
    return None

def handle_simulation(initial_state):
    """Handle simulation execution and results display"""
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        run_button = st.button("Run Simulation", key="run_sim", use_container_width=True)

    if run_button:
        try:
            if not st.session_state.matrix_sets:
                st.error("Please create at least one matrix set.")
                return

            # Get simulation demographics from session state
            simulation_demographics = {}
            if "sim_age" in st.session_state and st.session_state.sim_age != "*":
                simulation_demographics["Age"] = int(st.session_state.sim_age)
            for demo_name in ["Sex", "Vaccination Status"]:
                key = f"sim_{demo_name}"
                if key in st.session_state and st.session_state[key] != "*":
                    simulation_demographics[demo_name] = st.session_state[key]

            # Find matching matrix set
            matching_set = find_matching_matrix_set(simulation_demographics)
            
            if not matching_set:
                st.error("No matrix set found matching the selected demographics. Please adjust your selection.")
                return

            # Run simulation
            matrices = st.session_state.matrix_sets[matching_set]["matrices"]
            initial_state_idx = st.session_state.states.index(initial_state)
            
            simulation_data = run_simulation(
                matrices["Transition Matrix"],
                matrices["Mean"],
                matrices["Standard Deviation"],
                matrices["Min Cut-Off"],
                matrices["Max Cut-Off"],
                matrices["Distribution Type"],
                initial_state_idx
            )

            display_simulation_results(simulation_data, matching_set)

        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.error("Detailed error information:")
            st.exception(e)

def display_simulation_results(simulation_data, matching_set):
    """Display simulation results and visualizations"""
    st.subheader("Simulation Results")
    st.write("Using Matrix Set:", matching_set)
    
    simulation_df = pd.DataFrame(
        [(st.session_state.states[int(state)], time) for state, time in simulation_data],
        columns=["State", "Time Step (minutes)"]
    )
    st.table(simulation_df)
    
    fig = visualize_state_timeline(simulation_data)
    st.pyplot(fig) 