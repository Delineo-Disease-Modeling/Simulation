from __future__ import annotations

import contextlib
import gc
import logging
import math
import os
import random
import time

import numpy as np
from dataclasses import dataclass, field
from typing import Callable, Optional

from .config import DELINEO, DMP_API, INFECTION_MODEL, SIMULATION
from .data_interface import StreamDataLoader
from .location_ids import normalize_location_id
from .disabled_poi import reroute_disabled_poi_visits
from .engine_shadow import ShadowValidationMixin
from .event_queue import EventQueue
from .infection_models.v6_wells_riley import get_vaccination_protection
from .infectionmgr import InfectionManager
from .simdata import _trivial_movement_interventions, normalize_simdata
from .interventions import apply_person_interventions, move_people
from .pap import InfectionState, Person, VaccinationState
from .patterns_codec import BinaryPatterns
from .transmission import TransmissionMixin
from .snapshots import (
    SimulationSnapshotWriter,
    build_infection_snapshot,
    build_movement_snapshot,
)
from .world import (
    DiseaseSimulator,
    build_event_queue,
    build_locations,
    seed_population,
)

logger = logging.getLogger(__name__)

VALID_DMP_MODES = {"auto", "required", "off"}
DETERMINISTIC_RANDOM_SEED = 0


def _perf_timings_enabled() -> bool:
    return os.getenv("DELINEO_PERF_TIMINGS", "").lower() in {"1", "true", "yes", "on"}


def _engine_disabled() -> bool:
    """Whether the vectorized SoA engine is explicitly turned OFF via env.

    The engine is ON BY DEFAULT; ``DELINEO_SOA_ENGINE=0`` (or false/no/off) is
    the kill switch that forces the legacy non-engine path for every run. Enabling
    it is never a force: eligibility (`SimulationRunner._engine_eligibility`) still
    decides whether the engine can run a given config correctly, falling back to
    the non-engine path otherwise. (Any other value, including unset or ``1``,
    leaves the default-on behavior in place.)"""
    return os.getenv("DELINEO_SOA_ENGINE", "").lower() in {"0", "false", "no", "off"}


def _log_perf_timing(label: str, started_at: float) -> None:
    if _perf_timings_enabled():
        # Emit via print so the line is visible even when the simulator logger
        # is silenced at runtime (e.g. by the benchmark harness raising
        # simulator.runner to WARNING to suppress infection-event INFO logs).
        print(f"[perf] {label}: {time.perf_counter() - started_at:.3f}s", flush=True)


@dataclass(frozen=True)
class LoadedSimulationData:
    people_data: dict
    homes_data: dict
    places_data: dict
    patterns_data: dict


@dataclass
class SimulationContext:
    simulator: DiseaseSimulator
    event_queue: EventQueue
    infection_manager: InfectionManager
    snapshot_writer: SimulationSnapshotWriter
    variants: list[str]
    variant_infected: dict[str, dict[str, int]]
    # Holds Person object refs (not pid strings). Populated by seed_population
    # and infection_manager.schedule_infection; iterated in update_people_states.
    people_with_timelines: set
    max_length: int
    processed_count: int = 0
    last_movement_ts: int = 0
    last_interventions: Optional[dict] = None
    initial_infected_ids: list[str] = field(default_factory=list)
    # SoA engine mode: the current-timestep OccupancyView, rebuilt after each
    # vectorized movement and read by the snapshot + transmission kernel.
    occupancy: object = None
    # SoA engine mode: person indices whose state value changed in this step's
    # update_people_states. update_variant_tracking consumes it to update only
    # the changed entries instead of rewriting the whole infected map each step.
    states_changed_idx: list = field(default_factory=list)


class SimulationRunner(TransmissionMixin, ShadowValidationMixin):
    def __init__(
        self,
        simdata: dict,
        enable_logging: bool = True,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        data_loader: Callable = StreamDataLoader.load_bulk,
    ) -> None:
        self.simdata = normalize_simdata(simdata)
        self.enable_logging = enable_logging
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self.data_loader = data_loader
        self.aggregate_transmission = self.simdata["aggregate_transmission"]
        # Area-aware Wells-Riley ventilation (default off → fixed Q, golden
        # preserved). When on, facility Q scales with physical floor area.
        self.area_aware_ventilation = self.simdata["area_aware_ventilation"]
        self.ventilation_coeff = float(INFECTION_MODEL.get("ventilation_coeff", 9.0))
        self.area_clamp = (
            float(INFECTION_MODEL.get("area_clamp_min", 65.0)),
            float(INFECTION_MODEL.get("area_clamp_max", 70000.0)),
        )
        # External force-of-infection term (default off → golden preserved). When
        # on, each facility gets a one-way background quanta source from its
        # external (out-of-cluster) visitors; see _external_emission_per_loc and
        # _vectorized_transmission. external_prevalence (P_ext) defaults to 0, so
        # the term is inert until calibrated even when the flag is on.
        self.external_foi = self.simdata["external_foi"]
        self.external_prevalence = float(self.simdata["external_prevalence"])
        self.external_emit_factor = float(self.simdata["external_emit_factor"])
        self._perf_accum: dict[str, float] = {}
        self._soa_engine: bool = False
        self._soa_shadow: bool = False

    @contextlib.contextmanager
    def _timed(self, label: str):
        if not _perf_timings_enabled():
            yield
            return
        started = time.perf_counter()
        try:
            yield
        finally:
            self._perf_accum[label] = (
                self._perf_accum.get(label, 0.0) + (time.perf_counter() - started)
            )

    def run(self) -> dict:
        logger.info("QUEUE-BASED SIMULATION START (max_length=%s)", self.simdata["length"])
        self._seed_random()
        total_start = time.perf_counter()

        # The load+build phase allocates millions of long-lived objects (the
        # patterns person-index, ~50k Person objects, the event queue). CPython's
        # cyclic GC repeatedly rescans that growing set mid-build, which dominates
        # setup — ~13x on the patterns parse (50s->4s) and ~2x on ingest_patterns
        # (52s->24s). None of it is collectable during the build, so suspend GC
        # for the whole setup and re-enable it for the run loop (which produces
        # transient per-timestep garbage that should still be reclaimed).
        # DELINEO_GC_TUNE=0 disables this (baseline behavior) for ablation.
        gc_tune = os.environ.get("DELINEO_GC_TUNE", "1") != "0"
        gc_was_enabled = gc.isenabled()
        if gc_tune:
            gc.disable()
        try:
            try:
                stage_start = time.perf_counter()
                loaded = self.load_data()
                _log_perf_timing("load_data", stage_start)

                stage_start = time.perf_counter()
                context = self.build_context(loaded)
                _log_perf_timing("build_context", stage_start)
            except Exception as exc:
                logger.exception("Failed to load/build simulation context")
                return {"error": str(exc)}
            finally:
                if gc_was_enabled:
                    gc.enable()

            stage_start = time.perf_counter()
            self.run_queue(context)
            _log_perf_timing("run_queue", stage_start)
            stage_start = time.perf_counter()
            result = self.finalize(context)
            _log_perf_timing("finalize", stage_start)
            _log_perf_timing("simulation total", total_start)
            return result
        except Exception as exc:
            logger.exception("Simulation runtime failed")
            return {"error": str(exc)}
        finally:
            if gc_was_enabled and not gc.isenabled():
                gc.enable()

    def _progress(self, current_step, max_steps, message=None) -> None:
        if self.progress_callback:
            self.progress_callback(current_step, max_steps, message)

    def _seed_random(self) -> None:
        if not self.simdata["randseed"]:
            random.seed(DETERMINISTIC_RANDOM_SEED)
            # The live vectorized kernel (np.random.random) and all DMP
            # progression sampling (np.random.*) draw from numpy's global RNG,
            # so seeding only Python's random left deterministic runs
            # irreproducible on the engine path. Seed both.
            np.random.seed(DETERMINISTIC_RANDOM_SEED)

    def load_data(self) -> LoadedSimulationData:
        self._progress(0, 1, "Loading population data from server...")
        url = (
            f"{DELINEO['DB_URL']}patterns/{self.simdata['czone_id']}"
            f"?length={self.simdata['length']}"
        )

        logger.info("Fetching bulk data...")
        papdata, patterns_data = self.data_loader(url, timeout=360)
        people_data = papdata.get("people", {})
        homes_data = papdata.get("homes", {})
        places_data = papdata.get("places", {})
        logger.info(
            "Loaded: %d people, %d homes, %d places",
            len(people_data),
            len(homes_data),
            len(places_data),
        )
        disabled_poi_ids = self.simdata["disabled_poi_ids"]
        if disabled_poi_ids:
            logger.info(
                "Rerouting visits away from %d disabled POIs",
                len(disabled_poi_ids),
            )
            with self._timed("load_data/reroute_disabled_pois"):
                patterns_data = reroute_disabled_poi_visits(
                    patterns_data,
                    people_data,
                    disabled_poi_ids,
                )
        return LoadedSimulationData(
            people_data=people_data,
            homes_data=homes_data,
            places_data=places_data,
            patterns_data=patterns_data,
        )

    def _engine_eligibility(self, variants: list) -> tuple[bool, str]:
        """Decide whether the vectorized engine can run this config *correctly*.

        Engine mode replaces the per-Person ``move_people`` path with a fixed
        precomputed location scatter, so it cannot apply movement-altering
        interventions (capacity<1 / lockdown / selfiso reroute people home — see
        ``move_people``) and is only vectorized for a single variant. Rather than
        run those configs and silently drop the intervention (or read stale
        Person/Location dicts for multi-variant), we report them ineligible and
        fall back to the correct non-engine path. Returns ``(eligible, reason)``;
        ``reason`` is empty when eligible.

        Interventions are scanned across ALL scheduled time points, not just
        t=0, since a movement intervention can be scheduled to start mid-run.
        """
        if not self.aggregate_transmission:
            return False, "aggregate_transmission is off"
        if self.enable_logging:
            return False, "per-contact logging is on"
        if len(variants) != 1:
            return False, f"multi-variant run ({len(variants)} variants)"
        non_trivial = [
            iv
            for iv in (self.simdata.get("interventions") or [])
            if not _trivial_movement_interventions(iv)
        ]
        if non_trivial:
            times = sorted({int(iv.get("time", 0)) for iv in non_trivial})
            return (
                False,
                f"movement-altering interventions (capacity<1 / lockdown / "
                f"selfiso) scheduled at t={times}",
            )
        return True, ""

    def build_context(self, loaded: LoadedSimulationData) -> SimulationContext:
        self._progress(
            0,
            1,
            f"Building world: {len(loaded.homes_data)} homes, {len(loaded.places_data)} places...",
        )
        simulator = DiseaseSimulator(
            timestep=60,
            enable_logging=self.enable_logging,
            intervention_weights=self.simdata["interventions"],
        )
        variants = self.simdata["variants"]
        self._decide_engine_mode(variants)
        # Single-variant engine mode derives infectious locations from occupancy,
        # so the event queue / _person_index (build_event_queue) is unnecessary.
        engine_no_queue = self._soa_engine and len(variants) == 1

        with self._timed("build_context/build_locations"):
            build_locations(simulator, loaded.homes_data, loaded.places_data)
        if engine_no_queue:
            event_queue = None
        else:
            with self._timed("build_context/build_event_queue"):
                event_queue = build_event_queue(loaded.patterns_data, self.simdata["length"])

        self._progress(
            0,
            1,
            f"Initializing {len(loaded.people_data)} people & seeding infections...",
        )
        infection_manager = InfectionManager(
            infected_ids=[],
            disease_name=self.simdata["disease_name"],
            dmp_mode=self.simdata["dmp_mode"],
            model_path_by_variant=self.simdata["model_path_by_variant"],
            matrix_csv_by_variant=self.simdata["matrix_csv_by_variant"],
        )
        with self._timed("build_context/seed_population"):
            seeded_population = seed_population(
                simulator,
                loaded.people_data,
                variants,
                event_queue,
                infection_manager,
                self.simdata["initial_infected_count"],
            )

        # variant_infected accumulates the per-variant {pid: state} map that is
        # snapshotted each step. In engine mode it is maintained incrementally
        # (update_variant_tracking only touches people who changed this step), so
        # the initial seeds must be written here at build — the incremental path
        # would otherwise miss seeds that don't transition by the first timestep.
        susceptible = InfectionState.SUSCEPTIBLE
        variant_infected = {variant: {} for variant in variants}
        if self._soa_engine or os.environ.get("DELINEO_SOA_SHADOW"):
            self._attach_membership_shadow(simulator, loaded.people_data)
        if self._soa_engine:
            store = simulator.membership
            store.set_person_refs(simulator.get_person)
            # Seed infections were scheduled before the store existed; backfill
            # the ever-infected mask + state mirror from the already-infected set,
            # and seed variant_infected with their build-time (t=0) states.
            mirror_variant = variants[0]
            for pid in infection_manager.infected:
                store.mark_infected(pid)
                person = simulator.people.get(pid)
                if person is not None:
                    self._mirror_person_state(store, person, mirror_variant)
                    for disease in variants:
                        state = person.states.get(disease, susceptible)
                        if state != susceptible:
                            variant_infected[disease][person.id] = int(state.value)
                            store.snap_state[person._soa_idx] = int(state.value)
            with self._timed("build_context/precompute_movement"):
                store.precompute_movement(loaded.patterns_data, self.simdata["length"])
            self._precompute_location_quanta(simulator, store)

        return SimulationContext(
            simulator=simulator,
            event_queue=event_queue,
            infection_manager=infection_manager,
            snapshot_writer=SimulationSnapshotWriter(self.output_dir),
            variants=variants,
            variant_infected=variant_infected,
            people_with_timelines=seeded_population.people_with_timelines,
            max_length=self.simdata["length"],
            last_movement_ts=-simulator.timestep,
            initial_infected_ids=seeded_population.initial_infected_ids,
        )

    def _decide_engine_mode(self, variants: list) -> None:
        """Set self._soa_engine: ON by default, but only when this config is
        eligible (the kill switch DELINEO_SOA_ENGINE=0 forces it off). Ineligible
        configs fall back to the non-engine path for correct results. Warns if an
        external-FOI run won't use the engine (where that term lives)."""
        if _engine_disabled():
            self._soa_engine = False
            logger.info("SoA engine disabled via DELINEO_SOA_ENGINE=0.")
        else:
            eligible, reason = self._engine_eligibility(variants)
            self._soa_engine = eligible
            if not eligible:
                logger.info(
                    "SoA engine not eligible (%s); falling back to the "
                    "non-engine path for correct results.",
                    reason,
                )
            else:
                logger.info("SoA engine engaged (eligible config).")
        if (
            self.external_foi
            and self.external_prevalence > 0.0
            and not self._soa_engine
        ):
            logger.warning(
                "external_foi is ON (external_prevalence=%.4g) but this run is not "
                "using the SoA engine — the external term will have NO effect. It is "
                "currently implemented in _vectorized_transmission only.",
                self.external_prevalence,
            )

    def _precompute_location_quanta(self, simulator, store) -> None:
        """Per-room Wells-Riley base quanta + static external-FOI coefficients.

        Ventilation is static, so the vectorized kernel needs no per-room work at
        runtime: base_quanta[loc] = quanta_emission / ventilation, and (when
        external_foi is on) ext_ratio[loc] = (1 - f_j)/f_j * emit_factor for
        facilities with known f_j (0 for households / unknown f_j)."""
        exposure_hours = simulator.timestep / 60.0
        base_q = np.empty(store.num_locations, dtype=np.float64)
        build_ext = self.external_foi
        ext_ratio = (
            np.zeros(store.num_locations, dtype=np.float64) if build_ext else None
        )
        for loc_idx, (loc_id, is_hh) in enumerate(store.idx_to_loc):
            place = simulator.get_location(loc_id, is_hh)
            base_q[loc_idx] = (20.0 * 0.5 * exposure_hours) / self._ventilation_rate(
                place, is_hh
            )
            if build_ext and not is_hh:
                fj = getattr(place, "catchment_fj", None)
                if fj is not None and 0.0 < fj <= 1.0:
                    ext_ratio[loc_idx] = (1.0 - fj) / fj * self.external_emit_factor
        store.base_quanta = base_q
        store.ext_ratio = ext_ratio

    def run_queue(self, context: SimulationContext) -> None:
        if context.event_queue is None:
            self._run_queue_engine(context)
            return
        self._progress(0, context.max_length, "Running simulation...")
        logger.info(
            "Starting queue-based simulation (queue size: %d)",
            len(context.event_queue),
        )
        # Do NOT clear self._perf_accum here — build_context fills it before
        # run_queue is entered, and we want both phases summarized together.

        while context.event_queue:
            next_ts = context.event_queue.peek()[0]
            if next_ts > context.max_length:
                break

            if next_ts % SIMULATION["log_interval"] == 0:
                logger.info(
                    "Queue event at t=%d (queue=%d, buffer=%d)",
                    next_ts,
                    len(context.event_queue),
                    len(context.event_queue.buffer),
                )

            self.process_movement_up_to(context, next_ts)
            with self._timed("run_queue/process_infections"):
                self.process_infections_at_timestep(context, next_ts)

        self.process_movement_up_to(context, context.max_length)
        self._progress(context.max_length, context.max_length, "Simulation complete, writing output...")
        logger.info("SIMULATION COMPLETE (%d timesteps processed)", context.processed_count)

        if _perf_timings_enabled():
            for label in sorted(self._perf_accum):
                print(f"[perf] {label}: {self._perf_accum[label]:.3f}s", flush=True)

    def _run_queue_engine(self, context: SimulationContext) -> None:
        """Timestep-driven loop for single-variant engine mode (no event queue).

        Movement comes from the precomputed per-timestep scatter; transmission
        runs every step (vectorized, a no-op when no one is infectious). The
        event queue and its _person_index are not built at all.
        """
        sim = context.simulator
        store = sim.membership
        self._progress(0, context.max_length, "Running simulation...")
        logger.info("Starting timestep-driven engine simulation")

        # Ship the per-person decode tables once, before any timestep, so the
        # streaming per-person map routes (person-path) read `meta` first.
        context.snapshot_writer.write_meta(store.movement_meta())

        ts = sim.timestep
        while ts <= context.max_length:
            self._progress(ts, context.max_length)
            ts_str = str(ts)
            context.processed_count += 1

            if ts in store._move:
                interventions = sim.get_interventions(ts_str)
                with self._timed("run_queue/update_people_states"):
                    self.update_people_states(context, ts_str)
                if interventions is not context.last_interventions:
                    with self._timed("run_queue/apply_interventions"):
                        context.last_interventions = interventions
                        for person in sim.people.values():
                            apply_person_interventions(sim, person, interventions, ts_str)
                with self._timed("run_queue/apply_movement"):
                    store.apply_movement(ts)

            with self._timed("run_queue/process_infections"):
                self._vectorized_transmission(context, ts)
            with self._timed("run_queue/update_variant_tracking"):
                self.update_variant_tracking(context)
            with self._timed("run_queue/write_snapshot"):
                self.write_snapshot(context, ts_str)
            context.last_movement_ts = ts
            ts += sim.timestep

        self._progress(
            context.max_length, context.max_length, "Simulation complete, writing output..."
        )
        logger.info("SIMULATION COMPLETE (%d timesteps processed)", context.processed_count)
        if _perf_timings_enabled():
            for label in sorted(self._perf_accum):
                print(f"[perf] {label}: {self._perf_accum[label]:.3f}s", flush=True)

    def process_movement_up_to(self, context: SimulationContext, target_ts: int) -> None:
        ts = context.last_movement_ts + context.simulator.timestep
        while ts <= target_ts:
            self._progress(ts, context.max_length)
            ts_str = str(ts)
            context.processed_count += 1

            if ts_str in context.event_queue.buffer:
                timestep_data = context.event_queue.buffer[ts_str]
                interventions = context.simulator.get_interventions(ts_str)
                with self._timed("run_queue/update_people_states"):
                    self.update_people_states(context, ts_str)

                if interventions is not context.last_interventions:
                    with self._timed("run_queue/apply_interventions"):
                        context.last_interventions = interventions
                        for person in context.simulator.people.values():
                            apply_person_interventions(
                                context.simulator,
                                person,
                                interventions,
                                ts_str,
                            )

                if self._soa_engine:
                    # Defensive net: _engine_eligibility already excludes
                    # movement interventions before the engine is engaged, and an
                    # eligible (single-variant) engine run never reaches this
                    # queue path (it uses _run_queue_engine). If this ever fires,
                    # eligibility has a bug — fail loudly rather than silently drop
                    # the intervention.
                    if not _trivial_movement_interventions(interventions):
                        raise RuntimeError(
                            "SoA engine reached a movement-altering intervention "
                            "despite eligibility gating (capacity<1 / lockdown / "
                            "selfiso) — this is a bug in _engine_eligibility"
                        )
                    with self._timed("run_queue/apply_movement"):
                        if context.simulator.membership.apply_movement(ts):
                            context.occupancy = None  # rebuilt lazily below
                elif isinstance(timestep_data, dict):
                    if "homes" in timestep_data:
                        with self._timed("run_queue/move_people_home"):
                            move_people(
                                context.simulator,
                                timestep_data["homes"].items(),
                                True,
                                ts_str,
                                interventions,
                            )
                    if "places" in timestep_data:
                        with self._timed("run_queue/move_people_places"):
                            move_people(
                                context.simulator,
                                timestep_data["places"].items(),
                                False,
                                ts_str,
                                interventions,
                            )

            if self._soa_engine and context.occupancy is None:
                with self._timed("run_queue/build_occupancy"):
                    context.occupancy = context.simulator.membership.occupancy_view()

            with self._timed("run_queue/update_variant_tracking"):
                self.update_variant_tracking(context)
            with self._timed("run_queue/write_snapshot"):
                self.write_snapshot(context, ts_str)
            with self._timed("run_queue/consume_pattern"):
                context.event_queue.consume_pattern(ts_str)
            context.last_movement_ts = ts
            ts += context.simulator.timestep

    def update_people_states(self, context: SimulationContext, ts_str: str) -> None:
        # people_with_timelines holds Person refs directly (see PopulationBuildResult);
        # iterate them without a simulator.get_person(pid) lookup per call.
        if self._soa_engine:
            pstate = context.simulator.membership.pstate
            variant = context.variants[0]
            susceptible = InfectionState.SUSCEPTIBLE
            time = int(ts_str)
            changed = context.states_changed_idx
            changed.clear()
            for person in context.people_with_timelines:
                # update_state itself early-exits between timeline boundaries; do
                # the same check here so non-transitioning people cost nothing and
                # the per-person numpy scalar write (the bulk of this stage at
                # saturation) is skipped unless the state value actually changed.
                # Byte-identical to calling update_state + writing pstate for all.
                if time < person._next_transition_time:
                    continue
                person.update_state(ts_str, context.variants)
                idx = person._soa_idx
                value = int(person.states.get(variant, susceptible).value)
                if value != pstate[idx]:
                    pstate[idx] = value
                    changed.append(idx)
        else:
            for person in context.people_with_timelines:
                person.update_state(ts_str, context.variants)

    def update_variant_tracking(self, context: SimulationContext) -> None:
        susceptible = InfectionState.SUSCEPTIBLE
        if self._soa_engine:
            # Incremental: only people whose state value changed in this step's
            # update_people_states need their variant_infected entry refreshed.
            # Unchanged entries are already correct from the step they last
            # changed, and newly-infected people are written directly by the
            # transmission kernel (variant_bucket[...]). Byte-identical to
            # rewriting the whole ever-infected map every step, but O(changed)
            # instead of O(ever-infected).
            idx_to_person = context.simulator.membership.idx_to_person
            variant_infected = context.variant_infected
            variants = context.variants
            snap_state = context.simulator.membership.snap_state
            for idx in context.states_changed_idx:
                person = idx_to_person[idx]
                for disease in variants:
                    state = person.states.get(disease, susceptible)
                    if state != susceptible:
                        variant_infected[disease][person.id] = int(state.value)
                        snap_state[idx] = int(state.value)
            return
        for pid_str in context.event_queue.registry:
            person = context.simulator.get_person(pid_str)
            if not person:
                continue
            for disease in context.variants:
                state = person.states.get(disease, susceptible)
                if state != susceptible:
                    context.variant_infected[disease][pid_str] = int(state.value)

    def write_snapshot(self, context: SimulationContext, ts_str: str) -> None:
        if context.simulator.enable_logging and context.simulator.logger:
            for household in context.simulator.households.values():
                if household.population:
                    context.simulator.logger.log_location_state(household, ts_str)
            for facility in context.simulator.facilities.values():
                if facility.population:
                    context.simulator.logger.log_location_state(facility, ts_str)

        if self._soa_shadow:
            if self._soa_engine:
                # Engine mode drives movement via arrays (dicts are stale), so
                # validate the state mirror, not the dict-vs-occupancy match.
                self._shadow_validate_state_mirror(context)
            else:
                self._shadow_validate_occupancy(context.simulator)

        with self._timed("write_snapshot/build_movement"):
            if self._soa_engine:
                # Numeric per-location [count, infected] (map-cache shape) — the
                # ~50x snapshot win. Consumed directly by the Next sim-processor.
                store = context.simulator.membership
                movement = store.movement_snapshot_numeric()
                # Per-person current location (person index -> location index).
                # Decoded via the one-time `meta` entry so the per-person map
                # views (people-map, person-path) can reconstruct who-is-where
                # without the engine ever materializing pid lists.
                movement["loc"] = store.person_loc.tolist()
                # Per-place [infected, recovered] dot counts (places order), so
                # the Cases-map dot bake reads them directly instead of
                # reconstructing per person from `loc` + the sim snapshot.
                movement["pdots"] = store.place_dot_counts()
            else:
                movement = build_movement_snapshot(context.simulator)
        with self._timed("write_snapshot/build_infection"):
            infection = build_infection_snapshot(context.variant_infected)
        with self._timed("write_snapshot/writer_write"):
            context.snapshot_writer.write(ts_str, movement, infection)

    def process_infections_at_timestep(self, context: SimulationContext, timestep: int) -> None:
        if self._soa_engine and len(context.variants) == 1:
            # The queue still gates which timesteps have any infectious presence;
            # drain it to advance, then run one vectorized pass over all rooms.
            had_event = False
            while context.event_queue and context.event_queue.peek()[0] == timestep:
                context.event_queue.pop()
                had_event = True
            if had_event:
                with self._timed("infection_event/aggregate_iteration"):
                    self._vectorized_transmission(context, timestep)
            return
        while context.event_queue and context.event_queue.peek()[0] == timestep:
            ts, poi_id, is_household = context.event_queue.pop()
            self.process_infection_event(context, ts, poi_id, is_household)


    def finalize(self, context: SimulationContext) -> dict:
        context.snapshot_writer.close()

        if context.simulator.enable_logging and context.simulator.logger:
            logger.info("Exporting logs...")
            context.simulator.logger.export_logs_to_csv()
            context.simulator.logger.generate_summary_report()
            context.simulator.logger.graphic_analysis()

        result = context.snapshot_writer.result()
        result["metadata"] = {
            "disease_name": self.simdata["disease_name"],
            "variants": context.variants,
            "dmp_mode": self.simdata["dmp_mode"],
            "aggregate_transmission": self.simdata["aggregate_transmission"],
            "area_aware_ventilation": self.simdata["area_aware_ventilation"],
            "model_path_by_variant": self.simdata["model_path_by_variant"],
            "initial_infected_count": self.simdata["initial_infected_count"],
            "initial_infected_ids": context.initial_infected_ids,
            "timeline_source_counts": context.infection_manager.timeline_source_counts,
            "randseed": self.simdata["randseed"],
            "random_seed_behavior": (
                "random"
                if self.simdata["randseed"]
                else f"deterministic:{DETERMINISTIC_RANDOM_SEED}"
            ),
            "disabled_poi_ids": self.simdata["disabled_poi_ids"],
            "interventions": self.simdata["interventions"],
        }
        # Validation guard: under dmp_mode='auto' a DMP miss silently substitutes
        # the degraded fallback timeline (no hospitalization/death). Surface it
        # loudly so a degraded run isn't mistaken for validation-grade output;
        # run with dmp_mode='required' to turn the miss into a hard error.
        fallback_n = context.infection_manager.timeline_source_counts.get("fallback", 0)
        if fallback_n and self.simdata["dmp_mode"] != "off":
            logger.warning(
                "%d infection(s) used the DEGRADED fallback timeline "
                "(no hospitalization/death) — DMP matching missed. Results are "
                "not validation-grade; rerun with dmp_mode='required'.",
                fallback_n,
            )
        return result
