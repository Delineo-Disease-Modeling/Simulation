from __future__ import annotations

import logging
from typing import Optional, TextIO, TYPE_CHECKING

import requests

from .pap import Person, InfectionState, InfectionTimeline, VaccinationState
from .config import DMP_API, INFECTION_MODEL

if TYPE_CHECKING:
    from .event_queue import EventQueue

logger = logging.getLogger(__name__)

# Module-level session for HTTP connection reuse (keep-alive).
# Avoids TCP handshake + TLS negotiation on every DMP API call.
_dmp_session = requests.Session()

VALID_DMP_MODES = {"auto", "required", "off"}
ABSORBING_TIMELINE_END = 2 ** 62


try:
    from dmp_functions import DMPContext, initialize_dmp_from_string, run_dmp_simulation as _run_dmp_csv
    _CSV_DMP_AVAILABLE = True
except ImportError:
    _CSV_DMP_AVAILABLE = False


class InfectionManager:
    """Manages infection spread logic and DMP API timeline creation."""

    def __init__(
        self,
        infected_ids: list[str],
        disease_name: str = "COVID-19",
        dmp_mode: str = "auto",
        model_path_by_variant: Optional[dict[str, Optional[str]]] = None,
        matrix_csv_by_variant: Optional[dict[str, str]] = None,
    ) -> None:
        self.multidisease: bool = INFECTION_MODEL["allow_multidisease"]
        self.infected: set[str] = set(infected_ids)
        self.disease_name = disease_name or "COVID-19"
        mode = (dmp_mode or "auto").lower()
        self.dmp_mode = mode if mode in VALID_DMP_MODES else "auto"
        self.model_path_by_variant = model_path_by_variant or {}
        self.timeline_source_counts = {"dmp": 0, "fallback": 0}

        self._csv_contexts: dict = {}
        if matrix_csv_by_variant and _CSV_DMP_AVAILABLE:
            for variant, csv_content in matrix_csv_by_variant.items():
                if not csv_content or not csv_content.strip():
                    continue
                try:
                    ctx = DMPContext()
                    initialize_dmp_from_string(ctx, csv_content)
                    self._csv_contexts[variant] = ctx
                    logger.info("Loaded custom CSV matrix for variant '%s'", variant)
                except Exception as exc:
                    logger.warning("Failed to load CSV matrix for variant '%s': %s", variant, exc)

        # In-process DMP: read the local state-machine DB directly instead of
        # one HTTP round-trip per infection. Constructed once; None if the dmp
        # package/DB can't be loaded, in which case create_timeline uses HTTP.
        self._inprocess = None
        if self.dmp_mode != "off" and DMP_API.get("use_inprocess"):
            try:
                from .dmp_inprocess import InProcessDMP

                self._inprocess = InProcessDMP()
                logger.info("DMP timelines resolved in-process (HTTP path disabled)")
            except Exception as exc:
                logger.warning("In-process DMP unavailable (%s); using HTTP API", exc)
                self._inprocess = None


    def schedule_infection(
        self,
        simulator,
        event_queue: Optional["EventQueue"],
        person: Person,
        disease: str,
        curtime: int,
        people_with_timelines: Optional[set] = None,
    ) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Create and register a new infection timeline without changing timeline semantics."""
        timeline = self.create_timeline(person, disease, curtime)
        target_person = simulator.people[person.id]
        target_person.timeline = timeline
        # Force update_state to recompute on next call: its cached
        # _next_transition_time was based on the old (empty or stale) timeline.
        target_person._next_transition_time = 0
        self.infected.add(person.id)
        # Keep the SoA ever-infected mask in sync (engine mode); schedule_infection
        # is the single chokepoint for every infection (seed + kernel).
        store = getattr(simulator, "membership", None)
        if store is not None:
            store.mark_infected(person.id)

        if people_with_timelines is not None:
            # Store the Person ref directly (not pid string) so update_people_states
            # can iterate without a per-call simulator.get_person(pid) dict lookup.
            people_with_timelines.add(person)

        if event_queue is not None and disease in timeline and InfectionState.INFECTIOUS in timeline[disease]:
            infectious_timeline = timeline[disease][InfectionState.INFECTIOUS]
            event_queue.register_infectious(
                person.id,
                disease,
                infectious_timeline.start,
                infectious_timeline.end,
            )

        return timeline

    def create_timeline(self, person: Person, disease: str, curtime: int) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Create a disease timeline for a newly infected person.

        Priority:
          1. Custom CSV matrix (if loaded for this variant)
          2. DMP state-machine API (if dmp_mode != "off")
          3. Config-driven fallback timeline
        """
        if self.dmp_mode == "off":
            self.timeline_source_counts["fallback"] += 1
            return self._fallback_timeline(disease, curtime)

        if disease in self._csv_contexts:
            return self._csv_timeline(person, disease, curtime)

        demographics = self._demographics_for(person, disease)
        model_path = self._model_path_for_variant(disease)

        # Fast path: in-process DMP — cached matrices + a per-person stochastic
        # sample, no HTTP. Returns the same (state, hours) timeline the HTTP
        # endpoint would, so it flows through the shared CSV-result builder.
        if self._inprocess is not None:
            try:
                timeline_list = self._inprocess.simulate(
                    self.disease_name, model_path, demographics
                )
            except Exception as e:
                if self.dmp_mode == "required":
                    raise RuntimeError(
                        f"DMP timeline required but in-process failed: {e}"
                    ) from e
                logger.warning("In-process DMP error, using fallback timeline: %s", e)
                self.timeline_source_counts["fallback"] += 1
                return self._fallback_timeline(disease, curtime)

            if timeline_list:
                self.timeline_source_counts["dmp"] += 1
                return self._build_timeline_from_csv_result(timeline_list, disease, curtime)

            # No state machine matched these demographics.
            if self.dmp_mode == "required":
                raise RuntimeError(
                    f"DMP timeline required but no state machine matched {demographics}"
                )
            self.timeline_source_counts["fallback"] += 1
            return self._fallback_timeline(disease, curtime)

        # HTTP path: used only when the in-process provider is unavailable.
        payload = {
            "disease_name": self.disease_name,
            "model_path": model_path,
            "demographics": demographics,
        }

        try:
            resp = _dmp_session.post(
                f"{DMP_API['base_url']}/simulate",
                json=payload,
                timeout=DMP_API["timeout_seconds"],
            )
            resp.raise_for_status()
            timeline = self._build_timeline_from_response(resp.json(), disease, curtime)
            self.timeline_source_counts["dmp"] += 1
            return timeline
        except (requests.exceptions.RequestException, KeyError, TypeError, ValueError) as e:
            if self.dmp_mode == "required":
                raise RuntimeError(f"DMP timeline required but unavailable: {e}") from e
            logger.warning("DMP API error, using fallback timeline: %s", e)
            self.timeline_source_counts["fallback"] += 1
            return self._fallback_timeline(disease, curtime)

    def _demographics_for(self, person: Person, disease: str) -> dict:
        """Demographic payload for DMP matching. Shared by the in-process and
        HTTP paths so both resolve to the same state machine."""
        return {
            "Age": str(person.age),
            "Vaccination Status": (
                "Vaccinated"
                if person.vaccination_state != VaccinationState.NONE
                else "Unvaccinated"
            ),
            "Sex": "F" if person.sex == 1 else "M",
            "Variant": disease,
        }

    def _csv_timeline(self, person: Person, disease: str, curtime: int) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Build a timeline using the custom CSV matrix loaded for this variant."""
        ctx = self._csv_contexts[disease]
        demographics = {
            "Age": str(person.age),
            "Vaccination Status": "Vaccinated" if person.vaccination_state != VaccinationState.NONE else "Unvaccinated",
            "Sex": "F" if person.sex == 1 else "M",
            "Variant": disease,
        }
        try:
            result = _run_dmp_csv(ctx, demographics)
            timeline = self._build_timeline_from_csv_result(result["timeline"], disease, curtime)
            self.timeline_source_counts["dmp"] += 1
            return timeline
        except Exception as exc:
            if self.dmp_mode == "required":
                raise RuntimeError(f"CSV DMP timeline required but failed for variant '{disease}': {exc}") from exc
            logger.warning("CSV DMP failed for variant '%s', using fallback: %s", disease, exc)
            self.timeline_source_counts["fallback"] += 1
            return self._fallback_timeline(disease, curtime)

    @staticmethod
    def _build_sequential_timeline(
        events: list[tuple[InfectionState, int]],
    ) -> dict[InfectionState, InfectionTimeline]:
        """Build non-overlapping state windows from ordered transition events.

        DMP emits transitions ("state starts at t"). ``update_state`` expects
        active windows and treats the end timestamp as inclusive, so each state
        must end one minute before the next state starts. The final state is
        absorbing for the rest of the simulation.

        Assumes a MONOTONIC course: each mapped ``InfectionState`` occupies a
        single contiguous window. Adjacent transitions mapping to the same state
        (e.g. Infectious_Asymptomatic -> Infectious_Symptomatic, both INFECTIOUS)
        are coalesced. A state that re-enters AFTER an intervening different state
        cannot be represented (this structure stores one window per state), so we
        fail loudly rather than silently drop or stretch a window — extending the
        infectious window across an intervening hospitalized window would recreate
        the over-emission bug this fix removes.
        """
        ordered = sorted(
            ((state, int(start)) for state, start in events),
            key=lambda item: item[1],
        )
        coalesced: list[tuple[InfectionState, int]] = []
        for state, start in ordered:
            if coalesced and coalesced[-1][0] == state:
                continue
            coalesced.append((state, start))

        states = [state for state, _ in coalesced]
        if len(set(states)) != len(states):
            repeated = sorted({s.name for s in states if states.count(s) > 1})
            raise ValueError(
                f"non-monotonic disease timeline: state(s) {repeated} re-enter "
                "after an intervening state. The timeline stores one window per "
                "InfectionState and cannot represent relapse/re-entry — fix the "
                "state machine or extend the model to support multiple windows "
                "per state."
            )

        result: dict[InfectionState, InfectionTimeline] = {}
        for idx, (state, start) in enumerate(coalesced):
            if idx + 1 < len(coalesced):
                end = coalesced[idx + 1][1] - 1
                if end < start:
                    continue
            else:
                end = ABSORBING_TIMELINE_END
            result[state] = InfectionTimeline(start, end)
        return result

    @staticmethod
    def _build_timeline_from_csv_result(
        csv_timeline: list,
        disease: str,
        curtime: int,
    ) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Convert CSV simulation output (hours) into an absolute-time InfectionTimeline."""
        state_map = {
            k: getattr(InfectionState, v)
            for k, v in DMP_API["state_mapping"].items()
            if hasattr(InfectionState, v)
        }
        if not csv_timeline:
            return InfectionManager._fallback_timeline(disease, curtime)

        events: list[tuple[InfectionState, int]] = []
        for status, time_hours in csv_timeline:
            if status not in state_map:
                continue
            events.append((state_map[status], curtime + int(time_hours * 60)))

        result = InfectionManager._build_sequential_timeline(events)
        if not result:
            return InfectionManager._fallback_timeline(disease, curtime)
        return {disease: result}

    def _model_path_for_variant(self, disease: str) -> Optional[str]:
        if disease in self.model_path_by_variant:
            return self.model_path_by_variant[disease] or None
        if self.disease_name == "COVID-19":
            return f"variant.{disease}.general"
        return None

    @staticmethod
    def _build_timeline_from_response(
        timeline_data: dict, disease: str, curtime: int
    ) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Convert a cached DMP API response into an absolute-time timeline."""
        time_factor = DMP_API["time_conversion_factor"]
        state_map = {
            k: getattr(InfectionState, v)
            for k, v in DMP_API["state_mapping"].items()
            if hasattr(InfectionState, v)
        }

        events: list[tuple[InfectionState, int]] = []
        for status, time in timeline_data["timeline"]:
            if status not in state_map:
                continue
            events.append((state_map[status], curtime + int(time / time_factor)))

        result = InfectionManager._build_sequential_timeline(events)
        if not result:
            return InfectionManager._fallback_timeline(disease, curtime)
        return {disease: result}

    @staticmethod
    def _fallback_timeline(disease: str, curtime: int) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Config-driven default timeline when the DMP API is unavailable."""
        fb = INFECTION_MODEL["fallback_timeline"]
        events = [
            (InfectionState.INFECTED, curtime),
            (InfectionState.INFECTIOUS, curtime + fb["infectious_delay"]),
            (InfectionState.RECOVERED, curtime + fb["infected_duration"]),
        ]
        return {disease: InfectionManager._build_sequential_timeline(events)}

    # Private helpers
