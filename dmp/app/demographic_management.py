import streamlit as st

def initialize_demographics():
    """Initialize default demographics in session state"""
    if 'default_demographics' not in st.session_state:
        st.session_state.default_demographics = {
            "Age Range": "*",
            "Sex": "*",
            "Vaccination Status": "*"
        }

def validate_demographic_value(demo_name, value):
    """Validate demographic values based on their type"""
    if demo_name == "Age Range":
        if value == "*":
            return True
        try:
            # Check if it's a valid age range format (e.g., "19-64")
            start, end = map(int, value.split("-"))
            return start >= 0 and end >= start
        except (ValueError, AttributeError):
            return False
    elif demo_name == "Sex":
        return value in ["*", "M", "F"]
    elif demo_name == "Vaccination Status":
        return value in ["*", "Vaccinated", "Unvaccinated"]
    else:
        # For any other demographics, accept non-empty strings
        return bool(value and isinstance(value, str))

def get_age_ranges_from_matrix_sets():
    """Extract and parse all age ranges from matrix sets"""
    age_ranges = []
    for matrix_set in st.session_state.matrix_sets.values():
        age_range = matrix_set["demographics"].get("Age Range")
        if age_range and age_range != "*":
            try:
                start, end = map(int, age_range.split("-"))
                age_ranges.append((start, end))
            except ValueError:
                continue
    return age_ranges

def get_valid_ages():
    """Get list of valid ages based on matrix set age ranges"""
    age_ranges = get_age_ranges_from_matrix_sets()
    if not age_ranges:
        return []
    
    valid_ages = set()
    for start, end in age_ranges:
        valid_ages.update(range(start, end + 1))
    return sorted(list(valid_ages))

def collect_demographic_options():
    """Collect all unique demographics and their possible values"""
    demographic_options = {}
    for matrix_set in st.session_state.matrix_sets.values():
        for demo_name, demo_value in matrix_set["demographics"].items():
            if demo_name not in demographic_options:
                demographic_options[demo_name] = set()
            if demo_value != "*" and demo_name != "Age Range":
                demographic_options[demo_name].add(demo_value)
    return demographic_options 