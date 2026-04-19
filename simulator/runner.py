from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Callable, Optional

from .config import DELINEO, SIMULATION
from .data_interface import StreamDataLoader
from .event_queue import EventQueue
from .infection_models.v6_wells_riley import CAT
from .infectionmgr import InfectionManager
from .pap import InfectionState, Person, VaccinationState
from .snapshots import (
    SimulationSnapshotWriter,
    build_infection_snapshot,
    build_movement_snapshot,
)
from .world import (
    DiseaseSimulator,
    build_event_queue,
    build_locations,
    collect_infected_ids,
    seed_population,
)

logger = logging.getLogger(__name__)


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
    people_with_timelines: set[str]
    max_length: int
    processed_count: int = 0
    last_movement_ts: int = 0
    last_interventions: Optional[dict] = None


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
    if person.iv_threshold <= interventions["mask"]:
        if not person.is_masked():
            simulator.log_event("log_intervention_effect", person, "mask", "complied", ts_str)
        person.set_masked(True)

    if person.iv_threshold <= interventions["vaccine"]:
        min_doses = SIMULATION["vaccination_options"]["min_doses"]
        max_doses = SIMULATION["vaccination_options"]["max_doses"]
        doses = random.randint(min_doses, max_doses)
        if person.get_vaccinated() == VaccinationState.NONE:
            simulator.log_event(
                "log_intervention_effect",
                person,
                "vaccine",
                f"received_{doses}_doses",
                ts_str,
            )
        person.set_vaccinated(VaccinationState(doses))


class SimulationRunner:
    def __init__(
        self,
        simdata: dict,
        enable_logging: bool = True,
        output_dir: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        data_loader: Callable = StreamDataLoader.load_bulk,
    ) -> None:
        self.simdata = simdata
        self.enable_logging = enable_logging
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self.data_loader = data_loader

    def run(self) -> dict:
        logger.info("QUEUE-BASED SIMULATION START (max_length=%s)", self.simdata["length"])
        self._seed_random()

        try:
            loaded = self.load_data()
        except Exception as exc:
            logger.exception("Failed to load data")
            return {"error": str(exc)}

        context = self.build_context(loaded)
        self.run_queue(context)
        return self.finalize(context)

    def _progress(self, current_step, max_steps, message=None) -> None:
        if self.progress_callback:
            self.progress_callback(current_step, max_steps, message)

    def _seed_random(self) -> None:
        if not self.simdata["randseed"]:
            random.seed(0)

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
        return LoadedSimulationData(
            people_data=people_data,
            homes_data=homes_data,
            places_data=places_data,
            patterns_data=patterns_data,
        )

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
        build_locations(simulator, loaded.homes_data, loaded.places_data)
        event_queue = build_event_queue(loaded.patterns_data, self.simdata["length"])

        self._progress(
            0,
            1,
            f"Initializing {len(loaded.people_data)} people & seeding infections...",
        )
        variants = SIMULATION["variants"]
        seeded_population = seed_population(
            simulator,
            loaded.people_data,
            variants,
            event_queue,
        )
        infection_manager = InfectionManager(
            infected_ids=collect_infected_ids(simulator, variants)
        )

        return SimulationContext(
            simulator=simulator,
            event_queue=event_queue,
            infection_manager=infection_manager,
            snapshot_writer=SimulationSnapshotWriter(self.output_dir),
            variants=variants,
            variant_infected={variant: {} for variant in variants},
            people_with_timelines=seeded_population.people_with_timelines,
            max_length=self.simdata["length"],
            last_movement_ts=-simulator.timestep,
        )

    def run_queue(self, context: SimulationContext) -> None:
        self._progress(0, context.max_length, "Running simulation...")
        logger.info(
            "Starting queue-based simulation (queue size: %d)",
            len(context.event_queue),
        )

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
            self.process_infections_at_timestep(context, next_ts)

        self.process_movement_up_to(context, context.max_length)
        self._progress(context.max_length, context.max_length, "Simulation complete, writing output...")
        logger.info("SIMULATION COMPLETE (%d timesteps processed)", context.processed_count)

    def process_movement_up_to(self, context: SimulationContext, target_ts: int) -> None:
        ts = context.last_movement_ts + context.simulator.timestep
        while ts <= target_ts:
            self._progress(ts, context.max_length)
            ts_str = str(ts)
            context.processed_count += 1

            if ts_str in context.event_queue.buffer:
                timestep_data = context.event_queue.buffer[ts_str]
                interventions = context.simulator.get_interventions(ts_str)
                self.update_people_states(context, ts_str)

                if interventions is not context.last_interventions:
                    context.last_interventions = interventions
                    for person in context.simulator.people.values():
                        apply_person_interventions(
                            context.simulator,
                            person,
                            interventions,
                            ts_str,
                        )

                if isinstance(timestep_data, dict):
                    if "homes" in timestep_data:
                        move_people(
                            context.simulator,
                            timestep_data["homes"].items(),
                            True,
                            ts_str,
                            interventions,
                        )
                    if "places" in timestep_data:
                        move_people(
                            context.simulator,
                            timestep_data["places"].items(),
                            False,
                            ts_str,
                            interventions,
                        )

            self.update_variant_tracking(context)
            self.write_snapshot(context, ts_str)
            context.event_queue.consume_pattern(ts_str)
            context.last_movement_ts = ts
            ts += context.simulator.timestep

    def update_people_states(self, context: SimulationContext, ts_str: str) -> None:
        for pid_str in context.people_with_timelines:
            person = context.simulator.get_person(pid_str)
            if person:
                person.update_state(ts_str, context.variants)

    def update_variant_tracking(self, context: SimulationContext) -> None:
        for pid_str in context.event_queue.registry:
            person = context.simulator.get_person(pid_str)
            if not person:
                continue
            for disease in context.variants:
                state = person.states.get(disease, InfectionState.SUSCEPTIBLE)
                if state != InfectionState.SUSCEPTIBLE:
                    context.variant_infected[disease][pid_str] = int(state.value)

    def write_snapshot(self, context: SimulationContext, ts_str: str) -> None:
        if context.simulator.enable_logging and context.simulator.logger:
            for household in context.simulator.households.values():
                if household.population:
                    context.simulator.logger.log_location_state(household, ts_str)
            for facility in context.simulator.facilities.values():
                if facility.population:
                    context.simulator.logger.log_location_state(facility, ts_str)

        context.snapshot_writer.write(
            ts_str,
            build_movement_snapshot(context.simulator),
            build_infection_snapshot(context.variant_infected),
        )

    def process_infections_at_timestep(self, context: SimulationContext, timestep: int) -> None:
        while context.event_queue and context.event_queue.peek()[0] == timestep:
            ts, poi_id, is_household = context.event_queue.pop()
            self.process_infection_event(context, ts, poi_id, is_household)

    def process_infection_event(
        self,
        context: SimulationContext,
        ts: int,
        poi_id: str,
        is_household: bool,
    ) -> None:
        place = context.simulator.get_location(str(poi_id), is_household)
        if not place or not place.population:
            return

        snapshot = list(place.population.values())
        infectious_people = [person for person in snapshot if person.is_infectious()]
        if not infectious_people:
            return

        exposure_hours = context.simulator.timestep / 60.0

        for infector in infectious_people:
            for variant, state in infector.states.items():
                if not (state & InfectionState.INFECTIOUS):
                    continue

                for target in snapshot:
                    if target.id == infector.id or target.invisible:
                        continue
                    if target.states.get(variant, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE:
                        continue
                    if not context.infection_manager.multidisease and any(
                        disease_state != InfectionState.SUSCEPTIBLE
                        for disease_state in target.states.values()
                    ):
                        continue

                    if not CAT(
                        target,
                        indoor=not is_household,
                        exposure_hours=exposure_hours,
                        infector=infector,
                        infector_masked=infector.is_masked(),
                        susceptible_masked=target.is_masked(),
                    ):
                        continue

                    logger.info(
                        "[Infection] %s -> %s @ %s (t=%d, variant=%s)",
                        infector.id,
                        target.id,
                        poi_id,
                        ts,
                        variant,
                    )

                    if target.id not in context.infection_manager.infected:
                        context.infection_manager.infected.add(target.id)
                    elif not context.infection_manager.multidisease:
                        continue

                    context.infection_manager.schedule_infection(
                        context.simulator,
                        context.event_queue,
                        target,
                        variant,
                        ts,
                        context.people_with_timelines,
                    )
                    context.variant_infected[variant][target.id] = int(
                        (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
                    )
                    context.simulator.log_event(
                        "log_infection_event",
                        target,
                        infector,
                        place,
                        variant,
                        ts,
                    )

        if not is_household:
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

        return context.snapshot_writer.result()
