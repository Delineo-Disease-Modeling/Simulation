"""
Test Playground - Minimal simulation test environment.

Usage:
    from simulator.test_playground import run_test, ScenarioBuilder, SCENARIOS
    
    # Quick test
    result = run_test(length=480)
    
    # Custom scenario
    builder = ScenarioBuilder("custom")
    home = builder.add_home()
    store = builder.add_place("Store")
    person = builder.add_person(home, age=30)
    builder.set_infected([person])
    scenario = builder.build()

Patterns CSV Generator:
    from simulator.test_playground import PatternsCsvBuilder, save_patterns_scenario
    
    builder = PatternsCsvBuilder("test")
    builder.add_place("Store", "grocery")
    save_patterns_scenario(builder.build())
"""

from .generator import (
    ScenarioBuilder,
    TestScenario,
    Person,
    Home,
    Place,
    Movement,
    SCENARIOS,
    save_scenario,
    generate_papdata,
    generate_patterns,
)

from .run_test import run_test, test_scenario

from .patterns_csv_generator import (
    PatternsCsvBuilder,
    TestPatternsScenario,
    TestPlace,
    PlaceType,
    PLACE_TYPES,
    SCENARIOS as PATTERNS_SCENARIOS,
    save_scenario as save_patterns_scenario,
    generate_patterns_csv,
)

__all__ = [
    # Simulation test
    "run_test",
    "test_scenario",
    "ScenarioBuilder",
    "TestScenario",
    "Person",
    "Home",
    "Place",
    "Movement",
    "SCENARIOS",
    "save_scenario",
    "generate_papdata",
    "generate_patterns",
    # Patterns CSV generator
    "PatternsCsvBuilder",
    "TestPatternsScenario",
    "TestPlace",
    "PlaceType",
    "PLACE_TYPES",
    "PATTERNS_SCENARIOS",
    "save_patterns_scenario",
    "generate_patterns_csv",
]
