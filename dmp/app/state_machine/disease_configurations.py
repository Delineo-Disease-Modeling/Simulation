import streamlit as st
import json
import os
import pandas as pd

# Disease-specific state templates with model categories and demographic options
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
        "description": "COVID-19 state machine with realistic default parameters based on epidemiological research. This template provides a general COVID-19 progression model that can be customized for specific variants or scenarios.",
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
        },
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General COVID-19 progression model"
            },
            {
                "id": "variant",
                "name": "Variant-Specific Model",
                "description": "Model specific to COVID-19 variants"
            }
        ],
        "demographic_options": {
            "Age": ["0-18", "19-64", "65+"],
            "Sex": ["M", "F"],
            "Vaccination Status": ["Vaccinated", "Unvaccinated"]
        },
        "edges": [
            {
                "source": "Infected",
                "target": "Infectious_Asymptomatic",
                "transition_prob": 0.4,
                "mean_time": 5.0,
                "std_dev": 1.5,
                "distribution_type": "triangular",
                "min_cutoff": 3.0,
                "max_cutoff": 8.0
            },
            {
                "source": "Infected",
                "target": "Infectious_Symptomatic",
                "transition_prob": 0.6,
                "mean_time": 5.0,
                "std_dev": 1.5,
                "distribution_type": "triangular",
                "min_cutoff": 3.0,
                "max_cutoff": 8.0
            },
            {
                "source": "Infectious_Asymptomatic",
                "target": "Recovered",
                "transition_prob": 1.0,
                "mean_time": 10.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 7.0,
                "max_cutoff": 14.0
            },
            {
                "source": "Infectious_Symptomatic",
                "target": "Hospitalized",
                "transition_prob": 0.15,
                "mean_time": 10.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 7.0,
                "max_cutoff": 14.0
            },
            {
                "source": "Infectious_Symptomatic",
                "target": "Recovered",
                "transition_prob": 0.85,
                "mean_time": 10.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 7.0,
                "max_cutoff": 14.0
            },
            {
                "source": "Hospitalized",
                "target": "ICU",
                "transition_prob": 0.25,
                "mean_time": 7.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 10.0
            },
            {
                "source": "Hospitalized",
                "target": "Recovered",
                "transition_prob": 0.75,
                "mean_time": 7.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 10.0
            },
            {
                "source": "ICU",
                "target": "Recovered",
                "transition_prob": 0.7,
                "mean_time": 14.0,
                "std_dev": 4.0,
                "distribution_type": "triangular",
                "min_cutoff": 10.0,
                "max_cutoff": 21.0
            },
            {
                "source": "ICU",
                "target": "Deceased",
                "transition_prob": 0.3,
                "mean_time": 14.0,
                "std_dev": 4.0,
                "distribution_type": "triangular",
                "min_cutoff": 10.0,
                "max_cutoff": 21.0
            }
        ]
    },
    "Influenza": {
        "states": [],
        "description": "Influenza template - to be defined",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General influenza progression model"
            }
        ],
        "demographic_options": {
            "Age": ["0-18", "19-64", "65+"],
            "Sex": ["M", "F"],
            "Vaccination Status": ["Vaccinated", "Unvaccinated"]
        },
        "edges": []
    },
    "Ebola": {
        "states": [],
        "description": "Ebola template - to be defined",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General Ebola progression model"
            }
        ],
        "demographic_options": {
            "Age": ["0-18", "19-64", "65+"],
            "Sex": ["M", "F"]
        },
        "edges": []
    },
    "Zika": {
        "states": [],
        "description": "Zika template - to be defined",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General Zika progression model"
            }
        ],
        "demographic_options": {
            "Age": ["0-18", "19-64", "65+"],
            "Sex": ["M", "F"]
        },
        "edges": []
    },
    "Measles": {
        "states": [
            "Exposed",
            "Infectious_Asymptomatic",
            "Infectious_Presymptomatic", 
            "Infectious_Symptomatic",
            "Hospitalized",
            "ICU",
            "Recovered",
            "Deceased"
        ],
        "description": "Measles state machine with realistic progression from exposure through recovery. Measles is highly contagious with distinct phases: incubation, presymptomatic infectious period, symptomatic period, and potential complications requiring hospitalization.",
        "typical_transitions": [
            "Exposed → Infectious_Presymptomatic (incubation period)",
            "Exposed → Infectious_Asymptomatic (mild or subclinical infection)",
            "Infectious_Presymptomatic → Infectious_Symptomatic (rash appears)",
            "Infectious_Asymptomatic → Recovered (no symptoms develop)",
            "Infectious_Symptomatic → Recovered (most cases)",
            "Infectious_Symptomatic → Hospitalized (severe cases)",
            "Hospitalized → Recovered (most hospitalized cases)",
            "Hospitalized → ICU (critical cases)",
            "ICU → Recovered (most ICU cases)",
            "ICU → Deceased (rare but possible)"
            ],
        "parameters": {
            "vaccination": ["Unvaccinated", "Partially Vaccinated", "Fully Vaccinated"]
        },
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General measles progression model"
            },
            {
                "id": "vaccination",
                "name": "Vaccination Model",
                "description": "Model specific to vaccination status"
            }
        ],
        "demographic_options": {
            "Age": ["0-4", "5-14", "15-64", "65+"],
            "Sex": ["M", "F"]
        },
        "edges": [
            {
                "source": "Exposed",
                "target": "Infectious_Asymptomatic",
                "transition_prob": 0.0,
                "mean_time": 10.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 7.0,
                "max_cutoff": 14.0
            },
            {
                "source": "Infectious_Asymptomatic",
                "target": "Recovered",
                "transition_prob": 1.0,
                "mean_time": 3.0,
                "std_dev": 1.0,
                "distribution_type": "triangular",
                "min_cutoff": 2.0,
                "max_cutoff": 5.0
            },
            {
                "source": "Exposed",
                "target": "Infectious_Presymptomatic",
                "transition_prob": 1.0,
                "mean_time": 10.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 7.0,
                "max_cutoff": 14.0
            },
            {
                "source": "Infectious_Presymptomatic",
                "target": "Infectious_Symptomatic",
                "transition_prob": 1.0,
                "mean_time": 4.0,
                "std_dev": 1.0,
                "distribution_type": "triangular",
                "min_cutoff": 2.0,
                "max_cutoff": 6.0
            },
            {
                "source": "Infectious_Symptomatic",
                "target": "Recovered",
                "transition_prob": 0.80,
                "mean_time": 5.0,
                "std_dev": 1.5,
                "distribution_type": "triangular",
                "min_cutoff": 3.0,
                "max_cutoff": 8.0
            },
            {
                "source": "Infectious_Symptomatic",
                "target": "Hospitalized",
                "transition_prob": 0.18,
                "mean_time": 4.0,
                "std_dev": 1.0,
                "distribution_type": "triangular",
                "min_cutoff": 2.0,
                "max_cutoff": 6.0
            },
            {
                "source": "Infectious_Symptomatic",
                "target": "Deceased",
                "transition_prob": 0.02,
                "mean_time": 6.0,
                "std_dev": 1.0,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 8.0
            },
            {
                "source": "Hospitalized",
                "target": "ICU",
                "transition_prob": 0.1,
                "mean_time": 3.0,
                "std_dev": 1.0,
                "distribution_type": "triangular",
                "min_cutoff": 2.0,
                "max_cutoff": 4.0
            },
            {
                "source": "Hospitalized",
                "target": "Recovered",
                "transition_prob": 0.85,
                "mean_time": 6.0,
                "std_dev": 2.0,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 8.0
            },
            {
                "source": "Hospitalized",
                "target": "Deceased",
                "transition_prob": 0.05,
                "mean_time": 5.0,
                "std_dev": 1.5,
                "distribution_type": "triangular",
                "min_cutoff": 3.0,
                "max_cutoff": 7.0
            },
            {
                "source": "ICU",
                "target": "Recovered",
                "transition_prob": 0.6,
                "mean_time": 7.0,
                "std_dev": 2.5,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 10.0
            },
            {
                "source": "ICU",
                "target": "Deceased",
                "transition_prob": 0.4,
                "mean_time": 7.0,
                "std_dev": 2,
                "distribution_type": "triangular",
                "min_cutoff": 4.0,
                "max_cutoff": 10.0
            }
        ]
    },
    "Tuberculosis": {
        "states": [],
        "description": "Tuberculosis template - to be defined",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [
            {
                "id": "default",
                "name": "Default Model",
                "description": "General tuberculosis progression model"
            }
        ],
        "demographic_options": {
            "Age": ["0-18", "19-64", "65+"],
            "Sex": ["M", "F"]
        },
        "edges": []
    }
}

def get_disease_template(disease_name):
    """Get the template for a specific disease"""
    return DISEASE_TEMPLATES.get(disease_name, None)

def get_available_diseases():
    """Get list of available diseases"""
    return list(DISEASE_TEMPLATES.keys())

def display_disease_configurations():
    """Display disease configurations interface"""
    st.header("Disease Configurations")
    st.write("Configure disease-specific parameters, states, and transitions.")
    
    # Disease selection
    selected_disease = st.selectbox(
        "Select Disease:",
        options=get_available_diseases(),
        key="disease_config_selection"
    )
    
    if selected_disease:
        disease_template = get_disease_template(selected_disease)
        
        if disease_template:
            # Display disease information
            st.subheader(f"📋 {selected_disease} Configuration")
            
            # Description
            st.write("**Description:**")
            st.write(disease_template["description"])
            
            # States
            st.write("**States:**")
            if disease_template["states"]:
                for state in disease_template["states"]:
                    st.write(f"- {state}")
            else:
                st.write("No states defined")
            
            # Typical transitions
            st.write("**Typical Transitions:**")
            if disease_template["typical_transitions"]:
                for transition in disease_template["typical_transitions"]:
                    st.write(f"- {transition}")
            else:
                st.write("No typical transitions defined")
            
            # Model categories
            st.write("**Model Categories:**")
            if "model_categories" in disease_template:
                for category in disease_template["model_categories"]:
                    st.write(f"- **{category['name']}** ({category['id']}): {category['description']}")
            else:
                st.write("No model categories defined")
            
            # Demographic options
            st.write("**Demographic Options:**")
            if "demographic_options" in disease_template:
                for demo_type, options in disease_template["demographic_options"].items():
                    st.write(f"- **{demo_type}**: {', '.join(options)}")
            else:
                st.write("No demographic options defined")
            
            # Parameters (variants, etc.)
            if disease_template["parameters"]:
                st.write("**Parameters:**")
                for param_type, options in disease_template["parameters"].items():
                    st.write(f"- **{param_type}**: {', '.join(options)}")
            
            # Edges
            st.write("**Default Edges:**")
            if disease_template["edges"]:
                edge_df = pd.DataFrame(disease_template["edges"])
                st.dataframe(edge_df)
            else:
                st.write("No default edges defined")
            
            # Edit interface
            st.markdown("---")
            st.subheader("🔧 Edit Configuration")
            
            # Add new model category
            with st.expander("Add Model Category"):
                new_category_id = st.text_input("Category ID (e.g., 'custom')")
                new_category_name = st.text_input("Category Name (e.g., 'Custom Model')")
                new_category_desc = st.text_area("Category Description")
                
                if st.button("Add Model Category") and new_category_id and new_category_name:
                    if "model_categories" not in disease_template:
                        disease_template["model_categories"] = []
                    
                    disease_template["model_categories"].append({
                        "id": new_category_id,
                        "name": new_category_name,
                        "description": new_category_desc
                    })
                    st.success(f"Added model category: {new_category_name}")
            
            # Add new demographic option
            with st.expander("Add Demographic Option"):
                new_demo_type = st.text_input("Demographic Type (e.g., 'Age')")
                new_demo_options = st.text_area("Options (one per line)")
                
                if st.button("Add Demographic Option") and new_demo_type and new_demo_options:
                    if "demographic_options" not in disease_template:
                        disease_template["demographic_options"] = {}
                    
                    options_list = [opt.strip() for opt in new_demo_options.split('\n') if opt.strip()]
                    disease_template["demographic_options"][new_demo_type] = options_list
                    st.success(f"Added demographic option: {new_demo_type}")
            
            # Add new parameter
            with st.expander("Add Parameter"):
                new_param_type = st.text_input("Parameter Type (e.g., 'variant')")
                new_param_options = st.text_area("Parameter Options (one per line)")
                
                if st.button("Add Parameter") and new_param_type and new_param_options:
                    options_list = [opt.strip() for opt in new_param_options.split('\n') if opt.strip()]
                    disease_template["parameters"][new_param_type] = options_list
                    st.success(f"Added parameter: {new_param_type}")
        else:
            st.error(f"No template found for {selected_disease}")

def get_disease_states(disease_name):
    """Get states for a specific disease"""
    template = get_disease_template(disease_name)
    return template["states"] if template else []

def get_disease_parameters(disease_name):
    """Get parameters for a specific disease"""
    template = get_disease_template(disease_name)
    return template.get("parameters", {}) if template else {}

def get_disease_edges(disease_name):
    """Get default edges for a specific disease"""
    template = get_disease_template(disease_name)
    return template["edges"] if template else []

def get_available_variants(disease_name):
    """Get available variants for a specific disease"""
    parameters = get_disease_parameters(disease_name)
    return parameters.get("variant", [])

def get_disease_model_categories(disease_name):
    """Get model categories for a specific disease"""
    template = get_disease_template(disease_name)
    if template and "model_categories" in template:
        return template["model_categories"]
    return [
        {
            "id": "default",
            "name": "Default Model",
            "description": "General disease progression model"
        }
    ]

def get_disease_demographic_options(disease_name):
    """Get demographic options for a specific disease"""
    template = get_disease_template(disease_name)
    if template and "demographic_options" in template:
        return template["demographic_options"]
    return {
        "Age": ["0-18", "19-64", "65+"],
        "Sex": ["M", "F"]
    }