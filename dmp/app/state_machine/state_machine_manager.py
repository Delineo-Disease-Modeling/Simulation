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
            
            # Add edge editing functionality
            st.markdown("---")
            with st.expander("Edit Edges", expanded=False):
                # Edit existing edges
                if st.session_state.graph_edges:
                    st.write("**Edit Existing Edge**")
                    edge_to_edit = st.selectbox(
                        "Select Edge to Edit",
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
                        key="manager_edge_to_edit"
                    )
                    
                    # Find the selected edge
                    selected_edge = None
                    selected_edge_index = None
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
                        if edge_str == edge_to_edit:
                            selected_edge = edge
                            selected_edge_index = i
                            break
                    
                    if selected_edge:
                        st.write(f"**Editing: {selected_edge['data']['source']} → {selected_edge['data']['target']}**")
                        
                        # Edge parameters for editing
                        col1, col2, col3, col4, col5, col6 = st.columns(6)
                        with col1:
                            edit_transition_prob = st.number_input(
                                "Transition Probability",
                                min_value=0.0,
                                max_value=1.0,
                                value=float(selected_edge['data'].get('transition_prob', 1.0)),
                                step=0.05,
                                format="%.2f",
                                key="manager_edit_transition_prob"
                            )
                        with col2:
                            edit_mean_value = st.number_input(
                                "Mean Time (days)",
                                min_value=0.1,
                                max_value=50.0,
                                value=float(selected_edge['data'].get('mean_time', 5.0)),
                                step=0.1,
                                format="%.1f",
                                key="manager_edit_mean_value"
                            )
                        with col3:
                            edit_std_dev = st.number_input(
                                "Standard Deviation (days)",
                                min_value=0.1,
                                max_value=10.0,
                                value=float(selected_edge['data'].get('std_dev', 1.0)),
                                step=0.1,
                                format="%.1f",
                                key="manager_edit_std_dev"
                            )
                        with col4:
                            edit_dist_type = st.selectbox(
                                "Distribution Type",
                                options=["triangular", "uniform", "log-normal", "gamma"],
                                index=["triangular", "uniform", "log-normal", "gamma"].index(selected_edge['data'].get('distribution_type', 'triangular')),
                                key="manager_edit_dist_type"
                            )
                        with col5:
                            edit_min_cutoff = st.number_input(
                                "Min Cutoff",
                                min_value=0.0,
                                max_value=float(edit_mean_value),
                                value=float(selected_edge['data'].get('min_cutoff', 0.0)),
                                step=0.1,
                                format="%.1f",
                                key="manager_edit_min_cutoff"
                            )
                        with col6:
                            edit_max_cutoff = st.number_input(
                                "Max Cutoff",
                                min_value=float(edit_mean_value),
                                max_value=30.0,
                                value=float(selected_edge['data'].get('max_cutoff', float(edit_mean_value) + 1.0)),
                                step=0.1,
                                format="%.1f",
                                key="manager_edit_max_cutoff"
                            )

                        if st.button("Update Edge", key="manager_update_edge"):
                            # Update the edge with new values
                            st.session_state.graph_edges[selected_edge_index]['data'].update({
                                'transition_prob': edit_transition_prob,
                                'mean_time': edit_mean_value,
                                'std_dev': edit_std_dev,
                                'distribution_type': edit_dist_type,
                                'min_cutoff': edit_min_cutoff,
                                'max_cutoff': edit_max_cutoff,
                                'label': f"p={edit_transition_prob:.2f}\nμ={edit_mean_value}\nσ={edit_std_dev:.1f}\n{edit_dist_type}\nmin={edit_min_cutoff:.1f}\nmax={edit_max_cutoff:.1f}"
                            })
                            st.success(f"Updated edge from {selected_edge['data']['source']} to {selected_edge['data']['target']}")
                            st.rerun()
                
                st.markdown("---")
                
                # Add new edge
                st.write("**Add New Edge**")
                col1, col2 = st.columns(2)
                with col1:
                    source_state = st.selectbox("From State", st.session_state.states, key="manager_source_state")
                with col2:
                    target_states = st.session_state.states[1:] if len(st.session_state.states) > 1 else st.session_state.states
                    target_state = st.selectbox("To State", target_states, key="manager_target_state")
                
                # Edge parameters
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                with col1:
                    transition_prob = st.number_input(
                        "Transition Probability",
                        min_value=0.0,
                        max_value=1.0,
                        value=0.5,
                        step=0.05,
                        format="%.2f",
                        key="manager_transition_prob"
                    )
                with col2:
                    mean_value = st.number_input(
                        "Mean Time (days)",
                        min_value=0.1,
                        max_value=50.0,
                        value=5.0,
                        step=0.1,
                        format="%.1f",
                        key="manager_mean_value"
                    )
                with col3:
                    std_dev = st.number_input(
                        "Standard Deviation (days)",
                        min_value=0.1,
                        max_value=10.0,
                        value=1.0,
                        step=0.1,
                        format="%.1f",
                        key="manager_std_dev"
                    )
                with col4:
                    dist_type = st.selectbox(
                        "Distribution Type",
                        options=["triangular", "uniform", "log-normal", "gamma"],
                        key="manager_dist_type"
                    )
                with col5:
                    min_cutoff = st.number_input(
                        "Min Cutoff",
                        min_value=0.0,
                        max_value=float(mean_value),
                        value=0.0,
                        step=0.1,
                        format="%.1f",
                        key="manager_min_cutoff"
                    )
                with col6:
                    max_cutoff = st.number_input(
                        "Max Cutoff",
                        min_value=float(mean_value),
                        max_value=30.0,
                        value=float(mean_value) + 1.0,
                        step=0.1,
                        format="%.1f",
                        key="manager_max_cutoff"
                    )

                if st.button("Add Edge", key="manager_add_edge"):
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

                # Remove existing edges
                if st.session_state.graph_edges:
                    st.markdown("---")
                    st.write("**Remove Existing Edge**")
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
                        key="manager_edge_to_remove"
                    )
                    
                    if st.button("Remove Edge", key="manager_remove_edge"):
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
                        update_existing=True
                    )
                    
                    st.success(f"✅ Changes permanently saved to database: {machine_name}")
                    
                except Exception as e:
                    st.error(f"❌ Failed to save changes: {str(e)}")
            
            # Add visual state machine representation
            st.markdown("---")
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
                    # Round the time column to 1 decimal place
                    timeline_df["Time (hours)"] = timeline_df["Time (hours)"].round(1)
                    st.dataframe(timeline_df)
                    
                    # Display a visual representation of the timeline
                    st.subheader("Timeline Visualization")
                    for state, time in timeline:
                        st.write(f"{time:.1f} hours: {state}")
            
    else:
        st.write("No saved state machines found") 