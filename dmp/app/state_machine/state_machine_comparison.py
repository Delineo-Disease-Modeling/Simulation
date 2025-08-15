import streamlit as st
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from .state_machine_db import StateMachineDB
from core.simulation_functions import run_simulation
from .utils.graph_utils import convert_graph_to_matrices, create_edge_label
from .utils.graph_visualizer import render_graph_visualization

def compare_state_machines():
    """Compare two state machines side by side."""
    st.header("State Machine Comparison")
    st.write("Load two different state machines and compare their simulation results side by side.")
    
    # Initialize database
    db = StateMachineDB()
    
    # Initialize session state for comparison
    if 'comparison_machine_a' not in st.session_state:
        st.session_state.comparison_machine_a = None
    if 'comparison_machine_b' not in st.session_state:
        st.session_state.comparison_machine_b = None
    if 'comparison_results_a' not in st.session_state:
        st.session_state.comparison_results_a = None
    if 'comparison_results_b' not in st.session_state:
        st.session_state.comparison_results_b = None
    
    # Get all saved state machines
    saved_machines = db.list_state_machines()
    
    if not saved_machines:
        st.warning("No saved state machines found. Please create some state machines first.")
        return
    
    # Create machine selection interface
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Machine A")
        
        # Machine A selection
        machine_a_options = ["Select Machine A"] + [f"{machine[1]} ({machine[2]})" for machine in saved_machines]
        selected_machine_a = st.selectbox(
            "Choose Machine A:",
            options=machine_a_options,
            key="machine_a_selection"
        )
        
        if selected_machine_a != "Select Machine A":
            # Find the selected machine
            machine_a_index = machine_a_options.index(selected_machine_a) - 1
            machine_a_data = saved_machines[machine_a_index]
            
            # Load machine A
            if st.button("Load Machine A", key="load_machine_a"):
                machine_a_full = db.load_state_machine(machine_a_data[0])
                if machine_a_full:
                    st.session_state.comparison_machine_a = machine_a_full
                    st.success(f"✅ Loaded: {machine_a_full['name']}")
                    st.rerun()
            
            # Display machine A info
            if st.session_state.comparison_machine_a:
                machine_a = st.session_state.comparison_machine_a
                st.write(f"**Loaded:** {machine_a['name']}")
                st.write(f"**Disease:** {machine_a.get('disease_name', 'Unknown')}")
                st.write(f"**States:** {len(machine_a['states'])}")
                st.write(f"**Edges:** {len(machine_a['edges'])}")
                
                # Show states
                with st.expander("States", expanded=False):
                    for state in machine_a['states']:
                        st.write(f"- {state}")
    
    with col2:
        st.subheader("Machine B")
        
        # Machine B selection
        machine_b_options = ["Select Machine B"] + [f"{machine[1]} ({machine[2]})" for machine in saved_machines]
        selected_machine_b = st.selectbox(
            "Choose Machine B:",
            options=machine_b_options,
            key="machine_b_selection"
        )
        
        if selected_machine_b != "Select Machine B":
            # Find the selected machine
            machine_b_index = machine_b_options.index(selected_machine_b) - 1
            machine_b_data = saved_machines[machine_b_index]
            
            # Load machine B
            if st.button("Load Machine B", key="load_machine_b"):
                machine_b_full = db.load_state_machine(machine_b_data[0])
                if machine_b_full:
                    st.session_state.comparison_machine_b = machine_b_full
                    st.success(f"✅ Loaded: {machine_b_full['name']}")
                    st.rerun()
            
            # Display machine B info
            if st.session_state.comparison_machine_b:
                machine_b = st.session_state.comparison_machine_b
                st.write(f"**Loaded:** {machine_b['name']}")
                st.write(f"**Disease:** {machine_b.get('disease_name', 'Unknown')}")
                st.write(f"**States:** {len(machine_b['states'])}")
                st.write(f"**Edges:** {len(machine_b['edges'])}")
                
                # Show states
                with st.expander("States", expanded=False):
                    for state in machine_b['states']:
                        st.write(f"- {state}")
    
    # Simulation configuration
    st.markdown("---")
    st.subheader("Simulation Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        num_simulations = st.number_input(
            "Number of Simulations:",
            min_value=10,
            max_value=5000,
            value=100,
            step=10,
            help="Number of simulations to run for each machine"
        )
    
    with col2:
        show_progress = st.checkbox("Show Progress", value=True)
    
    with col3:
        if st.button("Run Comparison", key="run_comparison"):
            if not st.session_state.comparison_machine_a or not st.session_state.comparison_machine_b:
                st.error("Please load both machines before running comparison.")
            else:
                run_comparison_simulations(num_simulations, show_progress)
    
    # Display comparison results
    if st.session_state.comparison_results_a and st.session_state.comparison_results_b:
        display_comparison_results()
    
    # Display machine visualizations
    if st.session_state.comparison_machine_a or st.session_state.comparison_machine_b:
        st.markdown("---")
        st.subheader("Machine Visualizations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.session_state.comparison_machine_a:
                st.write("**Machine A:**")
                machine_a = st.session_state.comparison_machine_a
                render_graph_visualization(
                    machine_a['states'], 
                    machine_a['edges'], 
                    {}, 
                    height=400
                )
        
        with col2:
            if st.session_state.comparison_machine_b:
                st.write("**Machine B:**")
                machine_b = st.session_state.comparison_machine_b
                render_graph_visualization(
                    machine_b['states'], 
                    machine_b['edges'], 
                    {}, 
                    height=400
                )

def run_comparison_simulations(num_simulations, show_progress):
    """Run simulations for both machines."""
    machine_a = st.session_state.comparison_machine_a
    machine_b = st.session_state.comparison_machine_b
    
    # Get matrices for both machines
    matrices_a = convert_graph_to_matrices(machine_a['states'], machine_a['edges'])
    matrices_b = convert_graph_to_matrices(machine_b['states'], machine_b['edges'])
    
    # Run simulations for machine A
    st.write("🔄 Running simulations for Machine A...")
    simulation_results_a = []
    
    if show_progress:
        progress_bar_a = st.progress(0)
        status_text_a = st.empty()
    
    for i in range(num_simulations):
        timeline = run_simulation(
            transition_matrix=matrices_a["Transition Matrix"],
            mean_matrix=matrices_a["Mean Matrix"],
            std_dev_matrix=matrices_a["Standard Deviation Matrix"],
            min_cutoff_matrix=matrices_a["Min Cutoff Matrix"],
            max_cutoff_matrix=matrices_a["Max Cutoff Matrix"],
            distribution_matrix=matrices_a["Distribution Type Matrix"],
            initial_state_idx=0,  # Start from first state
            states=machine_a['states']
        )
        simulation_results_a.append(timeline)
        
        if show_progress and (i + 1) % max(1, num_simulations // 20) == 0:
            progress = (i + 1) / num_simulations
            progress_bar_a.progress(progress)
            status_text_a.text(f"Machine A: {i + 1}/{num_simulations}")
    
    if show_progress:
        progress_bar_a.progress(1.0)
        status_text_a.text("Machine A complete!")
    
    # Run simulations for machine B
    st.write("🔄 Running simulations for Machine B...")
    simulation_results_b = []
    
    if show_progress:
        progress_bar_b = st.progress(0)
        status_text_b = st.empty()
    
    for i in range(num_simulations):
        timeline = run_simulation(
            transition_matrix=matrices_b["Transition Matrix"],
            mean_matrix=matrices_b["Mean Matrix"],
            std_dev_matrix=matrices_b["Standard Deviation Matrix"],
            min_cutoff_matrix=matrices_b["Min Cutoff Matrix"],
            max_cutoff_matrix=matrices_b["Max Cutoff Matrix"],
            distribution_matrix=matrices_b["Distribution Type Matrix"],
            initial_state_idx=0,  # Start from first state
            states=machine_b['states']
        )
        simulation_results_b.append(timeline)
        
        if show_progress and (i + 1) % max(1, num_simulations // 20) == 0:
            progress = (i + 1) / num_simulations
            progress_bar_b.progress(progress)
            status_text_b.text(f"Machine B: {i + 1}/{num_simulations}")
    
    if show_progress:
        progress_bar_b.progress(1.0)
        status_text_b.text("Machine B complete!")
    
    # Store results
    st.session_state.comparison_results_a = simulation_results_a
    st.session_state.comparison_results_b = simulation_results_b
    
    st.success("✅ Comparison complete!")
    st.rerun()

def analyze_comparison_results(simulation_results, states):
    """Analyze simulation results for comparison."""
    if not simulation_results:
        return None
    
    # Extract data for analysis
    final_states = []
    total_durations = []
    state_visits = {state: [] for state in states}
    
    for timeline in simulation_results:
        # Final state
        final_states.append(timeline[-1][0])
        
        # Total duration
        total_duration = timeline[-1][1]
        total_durations.append(total_duration)
        
        # Count visits to each state
        visited_states = set()
        for state, _ in timeline:
            visited_states.add(state)
        
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
        'state_visit_rates': {state: np.mean(visits) * 100 for state, visits in state_visits.items()}
    }
    
    return stats

def display_comparison_results():
    """Display side-by-side comparison results."""
    st.markdown("---")
    st.subheader("📊 Comparison Results")
    
    # Analyze results
    stats_a = analyze_comparison_results(st.session_state.comparison_results_a, st.session_state.comparison_machine_a['states'])
    stats_b = analyze_comparison_results(st.session_state.comparison_results_b, st.session_state.comparison_machine_b['states'])
    
    if not stats_a or not stats_b:
        return
    
    # Display side-by-side comparison
    col1, col2 = st.columns(2)
    
    with col1:
        st.write(f"**Machine A: {st.session_state.comparison_machine_a['name']}**")
        st.metric("Total Simulations", stats_a['total_simulations'])
        st.metric("Mean Duration", f"{stats_a['total_duration_stats']['mean']:.1f} hours")
        st.metric("Duration Std Dev", f"{stats_a['total_duration_stats']['std']:.1f} hours")
        st.metric("Median Duration", f"{stats_a['total_duration_stats']['median']:.1f} hours")
        
        # Final state distribution
        st.write("**Final State Distribution:**")
        for state, count in stats_a['final_state_distribution'].items():
            percentage = (count / stats_a['total_simulations']) * 100
            st.write(f"- {state}: {count} ({percentage:.1f}%)")
        
        # State visit rates
        st.write("**State Visit Rates (% of simulations that visited each state):**")
        for state, rate in stats_a['state_visit_rates'].items():
            st.write(f"- {state}: {rate:.1f}%")
    
    with col2:
        st.write(f"**Machine B: {st.session_state.comparison_machine_b['name']}**")
        st.metric("Total Simulations", stats_b['total_simulations'])
        st.metric("Mean Duration", f"{stats_b['total_duration_stats']['mean']:.1f} hours")
        st.metric("Duration Std Dev", f"{stats_b['total_duration_stats']['std']:.1f} hours")
        st.metric("Median Duration", f"{stats_b['total_duration_stats']['median']:.1f} hours")
        
        # Final state distribution
        st.write("**Final State Distribution:**")
        for state, count in stats_b['final_state_distribution'].items():
            percentage = (count / stats_b['total_simulations']) * 100
            st.write(f"- {state}: {count} ({percentage:.1f}%)")
        
        # State visit rates
        st.write("**State Visit Rates (% of simulations that visited each state):**")
        for state, rate in stats_b['state_visit_rates'].items():
            st.write(f"- {state}: {rate:.1f}%")
    
    # Create comparison visualization
    st.markdown("---")
    st.subheader("📊 Duration Distribution Comparison")
    
    # Extract duration data
    durations_a = [timeline[-1][1] for timeline in st.session_state.comparison_results_a]
    durations_b = [timeline[-1][1] for timeline in st.session_state.comparison_results_b]
    
    # Create comparison plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Histogram comparison
    ax1.hist(durations_a, bins=20, alpha=0.7, label=f"Machine A (μ={stats_a['total_duration_stats']['mean']:.1f})", color='blue')
    ax1.hist(durations_b, bins=20, alpha=0.7, label=f"Machine B (μ={stats_b['total_duration_stats']['mean']:.1f})", color='red')
    ax1.set_xlabel('Duration (hours)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Duration Distribution Comparison')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Box plot comparison
    ax2.boxplot([durations_a, durations_b], labels=['Machine A', 'Machine B'])
    ax2.set_ylabel('Duration (hours)')
    ax2.set_title('Duration Box Plot Comparison')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    st.pyplot(fig)
    
    # Summary table
    st.markdown("---")
    st.subheader("📋 Summary Comparison")
    
    comparison_data = {
        "Metric": [
            "Mean Duration (hours)",
            "Median Duration (hours)",
            "Standard Deviation (hours)",
            "Minimum Duration (hours)",
            "Maximum Duration (hours)",
            "25th Percentile (hours)",
            "75th Percentile (hours)",
            "Total Simulations"
        ],
        "Machine A": [
            f"{stats_a['total_duration_stats']['mean']:.1f}",
            f"{stats_a['total_duration_stats']['median']:.1f}",
            f"{stats_a['total_duration_stats']['std']:.1f}",
            f"{stats_a['total_duration_stats']['min']:.1f}",
            f"{stats_a['total_duration_stats']['max']:.1f}",
            f"{stats_a['total_duration_stats']['percentiles']['25th']:.1f}",
            f"{stats_a['total_duration_stats']['percentiles']['75th']:.1f}",
            stats_a['total_simulations']
        ],
        "Machine B": [
            f"{stats_b['total_duration_stats']['mean']:.1f}",
            f"{stats_b['total_duration_stats']['median']:.1f}",
            f"{stats_b['total_duration_stats']['std']:.1f}",
            f"{stats_b['total_duration_stats']['min']:.1f}",
            f"{stats_b['total_duration_stats']['max']:.1f}",
            f"{stats_b['total_duration_stats']['percentiles']['25th']:.1f}",
            f"{stats_b['total_duration_stats']['percentiles']['75th']:.1f}",
            stats_b['total_simulations']
        ],
        "Difference": [
            f"{stats_b['total_duration_stats']['mean'] - stats_a['total_duration_stats']['mean']:+.1f}",
            f"{stats_b['total_duration_stats']['median'] - stats_a['total_duration_stats']['median']:+.1f}",
            f"{stats_b['total_duration_stats']['std'] - stats_a['total_duration_stats']['std']:+.1f}",
            f"{stats_b['total_duration_stats']['min'] - stats_a['total_duration_stats']['min']:+.1f}",
            f"{stats_b['total_duration_stats']['max'] - stats_a['total_duration_stats']['max']:+.1f}",
            f"{stats_b['total_duration_stats']['percentiles']['25th'] - stats_a['total_duration_stats']['percentiles']['25th']:+.1f}",
            f"{stats_b['total_duration_stats']['percentiles']['75th'] - stats_a['total_duration_stats']['percentiles']['75th']:+.1f}",
            f"{stats_b['total_simulations'] - stats_a['total_simulations']:+d}"
        ]
    }
    
    comparison_df = pd.DataFrame(comparison_data)
    st.dataframe(comparison_df, use_container_width=True) 