import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .state_editor import validate_matrices
from streamlit_javascript import st_javascript
from .disease_configurations import get_disease_template, get_available_diseases, get_disease_parameters, get_disease_edges, get_available_variants, get_disease_model_categories, get_disease_demographic_options
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
    if 'template_applied' not in st.session_state:
        st.session_state.template_applied = False
    if 'applied_template_name' not in st.session_state:
        st.session_state.applied_template_name = None
    
    st.header("Create A State Machine")
    
    # Define workflow steps
    workflow_steps = {
        1: "Choose Mode",
        2: "Disease & Model Category", 
        3: "Demographics",
        4: "Edge Management & Save"
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
                            
                            # Load model category and variant information
                            st.session_state.model_category = selected_machine_data.get('model_category', 'default')
                            st.session_state.variant_name = selected_machine_data.get('variant_name')
                            st.session_state.vaccination_status = None  # Will be set from demographics
                            
                            for key, value in selected_machine_data['demographics'].items():
                                # Check if this is a standard demographic (Sex, Age, Vaccination Status) or custom
                                if key in ["Sex", "Age", "Vaccination Status"]:
                                    st.session_state.demographics.append({"key": key, "value": value})
                                    # Set vaccination status for model category
                                    if key == "Vaccination Status":
                                        st.session_state.vaccination_status = value
                                elif key == "Vaccination":
                                    # Handle legacy vaccination field name
                                    st.session_state.demographics.append({"key": "Vaccination Status", "value": value})
                                    st.session_state.vaccination_status = value
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
                            
                            # Don't apply templates when loading existing machines
                            st.session_state.template_applied = False
                            st.session_state.applied_template_name = None
                            
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
                st.session_state.template_applied = False
                st.session_state.applied_template_name = None
                if 'editing_machine_id' in st.session_state:
                    del st.session_state.editing_machine_id
                st.session_state.current_step = 2
                st.success("Started new state machine")
                st.rerun()
    
    # Step 2: Disease Selection and Model Category
    elif st.session_state.current_step == 2:
        st.subheader("Step 2: Disease Selection & Model Category")
        st.write("Select a disease and choose whether to create a default or variant-specific model.")
        
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
        
        # Model category selection
        if selected_disease != "Custom Disease" and selected_disease in get_available_diseases():
            # Get model categories from disease configuration
            model_categories = get_disease_model_categories(selected_disease)
            
            # Initialize model category in session state if not exists
            if 'model_category' not in st.session_state:
                st.session_state.model_category = "default"
            if 'variant_name' not in st.session_state:
                st.session_state.variant_name = None
            if 'vaccination_status' not in st.session_state:
                st.session_state.vaccination_status = None
            
            # Create model category options from configuration
            model_category_options = [category["name"] for category in model_categories]
            model_category_ids = [category["id"] for category in model_categories]
            
            # Find current model category index
            current_category_index = 0
            if st.session_state.model_category in model_category_ids:
                current_category_index = model_category_ids.index(st.session_state.model_category)
            
            model_category = st.radio(
                "Model Category:",
                options=model_category_options,
                index=current_category_index,
                key="model_category_selection"
            )
            
            # Update session state with selected category ID
            selected_category_id = model_category_ids[model_category_options.index(model_category)]
            st.session_state.model_category = selected_category_id
            
            # Handle specific model category types
            if selected_category_id == "vaccination":
                # Get vaccination options from disease configuration
                demographic_options = get_disease_demographic_options(selected_disease)
                vaccination_options = demographic_options.get("Vaccination Status", ["Unvaccinated", "Partially Vaccinated", "Fully Vaccinated"])
                
                selected_vaccination_index = 0
                if st.session_state.vaccination_status in vaccination_options:
                    selected_vaccination_index = vaccination_options.index(st.session_state.vaccination_status)
                
                vaccination_status = st.selectbox(
                    "Select Vaccination Status:",
                    options=vaccination_options,
                    index=selected_vaccination_index,
                    key="vaccination_selection"
                )
                st.session_state.vaccination_status = vaccination_status
                st.session_state.variant_name = None
                
            elif selected_category_id == "variant":
                # Variant selection for variant-specific models
                available_variants = get_available_variants(selected_disease)
                if available_variants:
                    selected_variant_index = 0
                    if st.session_state.variant_name in available_variants:
                        selected_variant_index = available_variants.index(st.session_state.variant_name)
                    selected_variant = st.selectbox(
                        "Select Variant:",
                        options=available_variants,
                        index=selected_variant_index,
                        key="variant_selection"
                    )
                    st.session_state.variant_name = selected_variant
                else:
                    st.warning("⚠️ No variants defined for this disease. Please use the Disease Configurations tab to add variants.")
                    st.session_state.variant_name = None
                st.session_state.vaccination_status = None
                
            else:
                # Default model - clear variant and vaccination
                st.session_state.variant_name = None
                st.session_state.vaccination_status = None
        else:
            # For custom diseases, default to default model
            st.session_state.model_category = "default"
            st.session_state.variant_name = None
            st.session_state.vaccination_status = None
        
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
        
        # Show template applied indicator
        if st.session_state.template_applied and st.session_state.applied_template_name:
            st.success(f"✅ **{st.session_state.applied_template_name} Template Applied**")
            st.info(f"📋 **Template Status**: Using predefined states and edges from {st.session_state.applied_template_name} template. You can modify the parameters but the structure is based on the template.")
            
            # Add option to clear template
            if st.button("Clear Template (Start Fresh)", key="clear_template"):
                st.session_state.template_applied = False
                st.session_state.applied_template_name = None
                st.session_state.states = ["State1", "State2"]
                st.session_state.graph_edges = []
                st.success("Template cleared. You can now create a custom state machine.")
                st.rerun()
        
        # Apply disease template if a predefined disease is selected (only for new machines)
        if selected_disease != "Custom Disease" and selected_disease in get_available_diseases() and st.session_state.editing_mode != "edit":
            template = get_disease_template(selected_disease)
            if template and template['states']:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.info(f"📋 **{selected_disease} Template Available**: {template['description']}")
                with col2:
                    if st.button(f"Apply {selected_disease} Template", key="apply_disease_template"):
                        # Preserve current model category and vaccination status
                        current_model_category = st.session_state.get('model_category', 'default')
                        current_vaccination_status = st.session_state.get('vaccination_status', None)
                        current_vaccination_model_category = st.session_state.get('vaccination_model_category', 'default')
                        
                        # Update states with template states
                        st.session_state.states = template['states'].copy()
                        # Load predefined edges if available
                        predefined_edges = get_disease_edges(selected_disease)
                        if predefined_edges:
                            st.session_state.graph_edges = predefined_edges
                            st.success(f"✅ Applied {selected_disease} template with {len(template['states'])} states and {len(predefined_edges)} predefined edges")
                        else:
                            st.success(f"✅ Applied {selected_disease} template with {len(template['states'])} states")
                        
                        # Restore model category and vaccination status
                        st.session_state.model_category = current_model_category
                        st.session_state.vaccination_status = current_vaccination_status
                        st.session_state.vaccination_model_category = current_vaccination_model_category
                        
                        st.session_state.template_applied = True
                        st.session_state.applied_template_name = selected_disease
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
        

        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Mode Selection"):
                st.session_state.current_step = 1
                st.rerun()
        with col3:
            if st.button("Next: Demographics →"):
                st.session_state.current_step = 3
                st.rerun()
    
    # Step 3: Demographics
    elif st.session_state.current_step == 3:
        st.subheader("Step 3: Demographics")
        st.write("Configure demographic parameters for your state machine.")
        
        # Show template status if template is applied
        if st.session_state.template_applied and st.session_state.applied_template_name:
            st.success(f"✅ **{st.session_state.applied_template_name} Template Active**")
            st.info(f"📋 **Template Structure**: You're working with the {st.session_state.applied_template_name} template. The disease name and structure will reflect the template.")
        
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
                # Get available demographic types from disease configuration
                if st.session_state.disease_name in get_available_diseases():
                    demographic_options = get_disease_demographic_options(st.session_state.disease_name)
                    available_demo_types = list(demographic_options.keys())
                    # Add "Custom" option
                    available_demo_types.append("Custom")
                else:
                    # Default options for custom diseases
                    available_demo_types = ["Sex", "Age", "Vaccination Status", "Custom"]
                
                # Find current demo type index
                current_demo_index = 0
                if demo["key"] in available_demo_types:
                    current_demo_index = available_demo_types.index(demo["key"])
                
                demo_type = st.selectbox(
                    "Demographic Type",
                    options=available_demo_types,
                    index=current_demo_index,
                    key=f"demo_type_{i}"
                )
                st.session_state.demographics[i]["key"] = demo_type
            with col2:
                if demo_type == "Sex":
                    # Get sex options from disease configuration
                    if st.session_state.disease_name in get_available_diseases():
                        sex_options = demographic_options.get("Sex", ["M", "F"])
                    else:
                        sex_options = ["M", "F"]
                    
                    current_sex_index = 0
                    if demo["value"] in sex_options:
                        current_sex_index = sex_options.index(demo["value"])
                    
                    demo_value = st.selectbox(
                        "Value",
                        options=sex_options,
                        index=current_sex_index,
                        key=f"demo_value_{i}"
                    )
                elif demo_type == "Age":
                    # Get age options from disease configuration
                    if st.session_state.disease_name in get_available_diseases():
                        age_options = demographic_options.get("Age", ["0-18", "19-64", "65+"])
                    else:
                        age_options = ["0-18", "19-64", "65+"]
                    
                    current_age_index = 0
                    if demo["value"] in age_options:
                        current_age_index = age_options.index(demo["value"])
                    
                    demo_value = st.selectbox(
                        "Value",
                        options=age_options,
                        index=current_age_index,
                        key=f"demo_value_{i}"
                    )
                elif demo_type == "Vaccination Status":
                    # Get vaccination options from disease configuration
                    if st.session_state.disease_name in get_available_diseases():
                        vaccination_options = demographic_options.get("Vaccination Status", ["Unvaccinated", "Partially Vaccinated", "Fully Vaccinated"])
                    else:
                        vaccination_options = ["Unvaccinated", "Partially Vaccinated", "Fully Vaccinated"]
                    
                    current_vaccination_index = 0
                    if demo["value"] in vaccination_options:
                        current_vaccination_index = vaccination_options.index(demo["value"])
                    
                    demo_value = st.selectbox(
                        "Value",
                        options=vaccination_options,
                        index=current_vaccination_index,
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
                    # For other demographic types, use text input
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
        
        # Navigation buttons
        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("← Back to Disease Config"):
                st.session_state.current_step = 2
                st.rerun()
        with col3:
            if st.button("Next: Edge Management →"):
                st.session_state.current_step = 4
                st.rerun()
    
    # Step 4: Edge Management and Save
    elif st.session_state.current_step == 4:
        st.subheader("Step 4: Edge Management & Save")
        st.write("Define the transitions between states, visualize your state machine, and save it.")
        
        # Show template status if template is applied
        if st.session_state.template_applied and st.session_state.applied_template_name:
            st.success(f"✅ **{st.session_state.applied_template_name} Template Active**")
            st.info(f"📋 **Template Structure**: You're working with the {st.session_state.applied_template_name} template. The states and edge structure are predefined, but you can modify transition probabilities and timing parameters.")
        
        # Show current states for reference
        if 'states' in st.session_state and st.session_state.states:
            with st.expander("Current States", expanded=False):
                for i, state in enumerate(st.session_state.states, 1):
                    st.write(f"{i}. {state}")
        
        # Use utility functions for edge management
        render_add_edge_section(st.session_state.states, st.session_state.graph_edges, "creator_add")
        render_edit_edge_section(st.session_state.graph_edges, "creator_edit")
        render_remove_edge_section(st.session_state.graph_edges, "creator_remove")
        
        # Add simplified reachability analysis
        if st.session_state.graph_edges:
            st.markdown("---")
            
            # Import the calculation function from manager
            from .state_machine_manager import calculate_aggregated_probabilities
            
            aggregated_probs = calculate_aggregated_probabilities(st.session_state.states, st.session_state.graph_edges)
            
            if aggregated_probs:
                # Create a simple display
                st.write("**State reachability from initial state:**")
                
                # Create a simple table
                prob_data = []
                for state, prob in aggregated_probs.items():
                    prob_data.append({
                        "State": state,
                        "Probability": f"{prob:.3f}",
                        "Percentage": f"{prob * 100:.1f}%"
                    })
                
                # Sort by probability (highest first)
                prob_data.sort(key=lambda x: float(x["Probability"]), reverse=True)
                
                # Display as a simple table
                prob_df = pd.DataFrame(prob_data)
                st.dataframe(prob_df, use_container_width=True)
                
            else:
                st.info("ℹ️ Add edges to see state reachability analysis.")
        
        # JSON Editor for Edges
        st.markdown("---")
        with st.expander("📝 JSON Edge Editor", expanded=False):
            st.write("Edit all edges in JSON format for bulk modifications:")
            
            # Convert edges to a more readable format for JSON editing
            edges_for_json = []
            for edge in st.session_state.graph_edges:
                edge_data = edge['data'].copy()
                # Remove the label field as it's auto-generated
                if 'label' in edge_data:
                    del edge_data['label']
                edges_for_json.append(edge_data)
            
            # Display current edges as JSON
            current_json = json.dumps(edges_for_json, indent=2)
            
            # JSON editor with validation
            edited_json = st.text_area(
                "Edit Edges (JSON format):",
                value=current_json,
                height=400,
                key="creator_json_editor",
                help="Edit the edges in JSON format. Each edge should have: source, target, transition_prob, mean_time, std_dev, distribution_type, min_cutoff, max_cutoff"
            )
            
            # Add buttons for JSON operations
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔄 Update from JSON", key="update_from_json"):
                    try:
                        # Parse the JSON
                        parsed_edges = json.loads(edited_json)
                        
                        # Validate the structure
                        if not isinstance(parsed_edges, list):
                            st.error("❌ JSON must be a list of edge objects")
                            return
                        
                        # Convert back to the expected format with 'data' wrapper
                        new_edges = []
                        for edge_data in parsed_edges:
                            if not isinstance(edge_data, dict):
                                st.error("❌ Each edge must be a JSON object")
                                return
                            
                            # Validate required fields
                            required_fields = ['source', 'target', 'transition_prob', 'mean_time', 'std_dev', 'distribution_type', 'min_cutoff', 'max_cutoff']
                            missing_fields = [field for field in required_fields if field not in edge_data]
                            if missing_fields:
                                st.error(f"❌ Missing required fields: {', '.join(missing_fields)}")
                                return
                            
                            # Validate that source and target states exist
                            if edge_data['source'] not in st.session_state.states:
                                st.error(f"❌ Source state '{edge_data['source']}' not found in states list")
                                return
                            if edge_data['target'] not in st.session_state.states:
                                st.error(f"❌ Target state '{edge_data['target']}' not found in states list")
                                return
                            
                            # Create the edge in the expected format
                            new_edge = {
                                'data': {
                                    'source': edge_data['source'],
                                    'target': edge_data['target'],
                                    'transition_prob': float(edge_data['transition_prob']),
                                    'mean_time': int(edge_data['mean_time']),
                                    'std_dev': float(edge_data['std_dev']),
                                    'distribution_type': edge_data['distribution_type'],
                                    'min_cutoff': float(edge_data['min_cutoff']),
                                    'max_cutoff': float(edge_data['max_cutoff']),
                                    'label': create_edge_label(
                                        float(edge_data['transition_prob']),
                                        int(edge_data['mean_time']),
                                        float(edge_data['std_dev']),
                                        edge_data['distribution_type'],
                                        float(edge_data['min_cutoff']),
                                        float(edge_data['max_cutoff'])
                                    )
                                }
                            }
                            new_edges.append(new_edge)
                        
                        # Update the session state
                        st.session_state.graph_edges = new_edges
                        st.success(f"✅ Successfully updated {len(new_edges)} edges from JSON")
                        st.rerun()
                        
                    except json.JSONDecodeError as e:
                        st.error(f"❌ Invalid JSON format: {str(e)}")
                    except ValueError as e:
                        st.error(f"❌ Invalid data type: {str(e)}")
                    except Exception as e:
                        st.error(f"❌ Error updating edges: {str(e)}")
            
            with col2:
                if st.button("📋 Copy JSON", key="copy_json"):
                    st.write("```json")
                    st.code(current_json, language="json")
                    st.write("```")
                    st.success("✅ JSON copied to clipboard (use Ctrl+C)")
            
            with col3:
                if st.button("🗑️ Clear All Edges", key="clear_edges"):
                    st.session_state.graph_edges = []
                    st.success("✅ All edges cleared")
                    st.rerun()
        
        # Show validation info (moved outside the main expander)
        with st.expander("ℹ️ JSON Format Guide", expanded=False):
            st.write("""
            **Required fields for each edge:**
            - `source`: Source state name (must exist in states list)
            - `target`: Target state name (must exist in states list)
            - `transition_prob`: Probability of transition (0.0 to 1.0)
            - `mean_time`: Average time in hours before transition
            - `std_dev`: Standard deviation of transition time
            - `distribution_type`: Distribution type ("normal", "triangular", etc.)
            - `min_cutoff`: Minimum time cutoff in hours
            - `max_cutoff`: Maximum time cutoff in hours
            
            **Example edge:**
            ```json
            {
              "source": "Exposed",
              "target": "Infectious_Presymptomatic",
              "transition_prob": 1.0,
              "mean_time": 10.0,
              "std_dev": 2.0,
              "distribution_type": "triangular",
              "min_cutoff": 7.0,
              "max_cutoff": 14.0
            }
            ```
            """)
        
        
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
        
        # Add variant to name if it's a variant-specific model
        if st.session_state.model_category == "variant" and st.session_state.variant_name:
            name_parts.append(f"variant={st.session_state.variant_name}")
        
        # Add vaccination status to name if measles
        if st.session_state.disease_name == "Measles" and st.session_state.model_category == "vaccination" and st.session_state.vaccination_status:
            name_parts.append(f"vaccination={st.session_state.vaccination_status}")
        
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
            if st.button("← Back to Demographics"):
                st.session_state.current_step = 3
                st.rerun()
        with col2:
            if st.button("Start Over"):
                st.session_state.current_step = 1
                st.session_state.graph_edges = []
                st.session_state.demographics = []
                st.session_state.editing_mode = "new"
                st.session_state.disease_name = "COVID-19"
                st.session_state.template_applied = False
                st.session_state.applied_template_name = None
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
                                st.session_state.variant_name,
                                st.session_state.model_category,
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