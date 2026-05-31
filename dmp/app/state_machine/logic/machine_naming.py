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
