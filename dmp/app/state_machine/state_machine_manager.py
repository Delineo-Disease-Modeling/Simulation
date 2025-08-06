import streamlit as st
import streamlit.components.v1 as components
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .utils.graph_utils import convert_graph_to_matrices, display_matrices, build_nodes_list, get_cytoscape_stylesheet, create_edge_label, format_edge_display_string
from .utils.edge_editor import render_add_edge_section, render_edit_edge_section, render_remove_edge_section
from .utils.graph_visualizer import render_graph_visualization, render_matrix_representation
from .disease_configurations import get_disease_model_categories, get_disease_demographic_options, get_available_variants

def validate_transition_probabilities(states, graph_edges):
    """Validate that outgoing probabilities for each state sum to 1.0."""
    validation_results = {
        'is_valid': True,
        'errors': []
    }
    
    # Group edges by source state
    outgoing_edges = {}
    for edge in graph_edges:
        source = edge['data']['source']
        if source not in outgoing_edges:
            outgoing_edges[source] = []
        outgoing_edges[source].append(edge['data']['transition_prob'])
    
    # Check each state's outgoing probabilities
    for state in outgoing_edges:
        total_prob = sum(outgoing_edges[state])
        if abs(total_prob - 1.0) > 0.001:  # Allow for small floating point errors
            validation_results['is_valid'] = False
            validation_results['errors'].append(
                f"State '{state}' has outgoing probabilities that sum to {total_prob:.3f} instead of 1.0"
            )
    
    return validation_results

def calculate_aggregated_probabilities(states, graph_edges):
    """Calculate the aggregated probability of reaching each state from the initial state."""
    if not graph_edges:
        return {}
    
    # Create adjacency matrix with probabilities
    state_to_index = {state: i for i, state in enumerate(states)}
    n_states = len(states)
    
    # Initialize transition matrix
    transition_matrix = np.zeros((n_states, n_states))
    
    # Fill transition matrix from edges
    for edge in graph_edges:
        source_idx = state_to_index[edge['data']['source']]
        target_idx = state_to_index[edge['data']['target']]
        prob = edge['data']['transition_prob']
        transition_matrix[source_idx][target_idx] = prob
    
    # Calculate aggregated probabilities using matrix multiplication
    # Start from initial state (index 0)
    current_probs = np.zeros(n_states)
    current_probs[0] = 1.0  # Start in initial state
    
    aggregated_probs = current_probs.copy()
    
    # Iterate through states to calculate reachability
    for _ in range(n_states):  # Maximum n_states iterations
        new_probs = np.dot(current_probs, transition_matrix)
        aggregated_probs += new_probs
        current_probs = new_probs
        
        # Stop if no more probability flow
        if np.sum(new_probs) < 0.001:
            break
    
    # Convert back to state names
    result = {}
    for i, state in enumerate(states):
        result[state] = min(1.0, aggregated_probs[i])  # Cap at 1.0
    
    return result

def analyze_simulation_results(simulation_results, states):
    """Analyze multiple simulation results and return statistics."""
    if not simulation_results:
        return None
    
    # Extract data for analysis
    final_states = []
    total_durations = []
    state_visits = {state: [] for state in states}
    state_durations = {state: [] for state in states}  # Time spent in each state
    
    for timeline in simulation_results:
        # Final state
        final_states.append(timeline[-1][0])
        
        # Total duration
        total_duration = timeline[-1][1]
        total_durations.append(total_duration)
        
        # Calculate time spent in each state
        visited_states = set()
        for i in range(len(timeline)):
            current_state = timeline[i][0]
            current_time = timeline[i][1]
            visited_states.add(current_state)
            
            # Calculate time spent in this state
            if i < len(timeline) - 1:
                # Time spent = time to next state - current time
                next_time = timeline[i + 1][1]
                time_spent = next_time - current_time
            else:
                # For the final state, we don't know how long they stay there
                # We could either use 0 or some default value
                # For now, let's use 0 since the simulation ends here
                time_spent = 0
            
            if current_state in state_durations:
                state_durations[current_state].append(time_spent)
        
        # Count visits to each state
        for state in states:
            state_visits[state].append(1 if state in visited_states else 0)
    
    # Calculate statistics
    stats = {
        'total_simulations': len(simulation_results),
        'final_state_distribution': pd.Series(final_states).value_counts().to_dict(),
        'total_duration_stats': {
            'mean': np.mean(total_durations),
            'median': np.median(total_durations),
            'std': np.std(total_durations),
            'min': np.min(total_durations),
            'max': np.max(total_durations),
            'percentiles': {
                '25th': np.percentile(total_durations, 25),
                '75th': np.percentile(total_durations, 75)
            }
        },
        'state_visit_rates': {state: np.mean(visits) * 100 for state, visits in state_visits.items()},
        'state_time_stats': {}
    }
    
    # Calculate time statistics for each state
    for state in states:
        durations = state_durations[state]
        if durations:
            # Filter out zero durations (final states) for more meaningful statistics
            non_zero_durations = [d for d in durations if d > 0]
            if non_zero_durations:
                stats['state_time_stats'][state] = {
                    'mean_time': np.mean(non_zero_durations),
                    'median_time': np.median(non_zero_durations),
                    'std_time': np.std(non_zero_durations),
                    'min_time': np.min(non_zero_durations),
                    'max_time': np.max(non_zero_durations),
                    'visit_count': len(durations),
                    'non_zero_visits': len(non_zero_durations)
                }
            else:
                # All visits were final state (duration = 0)
                stats['state_time_stats'][state] = {
                    'mean_time': 0,
                    'median_time': 0,
                    'std_time': 0,
                    'min_time': 0,
                    'max_time': 0,
                    'visit_count': len(durations),
                    'non_zero_visits': 0
                }
        else:
            stats['state_time_stats'][state] = {
                'mean_time': 0,
                'median_time': 0,
                'std_time': 0,
                'min_time': 0,
                'max_time': 0,
                'visit_count': 0,
                'non_zero_visits': 0
            }
    
    return stats

def create_visualizations(stats, simulation_results, states):
    """Create visualizations for the analysis results."""
    if not stats or not simulation_results:
        return None
    
    # Create figure with subplots
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Multi-Run Simulation Analysis', fontsize=16, fontweight='bold')
    
    # 1. Final State Distribution (Pie Chart)
    if stats['final_state_distribution']:
        final_states = list(stats['final_state_distribution'].keys())
        counts = list(stats['final_state_distribution'].values())
        
        axes[0, 0].pie(counts, labels=final_states, autopct='%1.1f%%', startangle=90)
        axes[0, 0].set_title('Final State Distribution')
    
    # 2. Total Duration Distribution (Histogram)
    total_durations = [timeline[-1][1] for timeline in simulation_results]
    axes[0, 1].hist(total_durations, bins=min(20, len(total_durations)//5), alpha=0.7, edgecolor='black')
    axes[0, 1].axvline(stats['total_duration_stats']['mean'], color='red', linestyle='--', label=f"Mean: {stats['total_duration_stats']['mean']:.1f}h")
    axes[0, 1].axvline(stats['total_duration_stats']['median'], color='green', linestyle='--', label=f"Median: {stats['total_duration_stats']['median']:.1f}h")
    axes[0, 1].set_xlabel('Total Duration (hours)')
    axes[0, 1].set_ylabel('Frequency')
    axes[0, 1].set_title('Total Duration Distribution')
    axes[0, 1].legend()
    
    # 3. State Visit Rates (Bar Chart)
    visit_rates = list(stats['state_visit_rates'].values())
    state_names = list(stats['state_visit_rates'].keys())
    bars = axes[1, 0].bar(state_names, visit_rates, alpha=0.7)
    axes[1, 0].set_ylabel('Visit Rate (%)')
    axes[1, 0].set_title('State Visit Rates')
    axes[1, 0].tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for bar, rate in zip(bars, visit_rates):
        height = bar.get_height()
        axes[1, 0].text(bar.get_x() + bar.get_width()/2., height + 1,
                        f'{rate:.1f}%', ha='center', va='bottom')
    
    # 4. Mean Time in Each State (Bar Chart)
    mean_times = [stats['state_time_stats'][state]['mean_time'] for state in states]
    bars = axes[1, 1].bar(states, mean_times, alpha=0.7)
    axes[1, 1].set_ylabel('Mean Time (hours)')
    axes[1, 1].set_title('Mean Time Spent in Each State (excluding final state)')
    axes[1, 1].tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for bar, time in zip(bars, mean_times):
        height = bar.get_height()
        if height > 0:
            axes[1, 1].text(bar.get_x() + bar.get_width()/2., height + 0.1,
                            f'{time:.1f}h', ha='center', va='bottom')
    
    plt.tight_layout()
    return fig

def manage_state_machines(states):
    """Manage state machines using Streamlit."""
    # Initialize database
    db = StateMachineDB()
    
    # Initialize session state variables if not exists
    if 'selected_machine' not in st.session_state:
        st.session_state.selected_machine = None
    if 'node_positions' not in st.session_state:
        st.session_state.node_positions = {}
    if 'clicked_element' not in st.session_state:
        st.session_state.clicked_element = None
    if 'states' not in st.session_state:
        st.session_state.states = states
    if 'graph_edges' not in st.session_state:
        st.session_state.graph_edges = []
    if 'demographics' not in st.session_state:
        st.session_state.demographics = []
    if 'multi_run_results' not in st.session_state:
        st.session_state.multi_run_results = None

    st.header("Manage State Machines")
    st.write("View your saved state machines, load them, and run simulations.")
    
    # Add disease filter dropdown
    diseases = db.get_unique_diseases()
    all_diseases = ["All Diseases"] + diseases
    
    selected_disease = st.selectbox(
        "Filter by Disease:",
        options=all_diseases,
        key="disease_filter"
    )
    
    # Initialize filter variables
    selected_category = "All Categories"
    selected_variant = None
    selected_vaccination = None
    
    # Add category filter
    if selected_disease != "All Diseases":
        # Get model categories from disease configuration
        model_categories = get_disease_model_categories(selected_disease)
        category_options = ["All Categories"] + [category["name"] for category in model_categories]
        
        selected_category = st.selectbox(
            "Filter by Category:",
            options=category_options,
            key="category_filter"
        )
        
        # Add specific filters based on model category
        if selected_category != "All Categories":
            # Find the selected category ID
            selected_category_id = None
            for category in model_categories:
                if category["name"] == selected_category:
                    selected_category_id = category["id"]
                    break
            
            if selected_category_id == "vaccination":
                # Get vaccination options from disease configuration
                demographic_options = get_disease_demographic_options(selected_disease)
                vaccination_options = demographic_options.get("Vaccination Status", ["Unvaccinated", "Partially Vaccinated", "Fully Vaccinated"])
                vaccination_statuses = ["All Vaccination Statuses"] + vaccination_options
                
                selected_vaccination = st.selectbox(
                    "Filter by Vaccination Status:",
                    options=vaccination_statuses,
                    key="vaccination_filter"
                )
            elif selected_category_id == "variant":
                # Get variants from disease configuration
                variants = get_available_variants(selected_disease)
                all_variants = ["All Variants"] + variants
                selected_variant = st.selectbox(
                    "Filter by Variant:",
                    options=all_variants,
                    key="variant_filter"
                )
    
    # List all saved state machines
    saved_machines = db.list_state_machines()
    if saved_machines:
        # Filter machines by selected disease
        if selected_disease != "All Diseases":
            saved_machines = [machine for machine in saved_machines if machine[2] == selected_disease]
        
        # Filter by category
        if selected_category != "All Categories":
            # Find the selected category ID for filtering
            selected_category_id = None
            for category in model_categories:
                if category["name"] == selected_category:
                    selected_category_id = category["id"]
                    break
            
            if selected_category_id:
                # Filter by model_path that starts with the category
                saved_machines = [machine for machine in saved_machines if machine[5].startswith(selected_category_id)]
        
        # Filter by variant
        if selected_variant and selected_variant != "All Variants":
            # Filter by model_path that contains the variant
            saved_machines = [machine for machine in saved_machines if selected_variant in machine[5]]
        
        # Filter by vaccination status for measles
        if selected_disease == "Measles" and selected_vaccination and selected_vaccination != "All Vaccination Statuses":
            # Filter by vaccination status in the model_path
            saved_machines = [machine for machine in saved_machines if selected_vaccination in machine[5]]
        
        # Sort machines by update time (most recent first) and limit to last 10 by default
        saved_machines.sort(key=lambda x: x[7], reverse=True)  # Sort by update time descending
        
        # Add option to show all machines or just recent ones
        show_all = st.checkbox("Show all state machines", value=False, 
                              help="By default, only the last 10 updated state machines are shown. Check this to see all machines.")
        
        if not show_all and len(saved_machines) > 10:
            # Show only the last 10 updated machines
            recent_machines = saved_machines[:10]
            st.subheader(f"Recent State Machines (Last 10 Updated)")
            st.info(f"Showing {len(recent_machines)} of {len(saved_machines)} total state machines. Check 'Show all state machines' to see all.")
        else:
            recent_machines = saved_machines
            st.subheader(f"Saved State Machines ({len(recent_machines)} total)")
        
        # Display state machines in a table format
        for machine in recent_machines:
            disease_name = machine[2] if machine[2] and machine[2] != "Unknown" else "Unknown Disease"
            model_path = machine[5] if machine[5] else "default"
            
            # Create display name with model path info
            if model_path != "default":
                display_name = f"{machine[1]} ({disease_name} - {model_path})"
            else:
                display_name = f"{machine[1]} ({disease_name} - Default Model)"
            
            with st.expander(f"{display_name} - Created: {machine[6]}, Updated: {machine[7]})"):
                col1, col2 = st.columns(2)
                
                # Load demographics
                demographics = json.loads(machine[8] or "{}")
                
                with col1:
                    st.write("Demographics:")
                    for key, value in demographics.items():
                        st.write(f"- {key}: {value}")
                
                with col2:
                    col2a, col2b, col2c = st.columns(3)
                    
                    with col2a:
                        if st.button("Load", key=f"load_{machine[0]}"):
                            machine_data = db.load_state_machine(machine[0])
                            if machine_data:
                                # Update session state with loaded data
                                st.session_state.states = machine_data["states"]
                                st.session_state.graph_edges = machine_data["edges"]
                                st.session_state.demographics = [
                                    {"key": k, "value": v}
                                    for k, v in machine_data["demographics"].items()
                                ]
                                st.session_state.selected_machine = machine_data
                                st.success(f"Loaded state machine: {machine_data['name']}")
                                st.rerun()
                    
                    with col2b:
                        if st.button("Export JSON", key=f"export_{machine[0]}"):
                            machine_data = db.load_state_machine(machine[0])
                            if machine_data:
                                # Create export data
                                export_data = {
                                    "name": machine_data["name"],
                                    "disease_name": machine_data.get("disease_name", "Unknown"),
                                    "variant_name": machine_data.get("variant_name"),
                                    "model_path": machine_data.get("model_path", "default"),
                                    "states": machine_data["states"],
                                    "edges": machine_data["edges"],
                                    "demographics": machine_data["demographics"],
                                    "created_at": machine[6],
                                    "updated_at": machine[7]
                                }
                                
                                # Create downloadable JSON
                                json_str = json.dumps(export_data, indent=2)
                                st.download_button(
                                    label="📥 Download JSON",
                                    data=json_str,
                                    file_name=f"{machine_data['name'].replace(' ', '_')}.json",
                                    mime="application/json",
                                    key=f"download_{machine[0]}"
                                )
                    
                    with col2c:
                        if st.button("Delete", key=f"delete_{machine[0]}"):
                            db.delete_state_machine(machine[0])
                            st.success("State machine deleted")
                            st.rerun()

        # Display the loaded state machine if one is selected
        if st.session_state.selected_machine:
            st.markdown("---")
            st.subheader(f"Loaded State Machine: {st.session_state.selected_machine['name']}")
            
            # Add export button for loaded state machine
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write("**Current State Machine Details**")
            with col2:
                if st.button("📥 Export Current State Machine", key="export_loaded"):
                    # Create export data for the loaded state machine
                    export_data = {
                        "name": st.session_state.selected_machine["name"],
                        "disease_name": st.session_state.selected_machine.get("disease_name", "Unknown"),
                        "variant_name": st.session_state.selected_machine.get("variant_name"),
                        "model_path": st.session_state.selected_machine.get("model_path", "default"),
                        "states": st.session_state.states,
                        "edges": st.session_state.graph_edges,
                        "demographics": st.session_state.selected_machine["demographics"],
                        "export_date": pd.Timestamp.now().isoformat(),
                        "export_note": "Exported from State Machine Manager"
                    }
                    
                    # Create downloadable JSON
                    json_str = json.dumps(export_data, indent=2)
                    st.download_button(
                        label="📥 Download JSON",
                        data=json_str,
                        file_name=f"{st.session_state.selected_machine['name'].replace(' ', '_')}_export.json",
                        mime="application/json",
                        key="download_loaded"
                    )
            
            # Display states in a collapsible view
            with st.expander("States", expanded=False):
                for state in st.session_state.states:
                    st.write(f"- {state}")
            
            # Display edges with all their values
            with st.expander("Edge Details", expanded=False):
                if st.session_state.graph_edges:
                    st.write("**All Edges with Parameters:**")
                    for i, edge in enumerate(st.session_state.graph_edges, 1):
                        edge_data = edge['data']
                        st.write(f"**Edge {i}:** {edge_data['source']} → {edge_data['target']}")
                        st.write(f"  - Transition Probability: {edge_data.get('transition_prob', 'N/A')}")
                        st.write(f"  - Mean Time: {edge_data.get('mean_time', 'N/A')} hours")
                        st.write(f"  - Standard Deviation: {edge_data.get('std_dev', 'N/A')}")
                        st.write(f"  - Distribution Type: {edge_data.get('distribution_type', 'N/A')}")
                        st.write(f"  - Min Cutoff: {edge_data.get('min_cutoff', 'N/A')}")
                        st.write(f"  - Max Cutoff: {edge_data.get('max_cutoff', 'N/A')}")
                        st.write("---")
                else:
                    st.write("No edges defined for this state machine.")
            
            # Use utility function for matrix representation
            matrices = render_matrix_representation(st.session_state.states, st.session_state.graph_edges)
            
            # Add validation status section
            st.markdown("---")
            st.subheader("Validation Status")
            
            if st.session_state.graph_edges:
                validation_results = validate_transition_probabilities(st.session_state.states, st.session_state.graph_edges)
                
                if validation_results['is_valid']:
                    st.success("✅ **All transition probabilities are valid!**")
                    st.info("Each state's outgoing probabilities sum to 1.0")
                else:
                    st.error("❌ **Validation errors found:**")
                    for error in validation_results['errors']:
                        st.error(f"• {error}")
                

            else:
                st.info("ℹ️ No edges defined yet. Add edges to see validation status.")
            
            # Add aggregated probabilities section
            if st.session_state.graph_edges:
                st.markdown("---")
                st.subheader("📊 State Reachability Analysis")
                
                aggregated_probs = calculate_aggregated_probabilities(st.session_state.states, st.session_state.graph_edges)
                
                if aggregated_probs:
                    # Create a DataFrame for better display
                    prob_data = []
                    for state, prob in aggregated_probs.items():
                        prob_data.append({
                            "State": state,
                            "Reachability Probability": f"{prob:.3f}",
                            "Percentage": f"{prob * 100:.1f}%"
                        })
                    
                    # Sort by probability (highest first)
                    prob_data.sort(key=lambda x: float(x["Reachability Probability"]), reverse=True)
                    
                    # Display as a table
                    st.write("**Probability of reaching each state from the initial state:**")
                    prob_df = pd.DataFrame(prob_data)
                    st.dataframe(prob_df, use_container_width=True)
                    
                else:
                    st.info("ℹ️ Unable to calculate reachability probabilities.")
            
            # Add visual state machine representation
            st.markdown("---")
            
            # Use utility function for graph visualization
            render_graph_visualization(st.session_state.states, st.session_state.graph_edges, st.session_state.node_positions)
            
            # Add edge editing functionality
            st.markdown("---")
            with st.expander("Edit Edges", expanded=False):
                # Use utility functions for edge management (without nested expanders)
                render_add_edge_section(st.session_state.states, st.session_state.graph_edges, "manager_add", use_expander=False)
                render_edit_edge_section(st.session_state.graph_edges, "manager_edit", use_expander=False)
                render_remove_edge_section(st.session_state.graph_edges, "manager_remove", use_expander=False)
            
            # JSON Editor for Edges
            st.markdown("---")
            with st.expander("📝 JSON Edge Editor", expanded=False):
                st.write("Edit all edges in JSON format for bulk modifications:")
                
                # Convert edges to a more readable format for JSON editing
                edges_for_json = []
                for edge in st.session_state.graph_edges:
                    edge_data = edge['data'].copy()
                    # Remove the label field as it's auto-generated
                    if 'label' in edge_data:
                        del edge_data['label']
                    edges_for_json.append(edge_data)
                
                # Display current edges as JSON
                current_json = json.dumps(edges_for_json, indent=2)
                
                # JSON editor with validation
                edited_json = st.text_area(
                    "Edit Edges (JSON format):",
                    value=current_json,
                    height=400,
                    key="manager_json_editor",
                    help="Edit the edges in JSON format. Each edge should have: source, target, transition_prob, mean_time, std_dev, distribution_type, min_cutoff, max_cutoff"
                )
                
                # Add buttons for JSON operations
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("🔄 Update from JSON", key="manager_update_from_json"):
                        try:
                            # Parse the JSON
                            parsed_edges = json.loads(edited_json)
                            
                            # Validate the structure
                            if not isinstance(parsed_edges, list):
                                st.error("❌ JSON must be a list of edge objects")
                                return
                            
                            # Convert back to the expected format with 'data' wrapper
                            new_edges = []
                            for edge_data in parsed_edges:
                                if not isinstance(edge_data, dict):
                                    st.error("❌ Each edge must be a JSON object")
                                    return
                                
                                # Validate required fields
                                required_fields = ['source', 'target', 'transition_prob', 'mean_time', 'std_dev', 'distribution_type', 'min_cutoff', 'max_cutoff']
                                missing_fields = [field for field in required_fields if field not in edge_data]
                                if missing_fields:
                                    st.error(f"❌ Missing required fields: {', '.join(missing_fields)}")
                                    return
                                
                                # Validate that source and target states exist
                                if edge_data['source'] not in st.session_state.states:
                                    st.error(f"❌ Source state '{edge_data['source']}' not found in states list")
                                    return
                                if edge_data['target'] not in st.session_state.states:
                                    st.error(f"❌ Target state '{edge_data['target']}' not found in states list")
                                    return
                                
                                # Create the edge in the expected format
                                new_edge = {
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
                                }
                                new_edges.append(new_edge)
                            
                            # Update the session state
                            st.session_state.graph_edges = new_edges
                            st.success(f"✅ Successfully updated {len(new_edges)} edges from JSON")
                            st.rerun()
                            
                        except json.JSONDecodeError as e:
                            st.error(f"❌ Invalid JSON format: {str(e)}")
                        except ValueError as e:
                            st.error(f"❌ Invalid data type: {str(e)}")
                        except Exception as e:
                            st.error(f"❌ Error updating edges: {str(e)}")
                
                with col2:
                    if st.button("📋 Copy JSON", key="manager_copy_json"):
                        st.write("```json")
                        st.code(current_json, language="json")
                        st.write("```")
                        st.success("✅ JSON copied to clipboard (use Ctrl+C)")
                
                with col3:
                    if st.button("🗑️ Clear All Edges", key="manager_clear_edges"):
                        st.session_state.graph_edges = []
                        st.success("✅ All edges cleared")
                        st.rerun()
            
            # Show validation info (moved outside the main expander)
            with st.expander("ℹ️ JSON Format Guide", expanded=False):
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
            
            # Add save changes button
            # st.subheader("Save Changes")
            st.write("**Permanently save all changes to the database** (edge modifications, demographics, etc.) so they persist when you reload the page or return later.")
            if st.button("Save Changes to State Machine", key="manager_save_changes"):
                try:
                    # Validate transition probabilities before saving
                    validation_results = validate_transition_probabilities(st.session_state.states, st.session_state.graph_edges)
                    
                    # Show validation results
                    if not validation_results['is_valid']:
                        st.error("❌ **Validation Errors Found:**")
                        for error in validation_results['errors']:
                            st.error(f"• {error}")
                    
                    # Get the current state machine name
                    machine_name = st.session_state.selected_machine['name']
                    
                    # Create demographics dictionary from session state
                    demographics = {}
                    for demo in st.session_state.demographics:
                        if demo["key"] == "Custom":
                            if demo.get("custom_key") and demo.get("custom_value"):
                                demographics[demo["custom_key"]] = demo["custom_value"]
                        elif demo["key"] and demo["value"]:
                            demographics[demo["key"]] = demo["value"]
                    
                    # Save the updated state machine
                    state_machine_id = db.save_state_machine(
                        machine_name,
                        st.session_state.states,
                        st.session_state.graph_edges,
                        demographics,
                        st.session_state.selected_machine['disease_name'],
                        st.session_state.selected_machine.get('variant_name'),
                        st.session_state.selected_machine.get('model_category', 'default'),
                        update_existing=True
                    )
                    
                    st.success(f"✅ Changes permanently saved to database: {machine_name}")
                    
                except Exception as e:
                    st.error(f"❌ Failed to save changes: {str(e)}")
            
            # Display clicked element info if available
            if st.session_state.clicked_element:
                st.write("Selected element:", st.session_state.clicked_element)
            
            # Add simulation controls with tabs
            st.markdown("---")
            st.subheader("Simulation Controls")
            
            # Add initial state selection
            initial_state = st.selectbox(
                "Initial State",
                options=st.session_state.states,
                key="initial_state"
            )
            
            # Create tabs for single and multi-run simulation
            sim_tab, multi_tab = st.tabs(["Single Simulation", "Multi-Run Analysis"])
            
            with sim_tab:
                # Single simulation
                if st.button("Start Single Simulation", key="single_sim"):
                    if not st.session_state.graph_edges:
                        st.warning("Please add at least one edge to the state machine before running the simulation.")
                    else:
                        # Get the index of the selected initial state
                        initial_state_idx = st.session_state.states.index(initial_state)
                        
                        # Get matrices from the graph
                        matrices = convert_graph_to_matrices(st.session_state.states, st.session_state.graph_edges)
                        
                        # Run the simulation
                        timeline = run_simulation(
                            transition_matrix=matrices["Transition Matrix"],
                            mean_matrix=matrices["Mean Matrix"],
                            std_dev_matrix=matrices["Standard Deviation Matrix"],
                            min_cutoff_matrix=matrices["Min Cutoff Matrix"],
                            max_cutoff_matrix=matrices["Max Cutoff Matrix"],
                            distribution_matrix=matrices["Distribution Type Matrix"],
                            initial_state_idx=initial_state_idx,
                            states=st.session_state.states
                        )
                        
                        # Display the timeline
                        st.subheader("Simulation Timeline")
                        timeline_df = pd.DataFrame(timeline, columns=["State", "Time (hours)"])
                        # Round the time column to 1 decimal place
                        timeline_df["Time (hours)"] = timeline_df["Time (hours)"].round(1)
                        st.dataframe(timeline_df)
                        
                        # Display a visual representation of the timeline
                        st.subheader("Timeline Visualization")
                        
                        # Create a visual timeline chart
                        fig, ax = plt.subplots(figsize=(12, 6))
                        
                        # Extract states and times
                        states = [entry[0] for entry in timeline]
                        times = [entry[1] for entry in timeline]
                        
                        # Create horizontal timeline
                        y_positions = list(range(len(states)))
                        
                        # Plot state transitions
                        for i in range(len(states)):
                            # Plot state point
                            ax.scatter(times[i], y_positions[i], s=200, zorder=5, 
                                     color='steelblue', edgecolor='black', linewidth=2)
                            
                            # Add state label
                            ax.annotate(states[i], (times[i], y_positions[i]), 
                                       xytext=(5, 5), textcoords='offset points',
                                       fontsize=10, fontweight='bold',
                                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7))
                            
                            # Connect to next state if not the last one
                            if i < len(states) - 1:
                                ax.plot([times[i], times[i+1]], [y_positions[i], y_positions[i+1]], 
                                       'k-', linewidth=2, alpha=0.7, zorder=1)
                                
                                # Add time duration on the line
                                duration = times[i+1] - times[i]
                                mid_time = (times[i] + times[i+1]) / 2
                                mid_y = (y_positions[i] + y_positions[i+1]) / 2
                                ax.annotate(f'{duration:.1f}h', (mid_time, mid_y), 
                                           xytext=(0, -15), textcoords='offset points',
                                           ha='center', fontsize=9, fontweight='bold',
                                           bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
                        
                        # Customize the plot
                        ax.set_xlabel('Time (hours)', fontsize=12, fontweight='bold')
                        ax.set_ylabel('Disease States', fontsize=12, fontweight='bold')
                        ax.set_title('Disease Progression Timeline', fontsize=14, fontweight='bold', pad=20)
                        
                        # Set y-axis to show state names
                        ax.set_yticks(y_positions)
                        ax.set_yticklabels(states, fontsize=10)
                        
                        # Add grid for better readability
                        ax.grid(True, alpha=0.3, zorder=0)
                        
                        # Set x-axis limits with some padding
                        ax.set_xlim(-5, max(times) + 5)
                        
                        # Add total duration annotation
                        total_duration = times[-1]
                        ax.text(0.02, 0.98, f'Total Duration: {total_duration:.1f} hours', 
                               transform=ax.transAxes, fontsize=11, fontweight='bold',
                               bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8),
                               verticalalignment='top')
                        
                        # Remove top and right spines
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        
                        plt.tight_layout()
                        st.pyplot(fig)
                        
                        # Also show the timeline in a more compact format
                        st.subheader("Timeline Summary")
                        timeline_summary = []
                        for i, (state, time) in enumerate(timeline):
                            if i == 0:
                                timeline_summary.append(f"**{time:.1f}h**: Start in {state}")
                            else:
                                prev_time = timeline[i-1][1]
                                duration = time - prev_time
                                timeline_summary.append(f"**{time:.1f}h**: Transition to {state} (spent {duration:.1f}h in {timeline[i-1][0]})")
                        
                        for summary in timeline_summary:
                            st.markdown(summary)
            
            with multi_tab:
                # Multi-run analysis
                st.write("Run multiple simulations to analyze statistical patterns and variability.")
                
                # Configuration for multi-run
                col1, col2 = st.columns(2)
                with col1:
                    num_simulations = st.number_input(
                        "Number of Simulations (max 10,000)",
                        min_value=10,
                        max_value=10000,
                        value=100,
                        step=10,
                        help="Choose the number of simulations to run in this batch (maximum: 10,000)"
                    )
                
                with col2:
                    show_progress = st.checkbox("Show Progress Bar", value=True)
                
                # Run multi-simulation
                if st.button("Start Multi-Run Analysis", key="multi_sim"):
                    if not st.session_state.graph_edges:
                        st.warning("Please add at least one edge to the state machine before running the simulation.")
                    else:
                        # Get the index of the selected initial state
                        initial_state_idx = st.session_state.states.index(initial_state)
                        
                        # Get matrices from the graph
                        matrices = convert_graph_to_matrices(st.session_state.states, st.session_state.graph_edges)
                        
                        # Run multiple simulations
                        simulation_results = []
                        
                        if show_progress:
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                        
                        for i in range(num_simulations):
                            # Run single simulation
                            timeline = run_simulation(
                                transition_matrix=matrices["Transition Matrix"],
                                mean_matrix=matrices["Mean Matrix"],
                                std_dev_matrix=matrices["Standard Deviation Matrix"],
                                min_cutoff_matrix=matrices["Min Cutoff Matrix"],
                                max_cutoff_matrix=matrices["Max Cutoff Matrix"],
                                distribution_matrix=matrices["Distribution Type Matrix"],
                                initial_state_idx=initial_state_idx,
                                states=st.session_state.states
                            )
                            simulation_results.append(timeline)
                            
                            if show_progress and (i + 1) % max(1, num_simulations // 20) == 0:
                                progress = (i + 1) / num_simulations
                                progress_bar.progress(progress)
                                status_text.text(f"Running simulation {i + 1}/{num_simulations}")
                        
                        if show_progress:
                            progress_bar.progress(1.0)
                            status_text.text("Analysis complete!")
                        
                        # Store results in session state
                        st.session_state.multi_run_results = simulation_results
                        
                        # Analyze results
                        stats = analyze_simulation_results(simulation_results, st.session_state.states)
                        
                        if stats:
                            # Display summary statistics
                            st.subheader("📊 Analysis Summary")
                            
                            # Key metrics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Simulations", stats['total_simulations'])
                            with col2:
                                st.metric("Mean Duration", f"{stats['total_duration_stats']['mean']:.1f} hours")
                            with col3:
                                st.metric("Duration Std Dev", f"{stats['total_duration_stats']['std']:.1f} hours")
                            
                            # Detailed statistics
                            with st.expander("📈 Detailed Statistics", expanded=True):
                                # Final state distribution
                                st.write("**Final State Distribution:**")
                                final_state_df = pd.DataFrame([
                                    {"State": state, "Count": count, "Percentage": (count/stats['total_simulations'])*100}
                                    for state, count in stats['final_state_distribution'].items()
                                ])
                                st.dataframe(final_state_df)
                                
                                # Duration statistics
                                st.write("**Total Duration Statistics (hours):**")
                                duration_stats = stats['total_duration_stats']
                                duration_df = pd.DataFrame([
                                    {"Metric": "Mean", "Value": duration_stats['mean']},
                                    {"Metric": "Median", "Value": duration_stats['median']},
                                    {"Metric": "Standard Deviation", "Value": duration_stats['std']},
                                    {"Metric": "Minimum", "Value": duration_stats['min']},
                                    {"Metric": "Maximum", "Value": duration_stats['max']},
                                    {"Metric": "25th Percentile", "Value": duration_stats['percentiles']['25th']},
                                    {"Metric": "75th Percentile", "Value": duration_stats['percentiles']['75th']}
                                ])
                                st.dataframe(duration_df)
                                
                                # State visit rates
                                st.write("**State Visit Rates (% of simulations that visited each state):**")
                                visit_rates_df = pd.DataFrame([
                                    {"State": state, "Visit Rate (%)": rate}
                                    for state, rate in stats['state_visit_rates'].items()
                                ])
                                st.dataframe(visit_rates_df)
                                
                                # State time statistics
                                st.write("**Time Statistics by State (hours):**")
                                st.info("💡 **Note**: Time spent in each state is calculated as the duration between entering and leaving the state. Final states (where simulation ends) are excluded from time calculations.")
                                state_time_data = []
                                for state in st.session_state.states:
                                    state_stats = stats['state_time_stats'][state]
                                    state_time_data.append({
                                        "State": state,
                                        "Mean Time": state_stats['mean_time'],
                                        "Median Time": state_stats['median_time'],
                                        "Std Dev": state_stats['std_time'],
                                        "Min Time": state_stats['min_time'],
                                        "Max Time": state_stats['max_time'],
                                        "Total Visits": state_stats['visit_count'],
                                        "Non-Final Visits": state_stats['non_zero_visits']
                                    })
                                state_time_df = pd.DataFrame(state_time_data)
                                st.dataframe(state_time_df)
                            
                            # Visualizations
                            st.subheader("📊 Visualizations")
                            fig = create_visualizations(stats, simulation_results, st.session_state.states)
                            if fig:
                                st.pyplot(fig)
                            
                            # Sample timelines
                            with st.expander("📋 Sample Timelines", expanded=False):
                                st.write("**First 5 simulation timelines:**")
                                for i, timeline in enumerate(simulation_results[:5]):
                                    st.write(f"**Simulation {i+1}:**")
                                    timeline_df = pd.DataFrame(timeline, columns=["State", "Time (hours)"])
                                    timeline_df["Time (hours)"] = timeline_df["Time (hours)"].round(1)
                                    st.dataframe(timeline_df, use_container_width=True)
                                    st.write("---")
            
    else:
        st.write("No saved state machines found") 