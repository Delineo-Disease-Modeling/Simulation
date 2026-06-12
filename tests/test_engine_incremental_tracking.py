"""Regression guard for the incremental engine state/variant tracking (#2/#3).

update_variant_tracking only refreshes people who changed state this step, so
the initial seeds must be written into variant_infected at BUILD time — otherwise
a seed that doesn't transition by the first timestep would be silently missing
from the infection snapshot (the bug this guards).
"""
import unittest

from simulator.runner import LoadedSimulationData, SimulationRunner
from simulator.pap import InfectionState


def _loaded(n=8):
    # Engine mode sorts homes by int(id), so home ids must be numeric.
    return LoadedSimulationData(
        people_data={str(i): {"sex": i % 2, "age": 30 + i, "home": "1"} for i in range(n)},
        homes_data={"1": {"cbg": "cbg-home"}},
        places_data={},
        patterns_data={
            "60": {"homes": {"1": [str(i) for i in range(n)]}, "places": {}},
            "120": {"homes": {"1": [str(i) for i in range(n)]}, "places": {}},
        },
    )


def _simdata(seeds=3):
    return {
        "czone_id": 1, "length": 120, "randseed": False,
        "initial_infected_count": seeds, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


class EngineSeedTrackingTest(unittest.TestCase):
    def test_engine_engages_for_eligible_run(self):
        runner = SimulationRunner(_simdata(), enable_logging=False)
        runner._seed_random()
        runner.build_context(_loaded())
        self.assertTrue(runner._soa_engine, "single-variant no-intervention run should use the engine")

    def test_seeds_present_in_variant_infected_at_build(self):
        # The incremental tracker would miss non-transitioning seeds without the
        # build-time pre-population — this asserts they're there before step 1.
        runner = SimulationRunner(_simdata(seeds=3), enable_logging=False)
        runner._seed_random()
        context = runner.build_context(_loaded())
        variant = context.variants[0]
        seeded = set(context.initial_infected_ids)
        self.assertEqual(len(seeded), 3)
        self.assertTrue(
            seeded.issubset(set(context.variant_infected[variant])),
            f"seeds {seeded} missing from variant_infected {set(context.variant_infected[variant])}",
        )

    def test_seeds_in_first_snapshot_after_run(self):
        runner = SimulationRunner(_simdata(seeds=3), enable_logging=False)
        runner._seed_random()
        context = runner.build_context(_loaded())
        runner.run_queue(context)
        result = runner.finalize(context)
        variant = context.variants[0]
        seeded = set(context.initial_infected_ids)
        first = result["result"]["60"][variant]  # infection snapshot at ts=60
        self.assertTrue(
            seeded.issubset(set(first)),
            f"seeds {seeded} missing from first snapshot {set(first)}",
        )
        # every recorded value is a valid non-susceptible state
        for state_val in first.values():
            self.assertNotEqual(int(state_val) & ~int(InfectionState.SUSCEPTIBLE.value), 0)


if __name__ == "__main__":
    unittest.main()
