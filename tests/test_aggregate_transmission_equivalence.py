"""Regression guard for the aggregate (O(n)) Wells-Riley transmission kernel.

The aggregate kernel must (a) stay OFF by default so the pairwise golden is
untouched, and (b) reproduce the pairwise kernel's marginal per-susceptible
infection probability. (b) is checked by driving the real runner event handlers
on a synthetic room over many seeded Monte Carlo trials and comparing each
model's empirical infection frequency to the analytic Wells-Riley probability
and to each other. Trials are seeded, so the assertions are deterministic.
"""
import math
import os
import random
import unittest

from simulator.event_queue import EventQueue
from simulator.infectionmgr import InfectionManager
from simulator.pap import Facility, Household, InfectionState, Person, VaccinationState
from simulator.runner import SimulationContext, SimulationRunner, normalize_simdata
from simulator.snapshots import SimulationSnapshotWriter
from simulator.world import DiseaseSimulator
from simulator.infection_models.v6_wells_riley import get_vaccination_protection

_INFECTIOUS = InfectionState.INFECTED | InfectionState.INFECTIOUS
_NO_IV = [{"time": 0, "mask": 0.0, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}]


def _person(pid, masked, vax, home):
    p = Person(pid, 0, 30, home)
    p.masked = masked
    if vax != VaccinationState.NONE:
        p.set_vaccinated(vax)
    return p


def _infector_weight(masked, vax):
    f = 0.30 if masked else 1.0
    if vax != VaccinationState.NONE:
        t = Person("_", 0, 30, Household("c", "_")); t.set_vaccinated(vax)
        f *= 1.0 - get_vaccination_protection(t, "transmission")
    return f


def _intake(masked, vax):
    f = 0.50 if masked else 1.0
    if vax != VaccinationState.NONE:
        t = Person("_", 0, 30, Household("c", "_")); t.set_vaccinated(vax)
        f *= 1.0 - get_vaccination_protection(t, "infection")
    return f


def _analytic(infectors, suscept, exposure_min):
    base = (20.0 * 0.5 * (exposure_min / 60.0)) / 150.0  # facility ventilation
    w = sum(_infector_weight(m, v) for (m, v) in infectors)
    return 1.0 - math.exp(-(base * w * _intake(*suscept)))


def _run_trials(aggregate, infectors, suscept_types, exposure_min, n_trials, seed):
    runner = SimulationRunner(
        {"length": exposure_min, "interventions": _NO_IV, "czone_id": 1,
         "dmp_mode": "off", "aggregate_transmission": aggregate}, enable_logging=False)
    hits = [0] * len(suscept_types)
    random.seed(seed)
    for _ in range(n_trials):
        sim = DiseaseSimulator(timestep=exposure_min, intervention_weights=[dict(_NO_IV[0])],
                               enable_logging=False)
        place = Facility("room", "cbg", "Room", -1)
        sim.add_facility(place)
        home = Household("home-cbg", "home")
        inf_ids = []
        for i, (m, v) in enumerate(infectors):
            p = _person(f"inf{i}", m, v, home); p.states["Delta"] = _INFECTIOUS
            sim.add_person(p); place.add_member(p); inf_ids.append(p.id)
        sus_ids = []
        for ti, (m, v) in enumerate(suscept_types):
            p = _person(f"sus{ti}", m, v, home); p.states["Delta"] = InfectionState.SUSCEPTIBLE
            sim.add_person(p); place.add_member(p); sus_ids.append((ti, p.id))
        mgr = InfectionManager(infected_ids=inf_ids, disease_name="COVID-19", dmp_mode="off")
        ctx = SimulationContext(
            simulator=sim, event_queue=EventQueue(iter(())), infection_manager=mgr,
            snapshot_writer=SimulationSnapshotWriter(None), variants=["Delta"],
            variant_infected={"Delta": {}}, people_with_timelines=set(), max_length=exposure_min)
        runner.process_infection_event(ctx, exposure_min, "room", False)
        infected = ctx.variant_infected["Delta"]
        for ti, pid in sus_ids:
            if pid in infected:
                hits[ti] += 1
    return hits


class TestAggregateTransmissionEquivalence(unittest.TestCase):
    def test_enabled_by_default(self):
        # Default ON (config DELINEO_AGG_TRANSMISSION defaults to "1").
        if os.environ.get("DELINEO_AGG_TRANSMISSION", "1").lower() not in {"1", "true", "yes", "on"}:
            self.skipTest("DELINEO_AGG_TRANSMISSION disabled in this environment")
        base = {"length": 60, "interventions": _NO_IV, "czone_id": 1}
        self.assertTrue(normalize_simdata(base)["aggregate_transmission"])
        self.assertTrue(SimulationRunner(base, enable_logging=False).aggregate_transmission)

    def test_simdata_field_can_disable(self):
        # The per-run field overrides the default, so the pairwise kernel stays reachable.
        base = {"length": 60, "interventions": _NO_IV, "czone_id": 1,
                "aggregate_transmission": False}
        self.assertFalse(SimulationRunner(base, enable_logging=False).aggregate_transmission)

    def test_simdata_field_can_enable(self):
        base = {"length": 60, "interventions": _NO_IV, "czone_id": 1,
                "aggregate_transmission": True}
        self.assertTrue(SimulationRunner(base, enable_logging=False).aggregate_transmission)

    def test_marginal_probabilities_match(self):
        infectors = [
            (False, VaccinationState.NONE), (True, VaccinationState.NONE),
            (False, VaccinationState.IMMUNIZED), (False, VaccinationState.NONE),
            (False, VaccinationState.NONE),
        ]
        suscept_types = [
            (False, VaccinationState.NONE), (True, VaccinationState.NONE),
            (False, VaccinationState.IMMUNIZED), (True, VaccinationState.IMMUNIZED),
        ]
        exposure_min, n = 60, 3000
        pair = _run_trials(False, infectors, suscept_types, exposure_min, n, seed=2024)
        agg = _run_trials(True, infectors, suscept_types, exposure_min, n, seed=4048)

        for ti, st in enumerate(suscept_types):
            p_analytic = _analytic(infectors, st, exposure_min)
            p_pair, p_agg = pair[ti] / n, agg[ti] / n
            se = math.sqrt(max(p_pair * (1 - p_pair), 1e-9) / n
                           + max(p_agg * (1 - p_agg), 1e-9) / n)
            # aggregate vs pairwise
            self.assertLess(abs(p_pair - p_agg), 5 * se,
                            f"{st}: pairwise={p_pair:.4f} aggregate={p_agg:.4f}")
            # both vs analytic Wells-Riley
            se1 = math.sqrt(max(p_agg * (1 - p_agg), 1e-9) / n)
            self.assertLess(abs(p_agg - p_analytic), 5 * se1,
                            f"{st}: aggregate={p_agg:.4f} analytic={p_analytic:.4f}")


if __name__ == "__main__":
    unittest.main()
