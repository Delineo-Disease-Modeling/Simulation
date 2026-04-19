from __future__ import annotations

import random
from dataclasses import dataclass
from math import ceil
from bisect import bisect_right
from typing import Optional

from .config import INFECTION_MODEL, SIMULATION
from .event_queue import EventQueue
from .logger import SimulationLogger
from .pap import Facility, Household, InfectionState, InfectionTimeline, Person


class DiseaseSimulator:
    """Core world state: people, locations, interventions, and optional logging."""

    def __init__(
        self,
        timestep: int = SIMULATION["default_timestep"],
        intervention_weights: Optional[list[dict]] = None,
        enable_logging: bool = True,
        log_dir: str = "simulation_logs",
    ) -> None:
        self.timestep = timestep
        self.iv_weights = intervention_weights or []
        self.iv_weights.sort(key=lambda weight: weight["time"])
        self._iv_times = [weight["time"] * 60 for weight in self.iv_weights]
        self.people: dict[str, Person] = {}
        self.households: dict[str, Household] = {}
        self.facilities: dict[str, Facility] = {}
        self.enable_logging = enable_logging
        self.logger: Optional[SimulationLogger] = (
            SimulationLogger(log_dir, enable_logging) if enable_logging else None
        )

    def get_interventions(self, curtime: int | str) -> dict:
        idx = bisect_right(self._iv_times, int(curtime)) - 1
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
        if self.enable_logging and self.logger:
            getattr(self.logger, method)(*args, **kwargs)


@dataclass(frozen=True)
class PopulationBuildResult:
    people_with_timelines: set[str]


def parse_cbg(data) -> Optional[str]:
    if isinstance(data, list):
        return data[0] if data else None
    if isinstance(data, dict):
        return data.get("cbg")
    return data


def parse_facility(fid: str, data) -> Facility:
    if isinstance(data, list) and len(data) >= 2:
        cbg = data[0] if data else None
        label = data[1] if len(data) > 1 else None
        capacity = data[2] if len(data) > 2 else -1
        street_address = None
    elif isinstance(data, dict):
        cbg = data.get("cbg")
        label = data.get("label", f"Place_{fid}")
        capacity = data.get("capacity", -1)
        street_address = data.get("street_address")
    else:
        cbg = data
        label = f"Place_{fid}"
        capacity = -1
        street_address = None

    if isinstance(capacity, str):
        try:
            capacity = int(capacity)
        except ValueError:
            capacity = -1

    return Facility(str(fid), cbg, label, capacity, street_address=street_address)


def build_locations(simulator: DiseaseSimulator, homes_data: dict, places_data: dict) -> None:
    for hid, data in homes_data.items():
        simulator.add_household(Household(parse_cbg(data), str(hid)))

    for fid, data in places_data.items():
        simulator.add_facility(parse_facility(fid, data))


def build_event_queue(patterns_data: dict, max_length: int) -> EventQueue:
    event_queue = EventQueue(iter(()))
    filtered_patterns = {
        timestep: data
        for timestep, data in patterns_data.items()
        if int(timestep) <= max_length
    }
    event_queue.ingest_patterns(filtered_patterns)
    return event_queue


def seed_population(
    simulator: DiseaseSimulator,
    people_data: dict,
    variants: list[str],
    event_queue: EventQueue,
) -> PopulationBuildResult:
    seed_ids = random.sample(list(people_data.keys()), min(len(people_data), len(variants)))
    variant_assignments = dict(zip(seed_ids, variants))
    iv_thresholds = [
        ceil((100.0 * index) / len(people_data)) / 100.0
        for index in range(len(people_data))
    ]
    people_with_timelines: set[str] = set()

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
            event_queue.register_infectious(pid, variant, 0, duration)
            people_with_timelines.add(person.id)
            simulator.log_event("log_infection_event", person, None, person.household, variant, 0)

        person.iv_threshold = random.choice(iv_thresholds)
        iv_thresholds.remove(person.iv_threshold)

        simulator.add_person(person)
        household.add_member(person)
        simulator.log_event("log_person_demographics", person, 0)

    return PopulationBuildResult(people_with_timelines=people_with_timelines)


def collect_infected_ids(simulator: DiseaseSimulator, variants: list[str]) -> list[str]:
    return [
        person.id
        for person in simulator.people.values()
        for disease in variants
        if person.states.get(disease, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE
    ]
