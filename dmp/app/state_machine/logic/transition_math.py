"""Pure transition / simulation-analysis math for state machines.

These functions were extracted verbatim from ``state_machine_manager.py`` so
they can be unit-tested without a Streamlit runtime. They depend only on
``numpy``/``pandas``/``matplotlib`` and never touch ``st``.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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
