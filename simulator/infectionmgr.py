from __future__ import annotations

import random
import logging
import requests
from typing import Optional, TextIO

from .pap import Person, InfectionState, InfectionTimeline, VaccinationState
from .masking import Maskingeffects
from .config import DMP_API, INFECTION_MODEL

logger = logging.getLogger(__name__)

class InfectionManager:
    """Manages infection spread logic and DMP API timeline creation."""

    def __init__(self, infected_ids: list[str]) -> None:
        self.multidisease: bool = INFECTION_MODEL["allow_multidisease"]
        self.infected: list[str] = list(infected_ids)

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
        for person_id in self.infected:
            infector = simulator.people.get(person_id)
            if infector is None or infector.invisible:
                continue

            for target in infector.location.population:
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

                    # Mask-adjusted transmission check
                    mask_modifier = Maskingeffects.calculate_mask_transmission_modifier(infector, target)
                    transmission_prob = 0.0005 * mask_modifier

                    if random.random() >= transmission_prob:
                        continue

                    logger.info(
                        "Infection: %s -> %s (masked: %s/%s)",
                        infector.id, target.id, infector.is_masked(), target.is_masked(),
                    )

                    if target.id not in self.infected:
                        self.infected.append(target.id)
                    elif not self.multidisease:
                        continue

                    timeline = self.create_timeline(target, disease, curtime)
                    simulator.people[target.id].timeline = timeline

                    if file is not None:
                        file.write(f'{infector.id} infected {target.id} @ location {target.location.id} w/ {disease}\n')

                    # Track newly infected
                    newly_infected.setdefault(disease, {})
                    newly_infected[disease].setdefault(str(infector.id), []).append(str(target.id))

    def create_timeline(self, person: Person, disease: str, curtime: int) -> dict[str, dict[InfectionState, InfectionTimeline]]:
        """Create a disease timeline for a newly infected person using the DMP API.
        Falls back to a config-driven default timeline if the API is unreachable.
        """

        base_url = DMP_API["base_url"]
        time_factor = DMP_API["time_conversion_factor"]

        payload = {
            "disease_name": "COVID-19",
            "model_path": None,
            "demographics": {
                "Age": str(person.age),
                "Vaccination Status": "Vaccinated" if person.vaccination_state != VaccinationState.NONE else "Unvaccinated",
                "Sex": "F" if person.sex == 1 else "M",
                "Variant": disease,
            },
        }

        try:
            resp = requests.post(f"{base_url}/simulate", json=payload)
            resp.raise_for_status()
            timeline_data = resp.json()

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

        except requests.exceptions.RequestException as e:
            logger.warning("DMP API error, using fallback timeline: %s", e)
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
