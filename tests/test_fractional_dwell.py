"""Fractional dwell: partial-hour visits expose for their real minutes.

The patterns can carry minutes-present per person per hour (legacy JSON: a sparse
per-timestep ``minutes: {pid: m}`` map; binary: the MINS section). With the
``fractional_dwell`` setting on, the engine kernel scales a partial visitor's
shedding and inhaling at the facility by frac = minutes / 60 and counts the rest
of the hour at home. These tests pin:
  - the MINS section round-trips, is optional, and older decoders ignore it;
  - the store picks up minutes from both formats, ignores minutes listed at
    homes, and resets anyone an intervention sends home to the full hour;
  - the dose matches the hand calculation for partial susceptibles, partial
    infectors, and the at-home remainder of a partial hour;
  - setting off, or patterns without partial visits, leaves output identical;
  - the setting defaults on.
"""
import struct
import unittest

import numpy as np

from simulator.membership import MembershipStore
from simulator.pap import InfectionState
from simulator.patterns_codec import (
    BinaryPatterns,
    build_arrays_from_legacy,
    build_minutes_from_legacy,
    decode_patterns_binary,
    encode_patterns_binary,
)
from simulator.runner import LoadedSimulationData, SimulationRunner

INFECTIOUS = int(InfectionState.INFECTIOUS.value)

# Wells-Riley base dose per full hour in a Q=150 room: 20 quanta/h x 0.5 m^3/h / 150.
BASE_Q = 20.0 * 0.5 / 150.0

FACILITY = "900001"


def _simdata(fractional_dwell, length=60, seeds=0):
    return {
        "czone_id": 1, "length": length, "randseed": False,
        "initial_infected_count": seeds, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "fractional_dwell": fractional_dwell,
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


def _world(households, at_facility, minutes):
    """One timestep (minute 60).

    ``households``: {home_id: [pids]}; ``at_facility``: pids at FACILITY this
    hour (everyone else is at home); ``minutes``: {pid: minutes at FACILITY}.
    """
    people = {}
    for home_id, pids in households.items():
        for pid in pids:
            people[pid] = {"sex": int(pid) % 2, "age": 30, "home": home_id}
    away = set(at_facility)
    homes_slot = {}
    for home_id, pids in households.items():
        present = [p for p in pids if p not in away]
        if present:
            homes_slot[home_id] = present
    slot = {"homes": homes_slot, "places": {FACILITY: list(at_facility)} if at_facility else {}}
    if minutes:
        slot["minutes"] = dict(minutes)
    return LoadedSimulationData(
        people_data=people,
        homes_data={h: {"cbg": "cbg-home"} for h in households},
        places_data={FACILITY: {"cbg": "cbg-f", "label": "Shop"}},
        patterns_data={"60": slot},
    )


def _one_step(loaded, infectious_pids, fractional_dwell=True, seed=7):
    """Build the world, place everyone, make ``infectious_pids`` infectious and
    run one vectorized transmission pass. Returns (runner, context)."""
    runner = SimulationRunner(_simdata(fractional_dwell), enable_logging=False)
    runner._seed_random()
    context = runner.build_context(loaded)
    assert runner._soa_engine, "single-variant no-intervention run should use the engine"
    store = context.simulator.membership
    store.apply_movement(60)
    for pid in infectious_pids:
        store.pstate[store.pid_to_idx[pid]] = INFECTIOUS
    np.random.seed(seed)
    runner._vectorized_transmission(context, 60)
    return runner, context


def _attack_rate(context, pids):
    infected = context.infection_manager.infected
    return sum(1 for p in pids if p in infected) / len(pids)


def _assert_rate(test, observed, expected, n):
    sigma = (expected * (1.0 - expected) / n) ** 0.5
    test.assertLess(abs(observed - expected), 5.0 * sigma,
                    f"attack rate {observed:.4f} vs expected {expected:.4f} (n={n})")


class MinutesCodecTest(unittest.TestCase):
    PAPDATA = {"people": {"1": {}, "2": {}, "3": {}},
               "homes": {"1": {}, "2": {}}, "places": {"5": {}}}
    PATTERNS = {
        "60": {"homes": {"1": ["1"], "2": ["2"]}, "places": {"5": ["3"]},
               "minutes": {"3": 20}},
        "120": {"homes": {"1": ["1", "2"]}, "places": {"5": ["3"]}},
    }

    def _encode(self, with_minutes=True):
        M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(self.PATTERNS, self.PAPDATA)
        minutes = build_minutes_from_legacy(self.PATTERNS, ts, pids) if with_minutes else None
        return encode_patterns_binary(M, ts, pids, loc_ids, n_homes, minutes=minutes), M

    def test_minutes_round_trip(self):
        blob, M = self._encode()
        bp = decode_patterns_binary(blob)
        np.testing.assert_array_equal(bp.loc_matrix, M)
        self.assertEqual(bp.minutes.tolist(), [[60, 60, 20], [60, 60, 60]])

    def test_no_minutes_maps_means_no_section(self):
        patterns = {k: {kk: vv for kk, vv in v.items() if kk != "minutes"}
                    for k, v in self.PATTERNS.items()}
        M, ts, pids, *_ = build_arrays_from_legacy(patterns, self.PAPDATA)
        self.assertIsNone(build_minutes_from_legacy(patterns, ts, pids))
        blob, _ = self._encode(with_minutes=False)
        self.assertIsNone(decode_patterns_binary(blob).minutes)

    def test_older_decoder_reads_the_same_matrix(self):
        # A pre-MINS decoder stops after the main payload: the matrix bytes and
        # everything before them are identical with or without the section.
        with_mins, _ = self._encode(with_minutes=True)
        without, _ = self._encode(with_minutes=False)
        self.assertTrue(with_mins.startswith(without))
        self.assertGreater(len(with_mins), len(without))

    def test_unknown_section_is_skipped(self):
        blob, _ = self._encode(with_minutes=True)
        junk = struct.pack("<4sBQQ", b"ZZZZ", 0, 3, 3) + b"abc"
        bp = decode_patterns_binary(blob + junk)
        self.assertEqual(int(bp.minutes[0, 2]), 20)

    def test_items_reconstructs_sparse_minutes(self):
        blob, _ = self._encode()
        rows = dict(decode_patterns_binary(blob).items())
        self.assertEqual(rows["60"]["minutes"], {"3": 20})
        self.assertNotIn("minutes", rows["120"])

    def test_out_of_range_minutes_rejected(self):
        bad = {"60": dict(self.PATTERNS["60"], minutes={"3": 0}),
               "120": self.PATTERNS["120"]}
        M, ts, pids, *_ = build_arrays_from_legacy(bad, self.PAPDATA)
        with self.assertRaises(ValueError):
            build_minutes_from_legacy(bad, ts, pids)


class MinutesStoreTest(unittest.TestCase):
    KEYS = [("1", True), ("2", True), ("5", False)]
    PEOPLE = ["1", "2", "3"]

    def _store(self, patterns):
        store = MembershipStore(self.PEOPLE, self.KEYS)
        store.precompute_movement(patterns, max_length=120)
        return store

    def test_legacy_and_binary_give_the_same_minutes(self):
        legacy = self._store(MinutesCodecTest.PATTERNS)
        M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(
            MinutesCodecTest.PATTERNS, MinutesCodecTest.PAPDATA)
        minutes = build_minutes_from_legacy(MinutesCodecTest.PATTERNS, ts, pids)
        binary = self._store(decode_patterns_binary(
            encode_patterns_binary(M, ts, pids, loc_ids, n_homes, minutes=minutes)))
        for store in (legacy, binary):
            self.assertTrue(store.has_partial_minutes)
            store.apply_movement(60)
            self.assertEqual(store.person_minutes.tolist(), [60, 60, 20])
            store.apply_movement(120)
            self.assertEqual(store.person_minutes.tolist(), [60, 60, 60])

    def test_minutes_listed_at_home_are_ignored(self):
        patterns = {"60": {"homes": {"1": ["1"], "2": ["2"]}, "places": {"5": ["3"]},
                           "minutes": {"1": 15}}}
        store = self._store(patterns)
        self.assertFalse(store.has_partial_minutes)
        store.apply_movement(60)
        self.assertEqual(store.person_minutes.tolist(), [60, 60, 60])

    def test_intervention_redirect_gets_the_full_hour_at_home(self):
        store = self._store(MinutesCodecTest.PATTERNS)
        store.enable_movement_interventions(
            np.array([0, 1, 1], dtype=np.int32),
            np.full(3, np.inf),
            np.random.default_rng(0),
        )
        store.apply_movement_with_interventions(60, {"lockdown": 1.0})
        self.assertEqual(int(store.person_loc[2]), 1)  # sent home
        self.assertEqual(int(store.person_minutes[2]), 60)


class FractionalDoseTest(unittest.TestCase):
    N = 3000  # susceptibles per group

    def test_partial_susceptible_inhales_for_its_minutes(self):
        # 30 full-hour infectors (W=30) and two groups of susceptibles at the
        # facility: full hour vs 15 minutes. Dose = BASE_Q * 30 * frac.
        infectors = [str(i) for i in range(30)]
        full = [str(1000 + i) for i in range(self.N)]
        quarter = [str(10000 + i) for i in range(self.N)]
        everyone = infectors + full + quarter
        households = {str(100000 + i): [p] for i, p in enumerate(everyone)}
        loaded = _world(households, everyone, {p: 15 for p in quarter})
        _, ctx = _one_step(loaded, infectors)
        _assert_rate(self, _attack_rate(ctx, full), 1 - np.exp(-BASE_Q * 30), self.N)
        _assert_rate(self, _attack_rate(ctx, quarter), 1 - np.exp(-BASE_Q * 30 * 0.25), self.N)

    def test_partial_infector_sheds_for_its_minutes(self):
        # 30 infectors in for 15 minutes each emit W = 30 * 0.25 = 7.5.
        infectors = [str(i) for i in range(30)]
        full = [str(1000 + i) for i in range(self.N)]
        everyone = infectors + full
        households = {str(100000 + i): [p] for i, p in enumerate(everyone)}
        loaded = _world(households, everyone, {p: 15 for p in infectors})
        _, ctx = _one_step(loaded, infectors)
        _assert_rate(self, _attack_rate(ctx, full), 1 - np.exp(-BASE_Q * 7.5), self.N)

    def test_rest_of_the_hour_counts_at_home(self):
        # Each household: 10 infectors at home all hour + 1 susceptible who
        # spends 15 minutes at an infector-free facility and 45 at home.
        # Dose = BASE_Q * 10 * 0.75, all of it at home.
        households, partial, n = {}, [], 2000
        for h in range(n):
            infectors = [str(h * 100 + k) for k in range(10)]
            sus = str(h * 100 + 50)
            households[str(500000 + h)] = infectors + [sus]
            partial.append(sus)
        all_infectors = [p for pids in households.values() for p in pids if p not in partial]
        loaded = _world(households, partial, {p: 15 for p in partial})
        _, ctx = _one_step(loaded, all_infectors)
        _assert_rate(self, _attack_rate(ctx, partial), 1 - np.exp(-BASE_Q * 10 * 0.75), n)
        store = ctx.simulator.membership
        hits = int(store.incidence.sum())
        self.assertGreater(hits, 0)
        self.assertEqual(int(store.incidence[: store.n_homes].sum()), hits)

    def test_partial_infector_sheds_at_home_for_the_rest(self):
        # Each household: 10 infectors who each spend 15 minutes at the facility
        # (45 at home) + 1 susceptible at home all hour. W_home = 10 * 0.75.
        households, sus_all, n = {}, [], 2000
        for h in range(n):
            infectors = [str(h * 100 + k) for k in range(10)]
            sus = str(h * 100 + 50)
            households[str(500000 + h)] = infectors + [sus]
            sus_all.append(sus)
        all_infectors = [p for pids in households.values() for p in pids if p not in sus_all]
        loaded = _world(households, all_infectors, {p: 15 for p in all_infectors})
        _, ctx = _one_step(loaded, all_infectors)
        _assert_rate(self, _attack_rate(ctx, sus_all), 1 - np.exp(-BASE_Q * 10 * 0.75), n)

    def test_setting_off_ignores_minutes(self):
        infectors = [str(i) for i in range(30)]
        quarter = [str(10000 + i) for i in range(self.N)]
        everyone = infectors + quarter
        households = {str(100000 + i): [p] for i, p in enumerate(everyone)}
        loaded = _world(households, everyone, {p: 15 for p in quarter})
        _, ctx = _one_step(loaded, infectors, fractional_dwell=False)
        _assert_rate(self, _attack_rate(ctx, quarter), 1 - np.exp(-BASE_Q * 30), self.N)


class FractionalDefaultTest(unittest.TestCase):
    def test_default_is_on_and_overridable(self):
        from simulator.config import INFECTION_MODEL
        from simulator.simdata import normalize_simdata

        self.assertTrue(INFECTION_MODEL["fractional_dwell"])
        base = {"czone_id": 1, "length": 60}
        self.assertTrue(normalize_simdata(dict(base))["fractional_dwell"])
        self.assertFalse(
            normalize_simdata(dict(base, fractional_dwell=False))["fractional_dwell"]
        )


class FractionalGoldenTest(unittest.TestCase):
    """Whole runs: no partial visits, or the setting off, change nothing."""

    def _loaded(self, with_minutes):
        n_homes, per_home = 40, 3
        households = {str(i + 1): [str(i * per_home + k) for k in range(per_home)]
                      for i in range(n_homes)}
        pids = [p for ps in households.values() for p in ps]
        patterns = {}
        for t in range(60, 24 * 60 + 60, 60):
            visitors = [p for p in pids if (int(p) + t // 60) % 4 == 0]
            homes = {}
            for h, ps in households.items():
                present = [p for p in ps if p not in visitors]
                if present:
                    homes[h] = present
            slot = {"homes": homes, "places": {FACILITY: visitors}}
            if with_minutes:
                slot["minutes"] = {p: 10 + int(p) % 40 for p in visitors}
            patterns[str(t)] = slot
        people = {p: {"sex": int(p) % 2, "age": 30, "home": h}
                  for h, ps in households.items() for p in ps}
        return LoadedSimulationData(
            people_data=people,
            homes_data={h: {"cbg": "cbg-home"} for h in households},
            places_data={FACILITY: {"cbg": "cbg-f", "label": "Shop"}},
            patterns_data=patterns,
        )

    def _run(self, loaded, fractional_dwell):
        runner = SimulationRunner(_simdata(fractional_dwell, length=24 * 60, seeds=12),
                                  enable_logging=False)
        runner._seed_random()
        context = runner.build_context(loaded)
        runner.run_queue(context)
        store = context.simulator.membership
        return (sorted(context.infection_manager.infected), store.incidence.tolist(),
                runner._fractional_dwell_active(context))

    def test_setting_off_matches_patterns_without_minutes(self):
        plain = self._run(self._loaded(with_minutes=False), fractional_dwell=False)
        off = self._run(self._loaded(with_minutes=True), fractional_dwell=False)
        self.assertEqual(plain, off)
        self.assertFalse(off[2])

    def test_setting_on_without_partial_visits_is_identical(self):
        plain = self._run(self._loaded(with_minutes=False), fractional_dwell=False)
        on = self._run(self._loaded(with_minutes=False), fractional_dwell=True)
        self.assertEqual(plain[:2], on[:2])
        self.assertFalse(on[2])

    def test_setting_on_with_partial_visits_applies(self):
        on = self._run(self._loaded(with_minutes=True), fractional_dwell=True)
        self.assertTrue(on[2])


if __name__ == "__main__":
    unittest.main()
