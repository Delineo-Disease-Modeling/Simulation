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
        area: Optional[float] = None,
    ) -> None:
        self.id: str = str(id)
        self.cbg: Optional[str] = cbg
        self.label: Optional[str] = label
        self.capacity: int = capacity        # -1 = unlimited
        self.location_type: str = location_type
        self.area: Optional[float] = area    # physical floor area in m^2 (None = unknown)
        self.population: dict[str, Person] = {}
        # SoA shadow (Step 1): when a MembershipStore is attached, add_member
        # also records the placement into person_loc. Left None in production so
        # the hot path is a single `is not None` check. See membership.py.
        self._membership = None              # Optional[MembershipStore]
        self._loc_idx: int = -1              # this location's index in the store

    # population management

    @property
    def total_count(self) -> int:
        return len(self.population)

    def add_member(self, person: Person) -> None:
        self.population[str(person.id)] = person
        if self._membership is not None:
            self._membership.note_placement(person.id, self._loc_idx)

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
        area: Optional[float] = None,
    ) -> None:
        super().__init__(id=id, cbg=cbg, label=label, capacity=capacity, location_type="facility", area=area)
        self.street_address: Optional[str] = street_address


# Person

class Person:
    """Represents a single individual in the simulation."""

    def __init__(self, id: str, sex: int, age: int, household: Household) -> None:
        self.id: str = id
        self._soa_idx: int = -1     # index into MembershipStore arrays (engine mode)
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
        self.vaccination_status: bool = False
        self.vaccine_doses: int = 0
        self.days_since_vaccination: int = 0
        self.vaccine_effectiveness_infection: float = 0.0
        self.vaccine_effectiveness_transmission: float = 0.0
        self.vaccine_effectiveness_severity: float = 0.0
        self.iv_threshold: float = 0.0

        # Next time at which update_state's output will actually change for
        # this person — i.e., the next timeline boundary they'll cross. Lets
        # update_state early-exit during the long flat phases between
        # transitions (e.g. the 20h INFECTED window before INFECTIOUS or the
        # multi-day RECOVERED tail). 0 forces a recompute on the first call.
        # Invalidate by setting to 0 whenever self.timeline changes (see
        # InfectionManager.schedule_infection).
        self._next_transition_time: int = 0

    # interventions

    def is_masked(self) -> bool:
        return self.masked

    def set_masked(self, masked: bool) -> None:
        self.masked = masked

    def set_vaccinated(self, state: VaccinationState) -> None:
        self.vaccination_state = state
        self.vaccination_status = state != VaccinationState.NONE
        self.vaccine_doses = state.value

        if state == VaccinationState.PARTIAL:
            self.vaccine_effectiveness_infection = 0.50
            self.vaccine_effectiveness_transmission = 0.30
            self.vaccine_effectiveness_severity = 0.75
        elif state == VaccinationState.IMMUNIZED:
            self.vaccine_effectiveness_infection = 0.75
            self.vaccine_effectiveness_transmission = 0.50
            self.vaccine_effectiveness_severity = 0.90
        else:
            self.vaccine_effectiveness_infection = 0.0
            self.vaccine_effectiveness_transmission = 0.0
            self.vaccine_effectiveness_severity = 0.0

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
        time = int(curtime)

        # Fast path: if we're still in the same timeline window we were last
        # called in, no flags can change. Saves the full timeline scan on the
        # ~80% of timesteps that fall between transitions.
        if time < self._next_transition_time:
            return

        self.invisible = False
        for variant in variants:
            self.states[variant] = InfectionState.SUSCEPTIBLE

        # Walk the timeline once, both applying state flags AND tracking the
        # next time any boundary will be crossed.
        next_boundary = 2 ** 62  # effectively infinity for sim timesteps
        for disease, value in self.timeline.items():
            for state, tl in value.items():
                start = tl.start
                end = tl.end
                if start <= time <= end:
                    self.states[disease] = self.states[disease] | state
                    if state in (InfectionState.REMOVED, InfectionState.RECOVERED, InfectionState.HOSPITALIZED):
                        self.invisible = True
                    # Active window: next boundary is when this entry ends.
                    if end + 1 < next_boundary:
                        next_boundary = end + 1
                else:
                    self.states[disease] = self.states[disease] & ~state
                    # Inactive: only future boundary that can change us is
                    # when this entry becomes active. (Past entries don't
                    # contribute.)
                    if start > time and start < next_boundary:
                        next_boundary = start
        self._next_transition_time = next_boundary

    def __repr__(self) -> str:
        return f"Person(id={self.id!r}, age={self.age})"
