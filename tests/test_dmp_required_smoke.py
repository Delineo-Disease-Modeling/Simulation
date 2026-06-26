"""Real in-process DMP smoke test (kept out of the core unit suite).

The unit suite (test_natural_history.py) runs with dmp_mode="off" so it never
touches the DMP state-machine DB. This separate smoke test exercises the actual
prod path — in-process DMP with dmp_mode="required" — and asserts the run uses
DMP timelines with ZERO silent fallbacks. It is skipped automatically when the
DMP DB / package isn't available (e.g. a CI box without the fixture), so it never
turns a missing optional fixture into a red suite.
"""
import unittest

from simulator.runner import LoadedSimulationData, SimulationRunner


def _dmp_available() -> bool:
    try:
        from simulator.dmp_inprocess import InProcessDMP

        InProcessDMP()
        return True
    except Exception:
        return False


DMP_AVAILABLE = _dmp_available()

N = 40
_FACILITY = "1001"


def _loaded():
    pids = [str(i) for i in range(N)]
    patterns = {
        str(t): {"homes": {}, "places": {_FACILITY: pids}}
        for t in range(60, 4321, 60)  # 3 days, hourly
    }
    return LoadedSimulationData(
        people_data={p: {"sex": int(p) % 2, "age": 30, "home": "1"} for p in pids},
        homes_data={"1": {"cbg": "cbg-home"}},
        places_data={_FACILITY: {"cbg": "cbg-f1", "label": "Shop"}},
        patterns_data=patterns,
    )


def _simdata():
    return {
        "czone_id": 1, "length": 4320, "randseed": False,
        "initial_infected_count": 3, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "required",
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


@unittest.skipUnless(DMP_AVAILABLE, "in-process DMP DB/package not available")
class DmpRequiredSmokeTest(unittest.TestCase):
    def _run(self):
        runner = SimulationRunner(_simdata(), enable_logging=False)
        runner._seed_random()
        context = runner.build_context(_loaded())
        self.assertTrue(runner._soa_engine, "eligible run should use the engine")
        runner.run_queue(context)
        return context

    def test_required_mode_uses_dmp_with_zero_fallback(self):
        context = self._run()
        counts = context.infection_manager.timeline_source_counts
        self.assertEqual(
            counts["fallback"], 0,
            "dmp_mode='required' must never use the degraded fallback timeline",
        )
        self.assertGreater(counts["dmp"], 0, "expected DMP-sourced timelines")

    def test_outbreak_is_bounded_by_population(self):
        # Sanity / conservation: ever-infected is at least the seeds and never
        # exceeds the population. Proves the real-DMP path runs end to end.
        context = self._run()
        ever = len(context.infection_manager.infected)
        self.assertGreaterEqual(ever, 3)
        self.assertLessEqual(ever, N)


if __name__ == "__main__":
    unittest.main()
