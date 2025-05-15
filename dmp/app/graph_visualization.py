import streamlit as st
import streamlit.components.v1 as components
import os
import json

# Set page to wide mode
st.set_page_config(layout="wide")

def create_state_machine(states):
    """Create a graph visualization of disease states using Cytoscape.js"""
    # Initialize graph state in session state if not exists
    if 'graph_edges' not in st.session_state:
        st.session_state.graph_edges = []
    if 'node_positions' not in st.session_state:
        st.session_state.node_positions = {}
    if 'clicked_element' not in st.session_state:
        st.session_state.clicked_element = None

    # Create the graph
    st.markdown("---")  # Add a visual separator
    st.header("State Machine")
    
    # Add edge creation interface
    st.subheader("Add Edge")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        source_state = st.selectbox("From State", states, key="source_state")
    with col2:
        target_state = st.selectbox("To State", states, key="target_state")
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
                        "label": f"p={transition_prob:.2f}\nμ={mean_value}\nσ={std_dev:.1f}\n{dist_type}"
                    }
                }
                st.session_state.graph_edges.append(new_edge)
                st.success(f"Added edge from {source_state} to {target_state} with probability {transition_prob:.2f}, mean time {mean_value}, std dev {std_dev:.1f}, and {dist_type} distribution")
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
        </style>
    </head>
    <body>
        <div id="cy"></div>
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
        </script>
    </body>
    </html>
    """

    # Display the graph using Streamlit's components
    components.html(html, height=600)

    # Display clicked element info if available
    if st.session_state.clicked_element:
        st.write("Selected element:", st.session_state.clicked_element) 