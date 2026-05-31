"""Pure JSON (de)serialization + validation for state-machine edges.

Extracted from the duplicated "JSON Edge Editor" blocks in
state_machine_manager.py and state_machine_creator.py so the parsing/validation
can be unit-tested without Streamlit. The thin Streamlit wrapper that renders
the editor lives in utils/json_edge_editor.py.

Note: this imports create_edge_label from utils.graph_utils (which imports
streamlit), so unlike transition_math this module is not strictly Streamlit-free.
create_edge_label itself is a pure f-string; importing it keeps a single source
of truth for the edge label format (see graph_utils.create_edge_label).
"""

import json

from ..utils.graph_utils import create_edge_label

REQUIRED_EDGE_FIELDS = [
    'source', 'target', 'transition_prob', 'mean_time',
    'std_dev', 'distribution_type', 'min_cutoff', 'max_cutoff',
]


def edges_to_json_payload(graph_edges):
    """Serialize edges to the indented JSON string the editor displays.

    Strips the auto-generated 'label' field, exactly as the original editors did.
    """
    edges_for_json = []
    for edge in graph_edges:
        edge_data = edge['data'].copy()
        # Remove the label field as it's auto-generated
        if 'label' in edge_data:
            del edge_data['label']
        edges_for_json.append(edge_data)
    return json.dumps(edges_for_json, indent=2)


def parse_edges_json(edited_json, valid_states):
    """Parse + validate edited JSON into edges.

    Returns ``(status, new_edges, errors)`` where status is one of:

      - ``'ok'``      success; ``new_edges`` is the rebuilt edge list, ``errors`` == []
      - ``'invalid'`` a structural/validation failure. The original code did a bare
                      ``return`` out of the whole page on these, so the caller should
                      halt the render. ``new_edges`` is None.
      - ``'error'``   an exception while parsing/coercing. The original code showed
                      the error but did NOT return (it fell through to render the rest
                      of the page), so the caller should NOT halt. ``new_edges`` is None.

    This three-way status preserves the original asymmetry between validation
    failures (halt) and exceptions (show-and-continue). It stops at the first
    failure to match the original single-error display.
    """
    try:
        parsed_edges = json.loads(edited_json)

        # Validate the structure
        if not isinstance(parsed_edges, list):
            return 'invalid', None, ["❌ JSON must be a list of edge objects"]

        # Convert back to the expected format with 'data' wrapper
        new_edges = []
        for edge_data in parsed_edges:
            if not isinstance(edge_data, dict):
                return 'invalid', None, ["❌ Each edge must be a JSON object"]

            # Validate required fields
            missing_fields = [field for field in REQUIRED_EDGE_FIELDS if field not in edge_data]
            if missing_fields:
                return 'invalid', None, [f"❌ Missing required fields: {', '.join(missing_fields)}"]

            # Validate that source and target states exist
            if edge_data['source'] not in valid_states:
                return 'invalid', None, [f"❌ Source state '{edge_data['source']}' not found in states list"]
            if edge_data['target'] not in valid_states:
                return 'invalid', None, [f"❌ Target state '{edge_data['target']}' not found in states list"]

            # Create the edge in the expected format
            new_edges.append({
                'data': {
                    'source': edge_data['source'],
                    'target': edge_data['target'],
                    'transition_prob': float(edge_data['transition_prob']),
                    'mean_time': int(edge_data['mean_time']),
                    'std_dev': float(edge_data['std_dev']),
                    'distribution_type': edge_data['distribution_type'],
                    'min_cutoff': float(edge_data['min_cutoff']),
                    'max_cutoff': float(edge_data['max_cutoff']),
                    'label': create_edge_label(
                        float(edge_data['transition_prob']),
                        int(edge_data['mean_time']),
                        float(edge_data['std_dev']),
                        edge_data['distribution_type'],
                        float(edge_data['min_cutoff']),
                        float(edge_data['max_cutoff'])
                    )
                }
            })

        return 'ok', new_edges, []

    except json.JSONDecodeError as e:
        return 'error', None, [f"❌ Invalid JSON format: {str(e)}"]
    except ValueError as e:
        return 'error', None, [f"❌ Invalid data type: {str(e)}"]
    except Exception as e:
        return 'error', None, [f"❌ Error updating edges: {str(e)}"]
