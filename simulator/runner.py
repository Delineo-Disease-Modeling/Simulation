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
from .event_queue import EventQueue
from .infection_models.v6_wells_riley import CAT, get_vaccination_protection
from .infectionmgr import InfectionManager
from .pap import InfectionState, Person, VaccinationState
from .patterns_codec import BinaryPatterns
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


def normalize_location_id(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


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


def _trivial_movement_interventions(interventions: dict) -> bool:
    """True when no intervention redirects movement (so a pure person_loc
    scatter equals move_people). Masking/vaccination don't move people."""
    return (
        float(interventions.get("capacity", 1.0)) >= 1.0
        and float(interventions.get("lockdown", 0.0)) <= 0.0
        and float(interventions.get("selfiso", 0.0)) <= 0.0
    )


def normalize_simdata(simdata: dict) -> dict:
    normalized = dict(simdata)

    normalized["randseed"] = bool(
        normalized.get("randseed", SIMULATION["default_interventions"]["randseed"])
    )
    normalized["initial_infected_count"] = max(
        0,
        int(
            normalized.get(
                "initial_infected_count",
                SIMULATION["default_initial_infected_count"],
            )
        ),
    )
    normalized["disease_name"] = str(
        normalized.get("disease_name") or SIMULATION["disease_name"]
    )

    raw_variants = normalized.get("variants") or SIMULATION["variants"]
    if isinstance(raw_variants, str):
        raw_variants = [raw_variants]
    variants = [
        str(variant).strip()
        for variant in raw_variants
        if str(variant).strip()
    ]
    normalized["variants"] = variants or list(SIMULATION["variants"])

    raw_mode = str(normalized.get("dmp_mode") or DMP_API["mode"]).lower()
    normalized["dmp_mode"] = raw_mode if raw_mode in VALID_DMP_MODES else "auto"

    normalized["aggregate_transmission"] = bool(
        normalized.get(
            "aggregate_transmission", INFECTION_MODEL.get("aggregate_transmission", False)
        )
    )

    normalized["area_aware_ventilation"] = bool(
        normalized.get(
            "area_aware_ventilation",
            INFECTION_MODEL.get("area_aware_ventilation", False),
        )
    )

    normalized["external_foi"] = bool(
        normalized.get("external_foi", INFECTION_MODEL.get("external_foi", False))
    )
    normalized["external_prevalence"] = float(
        normalized.get(
            "external_prevalence", INFECTION_MODEL.get("external_prevalence", 0.0)
        )
    )
    normalized["external_emit_factor"] = float(
        normalized.get(
            "external_emit_factor", INFECTION_MODEL.get("external_emit_factor", 1.0)
        )
    )

    raw_model_paths = normalized.get("model_path_by_variant") or {}
    model_path_by_variant = {}
    if isinstance(raw_model_paths, dict):
        for variant, model_path in raw_model_paths.items():
            if model_path is None:
                model_path_by_variant[str(variant)] = None
                continue
            model_path_str = str(model_path).strip()
            if model_path_str:
                model_path_by_variant[str(variant)] = model_path_str
    normalized["model_path_by_variant"] = model_path_by_variant

    raw_csv = normalized.get("matrix_csv_by_variant") or {}
    matrix_csv_by_variant: dict[str, str] = {}
    if isinstance(raw_csv, dict):
        for variant, csv_content in raw_csv.items():
            if isinstance(csv_content, str) and csv_content.strip():
                matrix_csv_by_variant[str(variant)] = csv_content
    normalized["matrix_csv_by_variant"] = matrix_csv_by_variant

    raw_disabled_poi_ids = normalized.get("disabled_poi_ids") or []
    if isinstance(raw_disabled_poi_ids, (str, int, float)):
        raw_disabled_poi_ids = [raw_disabled_poi_ids]
    if not isinstance(raw_disabled_poi_ids, (list, tuple, set)):
        raw_disabled_poi_ids = []
    normalized["disabled_poi_ids"] = sorted(
        {
            normalized_id
            for normalized_id in (
                normalize_location_id(value) for value in raw_disabled_poi_ids
            )
            if normalized_id
        }
    )

    return normalized


def _person_home_id(person_data) -> str:
    if not isinstance(person_data, dict):
        return ""
    return normalize_location_id(
        person_data.get("home") or person_data.get("household_id")
    )


def _normalize_person_ids(person_ids) -> list[str]:
    if not isinstance(person_ids, (list, tuple, set)):
        return []
    return [
        normalized_id
        for normalized_id in (normalize_location_id(person_id) for person_id in person_ids)
        if normalized_id
    ]


def _home_id_by_person(people_data) -> dict:
    return {
        normalize_location_id(person_id): home_id
        for person_id, person_data in (people_data or {}).items()
        if (home_id := _person_home_id(person_data))
    }


def _reroute_binary_patterns(
    binary: BinaryPatterns,
    people_data: dict,
    disabled: set,
) -> BinaryPatterns:
    """Reroute disabled-POI visits in the dense ``loc_matrix`` representation.

    The binary patterns carry a ``[T, N]`` matrix of producer location indices
    (index < ``n_homes`` is a home). We send every (person, timestep) entry that
    sits at a disabled place back to that person's home index, vectorized — which
    preserves the engine's binary fast path (``precompute_movement`` reads
    ``loc_matrix`` directly, and the non-engine ``.items()`` reconstruction reads
    it too). People whose home isn't in this run's location table are left in
    place rather than dropped.
    """
    loc_ids = binary.loc_ids
    n_homes = binary.n_homes
    # Homes and places share one id table disambiguated ONLY by position
    # (index < n_homes is a home), and their id strings can collide -- the codec
    # keys its own remap by (id, is_home) for exactly this reason. So we must
    # resolve a disabled-POI id against PLACES and a person's home against HOMES,
    # never a single id->index map (that would mis-resolve a colliding id).
    home_id_to_idx: dict = {}
    place_id_to_idx: dict = {}
    for idx, loc_id in enumerate(loc_ids):
        nid = normalize_location_id(loc_id)
        if idx < n_homes:
            home_id_to_idx.setdefault(nid, idx)
        else:
            place_id_to_idx.setdefault(nid, idx)

    disabled_idx = sorted(
        {
            idx
            for disabled_id in disabled
            if (idx := place_id_to_idx.get(disabled_id)) is not None
        }
    )
    if not disabled_idx:
        return binary

    home_id_by_person = _home_id_by_person(people_data)
    home_idx_by_col = np.full(len(binary.pids), -1, dtype=np.int64)
    for col, pid in enumerate(binary.pids):
        home_id = home_id_by_person.get(normalize_location_id(pid))
        if home_id:
            home_idx = home_id_to_idx.get(home_id)
            if home_idx is not None:
                home_idx_by_col[col] = home_idx
    has_home = home_idx_by_col >= 0
    if not has_home.any():
        return binary

    disabled_arr = np.array(disabled_idx, dtype=binary.loc_matrix.dtype)
    at_disabled = np.isin(binary.loc_matrix, disabled_arr)
    mask = at_disabled & has_home[np.newaxis, :]
    if not mask.any():
        return binary

    home_row = home_idx_by_col.astype(binary.loc_matrix.dtype)
    binary.loc_matrix = np.where(
        mask, np.broadcast_to(home_row, binary.loc_matrix.shape), binary.loc_matrix
    )
    return binary


def reroute_disabled_poi_visits(
    patterns_data,
    people_data: dict,
    disabled_poi_ids,
):
    """Send visits to ``disabled_poi_ids`` back to each visitor's home.

    Operates on the loaded movement patterns *before* they feed the engine or
    the non-engine path, so the disabling is honored by both. Handles the dense
    binary representation (``BinaryPatterns``, the prod default) in-place and
    vectorized, and the legacy ``{ts: {homes, places}}`` dict by rebuilding it.
    """
    disabled = {
        normalized_id
        for normalized_id in (
            normalize_location_id(value) for value in (disabled_poi_ids or [])
        )
        if normalized_id
    }
    if not disabled:
        return patterns_data

    if isinstance(patterns_data, BinaryPatterns):
        return _reroute_binary_patterns(patterns_data, people_data, disabled)

    home_by_person = _home_id_by_person(people_data)
    if not home_by_person:
        return patterns_data

    rerouted: dict = {}
    for timestep, timestep_data in (patterns_data or {}).items():
        if not isinstance(timestep_data, dict):
            rerouted[timestep] = timestep_data
            continue

        raw_homes = timestep_data.get("homes") or {}
        homes = {
            normalize_location_id(home_id): _normalize_person_ids(person_ids)
            for home_id, person_ids in raw_homes.items()
            if normalize_location_id(home_id)
        }
        seen_by_home = {
            home_id: set(person_ids) for home_id, person_ids in homes.items()
        }

        places: dict[str, list[str]] = {}
        raw_places = timestep_data.get("places") or {}
        for place_id, person_ids in raw_places.items():
            place_key = normalize_location_id(place_id)
            normalized_people = _normalize_person_ids(person_ids)
            if not place_key:
                continue

            if place_key not in disabled:
                places[place_key] = normalized_people
                continue

            for person_id in normalized_people:
                home_id = home_by_person.get(person_id)
                if not home_id:
                    continue
                home_people = homes.setdefault(home_id, [])
                seen = seen_by_home.setdefault(home_id, set(home_people))
                if person_id not in seen:
                    home_people.append(person_id)
                    seen.add(person_id)

        rerouted[timestep] = {
            **timestep_data,
            "homes": homes,
            "places": places,
        }

    return rerouted


def move_people(
    simulator: DiseaseSimulator,
    items,
    is_household: bool,
    current_timestep: str,
    interventions: Optional[dict] = None,
) -> None:
    if interventions is None:
        interventions = simulator.get_interventions(current_timestep)

    for loc_id, people in items:
        place = simulator.get_location(str(loc_id), is_household)
        if place is None:
            raise Exception(
                f"Place {loc_id} was not found in the simulator data "
                f"(household={is_household})"
            )

        for person_id in people:
            person = simulator.get_person(person_id)
            if person is None:
                continue

            original_location = person.location

            if not is_household:
                at_capacity = (
                    place.capacity != -1
                    and place.total_count >= place.capacity * interventions["capacity"]
                )
                hit_lockdown = (
                    place != person.location
                    and random.random() < interventions["lockdown"]
                )
                self_iso = (
                    person.has_state(InfectionState.SYMPTOMATIC)
                    and random.random() < interventions["selfiso"]
                )

                if at_capacity:
                    simulator.log_event(
                        "log_intervention_effect",
                        person,
                        "capacity_limit",
                        "redirected_home",
                        current_timestep,
                        place,
                    )
                if hit_lockdown:
                    simulator.log_event(
                        "log_intervention_effect",
                        person,
                        "lockdown",
                        "stayed_home",
                        current_timestep,
                        place,
                    )
                if self_iso:
                    simulator.log_event(
                        "log_intervention_effect",
                        person,
                        "self_isolation",
                        "stayed_home",
                        current_timestep,
                        place,
                    )

                if at_capacity or hit_lockdown or self_iso:
                    person.location.remove_member(person_id)
                    person.household.add_member(person)
                    if original_location.id != person.household.id:
                        reason = (
                            "capacity_limit"
                            if at_capacity
                            else ("lockdown" if hit_lockdown else "self_isolation")
                        )
                        simulator.log_event(
                            "log_movement",
                            person,
                            original_location,
                            person.household,
                            current_timestep,
                            reason,
                        )
                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            if original_location.id != place.id:
                simulator.log_event(
                    "log_movement",
                    person,
                    original_location,
                    place,
                    current_timestep,
                    "normal",
                )
            person.location = place


def apply_person_interventions(
    simulator: DiseaseSimulator,
    person: Person,
    interventions: dict,
    ts_str: str,
) -> None:
    # Masking is reversible: lowering the policy unmasks previously compliant people.
    should_mask = person.iv_threshold <= interventions["mask"]
    if should_mask and not person.is_masked():
        simulator.log_event("log_intervention_effect", person, "mask", "complied", ts_str)
        person.set_masked(True)
    elif not should_mask and person.is_masked():
        simulator.log_event("log_intervention_effect", person, "mask", "unmasked", ts_str)
        person.set_masked(False)

    # Vaccination is permanent and dose count is locked at first inoculation.
    if (
        person.iv_threshold <= interventions["vaccine"]
        and person.get_vaccinated() == VaccinationState.NONE
    ):
        min_doses = SIMULATION["vaccination_options"]["min_doses"]
        max_doses = SIMULATION["vaccination_options"]["max_doses"]
        doses = random.randint(min_doses, max_doses)
        simulator.log_event(
            "log_intervention_effect",
            person,
            "vaccine",
            f"received_{doses}_doses",
            ts_str,
        )
        person.set_vaccinated(VaccinationState(doses))

    # Keep the SoA scalar mirror in sync when masking/vaccination changed.
    store = getattr(simulator, "membership", None)
    if store is not None and person._soa_idx >= 0:
        i = person._soa_idx
        store.masked[i] = person.masked
        if person.vaccination_status:
            store.vax_trans_factor[i] = 1.0 - get_vaccination_protection(person, "transmission")
            store.vax_inf_protection[i] = get_vaccination_protection(person, "infection")


class SimulationRunner:
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
        # The engine is ON BY DEFAULT, but only ENGAGED when it can run this
        # config correctly. Ineligible configs (movement interventions,
        # multi-variant, logging/agg constraints) transparently fall back to the
        # non-engine path instead of silently producing wrong results.
        # DELINEO_SOA_ENGINE=0 is the kill switch (forces non-engine everywhere).
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
        # The external-FOI term is implemented in the SoA engine kernel only
        # (the default-on path). Warn loudly rather than silently no-op if a run
        # asks for it but won't use the engine.
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
            # Per-room Wells-Riley base quanta (ventilation is static), so the
            # vectorized kernel needs no per-room work at runtime.
            exposure_hours = simulator.timestep / 60.0
            base_q = np.empty(store.num_locations, dtype=np.float64)
            # Static external-FOI coefficient per location: (1 - f_j)/f_j * emit
            # factor. At runtime W_external[loc] = n_internal[loc] * ext_ratio[loc]
            # * P_ext, so the externals act as extra well-mixed infectors. 0 for
            # households and for facilities with unknown f_j (no term applied).
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
                        ext_ratio[loc_idx] = (
                            (1.0 - fj) / fj * self.external_emit_factor
                        )
            store.base_quanta = base_q
            store.ext_ratio = ext_ratio

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

    def _attach_membership_shadow(self, simulator, people_data: dict) -> None:
        """SoA Step 1 (shadow): build a MembershipStore alongside the dicts.

        Attaches the store to every Location (so add_member mirrors placements
        into person_loc) and backfills the current post-seed occupancy. Iterating
        each location's population dict in order stamps arrival_seq so that, within
        a location, the array order reproduces the dict's insertion order. Gated by
        DELINEO_SOA_SHADOW — never runs in production.
        """
        from .membership import MembershipStore

        # Order homes then places, each by numeric id, to match the Next
        # sim-processor's homeIds/placeIds (sorted by Number). This makes the
        # numeric snapshot's positional [count, infected] arrays line up with the
        # frontend's map-cache slots without an id lookup.
        homes = sorted(simulator.households.values(), key=lambda h: int(h.id))
        places = sorted(simulator.facilities.values(), key=lambda f: int(f.id))
        location_keys = [(h.id, True) for h in homes]
        location_keys += [(f.id, False) for f in places]
        store = MembershipStore(list(people_data.keys()), location_keys)

        for loc_id, is_hh in location_keys:
            loc = simulator.get_location(loc_id, is_hh)
            loc._loc_idx = store.loc_to_idx[(loc_id, is_hh)]
            loc._membership = store

        for household in simulator.households.values():
            for pid in household.population:
                store.note_placement(pid, household._loc_idx)
        for facility in simulator.facilities.values():
            for pid in facility.population:
                store.note_placement(pid, facility._loc_idx)

        simulator.membership = store
        self._soa_shadow = bool(os.environ.get("DELINEO_SOA_SHADOW"))
        self._shadow_mismatches = 0
        self._shadow_checks = 0

    def _mirror_person_state(self, store, person, variant: str) -> None:
        """Mirror one person's hot scalars (state, masked, vax factors) into the
        store arrays. The vectorized kernel (stage 2) reads these instead of the
        Person objects. Single-variant; multidisease keeps the per-person kernel.
        """
        i = person._soa_idx
        if i < 0:
            return
        store.pstate[i] = int(person.states.get(variant, InfectionState.SUSCEPTIBLE).value)
        store.masked[i] = person.masked
        if person.vaccination_status:
            store.vax_trans_factor[i] = 1.0 - get_vaccination_protection(person, "transmission")
            store.vax_inf_protection[i] = get_vaccination_protection(person, "infection")
        else:
            store.vax_trans_factor[i] = 1.0
            store.vax_inf_protection[i] = 0.0

    def _shadow_validate_state_mirror(self, context) -> None:
        """Assert the mirrored arrays still match the Person objects (debug)."""
        store = context.simulator.membership
        variant = context.variants[0]
        susceptible = InfectionState.SUSCEPTIBLE
        self._shadow_checks += 1
        for person in context.simulator.people.values():
            i = person._soa_idx
            want = int(person.states.get(variant, susceptible).value)
            if store.pstate[i] != want or bool(store.masked[i]) != bool(person.masked):
                self._shadow_mismatches += 1
                logger.warning(
                    "SOA state-mirror mismatch pid=%s: pstate=%d want=%d masked=%s/%s",
                    person.id, store.pstate[i], want, bool(store.masked[i]), person.masked,
                )
                return

    def _shadow_validate_occupancy(self, simulator) -> None:
        """Assert the OccupancyView reproduces the dict membership (order incl.)."""
        store = getattr(simulator, "membership", None)
        if store is None:
            return
        view = store.occupancy_view()
        self._shadow_checks += 1
        for loc_id, is_hh in store.idx_to_loc:
            loc = simulator.get_location(loc_id, is_hh)
            dict_order = list(loc.population.keys())
            loc_idx = store.loc_to_idx[(loc_id, is_hh)]
            arr_order = [store.idx_to_pid[i] for i in view.occupants_of(loc_idx)]
            if dict_order != arr_order:
                self._shadow_mismatches += 1
                logger.warning(
                    "SOA shadow mismatch at loc %s (hh=%s): dict=%d arr=%d first_diff=%s",
                    loc_id, is_hh, len(dict_order), len(arr_order),
                    next((i for i, (a, b) in enumerate(zip(dict_order, arr_order)) if a != b), "len"),
                )

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

    def _vectorized_transmission(self, context: SimulationContext, ts: int) -> None:
        """Single-variant well-mixed Wells-Riley over all rooms at once.

        Equivalent to running _aggregate_transmission_event per room, but as
        numpy array ops: emission summed per room with bincount, then one
        vectorized infection draw per susceptible. RNG source differs (numpy vs
        python per-pair) -> ensemble-validated, not byte-identical.
        """
        store = context.simulator.membership
        variant = context.variants[0]
        pstate = store.pstate
        person_loc = store.person_loc
        masked = store.masked

        INFECTIOUS = int(InfectionState.INFECTIOUS.value)
        INVISIBLE = int(
            (InfectionState.HOSPITALIZED | InfectionState.RECOVERED | InfectionState.REMOVED).value
        )
        placed = person_loc >= 0
        infectious = placed & ((pstate & INFECTIOUS) != 0)

        # External force-of-infection: out-of-cluster visitors add a one-way
        # background emission to each room, W_ext[loc] = n_internal[loc]
        # * ext_ratio[loc] * P_ext, where ext_ratio = (1 - f_j)/f_j * emit_factor.
        # The externals are never agents (not in pstate / never susceptible /
        # never rendered), so this can seed or sustain transmission with zero
        # internal infectors present — which is exactly why we must NOT early-return
        # on infectious.any() when the term is active. Inert by default (flag off,
        # or external_prevalence 0, or ext_ratio unbuilt) -> golden path preserved.
        ext_on = (
            self.external_foi
            and self.external_prevalence > 0.0
            and store.ext_ratio is not None
        )
        if not infectious.any() and not ext_on:
            return

        # Emission weight per infector, summed per room (cheap O(N) numpy).
        inf_w = np.where(masked, 0.30, 1.0) * store.vax_trans_factor
        emit = np.where(infectious, inf_w, 0.0)
        W = np.bincount(
            person_loc[placed], weights=emit[placed], minlength=store.num_locations
        )
        if ext_on:
            # n_internal = realized internal occupancy per room (all placed people).
            n_internal = np.bincount(person_loc[placed], minlength=store.num_locations)
            W = W + store.ext_ratio * n_internal * self.external_prevalence

        # Restrict the expensive trials (exp + RNG + scheduling) to actually
        # exposed susceptibles — those placed in a room with infectors (or external
        # pressure). This keeps the kernel cheap at low prevalence (few eligible)
        # and at saturation (numpy), instead of drawing for all N every timestep.
        loc = np.where(placed, person_loc, 0)
        room_W = W[loc]
        eligible = placed & (pstate == 0) & ((pstate & INVISIBLE) == 0) & (room_W > 0.0)
        elig_idx = np.nonzero(eligible)[0]
        if elig_idx.size == 0:
            return

        intake = np.where(masked[elig_idx], 0.50, 1.0) * (
            1.0 - store.vax_inf_protection[elig_idx]
        )
        mean_quanta = store.base_quanta[loc[elig_idx]] * room_W[elig_idx] * intake
        prob = 1.0 - np.exp(-mean_quanta)
        draws = np.random.random(elig_idx.size)
        hits = elig_idx[draws < prob]
        if hits.size == 0:
            return

        infection_mgr = context.infection_manager
        infected_set = infection_mgr.infected
        idx_to_person = store.idx_to_person
        variant_bucket = context.variant_infected[variant]
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )
        for i in hits:
            target = idx_to_person[i]
            target_id = target.id
            infected_set.add(target_id)
            infection_mgr.schedule_infection(
                context.simulator,
                context.event_queue,
                target,
                variant,
                ts,
                context.people_with_timelines,
            )
            variant_bucket[target_id] = infected_state_value
            store.snap_state[i] = infected_state_value
            context.simulator.log_event(
                "log_infection_event", target, None, None, variant, ts
            )

    def _ventilation_rate(self, place, is_household: bool) -> float:
        """Wells-Riley ventilation term Q (m^3/hr).

        Households use a fixed 3000; facilities use a fixed 150 unless
        area-aware ventilation is enabled, in which case Q scales with the
        facility's physical floor area (Q = ventilation_coeff * clamp(area)),
        making per-contact risk inversely proportional to area. Facilities with
        no known area fall back to 150, so flag-off behaviour is bit-identical.
        """
        if is_household:
            return 3000.0
        if self.area_aware_ventilation:
            area = getattr(place, "area", None)
            if area is not None and area > 0:
                lo, hi = self.area_clamp
                return self.ventilation_coeff * min(max(float(area), lo), hi)
        return 150.0

    def process_infection_event(
        self,
        context: SimulationContext,
        ts: int,
        poi_id: str,
        is_household: bool,
    ) -> None:
        if self.aggregate_transmission:
            self._aggregate_transmission_event(context, ts, poi_id, is_household)
            return

        place = context.simulator.get_location(str(poi_id), is_household)
        if not place:
            return

        if self._soa_engine:
            store = context.simulator.membership
            loc_idx = store.loc_to_idx.get((str(poi_id), is_household))
            if loc_idx is None:
                return
            occ = context.occupancy.occupants_of(loc_idx)
            if len(occ) == 0:
                return
            idx_to_person = store.idx_to_person
            snapshot = [idx_to_person[i] for i in occ]
        else:
            if not place.population:
                return
            snapshot = list(place.population.values())

        infectious_people = [person for person in snapshot if person.is_infectious()]
        if not infectious_people:
            return

        exposure_hours = context.simulator.timestep / 60.0
        infection_mgr = context.infection_manager
        multidisease = infection_mgr.multidisease
        infected_set = infection_mgr.infected
        susceptible = InfectionState.SUSCEPTIBLE
        infectious_flag = InfectionState.INFECTIOUS
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )

        # Wells-Riley constants — see infection_models.v6_wells_riley.CAT.
        # Inlined here so the inner loop avoids the per-call function-call
        # overhead and the per-call hasattr/debug branches. Equivalent math,
        # equivalent RNG consumption (one random.random() per CAT-eligible
        # pair). CAT was called with indoor = not is_household; the outdoor
        # branch multiplies ventilation_rate by 20.
        _QUANTA_RATE = 20.0
        _BREATHING_RATE = 0.5
        ventilation_rate = self._ventilation_rate(place, is_household)
        base_quanta_per_pair = (
            _QUANTA_RATE * _BREATHING_RATE * exposure_hours
        ) / ventilation_rate

        with self._timed("infection_event/infection_pair_iteration"):
            for infector in infectious_people:
                infector_id = infector.id
                infector_masked = infector.masked
                # get_vaccination_protection short-circuits on
                # vaccination_status=False; skip the call entirely when we
                # already know there's no protection (avoids the getattr
                # chain for the common unvaccinated case).
                infector_factor = 1.0
                if infector.vaccination_status:
                    infector_factor = 1.0 - get_vaccination_protection(infector, 'transmission')

                for variant, state in infector.states.items():
                    if not (state & infectious_flag):
                        continue
                    variant_bucket = context.variant_infected[variant]

                    for target in snapshot:
                        target_id = target.id
                        if target_id == infector_id:
                            continue
                        if target.invisible:
                            continue
                        target_states = target.states
                        if target_states.get(variant, susceptible) != susceptible:
                            continue
                        if not multidisease:
                            # Inline the any() so we can break early on first
                            # non-susceptible state without paying generator overhead.
                            skip = False
                            for s in target_states.values():
                                if s != susceptible:
                                    skip = True
                                    break
                            if skip:
                                continue

                        # Inlined Wells-Riley transmission probability.
                        target_masked = target.masked
                        if infector_masked:
                            if target_masked:
                                mask_factor = 0.15  # 1 - 0.85
                            else:
                                mask_factor = 0.30  # 1 - 0.70
                        elif target_masked:
                            mask_factor = 0.50  # 1 - 0.50
                        else:
                            mask_factor = 1.0

                        if target.vaccination_status:
                            target_protection = get_vaccination_protection(target, 'infection')
                        else:
                            target_protection = 0.0

                        mean_quanta = (
                            base_quanta_per_pair
                            * mask_factor
                            * infector_factor
                            * (1.0 - target_protection)
                        )
                        # P = 1 - exp(-mean_quanta); infect iff
                        # random.random() < P. Match the original CAT's RNG
                        # draw order exactly so simdata stays byte-identical.
                        if random.random() >= 1.0 - math.exp(-mean_quanta):
                            continue

                        logger.info(
                            "[Infection] %s -> %s @ %s (t=%d, variant=%s)",
                            infector_id,
                            target_id,
                            poi_id,
                            ts,
                            variant,
                        )

                        if target_id not in infected_set:
                            infected_set.add(target_id)
                        elif not multidisease:
                            continue

                        infection_mgr.schedule_infection(
                            context.simulator,
                            context.event_queue,
                            target,
                            variant,
                            ts,
                            context.people_with_timelines,
                        )
                        variant_bucket[target_id] = infected_state_value
                        context.simulator.log_event(
                            "log_infection_event",
                            target,
                            infector,
                            place,
                            variant,
                            ts,
                        )

        # The contact-pair loop is O(n^2) over place population. log_event is
        # a no-op when enable_logging is False, but the iteration still runs.
        # Skip it entirely when logging is off — saves ~8s per simulation at
        # ZIP 74002 / 168h.
        if not is_household and context.simulator.enable_logging:
            with self._timed("infection_event/contact_pair_logging"):
                for index, person_one in enumerate(snapshot):
                    for person_two in snapshot[index + 1:]:
                        context.simulator.log_event(
                            "log_contact_event",
                            person_one,
                            person_two,
                            place,
                            ts,
                        )

    def _aggregate_transmission_event(
        self,
        context: SimulationContext,
        ts: int,
        poi_id: str,
        is_household: bool,
    ) -> None:
        """O(infectors + susceptibles) per-location Wells-Riley kernel.

        The well-mixed-room form of Wells-Riley: a susceptible's risk depends on
        the *total* quanta in the room (the sum over infectors), not on pairwise
        encounters. We sum each infectious person's emission weight once per
        location/variant (W), then draw a single infection trial per susceptible
        against P = 1 - exp(-base * W * susceptible_intake).

        This yields the same marginal infection probability per susceptible as
        the pairwise kernel in process_infection_event, because for independent
        per-infector Poisson exposures
            1 - prod_i (1 - p_i) == 1 - exp(-sum_i lambda_i),
        while doing O(infectors + susceptibles) work instead of
        O(infectors * susceptibles). Mask/vaccination factors separate cleanly
        into infector-side (mask 0.30 / vax transmission) and susceptible-side
        (mask 0.50 / vax infection) weights, so base * w_i * u_j reproduces the
        pairwise per-pair quanta exactly (e.g. both-masked 0.30 * 0.50 = 0.15).

        It consumes a *different* RNG stream than the pairwise path (one draw per
        susceptible/variant, not one per pair), so output is NOT byte-identical
        and is validated by ensemble equivalence rather than the golden hash.
        Enabled via INFECTION_MODEL["aggregate_transmission"] / the simdata
        "aggregate_transmission" field.
        """
        place = context.simulator.get_location(str(poi_id), is_household)
        if not place:
            return

        if self._soa_engine:
            store = context.simulator.membership
            loc_idx = store.loc_to_idx.get((str(poi_id), is_household))
            if loc_idx is None:
                return
            occ = context.occupancy.occupants_of(loc_idx)
            if len(occ) == 0:
                return
            idx_to_person = store.idx_to_person
            snapshot = [idx_to_person[i] for i in occ]
        else:
            if not place.population:
                return
            snapshot = list(place.population.values())

        infectious_people = [person for person in snapshot if person.is_infectious()]
        if not infectious_people:
            return

        exposure_hours = context.simulator.timestep / 60.0
        infection_mgr = context.infection_manager
        multidisease = infection_mgr.multidisease
        infected_set = infection_mgr.infected
        susceptible = InfectionState.SUSCEPTIBLE
        infectious_flag = InfectionState.INFECTIOUS
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )

        _QUANTA_RATE = 20.0
        _BREATHING_RATE = 0.5
        ventilation_rate = self._ventilation_rate(place, is_household)
        base_quanta = (_QUANTA_RATE * _BREATHING_RATE * exposure_hours) / ventilation_rate

        with self._timed("infection_event/aggregate_iteration"):
            # 1) Sum infector emission weights per variant — O(infectors).
            #    w_i = infector mask factor (0.30 masked, else 1.0) * infector
            #    vaccination transmission factor (same factors as the pairwise
            #    kernel, just summed instead of applied per pair).
            emission: dict[str, float] = {}
            for infector in infectious_people:
                infector_mask_factor = 0.30 if infector.masked else 1.0
                if infector.vaccination_status:
                    infector_factor = 1.0 - get_vaccination_protection(infector, 'transmission')
                else:
                    infector_factor = 1.0
                w_i = infector_mask_factor * infector_factor
                for variant, state in infector.states.items():
                    if state & infectious_flag:
                        emission[variant] = emission.get(variant, 0.0) + w_i

            if not emission:
                return

            # 2) One infection trial per susceptible per active variant against
            #    the summed room concentration — O(susceptibles).
            for target in snapshot:
                if target.invisible:
                    continue
                target_states = target.states
                if not multidisease:
                    skip = False
                    for s in target_states.values():
                        if s != susceptible:
                            skip = True
                            break
                    if skip:
                        continue

                target_mask_factor = 0.50 if target.masked else 1.0
                if target.vaccination_status:
                    target_protection = get_vaccination_protection(target, 'infection')
                else:
                    target_protection = 0.0
                # Susceptible intake weight u_j; the susceptible's protection is
                # constant across infectors, so it is computed once here rather
                # than once per pair as in the pairwise kernel.
                intake = target_mask_factor * (1.0 - target_protection)
                if intake <= 0.0:
                    continue

                target_id = target.id
                for variant, w_sum in emission.items():
                    if target_states.get(variant, susceptible) != susceptible:
                        continue
                    mean_quanta = base_quanta * w_sum * intake
                    if mean_quanta <= 0.0:
                        continue
                    if random.random() >= 1.0 - math.exp(-mean_quanta):
                        continue

                    logger.info(
                        "[Infection] (room) -> %s @ %s (t=%d, variant=%s)",
                        target_id, poi_id, ts, variant,
                    )

                    if target_id not in infected_set:
                        infected_set.add(target_id)
                    elif not multidisease:
                        continue

                    infection_mgr.schedule_infection(
                        context.simulator,
                        context.event_queue,
                        target,
                        variant,
                        ts,
                        context.people_with_timelines,
                    )
                    context.variant_infected[variant][target_id] = infected_state_value
                    context.simulator.log_event(
                        "log_infection_event",
                        target,
                        None,
                        place,
                        variant,
                        ts,
                    )

                    if not multidisease:
                        # First infection claims this susceptible for the
                        # timestep, mirroring the pairwise infected_set guard.
                        break

        # Contact-pair logging is O(n^2) and a no-op when logging is off; skip
        # the iteration entirely in that case (identical to the pairwise path).
        if not is_household and context.simulator.enable_logging:
            with self._timed("infection_event/contact_pair_logging"):
                for index, person_one in enumerate(snapshot):
                    for person_two in snapshot[index + 1:]:
                        context.simulator.log_event(
                            "log_contact_event",
                            person_one,
                            person_two,
                            place,
                            ts,
                        )

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
        return result
