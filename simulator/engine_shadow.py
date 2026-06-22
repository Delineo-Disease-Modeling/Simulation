"""Engine-vs-legacy shadow validation for SimulationRunner.

Debug/consistency scaffolding from the SoA-engine migration: mirrors per-person
state and occupancy between the engine and the legacy membership view and records
mismatches. Extracted from runner.py as a mixin (pure code-motion; keeps the
self.* coupling). Host must provide: _soa_shadow, _shadow_checks, _shadow_mismatches.
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from .config import DELINEO
from .infection_models.v6_wells_riley import get_vaccination_protection
from .pap import InfectionState, Person

if TYPE_CHECKING:
    from .runner import SimulationContext

logger = logging.getLogger(__name__)


class ShadowValidationMixin:
    """SoA-engine vs legacy-membership shadow checks for SimulationRunner."""

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
