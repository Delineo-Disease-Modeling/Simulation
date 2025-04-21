import streamlit as st
import numpy as np
import pandas as pd
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from core.simulation_functions import run_simulation
from cli.user_input import find_matching_matrix, extract_matrices

def create_initial_state_vector(num_states, initial_state_name, states_list):
    """Create initial state vector with 1 in the initial state and 0 elsewhere"""
    initial_vector = np.zeros(num_states)
    initial_vector[states_list.index(initial_state_name)] = 1
    return initial_vector

def find_matching_matrix_set(simulation_demographics, matrix_sets):
    """Find the best matching matrix set for given demographics"""
    if not matrix_sets:
        st.warning("No matrix sets available. Using default Matrix_Set_1")
        return "Matrix_Set_1"
    
    # Convert integer age to age range if needed
    if "Age" in simulation_demographics and isinstance(simulation_demographics["Age"], int):
        age = simulation_demographics["Age"]
        if age <= 18:
            simulation_demographics["Age"] = "0-18"
        elif age <= 64:
            simulation_demographics["Age"] = "19-64"
        else:
            simulation_demographics["Age"] = "65+"  # This range includes all ages above 64
    
    try:
        # Use the same find_matching_matrix function as the API
        matching_set = find_matching_matrix(simulation_demographics, st.session_state.mapping_df, st.session_state.demographic_categories)
        if not matching_set:
            st.warning("No matching matrix set found. Using default Matrix_Set_1")
            return "Matrix_Set_1"
        return matching_set
    except ValueError:
        st.warning("Error during matrix matching. Using default Matrix_Set_1")
        return "Matrix_Set_1"

def run_single_simulation(simulation_demographics, initial_state):
    """Run a single simulation and return the timeline"""
    if not st.session_state.matrix_sets:
        st.warning("No matrix sets available. Please upload matrix files first.")
        return None
        
    # Find matching matrix set
    matching_set = find_matching_matrix_set(simulation_demographics, st.session_state.matrix_sets)
    
    if not matching_set:
        st.error("No matching matrix set found")
        return None
    
    # Get matrices from the matching set
    matrix_set = st.session_state.matrix_sets[matching_set]
    matrices = matrix_set["matrices"]
    
    # Get initial state index and ensure it's a scalar integer
    initial_state_idx = int(st.session_state.states.index(initial_state))
    
    # Run simulation
    timeline = run_simulation(
        matrices["Transition Matrix"],
        matrices["Mean"],
        matrices["Standard Deviation"],
        matrices["Min Cut-Off"],
        matrices["Max Cut-Off"],
        matrices["Distribution Type"],
        initial_state_idx,
        st.session_state.states
    )
    
    return timeline

def display_simulation_results(simulation_data, matching_set):
    """Display simulation results and visualizations"""
    st.subheader("Simulation Results")
    st.write("Using Matrix Set:", matching_set)
    
    # Format timeline - state is already a string, no need to convert
    timeline = [(state, time) for state, time in simulation_data]
    
    # Display timeline in a table
    simulation_df = pd.DataFrame(timeline, columns=["State", "Time Step (hours)"])
    st.table(simulation_df)
    
    # Print timeline in hours like the API
    st.subheader("Timeline (hours)")
    for state, time in timeline:
        hours = time 
        st.write(f"{hours:.2f} hours: {state}")

def handle_simulation(initial_state):
    """Handle the simulation process"""
    if not st.session_state.matrix_sets:
        st.warning("Please upload matrix files first to run simulations.")
        return
        
    # Get simulation demographics from session state
    simulation_demographics = st.session_state.get("simulation_demographics", {})
    
    # Add run simulation button
    if st.button("Run Simulation"):
        # Run simulation
        timeline = run_single_simulation(simulation_demographics, initial_state)
        
        if timeline:
            # Find matching matrix set for display
            matching_set = find_matching_matrix_set(simulation_demographics, st.session_state.matrix_sets)
            display_simulation_results(timeline, matching_set) 