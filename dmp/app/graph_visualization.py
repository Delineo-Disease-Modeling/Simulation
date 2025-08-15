import streamlit as st
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from state_machine.state_machine_creator import create_state_machine
    from state_machine.state_machine_manager import manage_state_machines
    from state_machine.disease_configurations import display_disease_configurations
    from state_machine.state_machine_comparison import compare_state_machines
except ImportError as e:
    st.error(f"Error importing state machine modules: {str(e)}")
    st.stop()

# Set page to wide mode
st.set_page_config(layout="wide")

# Add a title at the top
st.title("Disease Modeling Platform")

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
    
    # Initialize database
    from state_machine.state_machine_db import StateMachineDB
    db = StateMachineDB()
    
    # Get the most recently updated state machine's states
    saved_machines = db.list_state_machines()
    if saved_machines:
        # Load the most recent machine's states
        machine_data = db.load_state_machine(saved_machines[0][0])
        if machine_data and machine_data["states"]:
            return machine_data["states"]
    
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
    
    # Initialize session state if not exists
    if 'states' not in st.session_state:
        st.session_state.states = states

    # Create tabs for different functionalities
    tab1, tab2, tab3, tab4 = st.tabs(["State Machine Manager", "State Machine Creator", "Disease Configurations", "State Machine Comparison"])
    
    with tab1:
        manage_state_machines(st.session_state.states)
    
    with tab2:
        create_state_machine(st.session_state.states)
    
    with tab3:
        display_disease_configurations()
    
    with tab4:
        compare_state_machines()

if __name__ == "__main__":
    main() 