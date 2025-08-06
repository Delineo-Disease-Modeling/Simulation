import streamlit as st
import os
from .state_machine_db import StateMachineDB
import numpy as np

DEFAULT_STATES = [
    "Infected",
    "Infectious_Asymptomatic",
    "Infectious_Symptomatic",
    "Hospitalized",
    "ICU",
    "Deceased",
    "Recovered"
]

def validate_matrices(states, edges):
    """Validate the state machine matrices and return any issues found."""
    issues = []
    
    # Convert graph to matrices
    n = len(states)
    state_to_idx = {state: i for i, state in enumerate(states)}
    
    # Initialize matrices
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
        
        # Get edge properties
        transition_prob = edge['data'].get('transition_prob', 1.0)
        mean_time = edge['data'].get('mean_time', 0)
        std_dev = edge['data'].get('std_dev', 0.0)
        dist_type = edge['data'].get('distribution_type', 'normal')
        min_cutoff = edge['data'].get('min_cutoff', 0.0)
        max_cutoff = edge['data'].get('max_cutoff', float('inf'))
        
        # Update matrices
        transition_matrix[i, j] = transition_prob
        mean_matrix[i, j] = mean_time
        std_dev_matrix[i, j] = std_dev
        distribution_matrix[i, j] = dist_type_to_num.get(dist_type, 0)
        min_cutoff_matrix[i, j] = min_cutoff
        max_cutoff_matrix[i, j] = max_cutoff
    
    # Validate transition probabilities
    for i in range(n):
        row_sum = np.sum(transition_matrix[i, :])
        if row_sum > 0 and not np.isclose(row_sum, 1.0, atol=1e-10):
            # Find all non-zero probabilities in this row
            non_zero_edges = []
            for j in range(n):
                if transition_matrix[i, j] > 0:
                    non_zero_edges.append((states[j], transition_matrix[i, j]))
            
            # Create detailed error message
            issue_msg = f"Row {i+1} ({states[i]}) of transition matrix sums to {row_sum:.6f}, should sum to 1.0\n"
            issue_msg += f"  Edges from {states[i]}:\n"
            for target_state, prob in non_zero_edges:
                issue_msg += f"    -> {target_state}: {prob:.6f}\n"
            issue_msg += f"  Missing probability: {1.0 - row_sum:.6f}\n"
            issue_msg += f"  To fix: Add edge(s) with total probability of {1.0 - row_sum:.6f} or adjust existing probabilities"
            
            issues.append(issue_msg)
    
    # Validate distribution parameters
    for i in range(n):
        for j in range(n):
            if transition_matrix[i, j] > 0:
                # Check mean time
                if mean_matrix[i, j] <= 0:
                    issues.append(f"Mean time must be positive for transition {states[i]} → {states[j]}")
                
                # Check standard deviation
                if std_dev_matrix[i, j] < 0:
                    issues.append(f"Standard deviation must be non-negative for transition {states[i]} → {states[j]}")
                
                # Check distribution type
                if distribution_matrix[i, j] == 0:
                    issues.append(f"Invalid distribution type for transition {states[i]} → {states[j]}")
                
                # Check cutoffs
                if min_cutoff_matrix[i, j] >= max_cutoff_matrix[i, j]:
                    issues.append(f"Min cutoff must be less than max cutoff for transition {states[i]} → {states[j]}")
                
                # Distribution-specific validations
                dist_type = next((k for k, v in dist_type_to_num.items() if v == distribution_matrix[i, j]), None)
                if dist_type == "gamma" and mean_matrix[i, j] <= 0:
                    issues.append(f"Gamma distribution requires positive mean for transition {states[i]} → {states[j]}")
    
    return issues

def load_default_states():
    """Load default states from file or return default list if file doesn't exist."""
    # Initialize database
    db = StateMachineDB()
    
    # Get the most recently updated state machine's states
    saved_machines = db.list_state_machines()
    if saved_machines:
        # Load the most recent machine's states
        machine_data = db.load_state_machine(saved_machines[0][0])
        if machine_data and machine_data["states"]:
            return machine_data["states"]
    
    return DEFAULT_STATES

def save_states(states, machine_id=None):
    """Save states to the database."""
    db = StateMachineDB()
    
    if machine_id:
        # Update existing machine's states
        machine_data = db.load_state_machine(machine_id)
        if machine_data:
            # Validate matrices before saving
            issues = validate_matrices(states, machine_data["edges"])
            if issues:
                st.error("Cannot save state machine due to validation errors:")
                for issue in issues:
                    st.error(f"- {issue}")
                return False
            
            db.save_state_machine(
                machine_data["name"],
                states,
                machine_data["edges"],
                machine_data["demographics"],
                update_existing=True
            )
    else:
        # Create a new machine with these states
        db.save_state_machine(
            "Default",
            states,
            [],  # No edges for new machine
            {}   # No demographics for new machine
        )
    return True

def handle_state_changes(new_states, old_states, machine_id=None):
    """Handle state changes by clearing related data and showing warnings."""
    if new_states != old_states:
        # Show warning about state changes
        st.warning("""
        ⚠️ Changing states for this state machine will:
        - Clear all existing edges
        - Clear all matrix data
        
        This action cannot be undone.
        """)
        
        # Add confirmation button
        if st.button("Confirm State Changes"):
            # Clear only the current state machine's data
            if 'graph_edges' in st.session_state:
                st.session_state.graph_edges = []
            if 'matrix_sets' in st.session_state:
                st.session_state.matrix_sets = {}
            if 'node_positions' in st.session_state:
                st.session_state.node_positions = {}
            
            # Save the new states to the database
            save_states(new_states, machine_id)
            
            st.success("States updated successfully! All edges and matrices have been cleared.")
            st.rerun()
        else:
            # If user doesn't confirm, revert to old states
            st.session_state.states = old_states
            return False
    
    return False

def edit_states():
    """Edit disease states interface."""
    st.header("Edit Disease States")

    # Initialize states in session state if not exists
    if 'states' not in st.session_state:
        st.session_state.states = load_default_states()
    if 'previous_states' not in st.session_state:
        st.session_state.previous_states = st.session_state.states.copy()
    if 'pending_state_save' not in st.session_state:
        st.session_state.pending_state_save = False
    if 'pending_states' not in st.session_state:
        st.session_state.pending_states = None
    if 'pending_default' not in st.session_state:
        st.session_state.pending_default = False

    # Reset to default
    if st.button("Use Default States"):
        st.session_state.pending_default = True

    # Handle default states confirmation
    if st.session_state.get("pending_default"):
        st.warning("""
        ⚠️ Resetting to default states will:
        - Clear all existing edges
        - Clear all matrix data

        This action cannot be undone.
        """)

        if st.button("Confirm Reset to Default"):
            # Clear session data
            st.session_state.graph_edges = []
            st.session_state.matrix_sets = {}
            st.session_state.node_positions = {}

            # Reset to default states
            st.session_state.states = DEFAULT_STATES.copy()
            st.session_state.previous_states = DEFAULT_STATES.copy()
            save_states(DEFAULT_STATES)

            # Clear flags
            st.session_state.pending_default = False

            st.success("Reset to default states successfully! All edges and matrices have been cleared.")
            st.rerun()

        if st.button("Cancel Reset"):
            st.session_state.pending_default = False
            st.info("Reset canceled.")
            st.rerun()

    # State Editing UI
    st.markdown("Enter one state per line. You can add, remove, or rename states below:")
    states_text = "\n".join(st.session_state.states)
    new_states_text = st.text_area("", value=states_text, height=200, key="states_text")

    # Convert textarea to list of states
    new_states = [state.strip() for state in new_states_text.split("\n") if state.strip()]

    # Handle Save Logic
    if st.button("Save States"):
        if len(new_states) < 2:
            st.error("You must have at least 2 states!")
        elif new_states != st.session_state.previous_states:
            # If states were changed, store pending changes and ask for confirmation
            st.session_state.pending_state_save = True
            st.session_state.pending_states = new_states
        else:
            # No change, just save
            save_states(new_states)
            st.success("States saved successfully!")

    # Handle Confirmation Flow
    if st.session_state.get("pending_state_save"):
        st.warning("""
        ⚠️ Changing states for this state machine will:
        - Clear all existing edges
        - Clear all matrix data

        This action cannot be undone.
        """)

        if st.button("Confirm State Changes"):
            # Clear session data
            st.session_state.graph_edges = []
            st.session_state.matrix_sets = {}
            st.session_state.node_positions = {}

            # Save new states
            new_states = st.session_state.pending_states
            st.session_state.states = new_states
            st.session_state.previous_states = new_states.copy()
            save_states(new_states)

            # Clear flags
            st.session_state.pending_state_save = False
            st.session_state.pending_states = None

            st.success("States updated successfully! All edges and matrices have been cleared.")
            st.rerun()

        if st.button("Cancel Changes"):
            st.session_state.pending_state_save = False
            st.session_state.pending_states = None
            st.info("Changes canceled.")
            st.rerun() 