import streamlit as st
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from state_machine.state_machine_creator import create_state_machine
    from state_machine.state_machine_manager import manage_state_machines
except ImportError as e:
    st.error(f"Error importing state machine modules: {str(e)}")
    st.stop()

# Set page to wide mode
st.set_page_config(layout="wide")

def load_default_states():
    """Load default states from file or return default list if file doesn't exist."""
    default_states = [
        "Infected",
        "Infectious_Asymptomatic",
        "Infectious_Symptomatic",
        "Hospitalized",
        "ICU",
        "Deceased",
        "Recovered"
    ]
    
    states_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "custom_states.txt")
    
    if os.path.exists(states_file):
        with open(states_file, 'r') as f:
            states = [line.strip() for line in f.readlines() if line.strip()]
        return states if states else default_states
    return default_states

def save_states(states):
    """Save states to file."""
    states_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "custom_states.txt")
    os.makedirs(os.path.dirname(states_file), exist_ok=True)
    with open(states_file, 'w') as f:
        f.write('\n'.join(states))

def main():
    # Load states
    states = load_default_states()
    
    # Create tabs for different sections
    create_tab, manage_tab, states_tab = st.tabs(["Create State Machine", "Manage State Machines", "Edit States"])
    
    with states_tab:
        st.header("Edit Disease States")
        st.write("Add, remove, or reorder states for your state machines.")
        
        # Display current states
        st.subheader("Current States")
        for i, state in enumerate(states):
            col1, col2 = st.columns([4, 1])
            with col1:
                states[i] = st.text_input(f"State {i+1}", value=state, key=f"state_{i}")
            with col2:
                if st.button("Remove", key=f"remove_{i}"):
                    states.pop(i)
                    st.rerun()
        
        # Add new state
        if st.button("Add New State"):
            states.append("")
            st.rerun()
        
        # Save states
        if st.button("Save States"):
            # Remove any empty states
            states = [state for state in states if state.strip()]
            if len(states) < 2:
                st.error("You must have at least 2 states!")
            else:
                save_states(states)
                st.success("States saved successfully!")
    
    with create_tab:
        create_state_machine(states)
    
    with manage_tab:
        manage_state_machines(states)

if __name__ == "__main__":
    main() 