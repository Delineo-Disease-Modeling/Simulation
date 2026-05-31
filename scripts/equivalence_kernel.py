#!/usr/bin/env python3
"""Kernel-level equivalence + speed check for the aggregate Wells-Riley path.

Drives the *real* runner event handlers — process_infection_event (pairwise,
O(infectors x susceptibles)) and _aggregate_transmission_event (O(infectors +
susceptibles)) — on synthetic single-room populations, many Monte Carlo trials,
and checks two things:

  1. EQUIVALENCE: each model's empirical per-susceptible infection frequency
     matches the analytic Wells-Riley probability P = 1 - exp(-base * W * u_j)
     AND matches the other model, within a binomial confidence band. This is the
     direct test that the aggregate kernel preserves the marginal infection
     probability of the pairwise kernel.

  2. SPEED: on a crowded room, times both kernels to show the O(n) vs O(n^2)
     gap the reformulation buys.

Run:  scripts/equivalence_kernel.py [--trials N]
Exits non-zero if any per-config deviation exceeds the band.
"""
from __future__ import annotations

import argparse
import math
import os
import random
import statistics
import sys
import time

# Allow running from anywhere: put the Simulation root (parent of scripts/) on path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from simulator.pap import (
    Facility,
    Household,
    InfectionState,
    Person,
    VaccinationState,
)
from simulator.infectionmgr import InfectionManager
from simulator.runner import SimulationRunner, SimulationContext
from simulator.snapshots import SimulationSnapshotWriter
from simulator.event_queue import EventQueue
from simulator.world import DiseaseSimulator
from simulator.infection_models.v6_wells_riley import get_vaccination_protection

_INFECTIOUS = InfectionState.INFECTED | InfectionState.INFECTIOUS
_NO_IV = [{"time": 0, "mask": 0.0, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}]


def _make_person(pid: str, masked: bool, vax: VaccinationState, household: Household) -> Person:
    p = Person(pid, 0, 30, household)
    p.masked = masked
    if vax != VaccinationState.NONE:
        p.set_vaccinated(vax)
    return p


def _infector_weight(masked: bool, vax: VaccinationState) -> float:
    """Per-infector emission weight w_i used by the aggregate kernel / analytic."""
    mask_factor = 0.30 if masked else 1.0
    if vax != VaccinationState.NONE:
        # get_vaccination_protection needs the attrs set_vaccinated populates.
        tmp = Person("_", 0, 30, Household("c", "_"))
        tmp.set_vaccinated(vax)
        vax_factor = 1.0 - get_vaccination_protection(tmp, "transmission")
    else:
        vax_factor = 1.0
    return mask_factor * vax_factor


def _suscept_intake(masked: bool, vax: VaccinationState) -> float:
    """Per-susceptible intake weight u_j used by the aggregate kernel / analytic."""
    mask_factor = 0.50 if masked else 1.0
    if vax != VaccinationState.NONE:
        tmp = Person("_", 0, 30, Household("c", "_"))
        tmp.set_vaccinated(vax)
        protection = get_vaccination_protection(tmp, "infection")
    else:
        protection = 0.0
    return mask_factor * (1.0 - protection)


def analytic_prob(infectors, suscept, is_household: bool, exposure_min: int) -> float:
    ventilation = 3000.0 if is_household else 150.0
    base = (20.0 * 0.5 * (exposure_min / 60.0)) / ventilation
    w_sum = sum(_infector_weight(m, v) for (m, v) in infectors)
    u = _suscept_intake(*suscept)
    return 1.0 - math.exp(-(base * w_sum * u))


def run_trials(aggregate: bool, infectors, suscept_types, n_per_type, is_household,
               exposure_min, n_trials, seed):
    """Return (per-type infection counts, totals-per-trial list).

    Each trial rebuilds a fresh room so no state leaks between trials. Counts
    are pooled over the n_per_type identical susceptibles of each type.
    """
    runner = SimulationRunner(
        {"length": exposure_min, "interventions": _NO_IV, "czone_id": 1,
         "dmp_mode": "off", "aggregate_transmission": aggregate},
        enable_logging=False,
    )
    is_hh = is_household
    poi_id = "room"
    type_hits = [0] * len(suscept_types)
    totals = []

    random.seed(seed)
    for _ in range(n_trials):
        sim = DiseaseSimulator(timestep=exposure_min, intervention_weights=[dict(_NO_IV[0])],
                               enable_logging=False)
        place = Household("cbg", poi_id) if is_hh else Facility(poi_id, "cbg", "Room", -1)
        if is_hh:
            sim.add_household(place)
        else:
            sim.add_facility(place)
        hh = Household("home-cbg", "home")  # nominal home for everyone

        # Infectors (infectious for Delta; never susceptible targets).
        infector_ids = []
        for i, (m, v) in enumerate(infectors):
            p = _make_person(f"inf{i}", m, v, hh)
            p.states["Delta"] = _INFECTIOUS
            sim.add_person(p)
            place.add_member(p)
            infector_ids.append(p.id)

        # Susceptibles, n_per_type of each type, tagged so we can pool by type.
        suscept_ids = []  # (type_index, pid)
        k = 0
        for ti, (m, v) in enumerate(suscept_types):
            for _r in range(n_per_type):
                p = _make_person(f"sus{k}", m, v, hh)
                p.states["Delta"] = InfectionState.SUSCEPTIBLE
                sim.add_person(p)
                place.add_member(p)
                suscept_ids.append((ti, p.id))
                k += 1

        eq = EventQueue(iter(()))
        mgr = InfectionManager(infected_ids=infector_ids, disease_name="COVID-19", dmp_mode="off")
        ctx = SimulationContext(
            simulator=sim, event_queue=eq, infection_manager=mgr,
            snapshot_writer=SimulationSnapshotWriter(None), variants=["Delta"],
            variant_infected={"Delta": {}}, people_with_timelines=set(),
            max_length=exposure_min,
        )

        runner.process_infection_event(ctx, exposure_min, poi_id, is_hh)

        infected = ctx.variant_infected["Delta"]
        trial_total = 0
        for ti, pid in suscept_ids:
            if pid in infected:
                type_hits[ti] += 1
                trial_total += 1
        totals.append(trial_total)

    return type_hits, totals


SCENARIOS = [
    {
        "name": "facility, 1h, 5 plain infectors",
        "is_household": False, "exposure_min": 60,
        "infectors": [(False, VaccinationState.NONE)] * 5,
        "suscept_types": [
            (False, VaccinationState.NONE),
            (True, VaccinationState.NONE),
            (False, VaccinationState.IMMUNIZED),
            (True, VaccinationState.IMMUNIZED),
        ],
    },
    {
        "name": "facility, 2h, mixed masked/vaxed infectors",
        "is_household": False, "exposure_min": 120,
        "infectors": [
            (False, VaccinationState.NONE),
            (True, VaccinationState.NONE),
            (False, VaccinationState.IMMUNIZED),
            (True, VaccinationState.PARTIAL),
            (False, VaccinationState.NONE),
            (False, VaccinationState.NONE),
        ],
        "suscept_types": [
            (False, VaccinationState.NONE),
            (True, VaccinationState.NONE),
            (False, VaccinationState.PARTIAL),
            (True, VaccinationState.IMMUNIZED),
        ],
    },
    {
        "name": "household, 8h, 3 plain infectors (low-P regime)",
        "is_household": True, "exposure_min": 480,
        "infectors": [(False, VaccinationState.NONE)] * 3,
        "suscept_types": [
            (False, VaccinationState.NONE),
            (True, VaccinationState.IMMUNIZED),
        ],
    },
]


def _build_room(n_infectors, n_suscept, is_household, exposure_min, infector_spec, suscept_spec):
    sim = DiseaseSimulator(timestep=exposure_min, intervention_weights=[dict(_NO_IV[0])],
                           enable_logging=False)
    place = Household("cbg", "room") if is_household else Facility("room", "cbg", "Room", -1)
    (sim.add_household if is_household else sim.add_facility)(place)
    hh = Household("home-cbg", "home")
    infector_ids = []
    for i in range(n_infectors):
        p = _make_person(f"inf{i}", *infector_spec, hh)
        p.states["Delta"] = _INFECTIOUS
        sim.add_person(p); place.add_member(p); infector_ids.append(p.id)
    for j in range(n_suscept):
        p = _make_person(f"sus{j}", *suscept_spec, hh)
        p.states["Delta"] = InfectionState.SUSCEPTIBLE
        sim.add_person(p); place.add_member(p)
    eq = EventQueue(iter(()))
    mgr = InfectionManager(infected_ids=infector_ids, disease_name="COVID-19", dmp_mode="off")
    ctx = SimulationContext(
        simulator=sim, event_queue=eq, infection_manager=mgr,
        snapshot_writer=SimulationSnapshotWriter(None), variants=["Delta"],
        variant_infected={"Delta": {}}, people_with_timelines=set(), max_length=exposure_min,
    )
    return ctx


def perf_demo(reps=60):
    """Time both kernels on a crowded room. Susceptibles are masked+immunized
    (low per-contact probability) so few infections are *scheduled* — this
    isolates the O(infectors x susceptibles) vs O(infectors + susceptibles)
    contact-evaluation cost rather than the (equal) infection-scheduling cost."""
    n_inf, n_sus = 60, 740
    inf_spec = (False, VaccinationState.NONE)
    sus_spec = (True, VaccinationState.IMMUNIZED)
    print(f"## speed: 1 facility event, {n_inf} infectious + {n_sus} susceptible, {reps} reps")
    print(f"   pairwise does {n_inf * n_sus:,} contact evals/event; "
          f"aggregate does {n_inf + n_sus:,}")
    timings = {}
    for label, agg in (("pairwise", False), ("aggregate", True)):
        runner = SimulationRunner(
            {"length": 60, "interventions": _NO_IV, "czone_id": 1,
             "dmp_mode": "off", "aggregate_transmission": agg}, enable_logging=False)
        random.seed(7)
        total = 0.0
        for _ in range(reps):
            ctx = _build_room(n_inf, n_sus, False, 60, inf_spec, sus_spec)  # untimed
            t0 = time.perf_counter()
            runner.process_infection_event(ctx, 60, "room", False)
            total += time.perf_counter() - t0
        timings[label] = total / reps
    speedup = timings["pairwise"] / timings["aggregate"] if timings["aggregate"] else float("inf")
    print(f"   pairwise:  {timings['pairwise']*1000:7.3f} ms/event")
    print(f"   aggregate: {timings['aggregate']*1000:7.3f} ms/event")
    print(f"   speedup:   {speedup:.1f}x\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=6000)
    ap.add_argument("--per-type", type=int, default=3)
    ap.add_argument("--sigma", type=float, default=4.0, help="allowed deviation in std errors")
    args = ap.parse_args()

    print(f"Kernel equivalence: {args.trials} trials x {args.per_type}/type, "
          f"tolerance {args.sigma} sigma\n")
    worst = 0.0
    failures = 0

    for sc in SCENARIOS:
        n = args.trials * args.per_type
        hits_pair, tot_pair = run_trials(False, sc["infectors"], sc["suscept_types"],
                                         args.per_type, sc["is_household"],
                                         sc["exposure_min"], args.trials, seed=12345)
        hits_agg, tot_agg = run_trials(True, sc["infectors"], sc["suscept_types"],
                                       args.per_type, sc["is_household"],
                                       sc["exposure_min"], args.trials, seed=67890)

        print(f"## {sc['name']}")
        print(f"   {'susceptible':<22} {'analytic':>9} {'pairwise':>9} {'aggregate':>9} "
              f"{'|p-a|/se':>9}")
        for ti, st in enumerate(sc["suscept_types"]):
            p_analytic = analytic_prob(sc["infectors"], st, sc["is_household"], sc["exposure_min"])
            p_pair = hits_pair[ti] / n
            p_agg = hits_agg[ti] / n
            # combined SE of the two empirical estimates
            se = math.sqrt(max(p_pair * (1 - p_pair), 1e-9) / n
                           + max(p_agg * (1 - p_agg), 1e-9) / n)
            dev = abs(p_pair - p_agg) / se if se > 0 else 0.0
            worst = max(worst, dev)
            tag = "masked" if st[0] else "plain"
            vtag = st[1].name.lower()
            flag = "  <-- FAIL" if dev > args.sigma else ""
            if dev > args.sigma:
                failures += 1
            print(f"   {tag+'/'+vtag:<22} {p_analytic:>9.4f} {p_pair:>9.4f} {p_agg:>9.4f} "
                  f"{dev:>9.2f}{flag}")
        mp, ma = statistics.mean(tot_pair), statistics.mean(tot_agg)
        print(f"   mean infected/trial: pairwise={mp:.3f}  aggregate={ma:.3f}  "
              f"(diff {abs(mp-ma):.3f})\n")

    print(f"Worst per-config deviation: {worst:.2f} sigma  "
          f"({'PASS' if failures == 0 else f'FAIL ({failures} configs)'})\n")

    perf_demo()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
