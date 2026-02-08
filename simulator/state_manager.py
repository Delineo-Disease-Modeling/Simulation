"""
Simulation State Manager

Handles saving and restoring simulation state for multi-month/multi-phase simulations.
This allows running simulations across different monthly pattern files while preserving
infection states, vaccination states, and other person-level data.
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime


def save_simulation_state(
    people: Dict[str, Any],
    output_path: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Save the current simulation state to a JSON file.
    
    Args:
        people: Dictionary of Person objects keyed by person ID
        output_path: Path to save the state file
        metadata: Optional metadata (current time, month, interventions, etc.)
    
    Returns:
        Path to the saved state file
    """
    print(f"[STATE_MANAGER] Saving state to: {output_path}")
    print(f"[STATE_MANAGER] People to save: {len(people)}")
    print(f"[STATE_MANAGER] Metadata: {metadata}")
    
    state = {
        'version': '1.0',
        'saved_at': datetime.now().isoformat(),
        'metadata': metadata or {},
        'people_count': len(people),
        'people': {}
    }
    
    # Debug: Count non-zero states before serialization
    non_zero_states = 0
    sample_states = []
    
    # Serialize each person
    for pid, person in people.items():
        if hasattr(person, 'to_dict'):
            state['people'][str(pid)] = person.to_dict()
        else:
            # Fallback for dict-based people data
            state['people'][str(pid)] = person
        
        # Debug: Check what states are being saved
        saved_person = state['people'][str(pid)]
        if 'states' in saved_person:
            for variant, state_val in saved_person['states'].items():
                if state_val != 0:
                    non_zero_states += 1
                    if len(sample_states) < 10:
                        sample_states.append((pid, variant, state_val))
    
    print(f"[STATE_MANAGER] Non-zero states being saved: {non_zero_states}")
    print(f"[STATE_MANAGER] Sample states: {sample_states}")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"[STATE_MANAGER] State saved successfully!")
    return output_path


def load_simulation_state(state_path: str) -> Dict[str, Any]:
    """
    Load simulation state from a JSON file.
    
    Args:
        state_path: Path to the state file
    
    Returns:
        Dictionary with 'metadata' and 'people' keys
    """
    print(f"[STATE_MANAGER] Loading state from: {state_path}")
    with open(state_path, 'r') as f:
        state = json.load(f)
    
    print(f"[STATE_MANAGER] Loaded {state.get('people_count', 'unknown')} people")
    print(f"[STATE_MANAGER] Saved at: {state.get('saved_at', 'unknown')}")
    
    return {
        'metadata': state.get('metadata', {}),
        'people': state.get('people', {}),
        'version': state.get('version', '1.0'),
        'saved_at': state.get('saved_at')
    }


def restore_people_state(
    people_objects: Dict[str, Any],
    saved_state: Dict[str, Dict],
    time_offset: int = 0
) -> int:
    """
    Restore state from saved data into existing Person objects.
    
    This is useful when you've already created Person objects from papdata
    but want to restore their infection/vaccination states from a previous run.
    
    Args:
        people_objects: Dictionary of Person objects to update
        saved_state: Dictionary of saved person states (from load_simulation_state)
        time_offset: Offset to subtract from timeline values (typically the end time of prev simulation).
                     This shifts timelines so they're relative to the new simulation's t=0.
    
    Returns:
        Number of people whose state was restored
    """
    from .pap import Person, InfectionState, InfectionTimeline, VaccinationState
    
    restored_count = 0
    infected_restored = 0
    
    print(f"[STATE_RESTORE] Attempting to restore {len(saved_state)} people into {len(people_objects)} existing people")
    print(f"[STATE_RESTORE] Time offset: {time_offset} (timeline values will be shifted by this amount)")
    
    for pid, saved_person in saved_state.items():
        if pid in people_objects:
            person = people_objects[pid]
            
            # Restore states directly (don't rely on timeline reconstruction)
            if 'states' in saved_person:
                old_states = dict(person.states) if hasattr(person, 'states') else {}
                person.states = {k: InfectionState(v) for k, v in saved_person['states'].items()}
                # Count infected
                for k, v in person.states.items():
                    if v.value & 1 == 1:
                        infected_restored += 1
            
            # Restore timeline with time offset adjustment
            # Timeline values need to be shifted so they're relative to the new simulation's start (t=0)
            # IMPORTANT: If ALL timeline entries for a disease have ended (end < 0), we should
            # NOT restore the timeline at all. This preserves the saved state (RECOVERED/REMOVED)
            # because update_state() would otherwise reset to SUSCEPTIBLE when it sees expired timelines.
            if 'timeline' in saved_person:
                person.timeline = {}
                for disease, state_timelines in saved_person['timeline'].items():
                    adjusted_timelines = {}
                    has_active_timeline = False
                    
                    for state_val, times in state_timelines.items():
                        state = InfectionState(int(state_val))
                        # Shift timeline values: if prev sim ended at t=44640 and infection started at t=40000,
                        # the new start should be 40000 - 44640 = -4640 (already happened)
                        # and if it ends at t=50000, new end = 50000 - 44640 = 5360 (will happen in new sim)
                        adjusted_start = times['start'] - time_offset
                        adjusted_end = times['end'] - time_offset
                        
                        # Only include timeline entries that haven't fully ended yet
                        if adjusted_end >= 0:
                            adjusted_timelines[state] = InfectionTimeline(adjusted_start, adjusted_end)
                            has_active_timeline = True
                    
                    # Only restore timeline for this disease if there are active entries
                    # If all entries have ended, DON'T add the timeline - this preserves the
                    # restored state value (e.g., RECOVERED) without update_state() resetting it
                    if has_active_timeline:
                        person.timeline[disease] = adjusted_timelines
                    else:
                        # All timeline entries expired - person's disease has concluded
                        # Don't add to timeline so update_state() won't touch this disease's state
                        print(f"[TIMELINE-DEBUG] Person {pid} disease {disease} fully concluded, preserving state={person.states.get(disease, 'none')}")
            
            # Restore other attributes
            if 'invisible' in saved_person:
                person.invisible = saved_person['invisible']
            if 'masked' in saved_person:
                person.masked = saved_person['masked']
            if 'vaccination_state' in saved_person:
                person.interventions = {'vaccine': VaccinationState(saved_person['vaccination_state'])}
            
            restored_count += 1
    
    print(f"[STATE_RESTORE] Restored {restored_count} people, {infected_restored} of them are infected")
    return restored_count


def get_state_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of a saved state without loading all person data.
    
    Args:
        state: Loaded state dictionary
    
    Returns:
        Summary with counts of infected, recovered, etc.
    """
    from .pap import InfectionState
    
    summary = {
        'total_people': len(state.get('people', {})),
        'infected': 0,
        'infectious': 0,
        'recovered': 0,
        'removed': 0,
        'susceptible': 0,
        'vaccinated': 0,
        'masked': 0,
    }
    
    for pid, person in state.get('people', {}).items():
        # Count by state
        states = person.get('states', {})
        has_infection = False
        
        for variant, state_val in states.items():
            state_flags = InfectionState(state_val)
            if state_flags & InfectionState.INFECTED:
                summary['infected'] += 1
                has_infection = True
            if state_flags & InfectionState.INFECTIOUS:
                summary['infectious'] += 1
            if state_flags & InfectionState.RECOVERED:
                summary['recovered'] += 1
            if state_flags & InfectionState.REMOVED:
                summary['removed'] += 1
        
        if not has_infection and summary['recovered'] == 0:
            summary['susceptible'] += 1
        
        # Vaccination
        if person.get('vaccination_state', 0) > 0:
            summary['vaccinated'] += 1
        
        # Masking
        if person.get('masked', False):
            summary['masked'] += 1
    
    return summary


class MultiMonthSimulation:
    """
    Orchestrates multi-month simulations with state persistence.
    
    Usage:
        sim = MultiMonthSimulation(
            patterns_folder='./data',
            start_month='2019-01',
            end_month='2019-03',
            state='OK'
        )
        
        for month, results in sim.run():
            print(f"Month {month}: {results['infections']} infections")
    """
    
    def __init__(
        self,
        patterns_folder: str,
        start_month: str,
        end_month: str,
        state: Optional[str] = None,
        state_save_folder: str = './simulation_states'
    ):
        """
        Initialize multi-month simulation.
        
        Args:
            patterns_folder: Folder containing monthly pattern CSVs
            start_month: Starting month (YYYY-MM)
            end_month: Ending month (YYYY-MM)
            state: Optional state code to filter pattern files
            state_save_folder: Folder to save intermediate states
        """
        # Import here to avoid circular imports
        import sys
        import os
        # Try local import first, fall back to Algorithms server path
        try:
            from monthly_patterns import MonthlyPatternsManager
        except ImportError:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../Algorithms/server'))
            from monthly_patterns import MonthlyPatternsManager
        
        self.patterns_folder = patterns_folder
        self.start_month = start_month
        self.end_month = end_month
        self.state = state
        self.state_save_folder = state_save_folder
        
        # Initialize patterns manager
        self.patterns_manager = MonthlyPatternsManager(patterns_folder, state)
        
        # Validate coverage
        is_valid, missing = self.patterns_manager.validate_range(start_month, end_month)
        if not is_valid:
            raise ValueError(f"Missing pattern files for months: {missing}")
        
        os.makedirs(state_save_folder, exist_ok=True)
    
    def get_state_file(self, month: str) -> str:
        """Get the path to the state file for a given month."""
        return os.path.join(self.state_save_folder, f'state_{month}.json')
    
    def iter_months(self):
        """Iterate over months in the simulation range."""
        return self.patterns_manager.iter_months(self.start_month, self.end_month)


if __name__ == "__main__":
    # Test the module
    print("State Manager module loaded successfully")
