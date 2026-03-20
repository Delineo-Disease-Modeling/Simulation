from __future__ import annotations

import logging
import os
import random
import heapq
from bisect import bisect_right
from math import ceil
from typing import Optional, Callable

from .pap import Person, Household, Facility, InfectionState, InfectionTimeline, VaccinationState
from .infectionmgr import InfectionManager
from .config import DELINEO, SIMULATION, INFECTION_MODEL
from .data_interface import StreamDataLoader
from .infection_models.v6_wells_riley import CAT
from .logger import SimulationLogger
from .io import IncrementalJSONWriter

logger = logging.getLogger(__name__)

POI_TYPES = [("homes", True), ("places", False)]


class DiseaseSimulator:
    """Core simulator state: holds people, locations, and intervention weights."""

    def __init__(
        self,
        timestep: int = SIMULATION["default_timestep"],
        intervention_weights: Optional[list[dict]] = None,
        enable_logging: bool = True,
        log_dir: str = "simulation_logs",
    ) -> None:
        self.timestep = timestep
        self.iv_weights = intervention_weights or []
        # Pre-sort by time for bisect lookup
        self.iv_weights.sort(key=lambda w: w["time"])
        self._iv_times = [w["time"] * 60 for w in self.iv_weights]
        self.people: dict[str, Person] = {}
        self.households: dict[str, Household] = {}
        self.facilities: dict[str, Facility] = {}
        self.enable_logging = enable_logging
        self.logger: Optional[SimulationLogger] = (
            SimulationLogger(log_dir, enable_logging) if enable_logging else None
        )

    def get_interventions(self, curtime: int) -> dict:
        t = int(curtime)
        idx = bisect_right(self._iv_times, t) - 1
        return self.iv_weights[max(idx, 0)]

    def add_person(self, person: Person) -> None:
        self.people[str(person.id)] = person

    def get_person(self, pid: str) -> Optional[Person]:
        return self.people.get(str(pid))

    def add_household(self, household: Household) -> None:
        self.households[str(household.id)] = household

    def get_household(self, hid: str) -> Optional[Household]:
        return self.households.get(str(hid))

    def add_facility(self, facility: Facility) -> None:
        self.facilities[str(facility.id)] = facility

    def get_facility(self, fid: str) -> Optional[Facility]:
        return self.facilities.get(str(fid))

    def get_location(self, loc_id: str, is_household: bool):
        return self.get_household(loc_id) if is_household else self.get_facility(loc_id)

    def log_event(self, method: str, *args, **kwargs) -> None:
        """Call a logger method if logging is enabled."""
        if self.enable_logging and self.logger:
            getattr(self.logger, method)(*args, **kwargs)


class EventQueue:
    """Manages the priority queue, infectious registry, and stream buffering.

    Uses a reverse person index (person_id → [(ts, poi_id, is_hh)]) built at
    ingest time so that both ``register_infectious`` and ``_ingest_patterns``
    are O(1) per person instead of scanning every POI.
    """

    def __init__(self, stream_iterator) -> None:
        self._queue: list[tuple] = []
        self._queued: set[tuple] = set()
        self._registry: dict[str, list[tuple]] = {}
        self._buffer: dict[str, dict] = {}
        # Reverse index: person_id → [(timestep, poi_id, is_household)]
        self._person_index: dict[str, list[tuple[int, str, bool]]] = {}
        self._stream = stream_iterator
        self._stream_exhausted = False

    @property
    def buffer(self) -> dict[str, dict]:
        return self._buffer

    def __bool__(self) -> bool:
        return bool(self._queue)

    def __len__(self) -> int:
        return len(self._queue)

    def peek(self) -> tuple:
        return self._queue[0]

    def pop(self) -> tuple:
        entry = heapq.heappop(self._queue)
        self._queued.discard(entry)
        return entry

    def enqueue(self, timestep: int, poi_id: str, is_household: bool) -> None:
        key = (timestep, str(poi_id), is_household)
        if key not in self._queued:
            heapq.heappush(self._queue, key)
            self._queued.add(key)

    def register_infectious(self, person_id: str, variant: str, start: int, end: int) -> None:
        """Record an infectious window and enqueue matching buffered visits via the index."""
        pid = str(person_id)
        self._registry.setdefault(pid, []).append((variant, start, end))

        # O(k) where k = number of visits for this person already in the buffer
        for ts, poi_id, is_hh in self._person_index.get(pid, ()):
            if start <= ts <= end:
                self.enqueue(ts, poi_id, is_hh)

    @property
    def registry(self) -> dict[str, list[tuple]]:
        return self._registry

    def _ingest_patterns(self, patterns: dict) -> None:
        """Add pattern data to the buffer, build the person index, and scan against the registry."""
        for ts_str, data in patterns.items():
            self._buffer[ts_str] = data
            if not isinstance(data, dict):
                continue
            ts = int(ts_str)
            for poi_type, is_hh in POI_TYPES:
                for poi_id, person_ids in data.get(poi_type, {}).items():
                    poi_id_str = str(poi_id)
                    for pid in person_ids:
                        pid_str = str(pid)
                        # Build reverse index entry
                        self._person_index.setdefault(pid_str, []).append((ts, poi_id_str, is_hh))
                        # If this person is already registered as infectious, enqueue directly
                        if pid_str in self._registry:
                            for _, inf_start, inf_end in self._registry[pid_str]:
                                if inf_start <= ts <= inf_end:
                                    self.enqueue(ts, poi_id_str, is_hh)
                                    break

    def _read_stream_chunk(self) -> bool:
        """Read one chunk from the stream. Returns False if exhausted."""
        if self._stream_exhausted:
            return False
        try:
            chunk = next(self._stream)
            if "patterns" in chunk:
                self._ingest_patterns(chunk["patterns"])
            return True
        except StopIteration:
            self._stream_exhausted = True
            return False

    def buffer_until(self, target_ts: int) -> None:
        """Read from stream until target timestep is buffered or stream ends."""
        target_str = str(target_ts)
        while target_str not in self._buffer:
            if not self._read_stream_chunk():
                break

    def drain_stream(self) -> None:
        """Read all remaining stream data into the buffer."""
        while self._read_stream_chunk():
            pass

    def consume_pattern(self, ts_str: str) -> None:
        """Free a consumed pattern from the buffer and its person index entries."""
        self._buffer.pop(ts_str, None)


# MOVEMENT

def move_people(simulator: DiseaseSimulator, items, is_household: bool, current_timestep: str, interventions: Optional[dict] = None) -> None:
    if interventions is None:
        interventions = simulator.get_interventions(current_timestep)

    for loc_id, people in items:
        place = simulator.get_location(str(loc_id), is_household)
        if place is None:
            raise Exception(f"Place {loc_id} was not found in the simulator data (household={is_household})")

        for person_id in people:
            person = simulator.get_person(person_id)
            if person is None:
                continue

            original_location = person.location

            # Facility-only intervention checks
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
                    simulator.log_event("log_intervention_effect", person, "capacity_limit", "redirected_home", current_timestep, place)
                if hit_lockdown:
                    simulator.log_event("log_intervention_effect", person, "lockdown", "stayed_home", current_timestep, place)
                if self_iso:
                    simulator.log_event("log_intervention_effect", person, "self_isolation", "stayed_home", current_timestep, place)

                if at_capacity or hit_lockdown or self_iso:
                    person.location.remove_member(person_id)
                    person.household.add_member(person)
                    if original_location.id != person.household.id:
                        reason = "capacity_limit" if at_capacity else ("lockdown" if hit_lockdown else "self_isolation")
                        simulator.log_event("log_movement", person, original_location, person.household, current_timestep, reason)
                    person.location = person.household
                    continue

            person.location.remove_member(person_id)
            place.add_member(person)
            if original_location.id != place.id:
                simulator.log_event("log_movement", person, original_location, place, current_timestep, "normal")
            person.location = place


# DATA LOADING HELPER FUNCS

def _parse_cbg(data) -> Optional[str]:
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data.get("cbg")
    return data


def _parse_facility(fid: str, data) -> Facility:
    if isinstance(data, list) and len(data) >= 2:
        cbg = data[0] if data else None
        label = data[1] if len(data) > 1 else None
        capacity = data[2] if len(data) > 2 else -1
    elif isinstance(data, dict):
        cbg = data.get("cbg")
        label = data.get("label", f"Place_{fid}")
        capacity = data.get("capacity", -1)
    else:
        cbg = data
        label = f"Place_{fid}"
        capacity = -1

    if isinstance(capacity, str):
        try:
            capacity = int(capacity)
        except ValueError:
            capacity = -1

    return Facility(str(fid), cbg, label, capacity)


# MAIN SIMULATION / ENTRY POINT

def run_simulator(
    simdata: dict,
    enable_logging: bool = True,
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> dict:
    logger.info("QUEUE-BASED SIMULATION START (max_length=%s)", simdata["length"])

    def _progress(current_step, max_steps, message=None):
        if progress_callback:
            progress_callback(current_step, max_steps, message)

    if not simdata["randseed"]:
        random.seed(0)

    # Step 1: Load Static Data (bulk mode — no per-key JSON round-trip)
    _progress(0, 1, "Loading population data from server...")
    url = f"{DELINEO['DB_URL']}patterns/{simdata['czone_id']}?length={simdata['length']}"

    try:
        logger.info("Fetching bulk data...")
        papdata, patterns_data = StreamDataLoader.load_bulk(url, timeout=360)
    except Exception as e:
        logger.exception("Failed to load data")
        return {"error": str(e)}

    people_data = papdata.get("people", {})
    homes_data = papdata.get("homes", {})
    places_data = papdata.get("places", {})
    logger.info("Loaded: %d people, %d homes, %d places", len(people_data), len(homes_data), len(places_data))

    # Initialize simulator
    _progress(0, 1, f"Building world: {len(homes_data)} homes, {len(places_data)} places...")
    simulator = DiseaseSimulator(
        timestep=60,
        enable_logging=enable_logging,
        intervention_weights=simdata["interventions"],
    )

    # Build locations
    for hid, data in homes_data.items():
        simulator.add_household(Household(_parse_cbg(data), str(hid)))

    for fid, data in places_data.items():
        simulator.add_facility(_parse_facility(fid, data))

    # Initialize event queue — pre-populate with all patterns (already in memory)
    sim_length = simdata["length"]
    eq = EventQueue(iter([]))  # no stream; data already loaded
    # Filter patterns by simulation length and ingest
    filtered = {k: v for k, v in patterns_data.items() if int(k) <= sim_length}
    eq._ingest_patterns(filtered)

    # Build people & seed infections
    _progress(0, 1, f"Initializing {len(people_data)} people & seeding infections...")
    variants = SIMULATION["variants"]
    seed_ids = random.sample(list(people_data.keys()), min(len(people_data), len(variants)))
    variant_assignments = dict(zip(seed_ids, variants))
    iv_thresholds = [ceil((100.0 * i) / len(people_data)) / 100.0 for i in range(len(people_data))]

    for pid, data in people_data.items():
        household = simulator.get_household(str(data["home"]))
        if household is None:
            continue

        person = Person(pid, data["sex"], data["age"], household)

        if str(pid) in variant_assignments:
            variant = variant_assignments[str(pid)]
            person.states[variant] = InfectionState.INFECTED | InfectionState.INFECTIOUS
            duration = INFECTION_MODEL["initial_timeline"]["duration"]
            person.timeline = {
                variant: {
                    InfectionState.INFECTED: InfectionTimeline(0, duration),
                    InfectionState.INFECTIOUS: InfectionTimeline(0, duration),
                }
            }
            eq.register_infectious(pid, variant, 0, duration)
            simulator.log_event("log_infection_event", person, None, person.household, variant, 0)

        person.iv_threshold = random.choice(iv_thresholds)
        iv_thresholds.remove(person.iv_threshold)

        simulator.add_person(person)
        household.add_member(person)
        simulator.log_event("log_person_demographics", person, 0)

    infectionmgr = InfectionManager(
        infected_ids=[
            p.id for p in simulator.people.values()
            for d in variants
            if p.states.get(d, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE
        ]
    )

    # Step 2: Queue-Based Simulation Loop
    simdata_writer = None
    patterns_writer = None
    simdata_json: Optional[dict] = {} if not output_dir else None
    patterns_json: Optional[dict] = {} if not output_dir else None

    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        simdata_writer = IncrementalJSONWriter(os.path.join(output_dir, "simdata.json.gz"))
        patterns_writer = IncrementalJSONWriter(os.path.join(output_dir, "patterns.json.gz"))

    variant_infected = {v: {} for v in variants}
    max_len = simdata["length"]
    processed_count = 0
    last_movement_ts = -simulator.timestep
    # Track people who have timelines (need update_state); start with seeded
    people_with_timelines: set[str] = {
        p.id for p in simulator.people.values() if p.timeline
    }
    last_interventions: Optional[dict] = None

    _progress(0, max_len, "Running simulation...")
    logger.info("Starting queue-based simulation (queue size: %d)", len(eq))

    def write_snapshot(ts_str: str) -> None:
        """Write movement + infection-state snapshots for a timestep."""
        movement = {
            "homes": {
                str(h.id): list(h.population.keys())
                for h in simulator.households.values() if h.population
            },
            "places": {
                str(f.id): list(f.population.keys())
                for f in simulator.facilities.values() if f.population
            },
        }
        result = {v: dict(inf) for v, inf in variant_infected.items()}

        if patterns_writer:
            patterns_writer.add(ts_str, movement)
            simdata_writer.add(ts_str, result)
        else:
            patterns_json[ts_str] = movement
            simdata_json[ts_str] = result

    def apply_interventions(person: Person, interventions: dict, ts_str: str) -> None:
        """Apply mask and vaccine interventions to a single person."""
        if person.iv_threshold <= interventions["mask"]:
            if not person.is_masked():
                simulator.log_event("log_intervention_effect", person, "mask", "complied", ts_str)
            person.set_masked(True)

        if person.iv_threshold <= interventions["vaccine"]:
            min_d = SIMULATION["vaccination_options"]["min_doses"]
            max_d = SIMULATION["vaccination_options"]["max_doses"]
            doses = random.randint(min_d, max_d)
            if person.get_vaccinated() == VaccinationState.NONE:
                simulator.log_event("log_intervention_effect", person, "vaccine", f"received_{doses}_doses", ts_str)
            person.set_vaccinated(VaccinationState(doses))

    def process_movement_up_to(target_ts: int) -> None:
        """Apply movement for every timestep up to target_ts (inclusive)."""
        nonlocal last_movement_ts, processed_count, last_interventions

        ts = last_movement_ts + simulator.timestep
        while ts <= target_ts:
            _progress(ts, max_len)
            ts_str = str(ts)
            processed_count += 1

            if ts_str in eq.buffer:
                data = eq.buffer[ts_str]
                interventions = simulator.get_interventions(ts_str)

                # Only update_state for people with infection timelines
                for pid_str in people_with_timelines:
                    person = simulator.get_person(pid_str)
                    if person:
                        person.update_state(ts_str, variants)

                # Only re-apply interventions when they change
                if interventions is not last_interventions:
                    last_interventions = interventions
                    for person in simulator.people.values():
                        apply_interventions(person, interventions, ts_str)

                if isinstance(data, dict):
                    if "homes" in data:
                        move_people(simulator, data["homes"].items(), True, ts_str, interventions)
                    if "places" in data:
                        move_people(simulator, data["places"].items(), False, ts_str, interventions)

            # Update variant tracking — only check registered people
            for pid_str in eq.registry:
                person = simulator.get_person(pid_str)
                if not person:
                    continue
                for disease in variants:
                    state = person.states.get(disease, InfectionState.SUSCEPTIBLE)
                    if state != InfectionState.SUSCEPTIBLE:
                        variant_infected[disease][pid_str] = int(state.value)

            write_snapshot(ts_str)
            eq.consume_pattern(ts_str)

            last_movement_ts = ts
            ts += simulator.timestep

    # Main queue loop
    while eq:
        next_ts = eq.peek()[0]
        if next_ts > max_len:
            break

        if next_ts % SIMULATION["log_interval"] == 0:
            logger.info("Queue event at t=%d (queue=%d, buffer=%d)", next_ts, len(eq), len(eq.buffer))

        process_movement_up_to(next_ts)

        # Process all events at this timestep
        while eq and eq.peek()[0] == next_ts:
            ts, poi_id, is_hh = eq.pop()

            place = simulator.get_location(str(poi_id), is_hh)
            if not place or not place.population:  # dict is falsy when empty
                continue

            _run_infection_at_poi(simulator, infectionmgr, eq, place, poi_id, is_hh, ts, variant_infected, people_with_timelines)

    # Fill remaining timesteps for complete output
    process_movement_up_to(max_len)

    _progress(max_len, max_len, "Simulation complete, writing output...")
    logger.info("SIMULATION COMPLETE (%d timesteps processed)", processed_count)

    if simdata_writer:
        simdata_writer.close()
    if patterns_writer:
        patterns_writer.close()

    if simulator.enable_logging and simulator.logger:
        logger.info("Exporting logs...")
        simulator.logger.export_logs_to_csv()
        simulator.logger.generate_summary_report()
        simulator.logger.graphic_analysis()

    if output_dir:
        return {
            "simdata": os.path.join(output_dir, "simdata.json.gz"),
            "patterns": os.path.join(output_dir, "patterns.json.gz"),
        }
    return {"movement": patterns_json, "result": simdata_json}


def _run_infection_at_poi(
    simulator: DiseaseSimulator,
    infectionmgr: InfectionManager,
    eq: EventQueue,
    place,
    poi_id: str,
    is_hh: bool,
    ts: int,
    variant_infected: dict[str, dict],
    people_with_timelines: Optional[set[str]] = None,
) -> None:
    """Run targeted infection checks at a single POI for one timestep."""
    snapshot = list(place.population.values())

    # Pre-filter: only people who are actually infectious for at least one variant
    infectious = [p for p in snapshot if p.is_infectious()]
    if not infectious:
        return

    exposure_hours = simulator.timestep / 60.0

    for infector in infectious:
        for variant, state in infector.states.items():
            if not (state & InfectionState.INFECTIOUS):
                continue

            for target in snapshot:
                if target.id == infector.id or target.invisible:
                    continue
                if target.states.get(variant, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE:
                    continue
                if not infectionmgr.multidisease and any(
                    s != InfectionState.SUSCEPTIBLE for s in target.states.values()
                ):
                    continue

                if not CAT(
                    target,
                    indoor=not is_hh,
                    exposure_hours=exposure_hours,
                    infector=infector,
                    infector_masked=infector.is_masked(),
                    susceptible_masked=target.is_masked(),
                ):
                    continue

                logger.info("[Infection] %s -> %s @ %s (t=%d, variant=%s)", infector.id, target.id, poi_id, ts, variant)

                if target.id not in infectionmgr.infected:
                    infectionmgr.infected.add(target.id)

                timeline = infectionmgr.create_timeline(target, variant, ts)
                simulator.people[target.id].timeline = timeline
                if people_with_timelines is not None:
                    people_with_timelines.add(target.id)

                if variant in timeline and InfectionState.INFECTIOUS in timeline[variant]:
                    inf_tl = timeline[variant][InfectionState.INFECTIOUS]
                    eq.register_infectious(target.id, variant, inf_tl.start, inf_tl.end)

                variant_infected[variant][target.id] = int(
                    (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
                )
                simulator.log_event("log_infection_event", target, infector, place, variant, ts)

    # Log contacts at facilities only
    if not is_hh:
        for i, p1 in enumerate(snapshot):
            for p2 in snapshot[i + 1:]:
                simulator.log_event("log_contact_event", p1, p2, place, ts)
