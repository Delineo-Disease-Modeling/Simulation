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

    st.header("Manage State Machines")
    st.write("View your saved state machines, load them, and run simulations.")
    
    # List all saved state machines
    saved_machines = db.list_state_machines()
    if saved_machines:
        # Create a table of state machines
        st.subheader("Saved State Machines")
        
        # Display state machines in a table format
        for machine in saved_machines:
            with st.expander(f"{machine[1]} (Created: {machine[2]}, Updated: {machine[3]})"):
                col1, col2 = st.columns(2)
                
                # Load demographics
                demographics = json.loads(machine[4] or "{}")
                
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
            
            # Build nodes list with persisted positions
            nodes = []
            for i, state in enumerate(st.session_state.states):
                default_pos = {
                    "x": (i - (len(st.session_state.states)-1)/2)*200,
                    "y": 0
                }
                pos = st.session_state.node_positions.get(state, default_pos)
                nodes.append({
                    "data": {"id": state, "label": state},
                    "position": pos
                })

            elements = nodes + st.session_state.graph_edges

            # Convert graph to matrices and display them
            matrices = convert_graph_to_matrices(st.session_state.states, st.session_state.graph_edges)
            with st.expander("Matrix Representation", expanded=False):
                display_matrices(matrices, st.session_state.states)
            
            # Add visual state machine representation
            st.subheader("Visual State Machine")
            
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
                </script>
            </body>
            </html>
            """

            # Display the graph using Streamlit's components
            components.html(html, height=600)

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
                    st.dataframe(timeline_df)
                    
                    # Display a visual representation of the timeline
                    st.subheader("Timeline Visualization")
                    for state, time in timeline:
                        st.write(f"{time:.2f} hours: {state}")
    else:
        st.write("No saved state machines found") 