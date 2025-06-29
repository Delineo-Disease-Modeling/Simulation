import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .state_editor import validate_matrices
from streamlit_javascript import st_javascript

def convert_graph_to_matrices(states, edges):
    """Convert graph representation to six matrices."""
    n = len(states)
    state_to_idx = {state: i for i, state in enumerate(states)}
    
    # Initialize matrices with zeros
    transition_matrix = np.zeros((n, n))
    distribution_matrix = np.zeros((n, n), dtype=int)
    mean_matrix = np.zeros((n, n))
    std_dev_matrix = np.zeros((n, n))
    min_cutoff_matrix = np.zeros((n, n))
    max_cutoff_matrix = np.zeros((n, n))
    
    # Distribution type mapping
    dist_type_to_num = {
        "triangular": 1,
        "uniform": 2,
        "log-normal": 3,
        "gamma": 4
    }
    
    # Fill matrices based on edges
    for edge in edges:
        source = edge['data']['source']
        target = edge['data']['target']
        i = state_to_idx[source]
        j = state_to_idx[target]
        
        # Get edge properties with defaults
        transition_matrix[i, j] = edge['data'].get('transition_prob', 1.0)
        mean_matrix[i, j] = edge['data'].get('mean_time', 0)
        std_dev_matrix[i, j] = edge['data'].get('std_dev', 0.0)
        dist_type = edge['data'].get('distribution_type', 'triangular')
        distribution_matrix[i, j] = dist_type_to_num.get(dist_type, 0)
        min_cutoff_matrix[i, j] = edge['data'].get('min_cutoff', 0.0)
        max_cutoff_matrix[i, j] = edge['data'].get('max_cutoff', float('inf'))
    
    return {
        "Transition Matrix": transition_matrix,
        "Distribution Type Matrix": distribution_matrix,
        "Mean Matrix": mean_matrix,
        "Standard Deviation Matrix": std_dev_matrix,
        "Min Cutoff Matrix": min_cutoff_matrix,
        "Max Cutoff Matrix": max_cutoff_matrix
    }

def display_matrices(matrices, states):
    """Display the six matrices in a grid layout."""
    st.subheader("Matrix Representation")
    
    # Create a 2x3 grid for the matrices
    cols = st.columns(3)
    matrix_names = list(matrices.keys())
    
    for i, (col, matrix_name) in enumerate(zip(cols, matrix_names[:3])):
        with col:
            st.write(f"**{matrix_name}**")
            df = pd.DataFrame(
                matrices[matrix_name],
                index=states,
                columns=states
            )
            st.dataframe(df, use_container_width=True)
    
    cols = st.columns(3)
    for i, (col, matrix_name) in enumerate(zip(cols, matrix_names[3:])):
        with col:
            st.write(f"**{matrix_name}**")
            df = pd.DataFrame(
                matrices[matrix_name],
                index=states,
                columns=states
            )
            st.dataframe(df, use_container_width=True)

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
    
    # Add mode selection
    st.subheader("Mode Selection")
    mode = st.radio(
        "Choose your mode:",
        options=["Create New State Machine", "Edit From Existing State Machine"],
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
                            # Check if this is a standard demographic (Sex, Age) or custom
                            if key in ["Sex", "Age"]:
                                st.session_state.demographics.append({"key": key, "value": value})
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
    
    elif mode == "Create New State Machine":
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
  
    
    st.write("""
    First, edit the states for your state machine above. Then, use the interface below to:
    1. Add edges between states
    2. Configure transition probabilities and timing
    3. Visualize your state machine
    4. Save your state machine with a set of demographics and their values
    """)

    # Remove Streamlit draw mode toggle
    # (No draw mode, no JS edge creation, no st_javascript message handling)

    # Add edge creation interface
    st.subheader("Add Edge")
    
    # State selection on first line
    col1, col2 = st.columns(2)
    with col1:
        source_state = st.selectbox("From State", states, key="source_state")
    with col2:
        target_states = states[1:] if len(states) > 1 else states
        target_state = st.selectbox("To State", target_states, key="target_state")
    
    # Other parameters on second line
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        transition_prob = st.number_input(
            "Transition Probability",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            format="%.2f",
            key="transition_prob"
        )
    with col2:
        mean_value = st.number_input(
            "Mean Time (days)",
            min_value=0.1,
            max_value=50.0,
            value=5.0,
            step=0.1,
            format="%.1f",
            key="mean_value"
        )
    with col3:
        std_dev = st.number_input(
            "Standard Deviation (days)",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
            format="%.1f",
            key="std_dev",
            disabled=(st.session_state.get("dist_type", "triangular") in ["triangular", "uniform"])
        )
        if st.session_state.get("dist_type", "triangular") in ["triangular", "uniform"]:
            st.caption("Not used for triangular/uniform distributions")
    with col4:
        dist_type = st.selectbox(
            "Distribution Type",
            options=["triangular", "uniform", "log-normal", "gamma"],
            key="dist_type"
        )
        # Add descriptions for each distribution type
        if st.session_state.get("dist_type", "triangular") == "triangular":
            st.caption("Most likely value with min/max bounds. Good for recovery times.")
        elif st.session_state.get("dist_type", "triangular") == "uniform":
            st.caption("Equal probability across min/max range. Good for uncertain periods.")
        elif st.session_state.get("dist_type", "triangular") == "log-normal":
            st.caption("Right-skewed (some take much longer). Good for disease progression.")
        elif st.session_state.get("dist_type", "triangular") == "gamma":
            st.caption("Flexible right-skewed. Good for waiting times and symptom onset.")
    with col5:
        min_cutoff = st.number_input(
            "Min Cutoff",
            min_value=0.0,
            max_value=float(st.session_state.mean_value),
            value=0.0,
            step=0.1,
            format="%.1f",
            key="min_cutoff"
        )
    with col6:
        max_cutoff = st.number_input(
            "Max Cutoff",
            min_value=float(st.session_state.mean_value),
            max_value=30.0,
            value=float(st.session_state.mean_value) + 1.0,
            step=0.1,
            format="%.1f",
            key="max_cutoff"
        )

    if st.button("Add Edge"):
        if source_state != target_state:  # Prevent self-loops
            edge_exists = any(
                edge["data"]["source"] == source_state and 
                edge["data"]["target"] == target_state 
                for edge in st.session_state.graph_edges
            )
            if not edge_exists:
                new_edge = {
                    "data": {
                        "source": source_state,
                        "target": target_state,
                        "transition_prob": transition_prob,
                        "mean_time": mean_value,
                        "std_dev": std_dev,
                        "distribution_type": dist_type,
                        "min_cutoff": min_cutoff,
                        "max_cutoff": max_cutoff,
                        "label": f"p={transition_prob:.2f}\nμ={mean_value}\nσ={std_dev:.1f}\n{dist_type}\nmin={min_cutoff:.1f}\nmax={max_cutoff:.1f}"
                    }
                }
                st.session_state.graph_edges.append(new_edge)
                st.success(f"Added edge from {source_state} to {target_state}")
                st.rerun()
            else:
                st.warning("This edge already exists!")
        else:
            st.warning("Cannot create self-loops!")

    # Add edge removal interface
    if st.session_state.graph_edges:
        st.subheader("Remove Edge")
        edge_to_remove = st.selectbox(
            "Select Edge to Remove",
            options=[
                f"{edge['data']['source']} → {edge['data']['target']} "
                f"(p={edge['data'].get('transition_prob', 1.0):.2f}, "
                f"μ={edge['data'].get('mean_time', 0)}, "
                f"σ={edge['data'].get('std_dev', 0.0):.1f}, "
                f"{edge['data'].get('distribution_type', 'triangular')}, "
                f"min={edge['data'].get('min_cutoff', 0.0):.1f}, "
                f"max={edge['data'].get('max_cutoff', float('inf')):.1f})"
                for edge in st.session_state.graph_edges
            ],
            key="edge_to_remove"
        )
        
        if st.button("Remove Edge"):
            # Find and remove the selected edge
            for i, edge in enumerate(st.session_state.graph_edges):
                edge_str = (
                    f"{edge['data']['source']} → {edge['data']['target']} "
                    f"(p={edge['data'].get('transition_prob', 1.0):.2f}, "
                    f"μ={edge['data'].get('mean_time', 0)}, "
                    f"σ={edge['data'].get('std_dev', 0.0):.1f}, "
                    f"{edge['data'].get('distribution_type', 'triangular')}, "
                    f"min={edge['data'].get('min_cutoff', 0.0):.1f}, "
                    f"max={edge['data'].get('max_cutoff', float('inf')):.1f})"
                )
                if edge_str == edge_to_remove:
                    st.session_state.graph_edges.pop(i)
                    st.success(f"Removed edge {edge_to_remove}")
                    st.rerun()
                    break

    # Add graph visualization
    st.markdown("---")
    st.subheader("State Machine Visualization")
    
    # Build nodes list with persisted positions
    nodes = []
    for i, state in enumerate(states):
        # Use a more spread out layout instead of straight line
        n = len(states)
        if n <= 3:
            # For 3 or fewer nodes, use a triangle layout
            angle = (i * 2 * np.pi / n) - np.pi/2  # Start from top
            radius = 200
            default_pos = {
                "x": radius * np.cos(angle),
                "y": radius * np.sin(angle)
            }
        else:
            # For more nodes, use a grid layout
            cols = int(np.ceil(np.sqrt(n)))
            row = i // cols
            col = i % cols
            default_pos = {
                "x": (col - (cols-1)/2) * 250,
                "y": (row - (n//cols)/2) * 200
            }
        pos = st.session_state.node_positions.get(state, default_pos)
        nodes.append({
            "data": {"id": state, "label": state},
            "position": pos
        })
    
    elements = nodes + st.session_state.graph_edges

    # Convert graph to matrices and display them
    matrices = convert_graph_to_matrices(states, st.session_state.graph_edges)
    with st.expander("Matrix Representation", expanded=False):
        display_matrices(matrices, states)

    # Define the stylesheet
    stylesheet = [
        {
            "selector": "node",
            "style": {
                "background-color": "#BEE",
                "label": "data(label)",
                "text-valign": "center",
                "text-halign": "center",
                "width": 100,
                "height": 100,
                "shape": "ellipse"
            }
        },
        {
            "selector": "edge",
            "style": {
                "width": 1,
                "line-color": "#ccc",
                "target-arrow-color": "#ccc",
                "target-arrow-shape": "triangle",
                "curve-style": "bezier",
                "label": "data(label)",
                "text-rotation": "none",
                "text-margin-y": -10,
                "font-size": 11,
                "text-background-color": "#fff",
                "text-background-opacity": 0.7,
                "text-background-padding": 3,
                "text-border-color": "#ccc",
                "text-border-width": 1,
                "text-border-opacity": 0.5,
                "text-wrap": "wrap",
                "text-max-width": 80
            }
        }
    ]

    # Clean Cytoscape HTML: remove draw button and related JS
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cytoscape Graph</title>
        <script src=\"https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js\"></script>
        <style>
            body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
            }}
            #cy {{
                width: 100%;
                height: 600px;
                position: relative;
                left: 0;
                top: 0;
                background-color: #f0f2f6;
                border-radius: 0.5rem;
            }}
            .reset-button {{
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 1000;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 5px 10px;
                cursor: pointer;
                font-size: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .reset-button:hover {{
                background-color: #f0f0f0;
            }}
        </style>
    </head>
    <body>
        <div id=\"cy\"></div>
        <button class=\"reset-button\" onclick=\"resetView()\">Reset View</button>
        <script>
            var cy = cytoscape({{
                container: document.getElementById('cy'),
                elements: {json.dumps(elements)},
                style: {json.dumps(stylesheet)},
                layout: {{
                    name: 'preset'
                }}
            }});

            // Handle node dragging
            cy.on('dragfree', 'node', function(evt) {{
                var node = evt.target;
                var pos = node.position();
                window.parent.postMessage({{
                    type: 'node_position',
                    id: node.id(),
                    x: pos.x,
                    y: pos.y
                }}, '*');
            }});

            // Handle edge clicking
            cy.on('tap', 'edge', function(evt) {{
                var edge = evt.target;
                window.parent.postMessage({{
                    type: 'edge_click',
                    id: edge.id(),
                    source: edge.data('source'),
                    target: edge.data('target'),
                    transition_prob: edge.data('transition_prob'),
                    mean_time: edge.data('mean_time'),
                    std_dev: edge.data('std_dev'),
                    distribution_type: edge.data('distribution_type'),
                    min_cutoff: edge.data('min_cutoff'),
                    max_cutoff: edge.data('max_cutoff')
                }}, '*');
            }});

            // Handle node clicking
            cy.on('tap', 'node', function(evt) {{
                var node = evt.target;
                window.parent.postMessage({{
                    type: 'node_click',
                    id: node.id()
                }}, '*');
            }});

            // Reset view function
            function resetView() {{
                cy.fit();
                cy.center();
            }}
        </script>
    </body>
    </html>
    """
    
    # Display the graph using Streamlit's components
    components.html(html, height=600)

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
                options=["", "Sex", "Age", "Custom"],
                index=0 if demo["key"] == "" else (1 if demo["key"] == "Sex" else 2 if demo["key"] == "Age" else 3),
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
    
    state_machine_name = " | ".join([f"{key}={value}" for key, value in demographics.items()]) if demographics else "Default"

    # Show different button text based on mode
    save_button_text = "Update State Machine" if st.session_state.editing_mode == "edit" else "Save State Machine"
    
    if st.button(save_button_text):
        if state_machine_name:
            # Run validation
            validation_issues = validate_matrices(states, st.session_state.graph_edges)
            if validation_issues:
                st.error("❌ Validation failed. Please fix the following issues before saving:")
                for issue in validation_issues:
                    st.error(f"- {issue}")
            else:
                # If valid, save or update the state machine
                try:
                    state_machine_id = db.save_state_machine(
                        state_machine_name,
                        states,
                        st.session_state.graph_edges,
                        demographics,
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