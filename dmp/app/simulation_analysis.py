import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from simulation_management import run_single_simulation
from demographic_management import collect_demographic_options, get_valid_ages

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
    
    # Add mode selection
    analysis_mode = st.radio(
        "Select Analysis Mode",
        ["Single Analysis", "Quick Comparison"]
    )
    
    # Get number of runs from user
    num_runs = st.slider("Number of simulation runs", 
                        min_value=10, 
                        max_value=1000, 
                        value=100,
                        step=10)
    
    if analysis_mode == "Single Analysis":
        if st.button("Run Analysis"):
            with st.spinner("Running multiple simulations..."):
                all_timelines, all_final_states = run_multiple_simulations(
                    num_runs, simulation_demographics, initial_state)
                
                analyze_simulation_results(all_timelines, all_final_states)
    
    else:  # Quick Comparison Mode
        st.subheader("Select Demographic Presets to Compare")
        
        # Get available demographic options
        demographic_options = collect_demographic_options()
        
        # Create two columns for the two presets
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### Preset 1")
            preset1_demographics = {}
            for demo_name, possible_values in demographic_options.items():
                if demo_name == "Age":
                    valid_ages = get_valid_ages()
                    if valid_ages:
                        age_options = ["*"] + valid_ages
                        preset1_demographics[demo_name] = st.selectbox(
                            f"Select {demo_name} (Preset 1)",
                            options=age_options,
                            key=f"preset1_{demo_name}"
                        )
                elif demo_name == "Sex":
                    sex_options = ["*"] + [opt for opt in ["M", "F"] if opt in possible_values]
                    preset1_demographics[demo_name] = st.selectbox(
                        f"Select {demo_name} (Preset 1)",
                        options=sex_options,
                        key=f"preset1_{demo_name}"
                    )
                elif demo_name == "Vaccination Status":
                    vax_options = ["*"] + [opt for opt in ["Vaccinated", "Unvaccinated"] if opt in possible_values]
                    preset1_demographics[demo_name] = st.selectbox(
                        f"Select {demo_name} (Preset 1)",
                        options=vax_options,
                        key=f"preset1_{demo_name}"
                    )
                else:
                    preset1_demographics[demo_name] = st.text_input(
                        f"Enter {demo_name} (Preset 1)",
                        value="*",
                        key=f"preset1_{demo_name}"
                    )
        
        with col2:
            st.write("### Preset 2")
            preset2_demographics = {}
            for demo_name, possible_values in demographic_options.items():
                if demo_name == "Age":
                    valid_ages = get_valid_ages()
                    if valid_ages:
                        age_options = ["*"] + valid_ages
                        preset2_demographics[demo_name] = st.selectbox(
                            f"Select {demo_name} (Preset 2)",
                            options=age_options,
                            key=f"preset2_{demo_name}"
                        )
                elif demo_name == "Sex":
                    sex_options = ["*"] + [opt for opt in ["M", "F"] if opt in possible_values]
                    preset2_demographics[demo_name] = st.selectbox(
                        f"Select {demo_name} (Preset 2)",
                        options=sex_options,
                        key=f"preset2_{demo_name}"
                    )
                elif demo_name == "Vaccination Status":
                    vax_options = ["*"] + [opt for opt in ["Vaccinated", "Unvaccinated"] if opt in possible_values]
                    preset2_demographics[demo_name] = st.selectbox(
                        f"Select {demo_name} (Preset 2)",
                        options=vax_options,
                        key=f"preset2_{demo_name}"
                    )
                else:
                    preset2_demographics[demo_name] = st.text_input(
                        f"Enter {demo_name} (Preset 2)",
                        value="*",
                        key=f"preset2_{demo_name}"
                    )
        
        if st.button("Run Comparison"):
            with st.spinner("Running simulations for both presets..."):
                # Run simulations for both presets
                preset1_timelines, preset1_final_states = run_multiple_simulations(
                    num_runs, preset1_demographics, initial_state)
                preset2_timelines, preset2_final_states = run_multiple_simulations(
                    num_runs, preset2_demographics, initial_state)
                
                # Compare final state distributions
                st.subheader("Comparison of Final State Distributions")
                
                # Get all unique states from both presets
                all_states = set()
                for state in preset1_final_states:
                    if state:
                        all_states.add(state)
                for state in preset2_final_states:
                    if state:
                        all_states.add(state)
                all_states = sorted(list(all_states))
                
                # Calculate percentages for both presets
                preset1_counts = {}
                preset2_counts = {}
                for state in all_states:
                    preset1_counts[state] = preset1_final_states.count(state)
                    preset2_counts[state] = preset2_final_states.count(state)
                
                preset1_percentages = {state: (count/num_runs)*100 
                                     for state, count in preset1_counts.items()}
                preset2_percentages = {state: (count/num_runs)*100 
                                     for state, count in preset2_counts.items()}
                
                # Create grouped bar chart
                fig, ax = plt.subplots(figsize=(12, 6))
                x = np.arange(len(all_states))
                width = 0.35
                
                bars1 = ax.bar(x - width/2, 
                             [preset1_percentages.get(state, 0) for state in all_states],
                             width, label='Preset 1')
                bars2 = ax.bar(x + width/2, 
                             [preset2_percentages.get(state, 0) for state in all_states],
                             width, label='Preset 2')
                
                ax.set_xlabel('Final State')
                ax.set_ylabel('Percentage of Simulations')
                ax.set_title('Comparison of Final State Distributions')
                ax.set_xticks(x)
                ax.set_xticklabels(all_states, rotation=45)
                ax.legend()
                
                # Add percentage labels on top of bars
                for bars in [bars1, bars2]:
                    for bar in bars:
                        height = bar.get_height()
                        if height > 0:  # Only add label if there's a value
                            ax.text(bar.get_x() + bar.get_width()/2., height,
                                   f'{height:.1f}%',
                                   ha='center', va='bottom')
                
                plt.tight_layout()
                st.pyplot(fig)
                
                # Display detailed statistics in columns
                st.subheader("Detailed Statistics")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### Preset 1 Statistics")
                    st.write("Final State Distribution:")
                    for state, percentage in preset1_percentages.items():
                        st.write(f"{state}: {percentage:.1f}%")
                    
                    # Calculate average time to reach each state for preset 1
                    state_times1 = {}
                    for timeline in preset1_timelines:
                        for state, time in timeline:
                            if state not in state_times1:
                                state_times1[state] = []
                            state_times1[state].append(time)
                    
                    st.write("\nAverage Time to Reach States (hours):")
                    for state, times in state_times1.items():
                        avg_time = np.mean(times)
                        std_time = np.std(times)
                        st.write(f"{state}: {avg_time:.1f} ± {std_time:.1f}")
                
                with col2:
                    st.write("### Preset 2 Statistics")
                    st.write("Final State Distribution:")
                    for state, percentage in preset2_percentages.items():
                        st.write(f"{state}: {percentage:.1f}%")
                    
                    # Calculate average time to reach each state for preset 2
                    state_times2 = {}
                    for timeline in preset2_timelines:
                        for state, time in timeline:
                            if state not in state_times2:
                                state_times2[state] = []
                            state_times2[state].append(time)
                    
                    st.write("\nAverage Time to Reach States (hours):")
                    for state, times in state_times2.items():
                        avg_time = np.mean(times)
                        std_time = np.std(times)
                        st.write(f"{state}: {avg_time:.1f} ± {std_time:.1f}") 