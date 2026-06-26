"""Movement + per-person interventions applied during the simulation loop.

move_people relocates agents under a movement intervention; apply_person_interventions
applies mask / vaccine / etc. effects to individuals. Extracted from runner.py
(pure code-motion).
"""
from __future__ import annotations

import random

from .config import SIMULATION
from .infection_models.v6_wells_riley import get_vaccination_protection
from .pap import InfectionState, Person, VaccinationState


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
    # Gate on level>0 so a 0.0 policy (no intervention) touches no one — the
    # threshold set includes an exact 0.0 (ceil(0)/100) — while keeping '<=' so a
    # 1.0 policy covers everyone (large populations have thresholds == 1.0 that a
    # strict '<' would miss). Masking is reversible: lowering the policy unmasks.
    mask_level = interventions["mask"]
    should_mask = mask_level > 0.0 and person.iv_threshold <= mask_level
    if should_mask and not person.is_masked():
        simulator.log_event("log_intervention_effect", person, "mask", "complied", ts_str)
        person.set_masked(True)
    elif not should_mask and person.is_masked():
        simulator.log_event("log_intervention_effect", person, "mask", "unmasked", ts_str)
        person.set_masked(False)

    # Vaccination is permanent and dose count is locked at first inoculation.
    vaccine_level = interventions["vaccine"]
    if (
        vaccine_level > 0.0
        and person.iv_threshold <= vaccine_level
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
