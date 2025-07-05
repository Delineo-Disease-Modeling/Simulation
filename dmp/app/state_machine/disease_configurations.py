import streamlit as st
import json
import os

# Disease-specific state templates
DISEASE_TEMPLATES = {
    "COVID-19": {
        "states": [
            "Infected",
            "Infectious_Asymptomatic",
            "Infectious_Symptomatic",
            "Hospitalized",
            "ICU",
            "Deceased",
            "Recovered"
        ],
        "description": "COVID-19 state machine with standard progression from infection to recovery or death",
        "typical_transitions": [
            "Infected → Infectious_Asymptomatic",
            "Infected → Infectious_Symptomatic",
            "Infectious_Asymptomatic → Recovered",
            "Infectious_Symptomatic → Hospitalized",
            "Infectious_Symptomatic → Recovered",
            "Hospitalized → ICU",
            "Hospitalized → Recovered",
            "ICU → Recovered",
            "ICU → Deceased"
        ],
        "parameters": {
            "variant": ["Delta", "Omicron"]
        }
    },
    "Influenza": {
        "states": [],
        "description": "Influenza template - to be defined",
        "typical_transitions": [],
        "parameters": {}
    },
    "Ebola": {
        "states": [],
        "description": "Ebola template - to be defined",
        "typical_transitions": [],
        "parameters": {}
    },
    "Zika": {
        "states": [],
        "description": "Zika template - to be defined",
        "typical_transitions": [],
        "parameters": {}
    },
    "Measles": {
        "states": [],
        "description": "Measles template - to be defined",
        "typical_transitions": [],
        "parameters": {}
    },
    "Tuberculosis": {
        "states": [],
        "description": "Tuberculosis template - to be defined",
        "typical_transitions": [],
        "parameters": {}
    }
}

def get_disease_template(disease_name):
    """Get the template for a specific disease."""
    return DISEASE_TEMPLATES.get(disease_name, None)

def get_available_diseases():
    """Get list of available diseases."""
    return list(DISEASE_TEMPLATES.keys())

def display_disease_configurations():
    """Display disease configurations and templates."""
    st.header("Disease Configurations")
    st.write("View predefined state templates for different diseases. These templates ensure consistency across state machines for the same disease.")
    
    # Disease selection
    selected_disease = st.selectbox(
        "Select Disease to View Template:",
        options=get_available_diseases(),
        key="disease_template_viewer"
    )
    
    if selected_disease:
        template = get_disease_template(selected_disease)
        
        if template:
            # Display disease information
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader(f"{selected_disease} Template")
                st.write(f"**Description:** {template['description']}")
                
                # Display states only if they exist
                if template['states']:
                    st.write("**Predefined States:**")
                    for i, state in enumerate(template['states'], 1):
                        st.write(f"{i}. {state}")
                    
                    # Display typical transitions only if they exist
                    if template['typical_transitions']:
                        st.write("**Typical Transitions:**")
                        for transition in template['typical_transitions']:
                            st.write(f"• {transition}")
                    
                    # Display disease parameters if they exist
                    if template.get('parameters'):
                        st.write("**Disease Parameters:**")
                        for param_name, param_options in template['parameters'].items():
                            st.write(f"• **{param_name.title()}**: {', '.join(param_options)}")
                else:
                    st.warning("⚠️ No states defined for this template yet.")
            
            with col2:
                st.write("**Template Info:**")
                st.write(f"**Total States:** {len(template['states'])}")
                st.write(f"**Typical Transitions:** {len(template['typical_transitions'])}")
    
    # Show all available templates in a compact view
    st.markdown("---")
    st.subheader("All Available Templates")
    
    # Create a table of all templates
    template_data = []
    for disease, template in DISEASE_TEMPLATES.items():
        template_data.append({
            "Disease": disease,
            "States": len(template['states']),
            "Description": template['description'][:50] + "..." if len(template['description']) > 50 else template['description']
        })
    
    # Display as a table
    import pandas as pd
    df = pd.DataFrame(template_data)
    st.dataframe(df, use_container_width=True)
    
def get_disease_states(disease_name):
    """Get the states for a specific disease."""
    template = get_disease_template(disease_name)
    return template['states'] if template else []

def get_disease_parameters(disease_name):
    """Get the parameters for a specific disease."""
    template = get_disease_template(disease_name)
    return template.get('parameters', {}) if template else {} 