from __future__ import annotations

import logging
from typing import Optional, TextIO, TYPE_CHECKING

import requests

from .pap import Person, InfectionState, InfectionTimeline, VaccinationState
from .infection_models.v6_wells_riley import CAT
from .config import DMP_API, INFECTION_MODEL

if TYPE_CHECKING:
    from .event_queue import EventQueue

logger = logging.getLogger(__name__)

# Module-level session for HTTP connection reuse (keep-alive).
# Avoids TCP handshake + TLS negotiation on every DMP API call.
_dmp_session = requests.Session()

VALID_DMP_MODES = {"auto", "required", "off"}


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

    def run_model(
        self,
        simulator,
        curtime: int,
        variant_infected: dict[str, dict[str, int]],
        newly_infected: dict[str, dict[str, list[str]]],
        file: Optional[TextIO] = None,
    ) -> None:
        """Run one timestep of infection spread across all locations with infected people."""
        if file is not None:
            self._write_timestep_header(file, curtime, variant_infected)

        # Update variant tracking
        for person_id in self.infected:
            person = simulator.people.get(person_id)
            if person is None:
                continue
            for disease in variant_infected:
                state = person.states.get(disease, InfectionState.SUSCEPTIBLE)
                if state != InfectionState.SUSCEPTIBLE:
                    variant_infected[disease][person_id] = int(state.value)

        # Attempt transmission from each infected person to co-located susceptibles
        exposure_hours = simulator.timestep / 60.0

        for person_id in self.infected:
            infector = simulator.people.get(person_id)
            if infector is None or infector.invisible:
                continue

            for target in infector.location.population.values():
                if infector.id == target.id:
                    continue

                for disease, state in infector.states.items():
                    if InfectionState.INFECTIOUS not in state:
                        continue

                    if target.states.get(disease, InfectionState.SUSCEPTIBLE) != InfectionState.SUSCEPTIBLE:
                        continue

                    if not self.multidisease and any(
                        s != InfectionState.SUSCEPTIBLE for s in target.states.values()
                    ):
                        continue

                    # Wells-Riley transmission check
                    if not CAT(
                        target,
                        indoor=True,
                        exposure_hours=exposure_hours,
                        infector=infector,
                        infector_masked=infector.is_masked(),
                        susceptible_masked=target.is_masked(),
                    ):
                        continue

                    logger.info(
                        "Infection: %s -> %s (masked: %s/%s)",
                        infector.id, target.id, infector.is_masked(), target.is_masked(),
                    )

                    if target.id not in self.infected:
                        self.infected.add(target.id)
                    elif not self.multidisease:
                        continue

                    timeline = self.schedule_infection(
                        simulator,
                        None,
                        target,
                        disease,
                        curtime,
                    )

                    if file is not None:
                        file.write(f'{infector.id} infected {target.id} @ location {target.location.id} w/ {disease}\n')

                    # Track newly infected
                    newly_infected.setdefault(disease, {})
                    newly_infected[disease].setdefault(str(infector.id), []).append(str(target.id))

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

        max_time_hours = max(t for _, t in csv_timeline)
        end_ts = curtime + int(max_time_hours * 60)

        result: dict[InfectionState, InfectionTimeline] = {}
        for status, time_hours in csv_timeline:
            if status not in state_map:
                continue
            inf_state = state_map[status]
            start_ts = curtime + int(time_hours * 60)
            if inf_state in result:
                result[inf_state] = InfectionTimeline(
                    min(result[inf_state].start, start_ts), end_ts
                )
            else:
                result[inf_state] = InfectionTimeline(start_ts, end_ts)

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
        state_map = {k: getattr(InfectionState, v) for k, v in DMP_API["state_mapping"].items()}
        max_time = max(time for _, time in timeline_data["timeline"])
        end_ts = curtime + max_time / time_factor

        result: dict[InfectionState, InfectionTimeline] = {}
        for status, time in timeline_data["timeline"]:
            if status not in state_map:
                continue
            inf_state = state_map[status]
            start_ts = curtime + time / time_factor

            if inf_state in result:
                result[inf_state] = InfectionTimeline(
                    min(result[inf_state].start, start_ts), end_ts
                )
            else:
                result[inf_state] = InfectionTimeline(start_ts, end_ts)

        return {disease: result}

    @staticmethod
    def _fallback_timeline(disease: str, curtime: int) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Config-driven default timeline when the DMP API is unavailable."""
        fb = INFECTION_MODEL["fallback_timeline"]
        return {
            disease: {
                InfectionState.INFECTED: InfectionTimeline(
                    curtime, curtime + fb["infected_duration"]
                ),
                InfectionState.INFECTIOUS: InfectionTimeline(
                    curtime + fb["infectious_delay"], curtime + fb["infected_duration"]
                ),
                InfectionState.RECOVERED: InfectionTimeline(
                    curtime + fb["infected_duration"], curtime + fb["recovery_duration"]
                ),
            }
        }

    # Private helpers

    def _write_timestep_header(
        self, file: TextIO, curtime: int, variant_infected: dict[str, dict]
    ) -> None:
        file.write(f'====== TIMESTEP {curtime} ======\n')
        for variant in variant_infected:
            ids = [pid for pid, val in variant_infected[variant].items() if val != 0]
            file.write(f'{variant}: {ids}\n')
            file.write(f"{variant} count: {len(ids)}\n")
