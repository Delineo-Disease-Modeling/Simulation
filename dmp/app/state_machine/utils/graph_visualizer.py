"""
Graph Visualization Utilities Module

This module contains graph visualization components for state machines. It provides:

- Cytoscape graph rendering: Interactive graph visualization with node dragging and edge clicking
- Matrix representation: Display of transition matrices in collapsible sections
- HTML generation: Complete HTML/CSS/JavaScript for Cytoscape integration
- Event handling: Node position updates and element click handling

These components are used by both the creator and manager to provide consistent
graph visualization and matrix display functionality while reducing code duplication.
"""

import streamlit as st
import streamlit.components.v1 as components
import json
from .graph_utils import build_nodes_list, get_cytoscape_stylesheet

def render_graph_visualization(states, graph_edges, node_positions, height=600):
    """Render the Cytoscape graph visualization."""
    st.subheader("State Machine Visualization")
    
    # Build nodes list with persisted positions
    nodes = build_nodes_list(states, node_positions)
    elements = nodes + graph_edges

    # Define the stylesheet
    stylesheet = get_cytoscape_stylesheet()

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
                height: {height}px;
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
    components.html(html, height=height)

def render_matrix_representation(states, graph_edges):
    """Render the matrix representation of the graph."""
    from .graph_utils import convert_graph_to_matrices, display_matrices
    
    # Convert graph to matrices and display them
    matrices = convert_graph_to_matrices(states, graph_edges)
    with st.expander("Matrix Representation", expanded=False):
        display_matrices(matrices, states)
    
    return matrices 