import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from simulation_management import run_single_simulation

def run_multiple_simulations(num_runs, simulation_demographics, initial_state):
    """Run multiple simulations and collect results"""
    all_timelines = []
    all_final_states = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i in range(num_runs):
        # Update progress
        progress = (i + 1) / num_runs
        progress_bar.progress(progress)
        status_text.text(f"Running simulation {i + 1}/{num_runs}")
        
        # Run simulation
        timeline = run_single_simulation(simulation_demographics, initial_state)
        all_timelines.append(timeline)
        
        # Get final state
        final_state = timeline[-1][0] if timeline else None
        all_final_states.append(final_state)
    
    progress_bar.empty()
    status_text.empty()
    
    return all_timelines, all_final_states

def analyze_simulation_results(all_timelines, all_final_states):
    """Analyze and visualize simulation results"""
    if not all_timelines or not all_final_states:
        st.error("No simulation results to analyze")
        return
    
    # Count final states
    final_state_counts = {}
    for state in all_final_states:
        final_state_counts[state] = final_state_counts.get(state, 0) + 1
    
    # Calculate percentages
    total_runs = len(all_final_states)
    final_state_percentages = {state: (count/total_runs)*100 
                             for state, count in final_state_counts.items()}
    
    # Plot final state distribution
    st.subheader("Final State Distribution")
    fig, ax = plt.subplots(figsize=(10, 6))
    states = list(final_state_counts.keys())
    counts = list(final_state_counts.values())
    
    bars = ax.bar(states, counts)
    ax.set_xlabel('Final State')
    ax.set_ylabel('Count')
    ax.set_title(f'Distribution of Final States ({total_runs} runs)')
    
    # Add percentage labels on top of bars
    for bar, percentage in zip(bars, final_state_percentages.values()):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{percentage:.1f}%',
                ha='center', va='bottom')
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)
    
    # Calculate and display statistics
    st.subheader("Statistics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Final State Distribution:")
        for state, percentage in final_state_percentages.items():
            st.write(f"{state}: {percentage:.1f}%")
    
    with col2:
        # Calculate average time to reach each state
        state_times = {}
        for timeline in all_timelines:
            for state, time in timeline:
                if state not in state_times:
                    state_times[state] = []
                state_times[state].append(time)
        
        st.write("Average Time to Reach States (hours):")
        for state, times in state_times.items():
            avg_time = np.mean(times)
            std_time = np.std(times)
            st.write(f"{state}: {avg_time:.1f} ± {std_time:.1f}")
    
    # New section: State Transition Analysis
    st.subheader("State Transition Analysis")
    
    # Calculate how many simulations passed through each state
    state_occurrences = {}
    for timeline in all_timelines:
        states_in_timeline = set(state for state, _ in timeline)
        for state in states_in_timeline:
            state_occurrences[state] = state_occurrences.get(state, 0) + 1
    
    # Calculate percentages
    state_occurrence_percentages = {state: (count/total_runs)*100 
                                  for state, count in state_occurrences.items()}
    
    # Sort states by occurrence percentage
    sorted_states = sorted(state_occurrence_percentages.items(), 
                         key=lambda x: x[1], 
                         reverse=True)
    
    # Create a new figure for state occurrence
    fig2, ax2 = plt.subplots(figsize=(10, 6))
    states = [state for state, _ in sorted_states]
    percentages = [percentage for _, percentage in sorted_states]
    
    bars = ax2.bar(states, percentages)
    ax2.set_xlabel('State')
    ax2.set_ylabel('Percentage of Simulations')
    ax2.set_title('Percentage of Simulations that Passed Through Each State')
    
    # Add percentage labels on top of bars
    for bar, percentage in zip(bars, percentages):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{percentage:.1f}%',
                ha='center', va='bottom')
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig2)
    
    # Display state occurrence statistics in a table
    st.write("State Occurrence Statistics:")
    col3, col4 = st.columns(2)
    
    with col3:
        st.write("State")
    with col4:
        st.write("Percentage of Simulations")
    
    for state, percentage in sorted_states:
        with col3:
            st.write(state)
        with col4:
            st.write(f"{percentage:.1f}%")

def analyze_simulations(simulation_demographics, initial_state):
    """Main function to handle simulation analysis"""
    st.header("Simulation Analysis")
    
    # Get number of runs from user
    num_runs = st.slider("Number of simulation runs", 
                        min_value=10, 
                        max_value=1000, 
                        value=100,
                        step=10)
    
    if st.button("Run Analysis"):
        with st.spinner("Running multiple simulations..."):
            all_timelines, all_final_states = run_multiple_simulations(
                num_runs, simulation_demographics, initial_state)
            
            analyze_simulation_results(all_timelines, all_final_states) 