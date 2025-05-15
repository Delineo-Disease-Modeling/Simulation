import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation

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
        "normal": 1,
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
        dist_type = edge['data'].get('distribution_type', 'normal')
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

    st.header("Create A State Machine")
    st.write("Use the interface below to create a state machine for your simulation.")
    
    # Add edge creation interface
    st.subheader("Add Edge")
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns(8)
    
    with col1:
        source_state = st.selectbox("From State", states, key="source_state")
    with col2:
        # Create a list of target states starting from the second element
        target_states = states[1:] if len(states) > 1 else states
        target_state = st.selectbox("To State", target_states, key="target_state")
    with col3:
        transition_prob = st.number_input(
            "Transition Probability",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            format="%.2f",
            key="transition_prob"
        )
    with col4:
        mean_value = st.number_input(
            "Mean Time",
            min_value=1,
            max_value=20,
            value=5,
            step=1,
            key="mean_value"
        )
    with col5:
        std_dev = st.number_input(
            "Standard Deviation",
            min_value=0.1,
            max_value=10.0,
            value=1.0,
            step=0.1,
            format="%.1f",
            key="std_dev"
        )
    with col6:
        dist_type = st.selectbox(
            "Distribution Type",
            options=["normal", "uniform", "log-normal", "gamma"],
            key="dist_type"
        )
    with col7:
        min_cutoff = st.number_input(
            "Min Cutoff",
            min_value=0.0,
            max_value=float(st.session_state.mean_value),
            value=0.0,
            step=0.1,
            format="%.1f",
            key="min_cutoff"
        )
    with col8:
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
            # Check if edge already exists
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
                st.success(f"Added edge from {source_state} to {target_state} with probability {transition_prob:.2f}, mean time {mean_value}, std dev {std_dev:.1f}, {dist_type} distribution, min cutoff {min_cutoff:.1f}, and max cutoff {max_cutoff:.1f}")
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
                f"{edge['data'].get('distribution_type', 'normal')}, "
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
                    f"{edge['data'].get('distribution_type', 'normal')}, "
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
        default_pos = {
            "x": (i - (len(states)-1)/2)*200,
            "y": 0
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

    # Create the HTML for the Cytoscape graph
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cytoscape Graph</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.26.0/cytoscape.min.js"></script>
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
        <div id="cy"></div>
        <button class="reset-button" onclick="resetView()">Reset View</button>
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

            // Handle node/edge clicks
            cy.on('tap', 'node, edge', function(evt) {{
                var element = evt.target;
                window.parent.postMessage({{
                    type: 'element_click',
                    id: element.id(),
                    isNode: element.isNode()
                }}, '*');
            }});

            // Listen for messages from Streamlit
            window.addEventListener('message', function(event) {{
                if (event.data.type === 'node_position') {{
                    var node = cy.getElementById(event.data.id);
                    if (node.length > 0) {{
                        node.position({{
                            x: event.data.x,
                            y: event.data.y
                        }});
                    }}
                }}
            }});

            // Reset view function
            function resetView() {{
                cy.fit();
                cy.center();
            }}

            // Add keyboard shortcut for reset view (R key)
            document.addEventListener('keydown', function(event) {{
                if (event.key === 'r' || event.key === 'R') {{
                    resetView();
                }}
            }});
        </script>
    </body>
    </html>
    """

    # Display the graph using Streamlit's components
    components.html(html, height=600)

    # Display clicked element info if available
    if st.session_state.clicked_element:
        st.write("Selected element:", st.session_state.clicked_element)

    # Add save interface
    st.markdown("---")
    st.subheader("Save State Machine")
    
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
            st.session_state.demographics[i]["key"] = st.text_input(
                "Demographic Name",
                value=demo["key"],
                key=f"demo_key_{i}"
            )
        with col2:
            st.session_state.demographics[i]["value"] = st.text_input(
                "Value",
                value=demo["value"],
                key=f"demo_value_{i}"
            )
        with col3:
            if st.button("Remove", key=f"remove_demo_{i}"):
                st.session_state.demographics.pop(i)
                st.rerun()
    
    # Create name from demographic values
    demo_values = []
    for demo in st.session_state.demographics:
        if demo["key"] and demo["value"]:
            demo_values.append(f"{demo['key']}={demo['value']}")
    
    state_machine_name = " | ".join(demo_values) if demo_values else "Default"
    
    if st.button("Save State Machine"):
        if state_machine_name:
            # Create demographics dictionary
            demographics = {
                demo["key"]: demo["value"]
                for demo in st.session_state.demographics
                if demo["key"] and demo["value"]
            }
            
            state_machine_id = db.save_state_machine(
                state_machine_name,
                states,
                st.session_state.graph_edges,
                demographics
            )
            st.success(f"Saved state machine: {state_machine_name}")
        else:
            st.error("Please provide at least one demographic value") 