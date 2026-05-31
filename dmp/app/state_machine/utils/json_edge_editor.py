"""Shared Streamlit "JSON Edge Editor" component.

Replaces the ~134-line JSON-editor block that was copy-pasted verbatim into
state_machine_manager.py and state_machine_creator.py (differing only in widget
keys and indentation). Pure parsing/serialization lives in logic/edge_json.py;
this module only renders and wires the Streamlit widgets.
"""

import streamlit as st

from ..logic.edge_json import edges_to_json_payload, parse_edges_json


def render_json_edge_editor(states, graph_edges, *, editor_key, update_key, copy_key, clear_key, use_expander=True):
    """Render the bulk JSON edge editor.

    The four widget keys are passed explicitly (rather than derived from a
    prefix) so each caller keeps its exact, historically-divergent key names.

    Returns True if the page render should halt — i.e. a validation failure,
    which the original code handled with a bare ``return`` out of the page.
    Returns False otherwise. On success it sets ``st.session_state.graph_edges``
    and reruns; on an exception it shows the error and returns False (falls
    through), matching the original behavior.
    """
    container = st.expander("📝 JSON Edge Editor", expanded=False) if use_expander else st.container()
    with container:
        st.write("Edit all edges in JSON format for bulk modifications:")

        # Display current edges as JSON (label stripped — it's auto-generated)
        current_json = edges_to_json_payload(graph_edges)

        # JSON editor with validation
        edited_json = st.text_area(
            "Edit Edges (JSON format):",
            value=current_json,
            height=400,
            key=editor_key,
            help="Edit the edges in JSON format. Each edge should have: source, target, transition_prob, mean_time, std_dev, distribution_type, min_cutoff, max_cutoff"
        )

        # Add buttons for JSON operations
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 Update from JSON", key=update_key):
                status, new_edges, errors = parse_edges_json(edited_json, states)
                if status == 'ok':
                    st.session_state.graph_edges = new_edges
                    st.success(f"✅ Successfully updated {len(new_edges)} edges from JSON")
                    st.rerun()
                else:
                    for error in errors:
                        st.error(error)
                    # 'invalid' -> original returned out of the page; 'error' -> fell through.
                    if status == 'invalid':
                        return True

        with col2:
            if st.button("📋 Copy JSON", key=copy_key):
                st.write("```json")
                st.code(current_json, language="json")
                st.write("```")
                st.success("✅ JSON copied to clipboard (use Ctrl+C)")

        with col3:
            if st.button("🗑️ Clear All Edges", key=clear_key):
                st.session_state.graph_edges = []
                st.success("✅ All edges cleared")
                st.rerun()

    return False


def render_json_format_guide(use_expander=True):
    """Render the static 'JSON Format Guide' help panel.

    The two original copies differed only in leading indentation, which
    Streamlit's markdown normalizes (clean_text -> textwrap.dedent), so the
    rendered output is identical regardless of the literal's indentation here.
    """
    container = st.expander("ℹ️ JSON Format Guide", expanded=False) if use_expander else st.container()
    with container:
        st.write("""
        **Required fields for each edge:**
        - `source`: Source state name (must exist in states list)
        - `target`: Target state name (must exist in states list)
        - `transition_prob`: Probability of transition (0.0 to 1.0)
        - `mean_time`: Average time in hours before transition
        - `std_dev`: Standard deviation of transition time
        - `distribution_type`: Distribution type ("normal", "triangular", etc.)
        - `min_cutoff`: Minimum time cutoff in hours
        - `max_cutoff`: Maximum time cutoff in hours

        **Example edge:**
        ```json
        {
          "source": "Exposed",
          "target": "Infectious_Presymptomatic",
          "transition_prob": 1.0,
          "mean_time": 10.0,
          "std_dev": 2.0,
          "distribution_type": "triangular",
          "min_cutoff": 7.0,
          "max_cutoff": 14.0
        }
        ```
        """)
