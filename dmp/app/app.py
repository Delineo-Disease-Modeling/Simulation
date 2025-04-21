import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
from pathlib import Path

# Add the Simulation directory to the Python path for imports
simulation_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(simulation_dir)

from dmp.core.simulation_functions import run_simulation
from dmp.cli.user_input import (
    validate_matrices, 
    find_matching_matrix, 
    extract_matrices, 
    parse_mapping_file, 
    validate_states_format
)
import json
from state_management import initialize_states, handle_states_management
from demographic_management import (
    initialize_demographics, 
    collect_demographic_options, 
    get_valid_ages,
    validate_demographic_value
)
from simulation_management import handle_simulation
from simulation_analysis import analyze_simulations

# Initialize session state variables
if 'matrix_sets' not in st.session_state:
    st.session_state.matrix_sets = {}

if 'default_demographics' not in st.session_state:
    st.session_state.default_demographics = {
        "Age": "*",
        "Sex": "*",
        "Vaccination Status": "*",
        "Variant": "*"  # Added Variant to default demographics
    }

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

# Main title
st.title("Disease Modeling Platform")

# Sidebar for input method selection
st.sidebar.title("Input Method")
input_method = st.sidebar.radio(
    "Choose input method:",
    ["File Upload", "Manual Input"]
)

# Handle states management
handle_states_management()

# File upload section - ONLY ONCE
if input_method == "File Upload":
    # File upload logic
    st.sidebar.subheader("Upload Files")
    uploaded_file = st.sidebar.file_uploader("Upload Combined Matrix CSV", type="csv")
    demographic_file = st.sidebar.file_uploader("Upload Demographic Mapping CSV", type="csv")
    states_file = st.sidebar.file_uploader("Upload States (optional)", type="txt")

    # Process uploaded files
    if uploaded_file is not None and demographic_file is not None:
        try:
            # Process states file if provided
            if states_file is not None:
                states_content = states_file.getvalue().decode()
                new_states = [s.strip() for s in states_content.split('\n') if s.strip()]
                validate_states_format(new_states)
                st.session_state.states = new_states

            # Process demographic mapping and matrices
            mapping_df, demographic_categories = parse_mapping_file(demographic_file)
            
            # Load matrices with explicit delimiter, no header, and skip comment lines
            matrix_df = pd.read_csv(uploaded_file, header=None, sep=',', skipinitialspace=True, comment='#')
            
            # Store the raw matrix data and mapping data in session state
            st.session_state.matrix_df = matrix_df
            st.session_state.mapping_df = mapping_df
            st.session_state.demographic_categories = demographic_categories
            
            # Create matrix sets from uploaded files
            for idx, row in mapping_df.iterrows():
                set_name = f"Matrix_Set_{idx + 1}"
                demographics = {col: row[col] for col in demographic_categories}
                
                try:
                    # Extract matrices for this set
                    block_size = 6 * len(st.session_state.states)
                    start_idx = idx * block_size
                    end_idx = start_idx + block_size
                    
                    matrices = {
                        "Transition Matrix": matrix_df.iloc[start_idx:start_idx + len(st.session_state.states)].values,
                        "Distribution Type": matrix_df.iloc[start_idx + len(st.session_state.states):start_idx + 2*len(st.session_state.states)].values,
                        "Mean": matrix_df.iloc[start_idx + 2*len(st.session_state.states):start_idx + 3*len(st.session_state.states)].values,
                        "Standard Deviation": matrix_df.iloc[start_idx + 3*len(st.session_state.states):start_idx + 4*len(st.session_state.states)].values,
                        "Min Cut-Off": matrix_df.iloc[start_idx + 4*len(st.session_state.states):start_idx + 5*len(st.session_state.states)].values,
                        "Max Cut-Off": matrix_df.iloc[start_idx + 5*len(st.session_state.states):end_idx].values
                    }
                    
                    st.session_state.matrix_sets[set_name] = {
                        "matrices": matrices,
                        "demographics": demographics
                    }
                except Exception as e:
                    st.error(f"Error processing matrix set {set_name}: {str(e)}")
                    continue
            
            st.success(f"Successfully loaded {len(st.session_state.matrix_sets)} matrix sets!")
            
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")
            st.exception(e)

else:  # Manual Input
    st.header("Matrix Set Management")
    
    # Matrix set creation with custom demographics
    col1, col2 = st.columns([3, 1])
    with col1:
        new_set_name = st.text_input("New Matrix Set Name")
    with col2:
        if st.button("Add Matrix Set") and new_set_name:
            if new_set_name not in st.session_state.matrix_sets:
                num_states = len(st.session_state.states)
                st.session_state.matrix_sets[new_set_name] = {
                    "matrices": {
                        "Transition Matrix": np.zeros((num_states, num_states)),
                        "Distribution Type": np.ones((num_states, num_states)),
                        "Mean": np.full((num_states, num_states), 5.0),
                        "Standard Deviation": np.ones((num_states, num_states)),
                        "Min Cut-Off": np.ones((num_states, num_states)),
                        "Max Cut-Off": np.full((num_states, num_states), 10.0)
                    },
                    "demographics": dict(st.session_state.default_demographics)
                }

    # Demographic Management Section
    st.header("Demographic Management")
    demo_tab1, demo_tab2 = st.tabs(["Default Demographics", "Add New Demographic"])
    
    with demo_tab1:
        st.subheader("Edit Default Demographics")
        default_demo_cols = st.columns(3)
        with default_demo_cols[0]:
            if st.button("Reset to Original Defaults"):
                st.session_state.default_demographics = {
                    "Age": "*",
                    "Sex": "*",
                    "Vaccination Status": "*",
                    "Variant": "*"  # Added Variant to default demographics
                }
        
        # Edit default demographics
        new_defaults = {}
        for demo_name in st.session_state.default_demographics.keys():
            if demo_name == "Sex":
                new_defaults[demo_name] = st.selectbox(
                    f"Default {demo_name}",
                    options=["*", "M", "F"],
                    index=["*", "M", "F"].index(st.session_state.default_demographics[demo_name])
                )
            elif demo_name == "Vaccination Status":
                new_defaults[demo_name] = st.selectbox(
                    f"Default {demo_name}",
                    options=["*", "Vaccinated", "Unvaccinated"],
                    index=["*", "Vaccinated", "Unvaccinated"].index(st.session_state.default_demographics[demo_name])
                )
            else:
                value = st.text_input(
                    f"Default {demo_name}",
                    value=st.session_state.default_demographics[demo_name],
                    help="Use * for any value"
                )
                if validate_demographic_value(demo_name, value):
                    new_defaults[demo_name] = value
                else:
                    st.error(f"Invalid value for {demo_name}")
                    new_defaults[demo_name] = st.session_state.default_demographics[demo_name]
        
        st.session_state.default_demographics = new_defaults

    with demo_tab2:
        st.subheader("Add New Demographic Category")
        new_demo_cols = st.columns(2)
        with new_demo_cols[0]:
            new_demo_name = st.text_input("New Demographic Name")
        with new_demo_cols[1]:
            new_demo_default = st.text_input("Default Value", value="*", help="Use * for any value")
            if st.button("Add Demographic") and new_demo_name:
                if new_demo_name in ["Sex", "Vaccination Status", "Age Range"]:
                    st.error("Cannot add reserved demographic names")
                elif new_demo_name in st.session_state.default_demographics:
                    st.error("Demographic already exists")
                elif not new_demo_name.strip():
                    st.error("Demographic name cannot be empty")
                else:
                    st.session_state.default_demographics[new_demo_name] = new_demo_default or "*"
                    # Add to existing matrix sets
                    for matrix_set in st.session_state.matrix_sets.values():
                        matrix_set["demographics"][new_demo_name] = new_demo_default or "*"

    # Matrix Sets Overview
    if st.session_state.matrix_sets:
        st.header("Matrix Sets Overview")
        
        overview_tab, edit_tab = st.tabs(["Overview", "Edit Matrix Set"])
        
        with overview_tab:
            for set_name, matrix_set in st.session_state.matrix_sets.items():
                with st.expander(f"Matrix Set: {set_name}"):
                    # Display demographics
                    st.subheader("Demographics")
                    demo_df = pd.DataFrame([matrix_set["demographics"]])
                    st.dataframe(demo_df)
                    
                    # Display matrices in a neat grid
                    st.subheader("Matrices")
                    cols = st.columns(3)
                    for idx, (matrix_name, matrix) in enumerate(matrix_set["matrices"].items()):
                        with cols[idx % 3]:
                            st.write(f"**{matrix_name}**")
                            # Format matrix values to 2 decimal places
                            formatted_matrix = np.round(matrix, 2)
                            df = pd.DataFrame(
                                formatted_matrix,
                                index=st.session_state.states,
                                columns=st.session_state.states
                            )
                            st.dataframe(df)
        
        # Edit tab
        with edit_tab:
            selected_set = st.selectbox(
                "Select Matrix Set to Edit",
                list(st.session_state.matrix_sets.keys())
            )
            
            if selected_set:
                st.subheader(f"Editing Matrix Set: {selected_set}")
                matrix_set = st.session_state.matrix_sets[selected_set]
                
                # Demographics editing
                st.write("### Demographics")
                updated_demographics = {}
                demo_cols = st.columns(min(3, len(matrix_set["demographics"])))
                
                for idx, (demo_name, demo_value) in enumerate(matrix_set["demographics"].items()):
                    with demo_cols[idx % len(demo_cols)]:
                        if demo_name == "Sex":
                            updated_demographics[demo_name] = st.selectbox(
                                demo_name,
                                options=["*", "M", "F"],
                                index=["*", "M", "F"].index(demo_value),
                                key=f"{selected_set}_{demo_name}"
                            )
                        elif demo_name == "Vaccination Status":
                            updated_demographics[demo_name] = st.selectbox(
                                demo_name,
                                options=["*", "Vaccinated", "Unvaccinated"],
                                index=["*", "Vaccinated", "Unvaccinated"].index(demo_value),
                                key=f"{selected_set}_{demo_name}"
                            )
                        else:
                            value = st.text_input(
                                demo_name,
                                value=demo_value,
                                help="Use * for any value",
                                key=f"{selected_set}_{demo_name}"
                            )
                            if validate_demographic_value(demo_name, value):
                                updated_demographics[demo_name] = value
                            else:
                                st.error(f"Invalid value for {demo_name}")
                                updated_demographics[demo_name] = demo_value
                
                matrix_set["demographics"] = updated_demographics
                
                # Matrix editing
                st.write("### Matrices")
                matrix_type = st.selectbox(
                    "Select Matrix to Edit",
                    list(matrix_set["matrices"].keys())
                )
                
                if matrix_type:
                    st.write(f"Editing {matrix_type}")
                    matrix = matrix_set["matrices"][matrix_type]
                    updated_matrix = []
                    
                    # Create matrix editor
                    for i in range(len(st.session_state.states)):
                        row = []
                        cols = st.columns(len(st.session_state.states))
                        for j in range(len(st.session_state.states)):
                            with cols[j]:
                                val = st.number_input(
                                    f"{st.session_state.states[i]} → {st.session_state.states[j]}",
                                    value=float(matrix[i][j]),
                                    format="%.2f",
                                    key=f"{selected_set}_{matrix_type}_{i}_{j}"
                                )
                                row.append(val)
                        updated_matrix.append(row)
                    
                    matrix_set["matrices"][matrix_type] = np.array(updated_matrix)

    # Add export/import functionality
    if st.session_state.matrix_sets:
        st.header("Export/Import Matrix Sets")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Export Matrix Sets"):
                # Convert matrix sets to JSON-compatible format
                export_data = {
                    name: {
                        "matrices": {k: v.tolist() for k, v in set_data["matrices"].items()},
                        "demographics": set_data["demographics"]
                    }
                    for name, set_data in st.session_state.matrix_sets.items()
                }
                st.download_button(
                    "Download Matrix Sets",
                    data=json.dumps(export_data, indent=2),
                    file_name="matrix_sets.json",
                    mime="application/json"
                )
        
        with col2:
            uploaded_file = st.file_uploader("Import Matrix Sets", type="json")
            if uploaded_file is not None:
                try:
                    import_data = json.load(uploaded_file)
                    for name, set_data in import_data.items():
                        st.session_state.matrix_sets[name] = {
                            "matrices": {k: np.array(v) for k, v in set_data["matrices"].items()},
                            "demographics": set_data["demographics"]
                        }
                    st.success("Matrix sets imported successfully!")
                except Exception as e:
                    st.error(f"Error importing matrix sets: {str(e)}")

    # Matrix Sets Overview section ends here

# Move Simulation Input Section outside of input method conditions
st.markdown("---")  # Add a visual separator
st.header("Run Simulation")

# Collect all unique demographics and their possible values
demographic_options = collect_demographic_options()

st.subheader("Enter Demographics for Simulation")
simulation_demographics = {}

if demographic_options or get_valid_ages():  # Show if there are demographics or valid ages
    num_columns = min(3, max(1, len(demographic_options) + 1))  # +1 for age
    demo_cols = st.columns(num_columns)
    
    # Handle age input first
    with demo_cols[0]:
        valid_ages = get_valid_ages()
        if valid_ages:
            age_options = ["*"] + valid_ages  # Add wildcard option
            age_selection = st.selectbox(
                "Select Age",
                options=age_options,
                key="sim_age"
            )
            if age_selection != "*":
                # Store the age as a number
                simulation_demographics["Age"] = int(age_selection)
            else:
                simulation_demographics["Age"] = "*"
    
    # Handle other demographics
    col_idx = 1
    for demo_name, possible_values in demographic_options.items():
        if demo_name != "Age":  # Skip age as we handle it separately
            with demo_cols[col_idx % num_columns]:
                valid_options = sorted([v for v in possible_values if v])
                
                if demo_name == "Sex":
                    sex_options = ["*"] + [opt for opt in ["M", "F"] if opt in valid_options]
                    selection = st.selectbox(
                        f"Select {demo_name}",
                        options=sex_options,
                        key=f"sim_{demo_name}"
                    )
                    simulation_demographics[demo_name] = selection
                elif demo_name == "Vaccination Status":
                    vax_options = ["*"] + [opt for opt in ["Vaccinated", "Unvaccinated"] if opt in valid_options]
                    selection = st.selectbox(
                        f"Select {demo_name}",
                        options=vax_options,
                        key=f"sim_{demo_name}"
                    )
                    simulation_demographics[demo_name] = selection
                elif demo_name == "Variant":
                    variant_options = ["*"] + [opt for opt in ["Delta", "Omicron"] if opt in valid_options]
                    selection = st.selectbox(
                        f"Select {demo_name}",
                        options=variant_options,
                        key=f"sim_{demo_name}"
                    )
                    simulation_demographics[demo_name] = selection
                else:
                    # For other demographics, use text input with wildcard option
                    value = st.text_input(
                        f"Enter {demo_name}",
                        value="*",
                        key=f"sim_{demo_name}"
                    )
                    simulation_demographics[demo_name] = value
                col_idx += 1

# Store the collected demographics in session state
st.session_state.simulation_demographics = simulation_demographics

# Add initial state selection
st.subheader("Select Initial State")
initial_state = st.selectbox(
    "Initial State",
    options=st.session_state.states,
    key="initial_state"
)

# Add tabs for single simulation and analysis
sim_tab, analysis_tab = st.tabs(["Single Simulation", "Analysis"])

with sim_tab:
    # Handle single simulation
    handle_simulation(initial_state)

with analysis_tab:
    # Handle multiple simulations and analysis
    analyze_simulations(simulation_demographics, initial_state)
