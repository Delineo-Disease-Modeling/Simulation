import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .state_editor import validate_matrices
from streamlit_javascript import st_javascript
from .disease_configurations import get_disease_template, get_available_diseases, get_disease_parameters
from .utils.graph_utils import convert_graph_to_matrices, display_matrices, build_nodes_list, get_cytoscape_stylesheet, create_edge_label, format_edge_display_string
from .utils.edge_editor import render_add_edge_section, render_edit_edge_section, render_remove_edge_section
from .utils.graph_visualizer import render_graph_visualization, render_matrix_representation

def create_state_machine(states):
    """Create a graph visualization of disease states using Cytoscape.js"""
    # Initialize database
    db = StateMachineDB()
    
    # Initialize graph state in session state if not exists
    if 'graph_edges' not in st.session_state:
        st.session_state.graph_edges = []
    if 'node_positions' not in st.session_state:
        st.session_state.node_positions = {}
    if 'clicked_element' not in st.session_state:
        st.session_state.clicked_element = None
    if 'new_edge' not in st.session_state:
        st.session_state.new_edge = None
    if 'editing_mode' not in st.session_state:
        st.session_state.editing_mode = "new"
    
    st.header("Create A State Machine")
    
    # Add mode selection for editing existing machines at the top
    st.subheader("Start New or Load Existing")
    mode = st.radio(
        "Choose your mode:",
        options=["Create From Scratch", "Edit From Existing State Machine"],
        key="mode_selection"
    )
    
    if mode == "Edit From Existing State Machine":
        # Load existing state machines
        existing_machines = db.list_state_machines()
        if existing_machines:
            machine_names = [machine[1] for machine in existing_machines]  # machine[1] is the name
            selected_machine = st.selectbox(
                "Select State Machine to Edit From:",
                options=machine_names,
                key="selected_machine_name"
            )
            
            if st.button("Load State Machine"):
                # Find the selected machine
                selected_machine_id = None
                for machine in existing_machines:
                    if machine[1] == selected_machine:  # machine[1] is the name
                        selected_machine_id = machine[0]  # machine[0] is the id
                        break
                
                if selected_machine_id:
                    # Load full state machine data
                    selected_machine_data = db.load_state_machine(selected_machine_id)
                    
                    if selected_machine_data:
                        # Load the state machine data into session state
                        st.session_state.graph_edges = selected_machine_data['edges']
                        st.session_state.demographics = []
                        for key, value in selected_machine_data['demographics'].items():
                            # Check if this is a standard demographic (Sex, Age, Vaccination) or custom
                            if key in ["Sex", "Age", "Vaccination"]:
                                st.session_state.demographics.append({"key": key, "value": value})
                            elif key.startswith("Disease_"):
                                # This is a disease parameter, handle separately
                                param_name = key.replace("Disease_", "").lower()
                                if 'disease_parameters' not in st.session_state:
                                    st.session_state.disease_parameters = {}
                                st.session_state.disease_parameters[param_name] = value
                            else:
                                # This is a custom demographic
                                st.session_state.demographics.append({
                                    "key": "Custom", 
                                    "value": f"{key}={value}",
                                    "custom_key": key,
                                    "custom_value": value
                                })
                        st.session_state.editing_mode = "edit"
                        st.session_state.editing_machine_id = selected_machine_data['id']
                        st.success(f"Loaded state machine: {selected_machine}")
                        st.rerun()
                    else:
                        st.error("Failed to load state machine data")
        else:
            st.warning("No existing state machines found. Please create a new one.")
            st.session_state.editing_mode = "new"
    
    elif mode == "Create From Scratch":
        if st.button("Start New State Machine"):
            # Clear session state for new machine
            st.session_state.graph_edges = []
            st.session_state.node_positions = {}
            st.session_state.demographics = []
            st.session_state.editing_mode = "new"
            if 'editing_machine_id' in st.session_state:
                del st.session_state.editing_machine_id
            st.success("Started new state machine")
            st.rerun()
    
    # Add disease selection and template application
    st.markdown("---")
    st.subheader("Disease Selection & Template")
    
    # Disease selection with templates
    disease_options = get_available_diseases() + ["Custom Disease"]
    
    selected_disease = st.selectbox(
        "Select Disease:",
        options=disease_options,
        key="disease_selection"
    )
    
    # Custom disease name input
    if selected_disease == "Custom Disease":
        custom_disease_name = st.text_input(
            "Enter Custom Disease Name:",
            key="custom_disease_name"
        )
        disease_name = custom_disease_name if custom_disease_name else "Unknown"
        
        # Add state editor for custom diseases
        st.markdown("---")
        st.subheader("Define States for Custom Disease")
        st.write("Enter the states for your custom disease (one per line):")
        
        # Initialize states in session state if not exists
        if 'states' not in st.session_state:
            st.session_state.states = ["State1", "State2"]
        if 'previous_states' not in st.session_state:
            st.session_state.previous_states = st.session_state.states.copy()
        
        # State editing interface
        states_text = "\n".join(st.session_state.states)
        new_states_text = st.text_area("States:", value=states_text, height=150, key="custom_states_text")
        
        # Convert textarea to list of states
        new_states = [state.strip() for state in new_states_text.split("\n") if state.strip()]
        
        # Update states if changed
        if new_states != st.session_state.previous_states:
            if len(new_states) >= 2:
                st.session_state.states = new_states
                st.session_state.previous_states = new_states.copy()
                st.success(f"✅ Updated states: {len(new_states)} states defined")
            else:
                st.error("You must have at least 2 states!")
    else:
        disease_name = selected_disease
    
    # Apply disease template if a predefined disease is selected
    if selected_disease != "Custom Disease" and selected_disease in get_available_diseases():
        template = get_disease_template(selected_disease)
        if template and template['states']:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.info(f"📋 **{selected_disease} Template Available**: {template['description']}")
            with col2:
                if st.button(f"Apply {selected_disease} Template", key="apply_disease_template"):
                    # Update states with template states
                    st.session_state.states = template['states'].copy()
                    st.success(f"✅ Applied {selected_disease} template with {len(template['states'])} states")
                    st.rerun()
            
            # Show template info
            with st.expander(f"View {selected_disease} Template Details", expanded=False):
                st.write("**Predefined States:**")
                for i, state in enumerate(template['states'], 1):
                    st.write(f"{i}. {state}")
                
                st.write("**Typical Transitions:**")
                for transition in template['typical_transitions']:
                    st.write(f"• {transition}")
        elif template:
            st.warning(f"⚠️ {selected_disease} template is not yet defined. Please use the Disease Configurations tab to define it.")
    
    # Add disease-specific parameters section
    if selected_disease != "Custom Disease" and selected_disease in get_available_diseases():
        disease_parameters = get_disease_parameters(selected_disease)
        if disease_parameters:
            st.markdown("---")
            st.subheader("Disease-Specific Parameters")
            st.write("Configure disease-specific parameters for your model:")
            
            # Initialize disease parameters in session state if not exists
            if 'disease_parameters' not in st.session_state:
                st.session_state.disease_parameters = {}
            
            # Create parameter inputs
            for param_name, param_options in disease_parameters.items():
                selected_value = st.selectbox(
                    f"{param_name.title()}:",
                    options=param_options,
                    key=f"disease_param_{param_name}",
                    index=0
                )
                st.session_state.disease_parameters[param_name] = selected_value
    
    # Add edge creation interface
    st.markdown("---")
    st.subheader("Edge Management")
    
    # Use utility functions for edge management
    render_add_edge_section(st.session_state.states, st.session_state.graph_edges, "creator_add")
    render_edit_edge_section(st.session_state.graph_edges, "creator_edit")
    render_remove_edge_section(st.session_state.graph_edges, "creator_remove")

    # Add graph visualization
    st.markdown("---")
    
    # Use utility function for matrix representation
    matrices = render_matrix_representation(st.session_state.states, st.session_state.graph_edges)

    # Use utility function for graph visualization
    render_graph_visualization(st.session_state.states, st.session_state.graph_edges, st.session_state.node_positions)

    # Listen for node position updates from JS and persist them (single st_javascript call)
    msg = st_javascript("""
        new Promise((resolve) => {
            window.addEventListener("message", (event) => {
                if (event.data && event.data.type === "node_position") {
                    resolve(event.data);
                }
            }, { once: true });
        });
    """)

    if msg and msg.get("type") == "node_position":
        node_id = msg["id"]
        x = msg["x"]
        y = msg["y"]
        st.session_state.node_positions[node_id] = {"x": x, "y": y}
        st.rerun()

    # Display clicked element info if available
    if st.session_state.clicked_element:
        st.write("Selected element:", st.session_state.clicked_element)

    # Add demographics interface
    st.markdown("---")
    st.subheader("Demographics")
    
    # Dynamic demographic inputs
    st.write("Demographic Values")

    # Initialize demographics in session state if not exists
    if 'demographics' not in st.session_state:
        st.session_state.demographics = []

    # Add new demographic button
    if st.button("Add Demographic"):
        st.session_state.demographics.append({"key": "", "value": ""})
        st.rerun()

    # Display existing demographics
    for i, demo in enumerate(st.session_state.demographics):
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            demo_type = st.selectbox(
                "Demographic Type",
                options=["", "Sex", "Age", "Vaccination", "Custom"],
                index=0 if demo["key"] == "" else (1 if demo["key"] == "Sex" else 2 if demo["key"] == "Age" else 3 if demo["key"] == "Vaccination" else 4),
                key=f"demo_type_{i}"
            )
            st.session_state.demographics[i]["key"] = demo_type
        with col2:
            if demo_type == "Sex":
                demo_value = st.selectbox(
                    "Value",
                    options=["", "Male", "Female"],
                    index=0 if demo["value"] == "" else (1 if demo["value"] == "Male" else 2),
                    key=f"demo_value_{i}"
                )
            elif demo_type == "Age":
                demo_value = st.selectbox(
                    "Value",
                    options=["", "0-18", "19-64", "65+"],
                    index=0 if demo["value"] == "" else (1 if demo["value"] == "0-18" else 2 if demo["value"] == "19-64" else 3),
                    key=f"demo_value_{i}"
                )
            elif demo_type == "Vaccination":
                demo_value = st.selectbox(
                    "Value",
                    options=["", "Unvaccinated", "Partially", "Fully"],
                    index=0 if demo["value"] == "" else (1 if demo["value"] == "Unvaccinated" else 2 if demo["value"] == "Partially" else 3),
                    key=f"demo_value_{i}"
                )
            elif demo_type == "Custom":
                col_custom1, col_custom2 = st.columns(2)
                with col_custom1:
                    custom_key = st.text_input(
                        "Custom Name",
                        value=demo.get("custom_key", ""),
                        key=f"custom_key_{i}"
                    )
                    st.session_state.demographics[i]["custom_key"] = custom_key
                with col_custom2:
                    custom_value = st.text_input(
                        "Custom Value",
                        value=demo.get("custom_value", ""),
                        key=f"custom_value_{i}"
                    )
                    st.session_state.demographics[i]["custom_value"] = custom_value
                demo_value = f"{custom_key}={custom_value}" if custom_key and custom_value else ""
            else:
                demo_value = st.text_input(
                    "Value",
                    value=demo["value"],
                    key=f"demo_value_{i}"
                )
            st.session_state.demographics[i]["value"] = demo_value
        with col3:
            if st.button("Remove", key=f"remove_demo_{i}"):
                st.session_state.demographics.pop(i)
                st.rerun()

    # Add save interface
    st.markdown("---")
    st.subheader("Save State Machine")
    
    # Create demographics dictionary
    demographics = {}
    for demo in st.session_state.demographics:
        if demo["key"] == "Custom":
            if demo.get("custom_key") and demo.get("custom_value"):
                demographics[demo["custom_key"]] = demo["custom_value"]
        elif demo["key"] and demo["value"]:
            demographics[demo["key"]] = demo["value"]
    
    # Create state machine name with disease parameters
    name_parts = [disease_name]
    
    # Add disease parameters to name
    if 'disease_parameters' in st.session_state and st.session_state.disease_parameters:
        for param_name, param_value in st.session_state.disease_parameters.items():
            name_parts.append(f"{param_name}={param_value}")
    
    # Add demographics to name
    if demographics:
        for key, value in demographics.items():
            name_parts.append(f"{key}={value}")
    
    state_machine_name = " | ".join(name_parts) if len(name_parts) > 1 else f"{disease_name} | Default"

    # Show different button text based on mode
    save_button_text = "Update State Machine" if st.session_state.editing_mode == "edit" else "Save State Machine"
    
    if st.button(save_button_text):
        if state_machine_name:
            # Run validation
            validation_issues = validate_matrices(st.session_state.states, st.session_state.graph_edges)
            if validation_issues:
                st.error("❌ Validation failed. Please fix the following issues before saving:")
                for issue in validation_issues:
                    st.error(f"- {issue}")
            else:
                # If valid, save or update the state machine
                try:
                    state_machine_id = db.save_state_machine(
                        state_machine_name,
                        st.session_state.states,
                        st.session_state.graph_edges,
                        demographics,
                        disease_name,
                        update_existing=True  # This will update existing or create new
                    )
                    
                    if st.session_state.editing_mode == "edit":
                        st.success(f"✅ Updated state machine: {state_machine_name}")
                    else:
                        st.success(f"✅ Saved new state machine: {state_machine_name}")
                        
                except ValueError as e:
                    st.error(f"❌ Error: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Failed to save state machine: {str(e)}")
        else:
            st.error("Please provide at least one demographic value")