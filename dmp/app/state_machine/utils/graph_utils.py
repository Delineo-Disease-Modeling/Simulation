"""
Graph Utilities Module

This module contains core graph manipulation and display functions used by both
the state machine creator and manager. It provides:

- Matrix conversion: Convert graph edges to transition matrices for simulation
- Matrix display: Render matrices in a grid layout for visualization
- Node building: Create node lists with positioning for Cytoscape visualization
- Styling: Standard Cytoscape stylesheet for consistent graph appearance
- Edge formatting: Utilities for creating edge labels and display strings

These functions are shared between the creator and manager to ensure consistent
behavior and reduce code duplication.
"""

import numpy as np
import pandas as pd
import streamlit as st

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

def build_nodes_list(states, node_positions):
    """Build nodes list with persisted positions."""
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
        pos = node_positions.get(state, default_pos)
        nodes.append({
            "data": {"id": state, "label": state},
            "position": pos
        })
    return nodes

def get_cytoscape_stylesheet():
    """Get the standard Cytoscape stylesheet."""
    return [
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

def create_edge_label(transition_prob, mean_time, std_dev, dist_type, min_cutoff, max_cutoff):
    """Create a standardized edge label."""
    return f"p={transition_prob:.3f}\nμ={mean_time}\nσ={std_dev:.1f}\n{dist_type}\nmin={min_cutoff:.1f}\nmax={max_cutoff:.1f}"

def format_edge_display_string(edge):
    """Format an edge for display in dropdowns."""
    return (
        f"{edge['data']['source']} → {edge['data']['target']} "
        f"(p={edge['data'].get('transition_prob', 1.0):.3f}, "
        f"μ={edge['data'].get('mean_time', 0)}, "
        f"σ={edge['data'].get('std_dev', 0.0):.1f}, "
        f"{edge['data'].get('distribution_type', 'triangular')}, "
        f"min={edge['data'].get('min_cutoff', 0.0):.1f}, "
        f"max={edge['data'].get('max_cutoff', float('inf')):.1f})"
    ) 