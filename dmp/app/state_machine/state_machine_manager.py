import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .utils.graph_utils import convert_graph_to_matrices, display_matrices, build_nodes_list, get_cytoscape_stylesheet, create_edge_label, format_edge_display_string
from .utils.edge_editor import render_add_edge_section, render_edit_edge_section, render_remove_edge_section
from .utils.graph_visualizer import render_graph_visualization, render_matrix_representation

def manage_state_machines(states):
    """Manage state machines using Streamlit."""
    # Initialize database
    db = StateMachineDB()
    
    # Initialize session state variables if not exists
    if 'selected_machine' not in st.session_state:
        st.session_state.selected_machine = None
    if 'node_positions' not in st.session_state:
        st.session_state.node_positions = {}
    if 'clicked_element' not in st.session_state:
        st.session_state.clicked_element = None
    if 'states' not in st.session_state:
        st.session_state.states = states
    if 'graph_edges' not in st.session_state:
        st.session_state.graph_edges = []
    if 'demographics' not in st.session_state:
        st.session_state.demographics = []

    st.header("Manage State Machines")
    st.write("View your saved state machines, load them, and run simulations.")
    
    # Add disease filter dropdown
    diseases = db.get_unique_diseases()
    all_diseases = ["All Diseases"] + diseases
    
    selected_disease = st.selectbox(
        "Filter by Disease:",
        options=all_diseases,
        key="disease_filter"
    )
    
    # List all saved state machines
    saved_machines = db.list_state_machines()
    if saved_machines:
        # Filter machines by selected disease
        if selected_disease != "All Diseases":
            saved_machines = [machine for machine in saved_machines if machine[2] == selected_disease]
        
        # Create a table of state machines
        st.subheader("Saved State Machines")
        
        # Display state machines in a table format
        for machine in saved_machines:
            disease_name = machine[2] if machine[2] and machine[2] != "Unknown" else "Unknown Disease"
            with st.expander(f"{machine[1]} ({disease_name}) - Created: {machine[3]}, Updated: {machine[4]})"):
                col1, col2 = st.columns(2)
                
                # Load demographics
                demographics = json.loads(machine[5] or "{}")
                
                with col1:
                    st.write("Demographics:")
                    for key, value in demographics.items():
                        st.write(f"- {key}: {value}")
                
                with col2:
                    if st.button("Load", key=f"load_{machine[0]}"):
                        machine_data = db.load_state_machine(machine[0])
                        if machine_data:
                            # Update session state with loaded data
                            st.session_state.states = machine_data["states"]
                            st.session_state.graph_edges = machine_data["edges"]
                            st.session_state.demographics = [
                                {"key": k, "value": v}
                                for k, v in machine_data["demographics"].items()
                            ]
                            st.session_state.selected_machine = machine_data
                            st.success(f"Loaded state machine: {machine_data['name']}")
                            st.rerun()
                    
                    if st.button("Delete", key=f"delete_{machine[0]}"):
                        db.delete_state_machine(machine[0])
                        st.success("State machine deleted")
                        st.rerun()

        # Display the loaded state machine if one is selected
        if st.session_state.selected_machine:
            st.markdown("---")
            st.subheader(f"Loaded State Machine: {st.session_state.selected_machine['name']}")
            
            # Display states in a collapsible view
            with st.expander("States", expanded=False):
                for state in st.session_state.states:
                    st.write(f"- {state}")
            
            
            # Use utility function for matrix representation
            matrices = render_matrix_representation(st.session_state.states, st.session_state.graph_edges)
            
            # Add visual state machine representation
            st.markdown("---")

            # Use utility function for graph visualization
            render_graph_visualization(st.session_state.states, st.session_state.graph_edges, st.session_state.node_positions)
            
            # Add edge editing functionality
            st.markdown("---")
            with st.expander("Edit Edges", expanded=False):
                # Use utility functions for edge management (without nested expanders)
                render_add_edge_section(st.session_state.states, st.session_state.graph_edges, "manager_add", use_expander=False)
                render_edit_edge_section(st.session_state.graph_edges, "manager_edit", use_expander=False)
                render_remove_edge_section(st.session_state.graph_edges, "manager_remove", use_expander=False)
            
            # Add save changes button
            # st.subheader("Save Changes")
            st.write("**Permanently save all changes to the database** (edge modifications, demographics, etc.) so they persist when you reload the page or return later.")
            if st.button("Save Changes to State Machine", key="manager_save_changes"):
                try:
                    # Get the current state machine name
                    machine_name = st.session_state.selected_machine['name']
                    
                    # Create demographics dictionary from session state
                    demographics = {}
                    for demo in st.session_state.demographics:
                        if demo["key"] == "Custom":
                            if demo.get("custom_key") and demo.get("custom_value"):
                                demographics[demo["custom_key"]] = demo["custom_value"]
                        elif demo["key"] and demo["value"]:
                            demographics[demo["key"]] = demo["value"]
                    
                    # Save the updated state machine
                    state_machine_id = db.save_state_machine(
                        machine_name,
                        st.session_state.states,
                        st.session_state.graph_edges,
                        demographics,
                        st.session_state.selected_machine['disease_name'],
                        update_existing=True
                    )
                    
                    st.success(f"✅ Changes permanently saved to database: {machine_name}")
                    
                except Exception as e:
                    st.error(f"❌ Failed to save changes: {str(e)}")
            
            # Display clicked element info if available
            if st.session_state.clicked_element:
                st.write("Selected element:", st.session_state.clicked_element)
            
            # Add simulation controls
            st.markdown("---")
            st.subheader("Simulation Controls")
            
            # Add initial state selection
            initial_state = st.selectbox(
                "Initial State",
                options=st.session_state.states,
                key="initial_state"
            )
            
            # Add start simulation button
            if st.button("Start Simulation"):
                if not st.session_state.graph_edges:
                    st.warning("Please add at least one edge to the state machine before running the simulation.")
                else:
                    # Get the index of the selected initial state
                    initial_state_idx = st.session_state.states.index(initial_state)
                    
                    # Get matrices from the graph
                    matrices = convert_graph_to_matrices(st.session_state.states, st.session_state.graph_edges)
                    
                    # Run the simulation
                    timeline = run_simulation(
                        transition_matrix=matrices["Transition Matrix"],
                        mean_matrix=matrices["Mean Matrix"],
                        std_dev_matrix=matrices["Standard Deviation Matrix"],
                        min_cutoff_matrix=matrices["Min Cutoff Matrix"],
                        max_cutoff_matrix=matrices["Max Cutoff Matrix"],
                        distribution_matrix=matrices["Distribution Type Matrix"],
                        initial_state_idx=initial_state_idx,
                        states=st.session_state.states
                    )
                    
                    # Display the timeline
                    st.subheader("Simulation Timeline")
                    timeline_df = pd.DataFrame(timeline, columns=["State", "Time (hours)"])
                    # Round the time column to 1 decimal place
                    timeline_df["Time (hours)"] = timeline_df["Time (hours)"].round(1)
                    st.dataframe(timeline_df)
                    
                    # Display a visual representation of the timeline
                    st.subheader("Timeline Visualization")
                    for state, time in timeline:
                        st.write(f"{time:.1f} hours: {state}")
            
    else:
        st.write("No saved state machines found") 