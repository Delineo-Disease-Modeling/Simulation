"""
Shared test fixtures for Delineo simulation tests.

Provides:
- Loaded test data (papdata, patterns) from tests/fixtures/
- Minimal synthetic populations for fast unit tests
- Helper functions for running simulations and analyzing results
"""
import sys
import os
import pytest

# Add project roots to path so we can import the simulation engine
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from helpers import load_json_fixture, resolve_fixture_path, run_sim


# ---------------------------------------------------------------------------
# Test data fixtures (loaded from tests/fixtures/)
# ---------------------------------------------------------------------------

BARNSDALL_PAPDATA_PATH = resolve_fixture_path(
    "tests/fixtures/barnsdall/papdata.json",
)
BARNSDALL_PATTERNS_PATH = resolve_fixture_path(
    "tests/fixtures/barnsdall/patterns.json",
)
TEST_PAPDATA_PATH = resolve_fixture_path(
    "tests/fixtures/test_data/papdata.json",
)
TEST_PATTERNS_JANUARY_PATH = resolve_fixture_path(
    "tests/fixtures/test_data/patterns_january.json",
)
TEST_PATTERNS_FEBRUARY_PATH = resolve_fixture_path(
    "tests/fixtures/test_data/patterns_february.json",
)


@pytest.fixture(scope="session")
def barnsdall_papdata():
    """Load the barnsdall papdata (small population, always available)."""
    return load_json_fixture(BARNSDALL_PAPDATA_PATH)


@pytest.fixture(scope="session")
def barnsdall_patterns():
    """Load the barnsdall patterns (small, always available)."""
    return load_json_fixture(BARNSDALL_PATTERNS_PATH)


@pytest.fixture(scope="session")
def test_papdata():
    """Load the full test papdata from tests/fixtures/test_data/."""
    return load_json_fixture(TEST_PAPDATA_PATH)


@pytest.fixture(scope="session")
def test_patterns_january():
    """Load January patterns from tests/fixtures/test_data/."""
    return load_json_fixture(TEST_PATTERNS_JANUARY_PATH)


@pytest.fixture(scope="session")
def test_patterns_february():
    """Load February patterns from tests/fixtures/test_data/."""
    return load_json_fixture(TEST_PATTERNS_FEBRUARY_PATH)


# ---------------------------------------------------------------------------
# Minimal synthetic fixtures for fast unit tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_papdata():
    """
    A minimal population: 10 people, 5 homes, 2 places.
    Small enough for tests that check infection mechanics precisely.
    """
    return {
        "people": {
            str(i): {"sex": i % 2, "age": 20 + i * 5, "home": str(i // 2)}
            for i in range(10)
        },
        "homes": {
            str(i): {"cbg": "999999999999", "members": 2}
            for i in range(5)
        },
        "places": {
            "0": {"cbg": "999999999999", "label": "TestStore", "capacity": 50,
                   "latitude": 36.5, "longitude": -96.3, "top_category": "Store",
                   "placekey": "test-key-0", "postal_code": 74003},
            "1": {"cbg": "999999999999", "label": "TestOffice", "capacity": 20,
                   "latitude": 36.6, "longitude": -96.2, "top_category": "Office",
                   "placekey": "test-key-1", "postal_code": 74003},
        }
    }


@pytest.fixture
def tiny_patterns():
    """
    Patterns for the tiny population — 4 hours (4 timesteps at 60min each).
    - Hour 1: everyone at home
    - Hour 2: persons 0-4 go to place 0, 5-9 go to place 1
    - Hour 3: same as hour 2 (gives time for infection)
    - Hour 4: everyone returns home
    """
    all_people = [str(i) for i in range(10)]
    group_a = [str(i) for i in range(5)]
    group_b = [str(i) for i in range(5, 10)]

    return {
        "60": {
            "homes": {str(i // 2): [str(i), str(i + 1)] for i in range(0, 10, 2)},
            "places": {}
        },
        "120": {
            "homes": {},
            "places": {"0": group_a, "1": group_b}
        },
        "180": {
            "homes": {},
            "places": {"0": group_a, "1": group_b}
        },
        "240": {
            "homes": {str(i // 2): [str(i), str(i + 1)] for i in range(0, 10, 2)},
            "places": {}
        },
    }


# ---------------------------------------------------------------------------
# Result analysis helpers
# ---------------------------------------------------------------------------

def count_infected_at_timestep(result, timestep, variant=None):
    """Count people with any non-zero (non-susceptible) state at a timestep."""
    if timestep not in result["result"]:
        return 0
    ts_data = result["result"][timestep]
    count = 0
    for v, people in ts_data.items():
        if variant and v != variant:
            continue
        for pid, state_val in people.items():
            if state_val != 0:  # not SUSCEPTIBLE
                count += 1
    return count


def get_total_ever_infected(result, variant=None):
    """Count unique people who were ever in a non-susceptible state."""
    infected_pids = set()
    for ts, ts_data in result["result"].items():
        for v, people in ts_data.items():
            if variant and v != variant:
                continue
            for pid, state_val in people.items():
                if state_val & 1:  # has INFECTED flag
                    infected_pids.add(pid)
    return len(infected_pids)


def get_peak_infected(result, variant=None):
    """Get the maximum number of simultaneously infected people and when it occurs."""
    peak = 0
    peak_time = 0
    for ts in sorted(result["result"].keys()):
        count = count_infected_at_timestep(result, ts, variant)
        if count > peak:
            peak = count
            peak_time = ts
    return peak, peak_time


def get_infection_curve(result, variant=None):
    """Return a list of (timestep, infected_count) tuples for plotting."""
    curve = []
    for ts in sorted(result["result"].keys()):
        count = count_infected_at_timestep(result, ts, variant)
        curve.append((ts, count))
    return curve


def get_final_state_counts(result):
    """
    At the last timestep, count people in each infection state category.
    Returns dict with keys: susceptible, infected, infectious, symptomatic,
    hospitalized, recovered, removed.
    """
    if not result["result"]:
        return {}
    
    last_ts = max(result["result"].keys())
    ts_data = result["result"][last_ts]
    
    counts = {
        "susceptible": 0, "infected": 0, "infectious": 0,
        "symptomatic": 0, "hospitalized": 0, "recovered": 0, "removed": 0,
    }
    
    # Count across all variants
    seen_pids = set()
    for variant, people in ts_data.items():
        for pid, state_val in people.items():
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            if state_val == 0:
                counts["susceptible"] += 1
            if state_val & 1:
                counts["infected"] += 1
            if state_val & 2:
                counts["infectious"] += 1
            if state_val & 4:
                counts["symptomatic"] += 1
            if state_val & 8:
                counts["hospitalized"] += 1
            if state_val & 16:
                counts["recovered"] += 1
            if state_val & 32:
                counts["removed"] += 1

    return counts


def get_population_size(result):
    """Get total population from the result's papdata."""
    return len(result["papdata"]["people"])
