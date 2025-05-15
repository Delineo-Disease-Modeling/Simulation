import streamlit as st
import streamlit.components.v1 as components
import os
import json
import numpy as np
import pandas as pd
from state_machine_db import StateMachineDB

# Set page to wide mode
st.set_page_config(layout="wide")

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
        
        # Parse edge label
        label_parts = edge['data']['label'].split('\n')
        transition_matrix[i, j] = float(label_parts[0].split('=')[1])
        mean_matrix[i, j] = float(label_parts[1].split('=')[1])
        std_dev_matrix[i, j] = float(label_parts[2].split('=')[1])
        dist_type = label_parts[3]
        distribution_matrix[i, j] = dist_type_to_num.get(dist_type, 0)
        min_cutoff_matrix[i, j] = float(label_parts[4].split('=')[1])
        max_cutoff_matrix[i, j] = float(label_parts[5].split('=')[1])
    
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

    # Create the graph
    st.markdown("---")  # Add a visual separator
    st.header("Create A State Machine")
    st.write("Use the interface below to create a state machine for your simulation.")
    
    # # Add save/load interface
    # st.subheader("Save/Load State Machine")
    # col1, col2 = st.columns(2)
    
    # with col1:
    #     # Save interface
    #     st.write("Save Current State Machine")
    #     save_name = st.text_input("State Machine Name", key="save_name")
    #     save_description = st.text_area("Description", key="save_description")
    #     if st.button("Save State Machine"):
    #         if save_name:
    #             state_machine_id = db.save_state_machine(
    #                 save_name,
    #                 save_description,
    #                 states,
    #                 st.session_state.graph_edges
    #             )
    #             st.success(f"State machine saved with ID: {state_machine_id}")
    #         else:
    #             st.error("Please provide a name for the state machine")
    
    # with col2:
    #     # Load interface
    #     st.write("Load Saved State Machine")
    #     saved_machines = db.list_state_machines()
    #     if saved_machines:
    #         machine_options = {f"{m[1]} (ID: {m[0]})": m[0] for m in saved_machines}
    #         selected_machine = st.selectbox(
    #             "Select State Machine",
    #             options=list(machine_options.keys()),
    #             key="load_machine"
    #         )
            
    #         col_load, col_delete = st.columns(2)
    #         with col_load:
    #             if st.button("Load Selected"):
    #                 machine_id = machine_options[selected_machine]
    #                 machine_data = db.load_state_machine(machine_id)
    #                 if machine_data:
    #                     # Update session state with loaded data
    #                     st.session_state.graph_edges = machine_data["edges"]
    #                     st.success(f"Loaded state machine: {machine_data['name']}")
    #                     st.rerun()
            
    #         with col_delete:
    #             if st.button("Delete Selected"):
    #                 machine_id = machine_options[selected_machine]
    #                 db.delete_state_machine(machine_id)
    #                 st.success("State machine deleted")
    #                 st.rerun()
    #     else:
    #         st.write("No saved state machines found")
    
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
            options=[f"{edge['data']['source']} → {edge['data']['target']} ({edge['data']['label']})" for edge in st.session_state.graph_edges],
            key="edge_to_remove"
        )
        
        if st.button("Remove Edge"):
            # Find and remove the selected edge
            for i, edge in enumerate(st.session_state.graph_edges):
                if f"{edge['data']['source']} → {edge['data']['target']} ({edge['data']['label']})" == edge_to_remove:
                    st.session_state.graph_edges.pop(i)
                    st.success(f"Removed edge {edge_to_remove}")
                    st.rerun()
                    break

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
    display_matrices(matrices, states)

    # Add simulation section
    st.markdown("---")  # Add a visual separator
    st.header("Start Simulation")
    
    # Get states with outgoing edges for initial state selection
    states_with_outgoing = set()
    for edge in st.session_state.graph_edges:
        states_with_outgoing.add(edge['data']['source'])
    
    # Filter initial state options to only include states with outgoing edges
    initial_state_options = [state for state in states if state in states_with_outgoing]
    
    # If no states have outgoing edges yet, show all states
    if not initial_state_options:
        initial_state_options = states
    
    # Add initial state selection
    st.subheader("Select Initial State")
    initial_state = st.selectbox(
        "Initial State",
        options=initial_state_options,
        key="graph_sim_initial_state"
    )
    
    # Add start simulation button
    if st.button("Start Simulation"):
        st.info("Simulation functionality will be implemented soon!")

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