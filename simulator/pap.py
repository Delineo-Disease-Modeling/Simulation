from __future__ import annotations

from enum import Flag, Enum
from typing import Optional

# Enums & small data classes

class InfectionState(Flag):
    SUSCEPTIBLE = 0
    INFECTED = 1
    INFECTIOUS = 2
    SYMPTOMATIC = 4
    HOSPITALIZED = 8
    RECOVERED = 16
    REMOVED = 32


class VaccinationState(Enum):
    NONE = 0
    PARTIAL = 1
    IMMUNIZED = 2


class InfectionTimeline:
    __slots__ = ("start", "end")

    def __init__(self, start: int, end: int) -> None:
        self.start = int(start)
        self.end = int(end)

    def __repr__(self) -> str:
        return f"InfectionTimeline({self.start}, {self.end})"

    def contains(self, time: int) -> bool:
        return self.start <= int(time) <= self.end


# Locations

class Location:
    """Unified base for any place a person can be (households & facilities).

    Every location has an *id*, a *cbg* (census block group), an optional
    *label*, a *capacity* (-1 = unlimited), and a *location_type* string
    """

    def __init__(
        self,
        id: str,
        cbg: Optional[str] = None,
        label: Optional[str] = None,
        capacity: int = -1,
        location_type: str = "unknown",
    ) -> None:
        self.id: str = str(id)
        self.cbg: Optional[str] = cbg
        self.label: Optional[str] = label
        self.capacity: int = capacity        # -1 = unlimited
        self.location_type: str = location_type
        self.population: dict[str, Person] = {}

    # population management

    @property
    def total_count(self) -> int:
        return len(self.population)

    def add_member(self, person: Person) -> None:
        self.population[str(person.id)] = person

    def remove_member(self, person_id: str) -> None:
        self.population.pop(str(person_id), None)

    # convenience queries

    @property
    def is_household(self) -> bool:
        return self.location_type == "household"

    @property
    def is_facility(self) -> bool:
        return self.location_type == "facility"

    def __repr__(self) -> str:
        return f"Location(id={self.id!r}, type={self.location_type!r}, pop={self.total_count})"


class Household(Location):
    """A residential location (no capacity limit by default)."""

    count: int = 0  # class-level auto-incrementing ID

    def __init__(self, cbg: Optional[str] = None, id: Optional[str] = None) -> None:
        if id is None:
            id = str(Household.count)
            Household.count += 1
        super().__init__(id=id, cbg=cbg, location_type="household")


class Facility(Location):
    """A non-residential location (store, workplace, school, …)."""

    def __init__(
        self,
        id: str,
        cbg: Optional[str] = None,
        label: Optional[str] = None,
        capacity: int = -1,
        street_address: Optional[str] = None,
    ) -> None:
        super().__init__(id=id, cbg=cbg, label=label, capacity=capacity, location_type="facility")
        self.street_address: Optional[str] = street_address


# Person

class Person:
    """Represents a single individual in the simulation."""

    def __init__(self, id: str, sex: int, age: int, household: Household) -> None:
        self.id: str = id
        self.sex: int = sex         # 0 = male, 1 = female
        self.age: int = age
        self.household: Household = household
        self.location: Location = household
        self.invisible: bool = False

        # Disease state per variant, e.g. {"Delta": InfectionState.INFECTED | InfectionState.INFECTIOUS}
        self.states: dict[str, InfectionState] = {}
        # Timeline per variant per state, e.g. {"Delta": {InfectionState.INFECTED: InfectionTimeline(...)}}
        self.timeline: dict[str, dict[InfectionState, InfectionTimeline]] = {}

        self.masked: bool = False
        self.vaccination_state: VaccinationState = VaccinationState.NONE
        self.iv_threshold: float = 0.0

    # interventions

    def is_masked(self) -> bool:
        return self.masked

    def set_masked(self, masked: bool) -> None:
        self.masked = masked

    def set_vaccinated(self, state: VaccinationState) -> None:
        self.vaccination_state = state

    def get_vaccinated(self) -> VaccinationState:
        return self.vaccination_state

    # infection queries

    def has_state(self, state: InfectionState) -> bool:
        """Return True if *any* variant has the given flag set."""
        for val in self.states.values():
            if state in val:
                return True
        return False

    def is_infectious(self) -> bool:
        return self.has_state(InfectionState.INFECTIOUS)

    def is_symptomatic(self) -> bool:
        return self.has_state(InfectionState.SYMPTOMATIC)

    # state progression

    def update_state(self, curtime: str | int, variants: list[str]) -> None:
        """Advance this person's infection state based on *curtime* and their timeline."""
        self.invisible = False
        time = int(curtime)

        for variant in variants:
            self.states[variant] = InfectionState.SUSCEPTIBLE

        for disease, value in self.timeline.items():
            for state, tl in value.items():
                if tl.start <= time <= tl.end:
                    self.states[disease] = self.states[disease] | state
                    if state in (InfectionState.REMOVED, InfectionState.RECOVERED, InfectionState.HOSPITALIZED):
                        self.invisible = True
                else:
                    self.states[disease] = self.states[disease] & ~state

    def __repr__(self) -> str:
        return f"Person(id={self.id!r}, age={self.age})"
