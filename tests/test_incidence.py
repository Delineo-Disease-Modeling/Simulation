"""Regression guard for per-location infection incidence.

The engine tallies every transmission event by the room it happened in
(MembershipStore.incidence), which powers the frontend's "infections at home
vs POI" split and true-incidence POI rankings. These tests assert:
  - incidence counts real transmissions, not seeds (index cases);
  - the home-vs-place attribution lands in the right index range;
  - the emitted snapshot (hinc/pinc) matches the raw counter.
"""
import unittest

from simulator.runner import LoadedSimulationData, SimulationRunner


def _simdata(seeds, length):
    return {
        "czone_id": 1, "length": length, "randseed": False,
        "initial_infected_count": seeds, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


def _home_only_loaded(n=60, length=600, step=60):
    """Everyone shares one household for the whole run; no places exist."""
    pids = [str(i) for i in range(n)]
    patterns = {
        str(ts): {"homes": {"1": pids}, "places": {}}
        for ts in range(step, length + step, step)
    }
    return LoadedSimulationData(
        people_data={p: {"sex": int(p) % 2, "age": 30, "home": "1"} for p in pids},
        homes_data={"1": {"cbg": "cbg-home"}},
        places_data={},
        patterns_data=patterns,
    )


class IncidenceTest(unittest.TestCase):
    def _run(self, loaded, simdata):
        runner = SimulationRunner(simdata, enable_logging=False)
        runner._seed_random()
        context = runner.build_context(loaded)
        self.assertTrue(runner._soa_engine, "expected the vectorized engine path")
        runner.run_queue(context)
        return runner, context

    def test_home_infections_are_counted_and_attributed(self):
        loaded = _home_only_loaded()
        runner, context = self._run(loaded, _simdata(seeds=30, length=600))
        store = context.simulator.membership

        n_seeds = len(context.initial_infected_ids)
        ever_infected = len(context.infection_manager.infected)
        transmissions = ever_infected - n_seeds

        # The invariant: one incidence tick per non-seed infection, no more.
        self.assertEqual(int(store.incidence.sum()), transmissions)
        # With strong within-home mixing this run must actually spread.
        self.assertGreater(transmissions, 0, "expected some home transmission")
        # All of it lands in the home index range (no places in this scenario).
        H = store.n_homes
        self.assertEqual(int(store.incidence[H:].sum()), 0)
        self.assertEqual(int(store.incidence[:H].sum()), transmissions)

        # The emitted snapshot mirrors the raw counter.
        snap = store.incidence_snapshot()
        self.assertEqual(snap["hinc"], transmissions)
        self.assertEqual(sum(snap["pinc"]), 0)

    def test_seeds_alone_produce_no_incidence(self):
        # One person, seeded, nobody to infect -> zero transmission events.
        loaded = _home_only_loaded(n=1, length=120)
        runner, context = self._run(loaded, _simdata(seeds=1, length=120))
        store = context.simulator.membership
        self.assertEqual(int(store.incidence.sum()), 0)
        self.assertEqual(store.incidence_snapshot()["hinc"], 0)


if __name__ == "__main__":
    unittest.main()
