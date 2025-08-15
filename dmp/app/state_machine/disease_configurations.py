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
        "description": "Influenza - placeholder for future implementation",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [],
        "demographic_options": {},
        "edges": []
    },
    "Ebola": {
        "states": [],
        "description": "Ebola - placeholder for future implementation",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [],
        "demographic_options": {},
        "edges": []
    },
    "Zika": {
        "states": [],
        "description": "Zika - placeholder for future implementation",
        "typical_transitions": [],
        "parameters": {},
        "model_categories": [],
        "demographic_options": {},
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

# Nested model structure for organizing state machines
# Model paths are separate from demographics - they're purely organizational
# The .general suffix is a placeholder for any future subcategory expansion
DISEASE_MODELS = {
    "COVID-19": {
        "default": {
            "general": {
                "description": "General COVID-19 model",
                "demographics": ["Age", "Sex"]
            }
        },
        "variant": {
            "Delta": {
                "general": {
                    "description": "Delta variant model",
                    "demographics": ["Age", "Sex", "Vaccination Status"]
                }
            },
            "Omicron": {
                "general": {
                    "description": "Omicron variant model",
                    "demographics": ["Age", "Sex", "Vaccination Status"]
                }
            }
        }
    },
    "Measles": {
        "default": {
            "general": {
                "description": "General measles model",
                "demographics": ["Age", "Sex"]
            }
        },
        "vaccination": {
            "Unvaccinated": {
                "general": {
                    "description": "Unvaccinated measles model",
                    "demographics": ["Age", "Sex"]
                }
            },
            "Partially Vaccinated": {
                "general": {
                    "description": "Partially vaccinated measles model",
                    "demographics": ["Age", "Sex"]
                }
            },
            "Fully Vaccinated": {
                "general": {
                    "description": "Fully vaccinated measles model",
                    "demographics": ["Age", "Sex"]
                }
            }
        }
    },
    "Influenza": {
        "default": {
            "general": {
                "description": "General influenza model",
                "demographics": ["Age", "Sex"]
            }
        }
    },
    "Ebola": {
        "default": {
            "general": {
                "description": "General Ebola model",
                "demographics": ["Age", "Sex"]
            }
        }
    },
    "Zika": {
        "default": {
            "general": {
                "description": "General Zika model",
                "demographics": ["Age", "Sex"]
            }
        }
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
    st.write("View disease-specific parameters, states, and model structure.")
    st.info("Note: Model structure can be configured in the disease_configurations.py file.")
    
    # Disease selection
    selected_disease = st.selectbox(
        "Select Disease:",
        options=get_available_diseases(),
        key="disease_config_selection"
    )
    
    if selected_disease:
        disease_template = get_disease_template(selected_disease)
        disease_models = get_disease_models(selected_disease)
        
        if disease_template:
            # Display disease information
            st.subheader(f"{selected_disease} Configuration")
            
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
            
            # Demographic options
            st.write("**Demographic Options:**")
            if "demographic_options" in disease_template and disease_template["demographic_options"]:
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
            
            # Nested Model Structure
            st.markdown("---")
            st.subheader("Model Structure")
            
            if disease_models:
                st.write("**Available Model Paths:**")
                available_paths = get_available_model_paths(selected_disease)
                
                # Display as hierarchical text with proper indentation
                def _display_hierarchy(node, level=0, path=""):
                    for key, value in node.items():
                        indent = "&nbsp;&nbsp;&nbsp;&nbsp;" * level
                        current_path = f"{path}.{key}" if path else key
                        
                        if isinstance(value, dict) and "description" in value:
                            # Leaf node (actual model)
                            st.markdown(f"{indent}**{key}** ({current_path})")
                            st.markdown(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;Description: {value['description']}")
                            st.markdown(f"{indent}&nbsp;&nbsp;&nbsp;&nbsp;Demographics: {', '.join(value['demographics'])}")
                        else:
                            # Branch node (category)
                            st.markdown(f"{indent}**{key}**")
                            _display_hierarchy(value, level + 1, current_path)
                
                _display_hierarchy(disease_models)
                
                st.write("**API Usage Examples:**")
                for path in available_paths:
                    model_info = get_model_info(selected_disease, path)
                    if model_info:
                        st.code(f'POST /simulate\n{{\n  "disease_name": "{selected_disease}",\n  "model_path": "{path}",\n  "demographics": {{...}}\n}}')
            else:
                st.write("No model structure defined")
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
    if template and "model_categories" in template and template["model_categories"]:
        return template["model_categories"]
    # Return empty array for placeholder diseases
    return []

def get_disease_demographic_options(disease_name):
    """Get demographic options for a specific disease"""
    template = get_disease_template(disease_name)
    if template and "demographic_options" in template and template["demographic_options"]:
        return template["demographic_options"]
    # Return empty dict for placeholder diseases
    return {}

def get_disease_models(disease_name):
    """Get the nested model structure for a specific disease"""
    return DISEASE_MODELS.get(disease_name, {})

def get_available_model_paths(disease_name):
    """Get all available model paths for a disease as dot-notation strings"""
    models = get_disease_models(disease_name)
    paths = []
    
    def _collect_paths(node, current_path=""):
        for key, value in node.items():
            if isinstance(value, dict) and "description" in value:
                # This is a leaf node (actual model)
                full_path = f"{current_path}.{key}" if current_path else key
                paths.append(full_path)
            elif isinstance(value, dict):
                # This is a branch node (category)
                new_path = f"{current_path}.{key}" if current_path else key
                _collect_paths(value, new_path)
    
    _collect_paths(models)
    return paths

def validate_model_path(disease_name, model_path):
    """Validate if a model path exists for a disease"""
    if not model_path:
        return False
    
    models = get_disease_models(disease_name)
    if not models:
        return False
    
    # Split the path by dots
    path_parts = model_path.split('.')
    
    # Navigate through the nested structure
    current = models
    for part in path_parts:
        if part not in current:
            return False
        current = current[part]
    
    # Check if we reached a leaf node (has description)
    return isinstance(current, dict) and "description" in current

def get_model_info(disease_name, model_path):
    """Get information about a specific model path"""
    if not validate_model_path(disease_name, model_path):
        return None
    
    models = get_disease_models(disease_name)
    path_parts = model_path.split('.')
    
    # Navigate to the model
    current = models
    for part in path_parts:
        current = current[part]
    
    return current

def get_parent_model_path(disease_name, model_path):
    """Get the parent model path (one level up)"""
    if not model_path or '.' not in model_path:
        return None
    
    parent_path = '.'.join(model_path.split('.')[:-1])
    if validate_model_path(disease_name, parent_path):
        return parent_path
    return None

def get_default_model_path(disease_name):
    """Get the default model path for a disease"""
    models = get_disease_models(disease_name)
    if not models or "default" not in models:
        return None
    
    # Find the first available default model
    default_models = models["default"]
    for key, value in default_models.items():
        if isinstance(value, dict) and "description" in value:
            return f"default.{key}"
    
    return None