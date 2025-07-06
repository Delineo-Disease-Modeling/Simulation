import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .state_editor import validate_matrices
from streamlit_javascript import st_javascript
from .disease_configurations import get_disease_template, get_available_diseases, get_disease_parameters, get_disease_edges
from .utils.graph_utils import convert_graph_to_matrices, display_matrices, build_nodes_list, get_cytoscape_stylesheet, create_edge_label, format_edge_display_string
from .utils.edge_editor import render_add_edge_section, render_edit_edge_section, render_remove_edge_section
from .utils.graph_visualizer import render_graph_visualization, render_matrix_representation

def create_state_machine(states):
    """Create a graph visualization of disease states using Cytoscape.js with progressive disclosure"""
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
    if 'current_step' not in st.session_state:
        st.session_state.current_step = 1
    if 'disease_name' not in st.session_state:
        st.session_state.disease_name = "COVID-19"
    
    st.header("Create A State Machine")
    
    # Define workflow steps
    workflow_steps = {
        1: "Choose Mode",
        2: "Disease & Parameters", 
        3: "Edge Management",
        4: "Demographics & Save"
    }
    
    # Progress indicator
    st.markdown("### Workflow Progress")
    cols = st.columns(len(workflow_steps))
    for i, (step_num, step_name) in enumerate(workflow_steps.items()):
        with cols[i]:
            if st.session_state.current_step == step_num:
                st.markdown(f"**{step_num}. {step_name}** 🎯")
            elif st.session_state.current_step > step_num:
                st.markdown(f"~~{step_num}. {step_name}~~ ✅")
            else:
                st.markdown(f"{step_num}. {step_name}")
    
    st.markdown("---")
    
    # Step 1: Choose Mode
    if st.session_state.current_step == 1:
        st.subheader("Step 1: Choose Mode")
        st.write("Start by choosing whether to create a new state machine or load an existing one.")
        
        # Add mode selection for editing existing machines
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
                            st.session_state.disease_name = selected_machine_data.get('disease_name', 'COVID-19')
                            st.session_state.states = selected_machine_data.get('states', ["State1", "State2"])
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
                            st.session_state.current_step = 2  # Go to disease selection step
                            st.success(f"Loaded state machine: {selected_machine}. You can now modify it through the workflow.")
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
                st.session_state.disease_name = "COVID-19"
                if 'editing_machine_id' in st.session_state:
                    del st.session_state.editing_machine_id
                st.session_state.current_step = 2
                st.success("Started new state machine")
                st.rerun()
    
    # Step 2: Disease Selection and Parameters
    elif st.session_state.current_step == 2:
        st.subheader("Step 2: Disease Selection & Parameters")
        st.write("Select a disease and configure its parameters.")
        
        # Disease selection with templates
        disease_options = get_available_diseases() + ["Custom Disease"]
        
        # Determine the index for the selected disease
        selected_disease_index = 0
        if st.session_state.disease_name in disease_options:
            selected_disease_index = disease_options.index(st.session_state.disease_name)
        elif st.session_state.disease_name not in get_available_diseases():
            # If it's a custom disease, select "Custom Disease" option
            selected_disease_index = len(disease_options) - 1
        
        selected_disease = st.selectbox(
            "Select Disease:",
            options=disease_options,
            index=selected_disease_index,
            key="disease_selection"
        )
        
        # Custom disease name input
        if selected_disease == "Custom Disease":
            custom_disease_name = st.text_input(
                "Enter Custom Disease Name:",
                value=st.session_state.disease_name if st.session_state.disease_name not in get_available_diseases() else "",
                key="custom_disease_name"
            )
            st.session_state.disease_name = custom_disease_name if custom_disease_name else "COVID-19"
            
            # Add state editor for custom diseases
            st.markdown("---")
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
            st.session_state.disease_name = selected_disease
        
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
                        # Load predefined edges if available
                        predefined_edges = get_disease_edges(selected_disease)
                        if predefined_edges:
                            st.session_state.graph_edges = predefined_edges
                            st.success(f"✅ Applied {selected_disease} template with {len(template['states'])} states and {len(predefined_edges)} predefined edges")
                        else:
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
                    
                    # Show predefined edges if available
                    predefined_edges = get_disease_edges(selected_disease)
                    if predefined_edges:
                        st.write("**Predefined Edges:**")
                        st.write(f"✅ Template includes {len(predefined_edges)} predefined edges with default framework values")
                        st.write("⚠️ **Important**: You'll need to configure the transition probabilities, timing, and other parameters with your own values.")
                        st.write("The template provides the structure - you provide the specific parameters for your model.")
            elif template:
                st.warning(f"⚠️ {selected_disease} template is not yet defined. Please use the Disease Configurations tab to define it.")
        
        # Add disease-specific parameters section (only for COVID-19 variants)
        if selected_disease == "COVID-19":
            disease_parameters = get_disease_parameters(selected_disease)
            if disease_parameters:
                st.markdown("---")
                st.write("Configure disease-specific parameters for your model:")
                
                # Initialize disease parameters in session state if not exists
                if 'disease_parameters' not in st.session_state:
                    st.session_state.disease_parameters = {}
                
                # Create parameter inputs
                for param_name, param_options in disease_parameters.items():
                    # Determine the index for the selected parameter value
                    selected_param_index = 0
                    if param_name in st.session_state.disease_parameters:
                        current_value = st.session_state.disease_parameters[param_name]
                        if current_value in param_options:
                            selected_param_index = param_options.index(current_value)
                    
                    selected_value = st.selectbox(
                        f"{param_name.title()}:",
                        options=param_options,
                        index=selected_param_index,
                        key=f"disease_param_{param_name}"
                    )
                    st.session_state.disease_parameters[param_name] = selected_value
        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Mode Selection"):
                st.session_state.current_step = 1
                st.rerun()
        with col3:
            if st.button("Next: Edge Management →"):
                st.session_state.current_step = 3
                st.rerun()
    
    # Step 3: Edge Management with Visualization
    elif st.session_state.current_step == 3:
        st.subheader("Step 3: Edge Management")
        st.write("Define the transitions between states and visualize your state machine.")
        
        # Show current states for reference
        if 'states' in st.session_state and st.session_state.states:
            with st.expander("Current States", expanded=False):
                for i, state in enumerate(st.session_state.states, 1):
                    st.write(f"{i}. {state}")
        
        # Use utility functions for edge management
        render_add_edge_section(st.session_state.states, st.session_state.graph_edges, "creator_add")
        render_edit_edge_section(st.session_state.graph_edges, "creator_edit")
        render_remove_edge_section(st.session_state.graph_edges, "creator_remove")
        
        # Show current edges
        if st.session_state.graph_edges:
            st.write("**Current Edges:**")
            for edge in st.session_state.graph_edges:
                st.write(f"• {edge['data']['source']} → {edge['data']['target']} (Rate: {edge['data'].get('transition_prob', 1.0)})")
        
        # Graph visualization
        st.markdown("---")
        st.write("**Visual Representation:**")
        
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
        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Disease Config"):
                st.session_state.current_step = 2
                st.rerun()
        with col3:
            if st.button("Next: Demographics & Save →"):
                st.session_state.current_step = 4
                st.rerun()
    
    # Step 4: Demographics and Save
    elif st.session_state.current_step == 4:
        st.subheader("Step 4: Demographics & Save")
        st.write("Configure demographic parameters and save your state machine.")
        
        # Dynamic demographic inputs
        st.write("**Demographic Values:**")

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
        
        # Save interface
        st.markdown("---")
        st.write("**Save State Machine:**")
        
        # Create demographics dictionary
        demographics = {}
        for demo in st.session_state.demographics:
            if demo["key"] == "Custom":
                if demo.get("custom_key") and demo.get("custom_value"):
                    demographics[demo["custom_key"]] = demo["custom_value"]
            elif demo["key"] and demo["value"]:
                demographics[demo["key"]] = demo["value"]
        
        # Create state machine name with disease parameters
        name_parts = [st.session_state.disease_name]
        
        # Add disease parameters to name
        if 'disease_parameters' in st.session_state and st.session_state.disease_parameters:
            for param_name, param_value in st.session_state.disease_parameters.items():
                name_parts.append(f"{param_name}={param_value}")
        
        # Add demographics to name
        if demographics:
            for key, value in demographics.items():
                name_parts.append(f"{key}={value}")
        
        state_machine_name = " | ".join(name_parts) if len(name_parts) > 1 else f"{st.session_state.disease_name} | Default"

        # Show different button text based on mode
        save_button_text = "Update State Machine" if st.session_state.editing_mode == "edit" else "Save State Machine"
        
        # Navigation and save buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Edge Management"):
                st.session_state.current_step = 3
                st.rerun()
        with col2:
            if st.button("Start Over"):
                st.session_state.current_step = 1
                st.session_state.graph_edges = []
                st.session_state.demographics = []
                st.session_state.editing_mode = "new"
                st.session_state.disease_name = "COVID-19"
                if 'editing_machine_id' in st.session_state:
                    del st.session_state.editing_machine_id
                st.rerun()
        with col3:
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
                                st.session_state.disease_name,
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