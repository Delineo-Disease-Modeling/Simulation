"""
Simulation Behavioral Tests — Intervention Effectiveness

Tests that verify interventions work in the expected DIRECTION:
- Masks should reduce infection spread
- Lockdown should reduce infection spread  
- Capacity limits should reduce infection spread
- Self-isolation should reduce infection spread
- Each intervention should have a monotonic effect (more → fewer infections)

NOTE: These tests don't check exact values — they check that interventions
produce the right *relative* effect. This makes them robust to model tuning.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from helpers import run_sim, get_total_ever_infected, get_peak_infected, get_infection_curve


# Use barnsdall data for faster runs with realistic population
SIM_LENGTH = 2880  # 2 days in minutes — long enough for meaningful spread
INITIAL_INFECTED = 5


def _run_with_intervention(papdata, patterns, **iv_overrides):
    """Helper to run simulation with specific intervention values."""
    return run_sim(
        papdata, patterns,
        max_length=SIM_LENGTH,
        initial_infected_count=INITIAL_INFECTED,
        interventions=iv_overrides,
    )


class TestMaskEffectiveness:
    """Masks should reduce the rate and total number of infections."""

    @pytest.mark.behavioral
    def test_masks_reduce_total_infections(self, barnsdall_papdata, barnsdall_patterns):
        """100% mask rate should produce fewer total infections than 0%."""
        result_no_mask = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, mask=0.0)
        result_full_mask = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, mask=1.0)

        no_mask_total = get_total_ever_infected(result_no_mask)
        full_mask_total = get_total_ever_infected(result_full_mask)

        assert full_mask_total <= no_mask_total, \
            f"Full masks ({full_mask_total}) should have ≤ infections than no masks ({no_mask_total})"

    @pytest.mark.behavioral
    def test_mask_effect_is_monotonic(self, barnsdall_papdata, barnsdall_patterns):
        """More masks → fewer or equal infections (monotonic relationship)."""
        rates = [0.0, 0.25, 0.5, 0.75, 1.0]
        totals = []

        for rate in rates:
            result = _run_with_intervention(
                barnsdall_papdata, barnsdall_patterns, mask=rate)
            totals.append(get_total_ever_infected(result))

        for i in range(1, len(totals)):
            assert totals[i] <= totals[i - 1], \
                f"Mask rate {rates[i]} ({totals[i]} infected) should have ≤ infections " \
                f"than {rates[i-1]} ({totals[i-1]} infected)"


class TestLockdownEffectiveness:
    """Lockdown should reduce infection by keeping people home."""

    @pytest.mark.behavioral
    def test_lockdown_reduces_infections(self, barnsdall_papdata, barnsdall_patterns):
        """Full lockdown should produce fewer infections than no lockdown."""
        result_no_lock = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, lockdown=0.0)
        result_full_lock = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, lockdown=1.0)

        no_lock_total = get_total_ever_infected(result_no_lock)
        full_lock_total = get_total_ever_infected(result_full_lock)

        assert full_lock_total <= no_lock_total, \
            f"Full lockdown ({full_lock_total}) should have ≤ infections than none ({no_lock_total})"

    @pytest.mark.behavioral
    def test_full_lockdown_limits_spread_to_household(self, barnsdall_papdata, barnsdall_patterns):
        """
        With lockdown=1.0, infections should only spread within households,
        since nobody goes to public places. Total infections should therefore
        be limited (much smaller than the full population).
        """
        result = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, lockdown=1.0)
        
        total = get_total_ever_infected(result)
        pop = len(barnsdall_papdata["people"])

        # With full lockdown, infections should be a small fraction of pop
        # (only household spread). Allow up to 20% as a generous bound.
        assert total < pop * 0.20, \
            f"Full lockdown: {total}/{pop} infected ({total/pop:.1%}) — expected < 20%"


class TestCapacityLimits:
    """Capacity restrictions should reduce infections by reducing density."""

    @pytest.mark.behavioral
    def test_reduced_capacity_reduces_infections(self, barnsdall_papdata, barnsdall_patterns):
        """Lower facility capacity should give fewer infections."""
        result_full_cap = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, capacity=1.0)
        result_half_cap = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, capacity=0.5)

        full_total = get_total_ever_infected(result_full_cap)
        half_total = get_total_ever_infected(result_half_cap)

        assert half_total <= full_total, \
            f"50% capacity ({half_total}) should have ≤ infections than 100% ({full_total})"


class TestSelfIsolation:
    """Symptomatic self-isolation should reduce onward transmission."""

    @pytest.mark.behavioral
    def test_self_isolation_reduces_infections(self, barnsdall_papdata, barnsdall_patterns):
        """Full self-isolation should produce fewer infections than none."""
        result_no_iso = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, selfiso=0.0)
        result_full_iso = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, selfiso=1.0)

        no_iso_total = get_total_ever_infected(result_no_iso)
        full_iso_total = get_total_ever_infected(result_full_iso)

        assert full_iso_total <= no_iso_total, \
            f"Full self-isolation ({full_iso_total}) should have ≤ infections than none ({no_iso_total})"


class TestCombinedInterventions:
    """Multiple interventions together should be at least as effective as any single one."""

    @pytest.mark.behavioral
    def test_combined_better_than_single(self, barnsdall_papdata, barnsdall_patterns):
        """Masks + lockdown + self-iso combined should ≤ any single intervention."""
        result_masks_only = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, mask=0.8)
        result_lockdown_only = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, lockdown=0.5)
        result_combined = _run_with_intervention(
            barnsdall_papdata, barnsdall_patterns, mask=0.8, lockdown=0.5, selfiso=0.8)

        masks_total = get_total_ever_infected(result_masks_only)
        lockdown_total = get_total_ever_infected(result_lockdown_only)
        combined_total = get_total_ever_infected(result_combined)

        best_single = min(masks_total, lockdown_total)
        assert combined_total <= best_single, \
            f"Combined ({combined_total}) should be ≤ best single ({best_single})"
