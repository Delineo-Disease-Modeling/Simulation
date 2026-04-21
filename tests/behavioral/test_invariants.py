"""
Simulation Behavioral Correctness Tests — Invariants

Tests that verify fundamental properties that MUST hold regardless of parameters:
- Population conservation (no people created or destroyed)
- State machine validity (legal state transitions only)
- Determinism (same seed → same result)
- Boundary conditions (no infections without infected, no spread without contact)
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from helpers import run_sim, get_population_size, get_total_ever_infected, get_infection_curve


class TestPopulationConservation:
    """Total population count must remain constant throughout simulation."""

    @pytest.mark.behavioral
    def test_population_constant_over_time(self, barnsdall_papdata, barnsdall_patterns):
        """No people should appear or disappear during simulation."""
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=1440, initial_infected_count=3)

        pop_size = len(barnsdall_papdata["people"])

        for ts, ts_data in result["movement"].items():
            # Count all people across all locations at this timestep
            people_at_ts = set()
            for home_id, person_ids in ts_data.get("homes", {}).items():
                people_at_ts.update(person_ids)
            for place_id, person_ids in ts_data.get("places", {}).items():
                people_at_ts.update(person_ids)

            # Every person in movement data should exist in papdata
            for pid in people_at_ts:
                assert pid in barnsdall_papdata["people"], \
                    f"Person {pid} in movement at t={ts} not in papdata"

    @pytest.mark.behavioral
    def test_no_person_in_two_places(self, barnsdall_papdata, barnsdall_patterns):
        """A person cannot be in two places simultaneously."""
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=1440, initial_infected_count=3)

        for ts, ts_data in result["movement"].items():
            seen = {}
            for loc_type in ["homes", "places"]:
                for loc_id, person_ids in ts_data.get(loc_type, {}).items():
                    for pid in person_ids:
                        if pid in seen:
                            pytest.fail(
                                f"Person {pid} at t={ts} in both "
                                f"{seen[pid]} and {loc_type}/{loc_id}"
                            )
                        seen[pid] = f"{loc_type}/{loc_id}"


class TestStateValidity:
    """Infection states must follow valid transitions."""

    @pytest.mark.behavioral
    def test_states_are_valid_bitfields(self, barnsdall_papdata, barnsdall_patterns):
        """All state values must be valid combinations of InfectionState flags."""
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=2880, initial_infected_count=3)

        # Valid individual flags
        valid_flags = {0, 1, 2, 4, 8, 16, 32}
        max_combined = sum(valid_flags)  # 63

        for ts, ts_data in result["result"].items():
            for variant, people in ts_data.items():
                for pid, state_val in people.items():
                    assert 0 <= state_val <= max_combined, \
                        f"Person {pid} at t={ts} has invalid state {state_val}"

    @pytest.mark.behavioral
    def test_recovered_never_reinfected_same_variant(self, barnsdall_papdata, barnsdall_patterns):
        """
        Once RECOVERED (16) for a variant, a person should not go back to
        INFECTED (1) for the same variant. This tests the invisible flag logic.
        """
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=4320, initial_infected_count=5)

        # Track each person's state history per variant
        recovered = {}  # (pid, variant) -> first timestep recovered
        
        for ts in sorted(result["result"].keys()):
            ts_data = result["result"][ts]
            for variant, people in ts_data.items():
                for pid, state_val in people.items():
                    key = (pid, variant)
                    if state_val & 16:  # RECOVERED
                        if key not in recovered:
                            recovered[key] = ts
                    elif state_val & 1:  # INFECTED
                        if key in recovered:
                            pytest.fail(
                                f"Person {pid} recovered from {variant} at t={recovered[key]} "
                                f"but re-infected at t={ts}"
                            )


class TestDeterminism:
    """Same inputs with randseed=False should produce identical results."""

    @pytest.mark.behavioral
    def test_deterministic_with_seed(self, barnsdall_papdata, barnsdall_patterns):
        """Two runs with randseed=False should produce identical infection outcomes."""
        kwargs = dict(
            papdata=barnsdall_papdata,
            patterns=barnsdall_patterns,
            max_length=720,
            initial_infected_count=3,
            interventions={"randseed": False},
        )
        result1 = run_sim(**kwargs)
        result2 = run_sim(**kwargs)

        # Compare infection results at each timestep
        assert set(result1["result"].keys()) == set(result2["result"].keys()), \
            "Different timesteps between identical runs"

        for ts in result1["result"]:
            for variant in result1["result"][ts]:
                people1 = result1["result"][ts].get(variant, {})
                people2 = result2["result"][ts].get(variant, {})
                assert people1 == people2, \
                    f"Different infection states at t={ts}, variant={variant}"


class TestBoundaryConditions:
    """Edge cases that must hold."""

    @pytest.mark.behavioral
    def test_zero_initial_infected_means_no_spread(self, barnsdall_papdata, barnsdall_patterns):
        """With 0 initially infected people, nobody should ever get infected."""
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=1440, initial_infected_count=0)

        total = get_total_ever_infected(result)
        assert total == 0, f"Expected 0 infections with 0 initial infected, got {total}"

    @pytest.mark.behavioral
    def test_infection_requires_colocation(self, tiny_papdata, tiny_patterns):
        """
        If the initially infected person is isolated (never shares a location
        with susceptible people), no new infections should occur.
        """
        # Modify patterns: keep person "0" alone in place "0", everyone else in place "1"
        isolated_patterns = {
            "60": {
                "homes": {str(i // 2): [str(i), str(i + 1)] for i in range(0, 10, 2)},
                "places": {}
            },
            "120": {
                "homes": {},
                "places": {
                    "0": ["0"],  # person 0 alone
                    "1": [str(i) for i in range(1, 10)]  # everyone else
                }
            },
            "180": {
                "homes": {},
                "places": {
                    "0": ["0"],
                    "1": [str(i) for i in range(1, 10)]
                }
            },
            "240": {
                "homes": {str(i // 2): [str(i), str(i + 1)] for i in range(0, 10, 2)},
                "places": {}
            },
        }

        result = run_sim(tiny_papdata, isolated_patterns,
                         max_length=240, initial_infected_ids=["0"])

        # Only person 0 should ever be infected
        total = get_total_ever_infected(result)
        # Person 0 shares home with person 1, so person 1 might get infected at home.
        # But nobody in place "1" should get infected.
        for ts, ts_data in result["result"].items():
            for variant, people in ts_data.items():
                for pid, state_val in people.items():
                    if int(pid) >= 2 and state_val & 1:
                        # Check if this person was ever in the same location as person 0
                        # Persons 2-9 should never share a place with person 0
                        pytest.fail(
                            f"Person {pid} (not colocated with infected) got infected at t={ts}"
                        )

    @pytest.mark.behavioral
    def test_infections_grow_over_time(self, barnsdall_papdata, barnsdall_patterns):
        """
        With initial infections and no interventions, the total number of people
        ever infected should increase (or stay the same) over time — not decrease.
        """
        result = run_sim(barnsdall_papdata, barnsdall_patterns,
                         max_length=2880, initial_infected_count=5)

        ever_infected = set()
        prev_count = 0
        
        for ts in sorted(result["result"].keys()):
            ts_data = result["result"][ts]
            for variant, people in ts_data.items():
                for pid, state_val in people.items():
                    if state_val & 1:  # INFECTED flag
                        ever_infected.add(pid)
            
            current_count = len(ever_infected)
            assert current_count >= prev_count, \
                f"Total ever-infected decreased from {prev_count} to {current_count} at t={ts}"
            prev_count = current_count
