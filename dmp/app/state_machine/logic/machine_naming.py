"""Pure builders for state-machine naming / demographics.

Extracted from the duplicated demographics-dict construction in
state_machine_manager.py and state_machine_creator.py. Streamlit-free.
"""


def build_demographics_dict(demographics_list):
    """Build the demographics dict from the session-state demographics rows.

    Mirrors the identical loops in both editors: a "Custom" row contributes
    custom_key -> custom_value (only when both are set); any other row
    contributes key -> value (only when both are truthy).
    """
    demographics = {}
    for demo in demographics_list:
        if demo["key"] == "Custom":
            if demo.get("custom_key") and demo.get("custom_value"):
                demographics[demo["custom_key"]] = demo["custom_value"]
        elif demo["key"] and demo["value"]:
            demographics[demo["key"]] = demo["value"]
    return demographics


def build_machine_name_and_path(disease_name, model_category, variant_name,
                                vaccination_status, demographics):
    """Build the saved machine name and model_path from the creator's selections.

    Pure extraction of the COVID-19 / Measles / default branching in the creator's
    step 4. Returns ``(state_machine_name, model_path)``.
    """
    name_parts = [disease_name]
    model_path = "default.general"  # Default

    if disease_name == "COVID-19":
        if model_category == "variant" and variant_name:
            model_path = f"variant.{variant_name}.general"
            name_parts.append(f"variant={variant_name}")
        else:
            model_path = "default.general"
    elif disease_name == "Measles":
        if model_category == "vaccination" and vaccination_status:
            model_path = f"vaccination.{vaccination_status}.general"
            name_parts.append(f"vaccination={vaccination_status}")
        else:
            model_path = "default.general"
    else:
        model_path = "default.general"

    # Add demographics to name
    if demographics:
        for key, value in demographics.items():
            name_parts.append(f"{key}={value}")

    state_machine_name = " | ".join(name_parts) if len(name_parts) > 1 else f"{disease_name} | Default"
    return state_machine_name, model_path
