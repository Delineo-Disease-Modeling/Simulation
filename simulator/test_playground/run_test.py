#!/usr/bin/env python
"""
Quick test runner for the test playground.
Run from the Simulation directory:
    python -m simulator.test_playground.run_test
"""

import sys
import json
from pathlib import Path

# Add parent to path for imports
PLAYGROUND_DIR = Path(__file__).parent
SIMULATOR_DIR = PLAYGROUND_DIR.parent
SIMULATION_DIR = SIMULATOR_DIR.parent
sys.path.insert(0, str(SIMULATION_DIR))

from simulator import simulate
from simulator.config import SIMULATION


def run_test(
    length: int = 480,
    interventions: dict = None,
    initial_infected: list = None,
    verbose: bool = True
):
    """
    Run a test simulation with the playground data.
    
    Args:
        length: Simulation length in minutes (default 480 = 8 hours)
        interventions: Override interventions dict
        initial_infected: List of person IDs to infect initially
        verbose: Print detailed output
    
    Returns:
        Simulation result dict
    """
    # Load scenario metadata
    meta_path = PLAYGROUND_DIR / "scenario_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        if initial_infected is None:
            initial_infected = meta.get("initial_infected", ["0"])
        if verbose:
            print(f"Scenario: {meta.get('scenario_name', 'unknown')}")
            print(f"  People: {meta.get('num_people')}")
            print(f"  Homes: {meta.get('num_homes')}")
            print(f"  Places: {meta.get('num_places')}")
    
    # Default interventions (no masks, no vaccines, full capacity)
    if interventions is None:
        interventions = {
            "mask": 0.0,
            "vaccine": 0.0,
            "capacity": 1.0,
            "lockdown": 0,
            "selfiso": 0.0,
            "randseed": False  # Deterministic for testing
        }
    
    if verbose:
        print(f"\nRunning simulation...")
        print(f"  Location: test_playground")
        print(f"  Length: {length} minutes ({length/60:.1f} hours)")
        print(f"  Initial infected: {initial_infected}")
        print(f"  Interventions: {interventions}")
    
    result = simulate.run_simulator(
        location="test_playground",
        max_length=length,  # Note: param is max_length, not length
        interventions=interventions,
        initial_infected_ids=initial_infected,
    )
    
    if verbose and "result" in result:
        timesteps = sorted(result["result"].keys(), key=lambda x: int(x) if str(x).isdigit() else 0)
        print(f"\n{'='*50}")
        print("RESULTS")
        print(f"{'='*50}")
        print(f"Total timesteps: {len(timesteps)}")
        
        # Count infections from people_state
        if "people_state" in result:
            people = result["people_state"]
            infected_count = 0
            recovered_count = 0
            for pid, pdata in people.items():
                states = pdata.get('states', {})
                for variant, state_val in states.items():
                    if state_val & 1:  # INFECTED bit
                        infected_count += 1
                    if state_val & 16:  # RECOVERED bit
                        recovered_count += 1
            
            susceptible = len(people) - infected_count - recovered_count
            print(f"\nFinal state (from people_state):")
            print(f"  Total people: {len(people)}")
            print(f"  Infected: {infected_count}")
            print(f"  Recovered: {recovered_count}")
            print(f"  Susceptible: {susceptible}")
        
        # Show variant infection timeline
        if timesteps:
            print("\nInfection Timeline (per variant):")
            for t in timesteps[:5]:
                state = result["result"][t]
                parts = []
                for variant, infected_dict in state.items():
                    count = len(infected_dict) if isinstance(infected_dict, dict) else infected_dict
                    parts.append(f"{variant}:{count}")
                print(f"  t={t:>4}: {', '.join(parts)}")
            
            if len(timesteps) > 5:
                print(f"  ... ({len(timesteps) - 5} more timesteps)")
    
    return result


def test_scenario(scenario_name: str, **kwargs):
    """Generate a scenario and run it."""
    from simulator.test_playground.generator import SCENARIOS, save_scenario
    
    if scenario_name not in SCENARIOS:
        print(f"Unknown scenario: {scenario_name}")
        print(f"Available: {list(SCENARIOS.keys())}")
        return None
    
    scenario = SCENARIOS[scenario_name]()
    save_scenario(scenario)
    
    return run_test(**kwargs)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run test playground simulation")
    parser.add_argument("--length", "-l", type=int, default=480,
                       help="Simulation length in minutes")
    parser.add_argument("--scenario", "-s", 
                       help="Regenerate with scenario before running")
    parser.add_argument("--mask", type=float, default=0.0,
                       help="Mask wearing rate (0-1)")
    parser.add_argument("--vaccine", type=float, default=0.0,
                       help="Vaccination rate (0-1)")
    parser.add_argument("--quiet", "-q", action="store_true",
                       help="Minimal output")
    
    args = parser.parse_args()
    
    interventions = {
        "mask": args.mask,
        "vaccine": args.vaccine,
        "capacity": 1.0,
        "lockdown": 0,
        "selfiso": 0.0,
        "randseed": False
    }
    
    if args.scenario:
        test_scenario(args.scenario, length=args.length, 
                     interventions=interventions, verbose=not args.quiet)
    else:
        run_test(length=args.length, interventions=interventions, 
                verbose=not args.quiet)
