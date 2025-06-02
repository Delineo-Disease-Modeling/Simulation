import streamlit as st
import os
import sys

# Add the parent directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from cli.user_input import validate_states_format

def initialize_states():
    """Initialize default states in session state"""
    if 'states' not in st.session_state:
        st.session_state.states = [
            "Infected", 
            "Infectious Asymptomatic", 
            "Infectious Symptomatic", 
            "Hospitalized", 
            "ICU", 
            "Removed", 
            "Recovered"
        ]
    if 'previous_states' not in st.session_state:
        st.session_state.previous_states = st.session_state.states.copy()

def handle_states_management():
    """Handle states management in sidebar"""
    st.sidebar.title("States Management")
    states_method = st.sidebar.radio(
        "Choose states input method:",
        ["Use Default States", "Custom States"]
    )

    if states_method == "Custom States":
        handle_custom_states()
    elif states_method == "Use Default States":
        handle_default_states()

def handle_custom_states():
    """Handle custom states input and validation"""
    custom_states = st.sidebar.text_area(
        "Enter states (one per line)",
        value="\n".join(st.session_state.states)
    )
    
    if st.sidebar.button("Update States"):
        try:
            new_states = [s.strip() for s in custom_states.split('\n') if s.strip()]
            validate_states_format(new_states)
            
            validate_and_update_states(new_states)
            
        except ValueError as e:
            st.sidebar.error(f"Error updating states: {str(e)}")

def handle_default_states():
    """Reset to default states"""
    default_states = [
        "Infected", 
        "Infectious Asymptomatic", 
        "Infectious Symptomatic", 
        "Hospitalized", 
        "ICU", 
        "Removed", 
        "Recovered"
    ]
    if st.session_state.states != default_states:
        validate_and_update_states(default_states)

def validate_and_update_states(new_states):
    """Validate and update states, checking matrix compatibility"""
    # Check if states are actually changing
    if new_states != st.session_state.states:
        # Store previous states for reference
        st.session_state.previous_states = st.session_state.states.copy()
        
        # Show warning about state changes
        st.sidebar.warning("""
        ⚠️ Changing states will:
        - Clear all existing edges
        - Clear all matrix data
        - Reset any saved state machines
        
        This action cannot be undone.
        """)
        
        # Clear all related data
        if 'graph_edges' in st.session_state:
            st.session_state.graph_edges = []
        if 'matrix_sets' in st.session_state:
            st.session_state.matrix_sets = {}
        if 'selected_machine' in st.session_state:
            st.session_state.selected_machine = None
        
        # Update states
        st.session_state.states = new_states
        st.sidebar.success("States updated successfully! All edges and matrices have been cleared.")
        
        # Force a rerun to update the UI
        st.rerun() 