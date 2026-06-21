"""External force-of-infection term (open-system coupling).

The ~85% of a POI's real visitors who live outside the simulated cluster are
represented as a one-way background quanta source rather than as agents:
W_external[loc] = n_internal[loc] * (1 - f_j)/f_j * emit_factor * P_ext, added to
each room's well-mixed emission in the SoA engine kernel. f_j (catchment_fj) is
emitted per-POI by popgen. These tests pin: the term is inert by default and when
P_ext=0 (golden preserved), it can seed infections from zero internal seed when
on, it scales with P_ext, and households (no f_j) get no external term.

Design: Algorithms docs/MOVEMENT_MODEL_REDESIGN.md §10.
"""
import unittest

from simulator.runner import LoadedSimulationData, SimulationRunner, normalize_simdata
from simulator.world import parse_facility
from simulator.config import INFECTION_MODEL

_N = 24


def _loaded(at_facility: bool, fj=0.1):
    homes_data = {"1": {"cbg": "cbg-home"}}
    # facility id must be numeric (engine sorts facilities by int(id)) and
    # distinct from the home id to avoid the home/place id space colliding.
    places_data = (
        {"1001": {"cbg": "cbg-f1", "label": "Shop", "catchment_fj": fj}}
        if at_facility else {}
    )
    pids = [str(i) for i in range(_N)]
    slot = (
        {"homes": {}, "places": {"1001": pids}}
        if at_facility else {"homes": {"1": pids}, "places": {}}
    )
    patterns_data = {str(t): slot for t in (60, 120, 180, 240, 300)}
    people_data = {p: {"sex": int(p) % 2, "age": 30, "home": "1"} for p in pids}
    return LoadedSimulationData(
        people_data=people_data, homes_data=homes_data,
        places_data=places_data, patterns_data=patterns_data,
    )


def _simdata(external_foi, external_prevalence, seeds):
    return {
        "czone_id": 1, "length": 300, "randseed": False,
        "initial_infected_count": seeds, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "external_foi": external_foi, "external_prevalence": external_prevalence,
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


def _ever_infected(external_foi=False, external_prevalence=0.0, seeds=0,
                   at_facility=True, fj=0.1):
    runner = SimulationRunner(_simdata(external_foi, external_prevalence, seeds),
                              enable_logging=False)
    runner._seed_random()
    context = runner.build_context(_loaded(at_facility, fj=fj))
    assert runner._soa_engine, "single-variant no-intervention run should use the engine"
    runner.run_queue(context)
    return len(context.infection_manager.infected)


class ExternalFoiKernelTest(unittest.TestCase):
    def test_off_no_spontaneous_infection(self):
        # flag off + zero seed -> closed system, nothing happens (golden).
        self.assertEqual(_ever_infected(external_foi=False, seeds=0), 0)

    def test_seeds_from_zero_internal_seed(self):
        # flag on + P_ext>0 + zero internal seed -> the external term alone seeds
        # an outbreak (the open-system cold-start the design is about).
        n = _ever_infected(external_foi=True, external_prevalence=0.2, seeds=0)
        self.assertGreater(n, 0)

    def test_inert_when_prevalence_zero(self):
        # flag ON but P_ext=0 -> inert (the v1 "default 0 = inert" guarantee).
        self.assertEqual(
            _ever_infected(external_foi=True, external_prevalence=0.0, seeds=0), 0
        )

    def test_scales_with_prevalence(self):
        lo = _ever_infected(external_foi=True, external_prevalence=0.02, seeds=0)
        hi = _ever_infected(external_foi=True, external_prevalence=0.2, seeds=0)
        self.assertGreaterEqual(hi, lo)
        self.assertGreater(hi, 0)

    def test_households_get_no_external_term(self):
        # Everyone stays home (a household, no f_j) with the term on -> ext_ratio
        # is 0 for households, so no external infection.
        self.assertEqual(
            _ever_infected(external_foi=True, external_prevalence=0.2, seeds=0,
                           at_facility=False),
            0,
        )

    def test_amplifies_an_existing_seed(self):
        off = _ever_infected(external_foi=False, seeds=2)
        on = _ever_infected(external_foi=True, external_prevalence=0.2, seeds=2)
        self.assertGreaterEqual(on, off)


class ExternalFoiPlumbingTest(unittest.TestCase):
    def test_parse_facility_catchment_fj(self):
        self.assertEqual(
            parse_facility("a", {"cbg": "c", "catchment_fj": 0.25}).catchment_fj, 0.25
        )
        # out-of-range / unparseable -> None (no term applied)
        self.assertIsNone(parse_facility("b", {"cbg": "c", "catchment_fj": 0}).catchment_fj)
        self.assertIsNone(parse_facility("c", {"cbg": "c", "catchment_fj": 1.5}).catchment_fj)
        self.assertIsNone(parse_facility("d", {"cbg": "c", "catchment_fj": "x"}).catchment_fj)
        self.assertIsNone(parse_facility("e", {"cbg": "c"}).catchment_fj)

    def test_normalize_simdata_defaults_and_overrides(self):
        d = normalize_simdata({"czone_id": 1, "length": 1,
                               "interventions": [{"time": 0}]})
        self.assertEqual(d["external_foi"], INFECTION_MODEL["external_foi"])
        self.assertEqual(d["external_prevalence"], INFECTION_MODEL["external_prevalence"])
        self.assertEqual(d["external_emit_factor"], INFECTION_MODEL["external_emit_factor"])
        d2 = normalize_simdata({"czone_id": 1, "length": 1, "interventions": [{"time": 0}],
                                "external_foi": True, "external_prevalence": 0.01,
                                "external_emit_factor": 0.5})
        self.assertTrue(d2["external_foi"])
        self.assertEqual(d2["external_prevalence"], 0.01)
        self.assertEqual(d2["external_emit_factor"], 0.5)

    def test_default_config_is_off_and_inert(self):
        self.assertFalse(INFECTION_MODEL["external_foi"])
        self.assertEqual(INFECTION_MODEL["external_prevalence"], 0.0)


if __name__ == "__main__":
    unittest.main()
