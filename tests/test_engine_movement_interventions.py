"""Movement interventions (lockdown / self-isolation / capacity) on the SoA engine.

The engine used to report these configs ineligible and fall back to the legacy
event-queue path. It now applies them itself in
``MembershipStore.apply_movement_with_interventions``. These tests pin the
semantics:
  - lockdown blocks whole facility trips, one draw per trip;
  - self-isolation keeps compliant SYMPTOMATIC people home;
  - facilities that list a capacity are capped at capacity * multiplier (the
    listed capacity itself at 100%), keeping people already inside and sending
    excess arrivals home;
  - runs without these interventions keep the plain scatter, and the
    intervention RNG never shifts the transmission RNG stream.
"""
import unittest
from unittest import mock

import numpy as np

from simulator.infectionmgr import InfectionManager
from simulator.membership import MembershipStore
from simulator.runner import LoadedSimulationData, SimulationRunner

FACILITY = "900"
DAY_HOURS = range(9, 17)  # 8 hourly steps at the facility each day
LENGTH = 3 * 1440


def _iv(time=0, capacity=1.0, lockdown=0.0, selfiso=0.0):
    return {"time": time, "mask": 0.0, "vaccine": 0.0,
            "capacity": capacity, "lockdown": lockdown, "selfiso": selfiso}


def _patterns(pids, length=LENGTH, facility=FACILITY, attendees=None):
    """Everyone lives alone (home id == pid). ``attendees`` (default: everyone)
    spend DAY_HOURS at ``facility`` each day and are home otherwise."""
    attendees = set(pids if attendees is None else attendees)
    patterns = {}
    for ts in range(60, length + 60, 60):
        at_fac = (ts // 60) % 24 in DAY_HOURS
        homes = {p: [p] for p in pids if not (at_fac and p in attendees)}
        places = {facility: sorted(attendees, key=int)} if at_fac else {}
        patterns[str(ts)] = {"homes": homes, "places": places}
    return patterns


def _loaded(n=200, capacity=None, length=LENGTH):
    pids = [str(i) for i in range(1, n + 1)]
    place = {"cbg": "cbg-fac", "label": "Facility"}
    if capacity is not None:
        place["capacity"] = capacity
    return LoadedSimulationData(
        people_data={p: {"sex": int(p) % 2, "age": 30, "home": p} for p in pids},
        homes_data={p: {"cbg": "cbg-home"} for p in pids},
        places_data={FACILITY: place},
        patterns_data=_patterns(pids, length),
    )


def _simdata(interventions, seeds=0, seed_ids=None, length=LENGTH, random_seed=7):
    data = {
        "czone_id": 1, "length": length, "randseed": False,
        "random_seed": random_seed, "initial_infected_count": seeds,
        "disease_name": "COVID-19", "variants": ["Delta"], "dmp_mode": "off",
        "interventions": interventions,
    }
    if seed_ids:
        data["initial_infected_ids"] = list(seed_ids)
    return data


def _run(simdata, loaded):
    runner = SimulationRunner(simdata, enable_logging=False)
    runner._seed_random()
    context = runner.build_context(loaded)
    assert runner._soa_engine, "expected the vectorized engine path"
    runner.run_queue(context)
    result = runner.finalize(context)
    return runner, context, result


def _facility_presence(result):
    """{ts: set of person indices at a facility} from the per-step loc stream."""
    movement = result["movement"]
    n_homes = movement["meta"]["n_homes"]
    out = {}
    for key, frame in movement.items():
        if key == "meta":
            continue
        loc = np.asarray(frame["loc"])
        out[int(key)] = set(np.nonzero(loc >= n_homes)[0].tolist())
    return out


def _symptomatic_course(self, person, disease, curtime):
    # Infected at t, infectious AND symptomatic from t+1h until recovery.
    return InfectionManager._build_timeline_from_csv_result(
        [("Infected", 0.0), ("Infectious_Symptomatic", 1.0), ("Recovered", 400.0)],
        disease,
        curtime,
    )


def _facility_steps(length=LENGTH):
    return [ts for ts in range(60, length + 60, 60) if (ts // 60) % 24 in DAY_HOURS]


class LockdownTest(unittest.TestCase):
    def test_full_lockdown_keeps_everyone_home(self):
        _, context, result = _run(_simdata([_iv(lockdown=1.0)]), _loaded())
        presence = _facility_presence(result)
        self.assertTrue(all(not people for people in presence.values()))
        store = context.simulator.membership
        self.assertEqual(store.redirects["lockdown"], 200 * len(_facility_steps()))
        self.assertEqual(
            result["metadata"]["movement_intervention_redirects"]["lockdown"],
            store.redirects["lockdown"],
        )

    def test_partial_lockdown_blocks_whole_trips(self):
        _, _, result = _run(_simdata([_iv(lockdown=0.5)]), _loaded())
        presence = _facility_presence(result)
        blocked = 0
        trips = 0
        for day in range(LENGTH // 1440):
            steps = [day * 1440 + h * 60 for h in DAY_HOURS]
            attended = [presence[ts] for ts in steps]
            # One draw per trip: a person is there for all of it or none of it.
            for people in attended[1:]:
                self.assertEqual(people, attended[0])
            trips += 200
            blocked += 200 - len(attended[0])
        self.assertGreater(blocked / trips, 0.4)
        self.assertLess(blocked / trips, 0.6)

    def test_lockdown_scheduled_mid_run_starts_then(self):
        # Intervention time is in hours: lockdown from the start of day 2.
        ivs = [_iv(time=0), _iv(time=24, lockdown=1.0)]
        _, _, result = _run(_simdata(ivs), _loaded())
        presence = _facility_presence(result)
        for ts in _facility_steps():
            expected = 200 if ts < 1440 else 0
            self.assertEqual(len(presence[ts]), expected, ts)

    def test_higher_lockdown_blocks_a_superset_of_trips(self):
        # The intervention RNG is its own stream and trip starts depend only on
        # the patterns, so two levels at the same seed share every trip draw.
        _, _, low = _run(_simdata([_iv(lockdown=0.3)]), _loaded())
        _, _, high = _run(_simdata([_iv(lockdown=0.6)]), _loaded())
        low_p, high_p = _facility_presence(low), _facility_presence(high)
        for ts in _facility_steps():
            self.assertTrue(high_p[ts] <= low_p[ts], ts)
        self.assertLess(
            sum(map(len, high_p.values())), sum(map(len, low_p.values()))
        )

    def test_redirected_people_are_at_their_own_home(self):
        _, context, result = _run(_simdata([_iv(lockdown=1.0)]), _loaded())
        store = context.simulator.membership
        loc = np.asarray(result["movement"][str(_facility_steps()[0])]["loc"])
        np.testing.assert_array_equal(loc, store.home_loc)


@mock.patch.object(InfectionManager, "create_timeline", _symptomatic_course)
class SelfIsolationTest(unittest.TestCase):
    SEEDS = [str(i) for i in range(1, 41)]

    def test_symptomatic_people_isolate_and_stop_facility_spread(self):
        # Everyone lives alone, so the facility is the only place to transmit.
        _, ctx_off, res_off = _run(
            _simdata([_iv()], seed_ids=self.SEEDS), _loaded()
        )
        _, ctx_on, res_on = _run(
            _simdata([_iv(selfiso=1.0)], seed_ids=self.SEEDS), _loaded()
        )
        store_off = ctx_off.simulator.membership
        store_on = ctx_on.simulator.membership
        self.assertGreater(int(store_off.incidence.sum()), 0)
        self.assertEqual(int(store_on.incidence.sum()), 0)
        self.assertEqual(len(ctx_on.infection_manager.infected), len(self.SEEDS))

        # The symptomatic seeds are never at the facility; everyone else is.
        seed_idx = {store_on.pid_to_idx[p] for p in self.SEEDS}
        for ts, people in _facility_presence(res_on).items():
            if ts in _facility_steps():
                self.assertFalse(people & seed_idx, ts)
                self.assertEqual(len(people), 200 - len(self.SEEDS), ts)
        self.assertGreater(store_on.redirects["selfiso"], 0)
        self.assertEqual(store_on.redirects["lockdown"], 0)

    def test_partial_selfiso_is_per_person_compliance(self):
        _, context, result = _run(
            _simdata([_iv(selfiso=0.5)], seed_ids=self.SEEDS), _loaded()
        )
        store = context.simulator.membership
        seed_idx = [store.pid_to_idx[p] for p in self.SEEDS]
        compliers = {i for i in seed_idx if store.iso_u[i] < 0.5}
        self.assertTrue(0 < len(compliers) < len(seed_idx))
        for ts, people in _facility_presence(result).items():
            if ts in _facility_steps():
                self.assertFalse(people & compliers, ts)
                # Seeds that did not comply still go (still symptomatic here).
                self.assertTrue((set(seed_idx) - compliers) <= people, ts)


class CapacityTest(unittest.TestCase):
    def test_capacity_caps_facility_and_keeps_people_inside(self):
        _, context, result = _run(
            _simdata([_iv(capacity=0.5)]), _loaded(n=100, capacity=20)
        )
        presence = _facility_presence(result)
        for day in range(LENGTH // 1440):
            steps = [day * 1440 + h * 60 for h in DAY_HOURS]
            first = presence[steps[0]]
            self.assertEqual(len(first), 10)
            for ts in steps[1:]:
                # People already inside keep their place for the whole visit.
                self.assertEqual(presence[ts], first, ts)
        store = context.simulator.membership
        self.assertEqual(store.redirects["capacity"], 90 * len(_facility_steps()))

    def test_limit_rounds_up_like_the_legacy_path(self):
        # capacity 7 at 50% admits ceil(3.5) = 4, as move_people does.
        _, _, result = _run(_simdata([_iv(capacity=0.5)]), _loaded(n=30, capacity=7))
        for ts in _facility_steps():
            self.assertEqual(len(_facility_presence(result)[ts]), 4, ts)

    def test_listed_capacity_is_enforced_at_full_multiplier(self):
        # No scheduled movement intervention at all: the listed capacity alone
        # turns the cap on, and 100% means "hold the listed capacity".
        _, context, result = _run(_simdata([_iv()]), _loaded(n=50, capacity=20))
        self.assertTrue(context.simulator.membership.movement_interventions_enabled)
        for ts in _facility_steps():
            self.assertEqual(len(_facility_presence(result)[ts]), 20, ts)

    def test_unlisted_or_nonpositive_capacity_is_uncapped(self):
        for capacity in (None, -1, 0):
            _, _, result = _run(
                _simdata([_iv(capacity=0.1)]), _loaded(n=50, capacity=capacity)
            )
            for ts in _facility_steps():
                self.assertEqual(len(_facility_presence(result)[ts]), 50, (capacity, ts))


class EngineInterventionWiringTest(unittest.TestCase):
    def test_runs_without_movement_interventions_keep_plain_scatter(self):
        _, context, result = _run(_simdata([_iv()]), _loaded(n=20))
        self.assertFalse(context.simulator.membership.movement_interventions_enabled)
        self.assertNotIn("movement_intervention_redirects", result["metadata"])

    def test_inert_intervention_does_not_shift_transmission_rng(self):
        # A selfiso level no one's draw can fall under enables the intervention
        # machinery without moving anyone. Output must match the plain run
        # exactly, which proves its draws stay off numpy's global stream.
        loaded = _loaded(n=120)
        seeds = [str(i) for i in range(1, 11)]
        _, ctx_a, res_a = _run(_simdata([_iv()], seed_ids=seeds), loaded)
        _, ctx_b, res_b = _run(_simdata([_iv(selfiso=1e-12)], seed_ids=seeds), loaded)
        self.assertFalse(ctx_a.simulator.membership.movement_interventions_enabled)
        self.assertTrue(ctx_b.simulator.membership.movement_interventions_enabled)
        self.assertGreater(len(ctx_a.infection_manager.infected), len(seeds))
        self.assertEqual(res_a["result"], res_b["result"])
        self.assertEqual(res_a["movement"], res_b["movement"])


class StoreSemanticsTest(unittest.TestCase):
    """Direct MembershipStore checks, independent of the runner."""

    def _store(self, n=6, capacity=np.inf, seed=0):
        pids = [str(i) for i in range(1, n + 1)]
        keys = [(p, True) for p in pids] + [(FACILITY, False)]
        store = MembershipStore(pids, keys)
        store.person_loc[:] = np.arange(n, dtype=np.int32)  # everyone at home
        store.precompute_movement(_patterns(pids, length=1440), 1440)
        caps = np.full(len(keys), np.inf)
        caps[-1] = capacity
        store.enable_movement_interventions(
            np.arange(n, dtype=np.int32), caps, np.random.default_rng(seed)
        )
        return store

    def test_capacity_prefers_people_already_inside(self):
        store = self._store(capacity=4)
        fac = store.n_homes
        store.apply_movement_with_interventions(9 * 60, _iv(capacity=0.5))
        first = set(np.nonzero(store.person_loc == fac)[0].tolist())
        self.assertEqual(len(first), 2)
        store.apply_movement_with_interventions(10 * 60, _iv(capacity=0.5))
        self.assertEqual(set(np.nonzero(store.person_loc == fac)[0].tolist()), first)

    def test_lowered_limit_mid_visit_trims_to_new_limit(self):
        store = self._store(capacity=4)
        fac = store.n_homes
        store.apply_movement_with_interventions(9 * 60, _iv(capacity=1.0))
        inside = set(np.nonzero(store.person_loc == fac)[0].tolist())
        self.assertEqual(len(inside), 4)  # listed capacity holds at 100%
        store.apply_movement_with_interventions(10 * 60, _iv(capacity=0.25))
        now = set(np.nonzero(store.person_loc == fac)[0].tolist())
        self.assertEqual(len(now), 1)
        self.assertTrue(now <= inside)  # the one left was already inside

    def test_selfiso_reads_symptomatic_bit(self):
        store = self._store()
        fac = store.n_homes
        store.pstate[0] = 2 | 4  # INFECTIOUS | SYMPTOMATIC
        store.pstate[1] = 2      # INFECTIOUS only
        store.apply_movement_with_interventions(9 * 60, _iv(selfiso=1.0))
        self.assertEqual(store.person_loc[0], 0)    # isolated at home
        self.assertEqual(store.person_loc[1], fac)  # asymptomatic still goes
        self.assertEqual(store.redirects["selfiso"], 1)


if __name__ == "__main__":
    unittest.main()
