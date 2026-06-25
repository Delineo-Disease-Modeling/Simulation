"""Phase 0 regression guards for the disease natural-history fixes.

These pin the two confirmed live-path defects found in the pre-validation audit
so the Phase 1/2 fixes can be verified red -> green:

  Blocker 1 (SIR -> SIS): every state in a DMP/fallback timeline shares one
  ``end_ts`` and ``update_state`` clears all flags once ``time > end_ts``, so a
  recovered/dead agent reverts to SUSCEPTIBLE and is reinfected. The eligible
  mask in ``_vectorized_transmission`` has no ever-infected guard either.

  Blocker 2 (over-emission): the INFECTIOUS window runs to the terminal time
  (not the onset of the next state), so an infector keeps emitting through
  hospitalization/recovery; the emitter mask never excludes INVISIBLE.

Tests in ``TimelineWindowTest`` target the Phase 1 timeline-builder fix
(sequential windows + absorbing terminal). ``KernelGuardTest`` targets the
Phase 2 kernel guards (emitter INVISIBLE exclusion + eligible infected_mask
guard). ``KernelNumericTest`` is a stable pin on the Wells-Riley probability the
prod kernel produces, so neither fix silently changes the transmission math.

Expected before the fixes: TimelineWindowTest + KernelGuardTest FAIL,
KernelNumericTest PASSES. After the fixes: all pass.
"""
import math
import unittest

import numpy as np

from simulator.infectionmgr import InfectionManager
from simulator.interventions import apply_person_interventions
from simulator.pap import Household, InfectionState, Person, VaccinationState
from simulator.runner import LoadedSimulationData, SimulationRunner


def _person(pid="p1", age=30, sex=0):
    household = Household(cbg="cbg-home", id="h1")
    return Person(id=pid, sex=sex, age=age, household=household)


# --- Phase 1 target: timeline window semantics -----------------------------

class TimelineWindowTest(unittest.TestCase):
    """A DMP/fallback timeline must give each state a window that ends when the
    next state begins, with an ABSORBING terminal state — not one shared end_ts
    after which everyone reverts to susceptible."""

    DISEASE = "Delta"

    def _timeline_person(self, csv_timeline):
        person = _person()
        person.timeline = InfectionManager._build_timeline_from_csv_result(
            csv_timeline, self.DISEASE, 0
        )
        person._next_transition_time = 0  # force a recompute
        return person

    def test_recovered_is_absorbing(self):
        # infected(0h) -> infectious(48h) -> recovered(240h). Long after the
        # last timeline event the agent must STILL be recovered (immune), not
        # back to susceptible (which is the SIR -> SIS collapse).
        person = self._timeline_person(
            [("Infected", 0), ("Infectious_Symptomatic", 48), ("Recovered", 240)]
        )
        person.update_state(240 * 60 + 100_000, [self.DISEASE])
        self.assertNotEqual(
            person.states[self.DISEASE],
            InfectionState.SUSCEPTIBLE,
            "recovered agent reverted to susceptible (SIR collapsed to SIS)",
        )
        self.assertIn(InfectionState.RECOVERED, person.states[self.DISEASE])

    def test_dead_agent_stays_removed(self):
        # A fatal course must be absorbing too — the dead must not reanimate as
        # susceptible and get reinfected.
        person = self._timeline_person(
            [("Infected", 0), ("Infectious_Symptomatic", 48),
             ("Hospitalized", 120), ("Deceased", 360)]
        )
        person.update_state(360 * 60 + 100_000, [self.DISEASE])
        self.assertIn(InfectionState.REMOVED, person.states[self.DISEASE])
        self.assertNotEqual(person.states[self.DISEASE], InfectionState.SUSCEPTIBLE)

    def test_infectious_window_ends_at_next_state(self):
        # While HOSPITALIZED (between hosp onset and recovery) the agent must NOT
        # still carry the INFECTIOUS flag — the infectious window should end when
        # hospitalization begins, not stretch to the terminal time.
        person = self._timeline_person(
            [("Infected", 0), ("Infectious_Symptomatic", 48),
             ("Hospitalized", 120), ("Recovered", 240)]
        )
        person.update_state(150 * 60, [self.DISEASE])  # 30h into hospitalization
        self.assertIn(InfectionState.HOSPITALIZED, person.states[self.DISEASE])
        self.assertNotIn(
            InfectionState.INFECTIOUS,
            person.states[self.DISEASE],
            "infectious flag persisted into hospitalization (over-emission)",
        )

    def test_fallback_recovered_is_absorbing(self):
        # The dmp_mode='off' fallback timeline has the same defect: RECOVERED is
        # a finite [infected_duration, recovery_duration] window, after which the
        # agent reverts to susceptible. It must be absorbing.
        person = _person()
        person.timeline = InfectionManager._fallback_timeline(self.DISEASE, 0)
        person._next_transition_time = 0
        person.update_state(1_000_000, [self.DISEASE])  # far past recovery_duration
        self.assertNotEqual(
            person.states[self.DISEASE],
            InfectionState.SUSCEPTIBLE,
            "fallback recovered agent reverted to susceptible",
        )

    def test_non_monotonic_timeline_raises(self):
        # A mapped state that re-enters after an intervening different state
        # cannot be represented (one window per state). Stretching it across the
        # intervening window would recreate the over-emission bug, so the builder
        # must fail loudly rather than silently drop or merge.
        with self.assertRaises(ValueError):
            InfectionManager._build_sequential_timeline([
                (InfectionState.INFECTIOUS, 120),
                (InfectionState.HOSPITALIZED, 300),
                (InfectionState.INFECTIOUS, 400),
                (InfectionState.RECOVERED, 600),
            ])

    def test_symptomatic_infection_sets_infectious_and_symptomatic(self):
        # Infectious_Symptomatic must set BOTH bits so the SYMPTOMATIC compartment,
        # self-isolation, and case-ascertainment are real (not collapsed to INFECTIOUS).
        person = self._timeline_person(
            [("Infected", 0), ("Infectious_Symptomatic", 48), ("Recovered", 240)]
        )
        person.update_state(100 * 60, [self.DISEASE])  # mid symptomatic-infectious window
        self.assertIn(InfectionState.INFECTIOUS, person.states[self.DISEASE])
        self.assertIn(
            InfectionState.SYMPTOMATIC,
            person.states[self.DISEASE],
            "Infectious_Symptomatic did not set the SYMPTOMATIC bit",
        )

    def test_asymptomatic_infection_is_infectious_not_symptomatic(self):
        person = self._timeline_person(
            [("Infected", 0), ("Infectious_Asymptomatic", 48), ("Recovered", 240)]
        )
        person.update_state(100 * 60, [self.DISEASE])
        self.assertIn(InfectionState.INFECTIOUS, person.states[self.DISEASE])
        self.assertNotIn(InfectionState.SYMPTOMATIC, person.states[self.DISEASE])


# --- Phase 2 target: vectorized-kernel guards ------------------------------

def _home_loaded(n):
    # Everyone shares one home so they co-locate in a single room. Home id is
    # numeric (engine sorts homes by int(id)); person ids are 0..n-1.
    pids = [str(i) for i in range(n)]
    return LoadedSimulationData(
        people_data={p: {"sex": int(p) % 2, "age": 30, "home": "1"} for p in pids},
        homes_data={"1": {"cbg": "cbg-home"}},
        places_data={},
        patterns_data={
            "60": {"homes": {"1": pids}, "places": {}},
            "120": {"homes": {"1": pids}, "places": {}},
        },
    )


def _kernel_simdata():
    return {
        "czone_id": 1, "length": 120, "randseed": False,
        "initial_infected_count": 0, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


def _kernel_setup(n):
    """Build a real engine context, then return (runner, context, store) with
    everyone co-located in room 0 so the kernel can be driven directly."""
    runner = SimulationRunner(_kernel_simdata(), enable_logging=False)
    runner._seed_random()
    context = runner.build_context(_home_loaded(n))
    assert runner._soa_engine, "single-variant no-intervention run should use the engine"
    store = context.simulator.membership
    store.person_loc[:] = 0          # all in the single home location
    store.pstate[:] = 0
    return runner, context, store


class KernelGuardTest(unittest.TestCase):
    """The live vectorized kernel must not let a removed (hospitalized/recovered/
    dead) agent emit, and must not reinfect an ever-infected agent."""

    INFECTIOUS = int(InfectionState.INFECTIOUS.value)
    HOSPITALIZED = int(InfectionState.HOSPITALIZED.value)
    RECOVERED = int(InfectionState.RECOVERED.value)

    def test_hospitalized_does_not_emit(self):
        runner, context, store = _kernel_setup(2)
        # person 0 is infectious AND hospitalized (removed from circulation);
        # person 1 is susceptible in the same room. A hospitalized case must not
        # contribute force-of-infection.
        store.pstate[0] = self.INFECTIOUS | self.HOSPITALIZED
        store.pstate[1] = 0
        store.base_quanta[:] = 100.0  # P ~ 1 if any emission reaches a susceptible
        np.random.seed(0)
        runner._vectorized_transmission(context, 60)
        self.assertNotIn(
            store.idx_to_pid[1],
            context.infection_manager.infected,
            "a hospitalized (removed) agent infected a susceptible",
        )

    def test_recovered_agent_not_reinfected(self):
        runner, context, store = _kernel_setup(2)
        # person 0 is a live infector; person 1 currently looks susceptible
        # (pstate==0) but is ever-infected (recovered). It must not be reinfected.
        store.pstate[0] = self.INFECTIOUS
        store.pstate[1] = 0
        store.infected_mask[1] = True
        store.snap_state[1] = self.RECOVERED
        store.base_quanta[:] = 100.0
        np.random.seed(0)
        runner._vectorized_transmission(context, 60)
        self.assertEqual(
            int(store.snap_state[1]),
            self.RECOVERED,
            "an ever-infected (recovered) agent was reinfected by the kernel",
        )


class KernelNumericTest(unittest.TestCase):
    """Stable pin on the Wells-Riley probability the prod kernel produces, so the
    natural-history fixes don't silently shift the transmission math. Passes
    before and after the fixes."""

    def test_vectorized_kernel_probability(self):
        n_susceptible = 2000
        runner, context, store = _kernel_setup(n_susceptible + 1)
        store.pstate[0] = int(InfectionState.INFECTIOUS.value)  # one infector
        base = 0.5
        store.base_quanta[:] = base  # mean_quanta = base * W(=1) * intake(=1)
        np.random.seed(12345)
        runner._vectorized_transmission(context, 60)
        infected_fraction = len(context.infection_manager.infected) / n_susceptible
        expected = 1.0 - math.exp(-base)  # ~0.3935
        self.assertAlmostEqual(infected_fraction, expected, delta=0.04)


# --- Phase 3: intervention baseline + reproducibility ----------------------

class _StubSim:
    """Minimal stand-in for apply_person_interventions (no logging, no store)."""
    enable_logging = False

    def log_event(self, *args, **kwargs):
        pass


_ZERO_IV = {"mask": 0.0, "vaccine": 0.0, "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}


class InterventionBaselineTest(unittest.TestCase):
    def test_zero_intervention_baseline_is_clean(self):
        # iv_threshold==0.0 is the boundary agent the inclusive '<=' gate masked
        # and vaccinated even in a no-intervention run. A 0.0 policy must touch
        # no one.
        person = _person()
        person.iv_threshold = 0.0
        apply_person_interventions(_StubSim(), person, _ZERO_IV, "60")
        self.assertFalse(person.is_masked(), "0.0 mask policy still masked an agent")
        self.assertEqual(
            person.get_vaccinated(),
            VaccinationState.NONE,
            "0.0 vaccine policy still vaccinated an agent",
        )

    def test_full_intervention_covers_threshold_one_agent(self):
        # 100% must mean everyone, including the iv_threshold==1.0 agent(s) that a
        # strict '<' gate would have missed (large populations have thresholds ==
        # 1.0). The level>0 & '<=' gate keeps 1.0 fully covering.
        person = _person()
        person.iv_threshold = 1.0
        full = {"mask": 1.0, "vaccine": 1.0, "capacity": 1.0,
                "lockdown": 0.0, "selfiso": 0.0}
        apply_person_interventions(_StubSim(), person, full, "60")
        self.assertTrue(person.is_masked(), "100% mask policy missed a threshold==1.0 agent")
        self.assertNotEqual(
            person.get_vaccinated(),
            VaccinationState.NONE,
            "100% vaccine policy missed a threshold==1.0 agent",
        )


def _facility_loaded(n):
    # Everyone goes to one facility every hour so transmission actually spreads
    # (facility Q=150 vs household 3000) and the kernel's numpy draws matter.
    pids = [str(i) for i in range(n)]
    patterns = {
        str(t): {"homes": {}, "places": {"1001": pids}} for t in range(60, 661, 60)
    }
    return LoadedSimulationData(
        people_data={p: {"sex": int(p) % 2, "age": 30, "home": "1"} for p in pids},
        homes_data={"1": {"cbg": "cbg-home"}},
        places_data={"1001": {"cbg": "cbg-f1", "label": "Shop"}},
        patterns_data=patterns,
    )


def _facility_simdata():
    return {
        "czone_id": 1, "length": 660, "randseed": False,
        "initial_infected_count": 2, "disease_name": "COVID-19",
        "variants": ["Delta"], "dmp_mode": "off",
        "interventions": [{"time": 0, "mask": 0.0, "vaccine": 0.0,
                           "capacity": 1.0, "lockdown": 0.0, "selfiso": 0.0}],
    }


def _run_facility():
    runner = SimulationRunner(_facility_simdata(), enable_logging=False)
    runner._seed_random()
    context = runner.build_context(_facility_loaded(60))
    runner.run_queue(context)
    return runner.finalize(context), set(context.infection_manager.infected)


class ReproducibilityTest(unittest.TestCase):
    def test_seed_random_seeds_numpy(self):
        # The live kernel draws from numpy's global RNG; _seed_random must reset
        # it so deterministic mode is actually reproducible.
        runner = SimulationRunner(_facility_simdata(), enable_logging=False)
        runner._seed_random()
        a = np.random.random(8)
        runner._seed_random()
        b = np.random.random(8)
        np.testing.assert_array_equal(a, b)

    def test_engine_run_is_reproducible(self):
        res_a, inf_a = _run_facility()
        res_b, inf_b = _run_facility()
        self.assertGreater(len(inf_a), 2, "no transmission occurred — test is vacuous")
        self.assertEqual(
            inf_a, inf_b,
            "two randseed=False engine runs diverged (RNG not fully seeded)",
        )
        self.assertEqual(
            res_a["result"], res_b["result"],
            "per-timestep infection snapshots diverged between identical runs",
        )


if __name__ == "__main__":
    unittest.main()
