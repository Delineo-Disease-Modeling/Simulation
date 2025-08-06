"""
Edge Editor Utilities Module

This module contains reusable edge editing components for state machines. It provides:

- Edge parameter rendering: Consistent input fields for transition probabilities, timing, and distributions
- Add edge functionality: Complete interface for adding new edges with validation
- Edit edge functionality: Interface for modifying existing edge parameters
- Remove edge functionality: Interface for deleting edges from the graph

These components are used by both the creator and manager to ensure consistent
edge editing behavior and reduce code duplication. The components handle all
validation, formatting, and state management for edge operations.
"""

import streamlit as st
from .graph_utils import create_edge_label, format_edge_display_string

def render_edge_parameters(key_prefix, transition_prob=0.5, mean_value=5.0, std_dev=1.0, 
                          dist_type="triangular", min_cutoff=0.0, max_cutoff=6.0):
    """Render edge parameter inputs with consistent styling and validation."""
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        transition_prob = st.number_input(
            "Transition Probability",
            min_value=0.0,
            max_value=1.0,
            value=transition_prob,
            step=0.001,
            format="%.3f",
            key=f"{key_prefix}_transition_prob"
        )
    
    with col2:
        mean_value = st.number_input(
            "Mean Time (days)",
            min_value=0.1,
            max_value=50.0,
            value=mean_value,
            step=0.1,
            format="%.1f",
            key=f"{key_prefix}_mean_value"
        )
    
    with col3:
        std_dev = st.number_input(
            "Standard Deviation (days)",
            min_value=0.1,
            max_value=10.0,
            value=std_dev,
            step=0.1,
            format="%.1f",
            key=f"{key_prefix}_std_dev",
            disabled=(st.session_state.get(f"{key_prefix}_dist_type", dist_type) in ["triangular", "uniform"])
        )
        if st.session_state.get(f"{key_prefix}_dist_type", dist_type) in ["triangular", "uniform"]:
            st.caption("Not used for triangular/uniform distributions")
    
    with col4:
        dist_type = st.selectbox(
            "Distribution Type",
            options=["triangular", "uniform", "log-normal", "gamma"],
            index=["triangular", "uniform", "log-normal", "gamma"].index(dist_type),
            key=f"{key_prefix}_dist_type"
        )
        # Add descriptions for each distribution type
        if st.session_state.get(f"{key_prefix}_dist_type", dist_type) == "triangular":
            st.caption("Most likely value with min/max bounds. Good for recovery times.")
        elif st.session_state.get(f"{key_prefix}_dist_type", dist_type) == "uniform":
            st.caption("Equal probability across min/max range. Good for uncertain periods.")
        elif st.session_state.get(f"{key_prefix}_dist_type", dist_type) == "log-normal":
            st.caption("Right-skewed (some take much longer). Good for disease progression.")
        elif st.session_state.get(f"{key_prefix}_dist_type", dist_type) == "gamma":
            st.caption("Flexible right-skewed. Good for waiting times and symptom onset.")
    
    with col5:
        min_cutoff = st.number_input(
            "Min Cutoff",
            min_value=0.0,
            max_value=float(st.session_state.get(f"{key_prefix}_mean_value", mean_value)),
            value=min_cutoff,
            step=0.1,
            format="%.1f",
            key=f"{key_prefix}_min_cutoff"
        )
    
    with col6:
        max_cutoff = st.number_input(
            "Max Cutoff",
            min_value=float(st.session_state.get(f"{key_prefix}_mean_value", mean_value)),
            max_value=30.0,
            value=max_cutoff,
            step=0.1,
            format="%.1f",
            key=f"{key_prefix}_max_cutoff"
        )
    
    return transition_prob, mean_value, std_dev, dist_type, min_cutoff, max_cutoff

def render_add_edge_section(states, graph_edges, key_prefix="add", use_expander=True):
    """Render the add edge section with consistent styling."""
    if use_expander:
        with st.expander("Add Edge", expanded=False):
            _render_add_edge_content(states, graph_edges, key_prefix)
    else:
        st.write("**Add New Edge**")
        _render_add_edge_content(states, graph_edges, key_prefix)

def _render_add_edge_content(states, graph_edges, key_prefix):
    """Internal function to render add edge content without expander."""
    # State selection on first line
    col1, col2 = st.columns(2)
    with col1:
        source_state = st.selectbox("From State", states, key=f"{key_prefix}_source_state")
    with col2:
        target_states = states[1:] if len(states) > 1 else states
        target_state = st.selectbox("To State", target_states, key=f"{key_prefix}_target_state")
    
    # Edge parameters
    transition_prob, mean_value, std_dev, dist_type, min_cutoff, max_cutoff = render_edge_parameters(
        key_prefix, 0.5, 5.0, 1.0, "triangular", 0.0, 6.0
    )

    if st.button("Add Edge", key=f"{key_prefix}_add_button"):
        if source_state != target_state:  # Prevent self-loops
            edge_exists = any(
                edge["data"]["source"] == source_state and 
                edge["data"]["target"] == target_state 
                for edge in graph_edges
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
                        "label": create_edge_label(transition_prob, mean_value, std_dev, dist_type, min_cutoff, max_cutoff)
                    }
                }
                graph_edges.append(new_edge)
                st.success(f"Added edge from {source_state} to {target_state}")
                st.rerun()
            else:
                st.warning("This edge already exists!")
        else:
            st.warning("Cannot create self-loops!")

def render_edit_edge_section(graph_edges, key_prefix="edit", use_expander=True):
    """Render the edit edge section with consistent styling."""
    if not graph_edges:
        return
    
    if use_expander:
        with st.expander("Edit Existing Edge", expanded=False):
            _render_edit_edge_content(graph_edges, key_prefix)
    else:
        st.write("**Edit Existing Edge**")
        _render_edit_edge_content(graph_edges, key_prefix)

def _render_edit_edge_content(graph_edges, key_prefix):
    """Internal function to render edit edge content without expander."""
    edge_to_edit = st.selectbox(
        "Select Edge to Edit",
        options=[format_edge_display_string(edge) for edge in graph_edges],
        key=f"{key_prefix}_edge_to_edit"
    )
    
    # Find the selected edge
    selected_edge = None
    selected_edge_index = None
    for i, edge in enumerate(graph_edges):
        edge_str = format_edge_display_string(edge)
        if edge_str == edge_to_edit:
            selected_edge = edge
            selected_edge_index = i
            break
    
    if selected_edge:
        st.write(f"**Editing: {selected_edge['data']['source']} → {selected_edge['data']['target']}**")
        
        # Edge parameters for editing
        transition_prob, mean_value, std_dev, dist_type, min_cutoff, max_cutoff = render_edge_parameters(
            key_prefix,
            float(selected_edge['data'].get('transition_prob', 1.0)),
            float(selected_edge['data'].get('mean_time', 5.0)),
            float(selected_edge['data'].get('std_dev', 1.0)),
            selected_edge['data'].get('distribution_type', 'triangular'),
            float(selected_edge['data'].get('min_cutoff', 0.0)),
            float(selected_edge['data'].get('max_cutoff', float(selected_edge['data'].get('mean_time', 5.0)) + 1.0))
        )

        if st.button("Update Edge", key=f"{key_prefix}_update_button"):
            # Update the edge with new values
            graph_edges[selected_edge_index]['data'].update({
                'transition_prob': transition_prob,
                'mean_time': mean_value,
                'std_dev': std_dev,
                'distribution_type': dist_type,
                'min_cutoff': min_cutoff,
                'max_cutoff': max_cutoff,
                'label': create_edge_label(transition_prob, mean_value, std_dev, dist_type, min_cutoff, max_cutoff)
            })
            st.success(f"Updated edge from {selected_edge['data']['source']} to {selected_edge['data']['target']}")
            st.rerun()

def render_remove_edge_section(graph_edges, key_prefix="remove", use_expander=True):
    """Render the remove edge section with consistent styling."""
    if not graph_edges:
        return
    
    if use_expander:
        with st.expander("Remove Edge", expanded=False):
            _render_remove_edge_content(graph_edges, key_prefix)
    else:
        st.write("**Remove Existing Edge**")
        _render_remove_edge_content(graph_edges, key_prefix)

def _render_remove_edge_content(graph_edges, key_prefix):
    """Internal function to render remove edge content without expander."""
    edge_to_remove = st.selectbox(
        "Select Edge to Remove",
        options=[format_edge_display_string(edge) for edge in graph_edges],
        key=f"{key_prefix}_edge_to_remove"
    )
    
    if st.button("Remove Edge", key=f"{key_prefix}_remove_button"):
        # Find and remove the selected edge
        for i, edge in enumerate(graph_edges):
            edge_str = format_edge_display_string(edge)
            if edge_str == edge_to_remove:
                graph_edges.pop(i)
                st.success(f"Removed edge {edge_to_remove}")
                st.rerun()
                break 