"""
Test Playground Generator for Delineo Simulation

Creates minimal papdata.json and patterns.json for debugging and testing.
All IDs are strings (critical requirement of the simulation engine).

Usage:
    python generator.py                    # Generate with defaults
    python generator.py --run              # Generate and run simulation
    python generator.py --scenario office  # Use predefined scenario
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

# Output directory (same as this script)
OUTPUT_DIR = Path(__file__).parent


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class Person:
    id: str
    sex: int        # 0 = male, 1 = female
    age: int
    home: str       # home ID (string!)
    
    def to_papdata(self) -> dict:
        return {"sex": self.sex, "age": self.age, "home": self.home}


@dataclass
class Home:
    id: str
    cbg: str
    members: int
    
    def to_papdata(self) -> dict:
        return {"cbg": self.cbg, "members": self.members}


@dataclass
class Place:
    id: str
    label: str
    cbg: str = "-1"
    latitude: float = 39.0
    longitude: float = -76.5
    capacity: int = 50
    
    def to_papdata(self) -> dict:
        return {
            "label": self.label,
            "cbg": self.cbg,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "capacity": self.capacity
        }


@dataclass 
class Movement:
    """A single movement event: person moves to a location at a timestep."""
    timestep: int       # minutes from start
    person_id: str
    location_type: str  # "home" or "place"
    location_id: str


@dataclass
class TestScenario:
    """Complete test scenario with people, homes, places, and movements."""
    name: str
    cbg: str = "000000000001"  # Test CBG
    people: list = field(default_factory=list)
    homes: list = field(default_factory=list)
    places: list = field(default_factory=list)
    movements: list = field(default_factory=list)
    initial_infected: list = field(default_factory=list)  # person IDs


# =============================================================================
# PREDEFINED SCENARIOS
# =============================================================================

def scenario_minimal() -> TestScenario:
    """
    Minimal scenario: 2 homes, 1 store, 5 people.
    Person 0 is infected, visits store, potentially infects others.
    """
    scenario = TestScenario(name="minimal")
    
    # Homes
    scenario.homes = [
        Home(id="0", cbg=scenario.cbg, members=3),  # Family of 3
        Home(id="1", cbg=scenario.cbg, members=2),  # Couple
    ]
    
    # Places
    scenario.places = [
        Place(id="0", label="Test Grocery Store", capacity=20),
    ]
    
    # People (5 total)
    scenario.people = [
        # Home 0: Family
        Person(id="0", sex=0, age=35, home="0"),  # Dad (INFECTED)
        Person(id="1", sex=1, age=33, home="0"),  # Mom
        Person(id="2", sex=0, age=8, home="0"),   # Kid
        # Home 1: Couple
        Person(id="3", sex=0, age=28, home="1"),  # Adult 1
        Person(id="4", sex=1, age=26, home="1"),  # Adult 2
    ]
    
    # Movement patterns (simple schedule)
    # Everyone starts at home (implicit)
    # At t=60 (1hr): Person 0 and 3 go to store
    # At t=120 (2hr): They return home
    # At t=180 (3hr): Person 1 goes to store
    # At t=240 (4hr): Person 1 returns home
    scenario.movements = [
        # Hour 1: Dad and Adult1 go shopping
        Movement(60, "0", "place", "0"),
        Movement(60, "3", "place", "0"),
        # Hour 2: They return home
        Movement(120, "0", "home", "0"),
        Movement(120, "3", "home", "1"),
        # Hour 3: Mom goes shopping (potential secondary infection)
        Movement(180, "1", "place", "0"),
        # Hour 4: Mom returns
        Movement(240, "1", "home", "0"),
    ]
    
    scenario.initial_infected = ["0"]  # Dad is patient zero
    
    return scenario


def scenario_office() -> TestScenario:
    """
    Office scenario: 3 homes, 1 office, 1 cafe, 6 people.
    Tests workplace transmission dynamics.
    """
    scenario = TestScenario(name="office")
    
    scenario.homes = [
        Home(id="0", cbg=scenario.cbg, members=2),
        Home(id="1", cbg=scenario.cbg, members=2),
        Home(id="2", cbg=scenario.cbg, members=2),
    ]
    
    scenario.places = [
        Place(id="0", label="Small Office", capacity=10),
        Place(id="1", label="Coffee Shop", capacity=8),
    ]
    
    scenario.people = [
        # Home 0
        Person(id="0", sex=0, age=30, home="0"),  # Worker A (INFECTED)
        Person(id="1", sex=1, age=28, home="0"),  # Partner A
        # Home 1  
        Person(id="2", sex=1, age=35, home="1"),  # Worker B
        Person(id="3", sex=0, age=37, home="1"),  # Partner B
        # Home 2
        Person(id="4", sex=0, age=25, home="2"),  # Worker C
        Person(id="5", sex=1, age=24, home="2"),  # Partner C
    ]
    
    # Work day simulation (8 hours = 480 minutes)
    scenario.movements = [
        # 9 AM (t=60): Workers go to office
        Movement(60, "0", "place", "0"),
        Movement(60, "2", "place", "0"),
        Movement(60, "4", "place", "0"),
        # 12 PM (t=240): Lunch at cafe
        Movement(240, "0", "place", "1"),
        Movement(240, "2", "place", "1"),
        Movement(240, "4", "place", "1"),
        # 1 PM (t=300): Back to office
        Movement(300, "0", "place", "0"),
        Movement(300, "2", "place", "0"),
        Movement(300, "4", "place", "0"),
        # 5 PM (t=540): Go home
        Movement(540, "0", "home", "0"),
        Movement(540, "2", "home", "1"),
        Movement(540, "4", "home", "2"),
    ]
    
    scenario.initial_infected = ["0"]
    
    return scenario


def scenario_superspreader() -> TestScenario:
    """
    Superspreader event: 1 infected person visits multiple locations.
    Tests rapid spread through a small population.
    """
    scenario = TestScenario(name="superspreader")
    
    scenario.homes = [
        Home(id="0", cbg=scenario.cbg, members=1),  # Superspreader lives alone
        Home(id="1", cbg=scenario.cbg, members=2),
        Home(id="2", cbg=scenario.cbg, members=2),
    ]
    
    scenario.places = [
        Place(id="0", label="Gym", capacity=15),
        Place(id="1", label="Restaurant", capacity=20),
        Place(id="2", label="Bar", capacity=25),
    ]
    
    scenario.people = [
        Person(id="0", sex=0, age=25, home="0"),  # Superspreader (INFECTED)
        Person(id="1", sex=0, age=30, home="1"),
        Person(id="2", sex=1, age=28, home="1"),
        Person(id="3", sex=1, age=35, home="2"),
        Person(id="4", sex=0, age=40, home="2"),
    ]
    
    # Superspreader visits all locations, others visit one each
    scenario.movements = [
        # Morning: Gym
        Movement(60, "0", "place", "0"),   # Spreader at gym
        Movement(60, "1", "place", "0"),   # Person 1 at gym
        Movement(120, "0", "home", "0"),
        Movement(120, "1", "home", "1"),
        # Lunch: Restaurant
        Movement(180, "0", "place", "1"),  # Spreader at restaurant
        Movement(180, "2", "place", "1"),  # Person 2 at restaurant
        Movement(240, "0", "home", "0"),
        Movement(240, "2", "home", "1"),
        # Evening: Bar
        Movement(300, "0", "place", "2"),  # Spreader at bar
        Movement(300, "3", "place", "2"),  # Person 3 at bar
        Movement(300, "4", "place", "2"),  # Person 4 at bar
        Movement(360, "0", "home", "0"),
        Movement(360, "3", "home", "2"),
        Movement(360, "4", "home", "2"),
    ]
    
    scenario.initial_infected = ["0"]
    
    return scenario


SCENARIOS = {
    "minimal": scenario_minimal,
    "office": scenario_office,
    "superspreader": scenario_superspreader,
}


# =============================================================================
# GENERATORS
# =============================================================================

def generate_papdata(scenario: TestScenario) -> dict:
    """Generate papdata.json content from a scenario."""
    return {
        "people": {p.id: p.to_papdata() for p in scenario.people},
        "homes": {h.id: h.to_papdata() for h in scenario.homes},
        "places": {p.id: p.to_papdata() for p in scenario.places},
    }


def generate_patterns(scenario: TestScenario, duration_hours: int = 24) -> dict:
    """
    Generate patterns.json from movements.
    
    Patterns format: {
        "60": {"homes": {"home_id": ["person_id", ...]}, "places": {...}},
        "120": {...},
        ...
    }
    """
    patterns = {}
    
    # Group movements by timestep
    movements_by_time = {}
    for m in scenario.movements:
        if m.timestep not in movements_by_time:
            movements_by_time[m.timestep] = []
        movements_by_time[m.timestep].append(m)
    
    # Convert to patterns format
    for timestep, movements in movements_by_time.items():
        patterns[str(timestep)] = {"homes": {}, "places": {}}
        
        for m in movements:
            loc_type = "homes" if m.location_type == "home" else "places"
            if m.location_id not in patterns[str(timestep)][loc_type]:
                patterns[str(timestep)][loc_type][m.location_id] = []
            patterns[str(timestep)][loc_type][m.location_id].append(m.person_id)
    
    return patterns


def save_scenario(scenario: TestScenario, output_dir: Path = OUTPUT_DIR):
    """Save papdata.json and patterns.json for a scenario."""
    papdata = generate_papdata(scenario)
    patterns = generate_patterns(scenario)
    
    papdata_path = output_dir / "papdata.json"
    patterns_path = output_dir / "patterns.json"
    
    with open(papdata_path, "w") as f:
        json.dump(papdata, f, indent=2)
    
    with open(patterns_path, "w") as f:
        json.dump(patterns, f, indent=2)
    
    # Also save scenario metadata
    meta = {
        "scenario_name": scenario.name,
        "num_people": len(scenario.people),
        "num_homes": len(scenario.homes),
        "num_places": len(scenario.places),
        "num_movements": len(scenario.movements),
        "initial_infected": scenario.initial_infected,
    }
    with open(output_dir / "scenario_meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    
    print(f"✓ Generated test data for scenario: {scenario.name}")
    print(f"  - People: {len(scenario.people)}")
    print(f"  - Homes: {len(scenario.homes)}")
    print(f"  - Places: {len(scenario.places)}")
    print(f"  - Movement events: {len(scenario.movements)}")
    print(f"  - Initial infected: {scenario.initial_infected}")
    print(f"  - Output: {output_dir}")
    
    return papdata, patterns


# =============================================================================
# CUSTOM SCENARIO BUILDER
# =============================================================================

class ScenarioBuilder:
    """Fluent builder for creating custom test scenarios."""
    
    def __init__(self, name: str = "custom"):
        self.scenario = TestScenario(name=name)
        self._person_counter = 0
        self._home_counter = 0
        self._place_counter = 0
    
    def set_cbg(self, cbg: str) -> "ScenarioBuilder":
        self.scenario.cbg = cbg
        return self
    
    def add_home(self, members: int = 2) -> str:
        """Add a home and return its ID."""
        home_id = str(self._home_counter)
        self.scenario.homes.append(Home(
            id=home_id,
            cbg=self.scenario.cbg,
            members=members
        ))
        self._home_counter += 1
        return home_id
    
    def add_place(self, label: str, capacity: int = 50) -> str:
        """Add a place and return its ID."""
        place_id = str(self._place_counter)
        self.scenario.places.append(Place(
            id=place_id,
            label=label,
            capacity=capacity
        ))
        self._place_counter += 1
        return place_id
    
    def add_person(self, home_id: str, age: int = 30, sex: int = 0) -> str:
        """Add a person and return their ID."""
        person_id = str(self._person_counter)
        self.scenario.people.append(Person(
            id=person_id,
            sex=sex,
            age=age,
            home=home_id
        ))
        self._person_counter += 1
        
        # Update home member count
        for h in self.scenario.homes:
            if h.id == home_id:
                h.members += 1
                break
        
        return person_id
    
    def add_movement(self, timestep: int, person_id: str, 
                     location_type: str, location_id: str) -> "ScenarioBuilder":
        """Add a movement event."""
        self.scenario.movements.append(Movement(
            timestep=timestep,
            person_id=person_id,
            location_type=location_type,
            location_id=location_id
        ))
        return self
    
    def set_infected(self, person_ids: list) -> "ScenarioBuilder":
        """Set initial infected person IDs."""
        self.scenario.initial_infected = person_ids
        return self
    
    def build(self) -> TestScenario:
        """Build and return the scenario."""
        # Fix member counts (builder tracks additions)
        home_counts = {}
        for p in self.scenario.people:
            home_counts[p.home] = home_counts.get(p.home, 0) + 1
        for h in self.scenario.homes:
            h.members = home_counts.get(h.id, 0)
        
        return self.scenario


# =============================================================================
# CLI INTERFACE
# =============================================================================

def run_simulation(location: str = "test_playground", length: int = 480):
    """Run simulation using generated test data."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    from simulator import simulate
    
    print(f"\n{'='*60}")
    print(f"Running simulation: location={location}, length={length} minutes")
    print(f"{'='*60}\n")
    
    # Load scenario metadata for initial infected
    meta_path = OUTPUT_DIR / "scenario_meta.json"
    initial_infected = None
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
            initial_infected = meta.get("initial_infected")
            print(f"Initial infected from scenario: {initial_infected}")
    
    result = simulate.run_simulator(
        location=location,
        max_length=length,  # Note: param is max_length
        interventions={"mask": 0.0, "vaccine": 0.0, "capacity": 1.0, 
                      "lockdown": 0, "selfiso": 0.0, "randseed": False},
        initial_infected_ids=initial_infected,
    )
    
    print(f"\n{'='*60}")
    print("Simulation Results Summary")
    print(f"{'='*60}")
    
    if "result" in result and result["result"]:
        timesteps = sorted(result["result"].keys(), key=int)
        print(f"Timesteps: {len(timesteps)}")
        
        # Show first and last states
        if timesteps:
            first = result["result"][timesteps[0]]
            last = result["result"][timesteps[-1]]
            print(f"\nInitial state (t={timesteps[0]}):")
            print(f"  Susceptible: {first.get('susceptible', 'N/A')}")
            print(f"  Infected: {first.get('infected', 'N/A')}")
            
            print(f"\nFinal state (t={timesteps[-1]}):")
            print(f"  Susceptible: {last.get('susceptible', 'N/A')}")
            print(f"  Infected: {last.get('infected', 'N/A')}")
            print(f"  Recovered: {last.get('recovered', 'N/A')}")
            print(f"  Removed: {last.get('removed', 'N/A')}")
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Playground Generator")
    parser.add_argument("--scenario", "-s", choices=list(SCENARIOS.keys()),
                       default="minimal", help="Predefined scenario to use")
    parser.add_argument("--run", "-r", action="store_true",
                       help="Run simulation after generating data")
    parser.add_argument("--length", "-l", type=int, default=480,
                       help="Simulation length in minutes (default: 480 = 8 hours)")
    parser.add_argument("--list", action="store_true",
                       help="List available scenarios")
    
    args = parser.parse_args()
    
    if args.list:
        print("Available scenarios:")
        for name, factory in SCENARIOS.items():
            s = factory()
            print(f"  {name}: {len(s.people)} people, {len(s.homes)} homes, "
                  f"{len(s.places)} places")
        return
    
    # Generate scenario
    scenario = SCENARIOS[args.scenario]()
    save_scenario(scenario)
    
    # Optionally run simulation
    if args.run:
        run_simulation(length=args.length)


if __name__ == "__main__":
    main()
