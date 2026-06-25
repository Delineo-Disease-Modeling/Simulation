"""Wells-Riley transmission kernels, extracted from runner.SimulationRunner.

Three parallel kernels live here: the vectorized SoA-engine path
(``_vectorized_transmission``, the prod default), the per-event legacy kernel
(``process_infection_event``), and the O(n) aggregate fallback
(``_aggregate_transmission_event``). They are a mixin rather than free functions
because they read a dozen pieces of runner state (the engine ``_soa_engine``, the
``_timed`` helper, the ventilation/external-FOI/aggregate config flags) and call
one another; the mixin keeps that coupling intact while physically separating the
~470 lines of transmission physics from the runner's orchestration. Pure
code-motion -- behavior is unchanged (guarded by the aggregate-equivalence and
engine golden tests).
"""
from __future__ import annotations

import logging
import math
import random
from typing import TYPE_CHECKING

import numpy as np

from .infection_models.v6_wells_riley import get_vaccination_protection
from .pap import InfectionState

if TYPE_CHECKING:
    from .runner import SimulationContext

logger = logging.getLogger(__name__)


class TransmissionMixin:
    """Wells-Riley transmission kernels for ``SimulationRunner``.

    The host class must provide: ``_soa_engine``, ``_timed``,
    ``aggregate_transmission``, ``external_foi``, ``external_prevalence``,
    ``area_aware_ventilation``, ``area_clamp``, ``ventilation_coeff``.
    """

    def _vectorized_transmission(self, context: SimulationContext, ts: int) -> None:
        """Single-variant well-mixed Wells-Riley over all rooms at once.

        Equivalent to running _aggregate_transmission_event per room, but as
        numpy array ops: emission summed per room with bincount, then one
        vectorized infection draw per susceptible. RNG source differs (numpy vs
        python per-pair) -> ensemble-validated, not byte-identical.
        """
        store = context.simulator.membership
        variant = context.variants[0]
        pstate = store.pstate
        person_loc = store.person_loc
        masked = store.masked

        INFECTIOUS = int(InfectionState.INFECTIOUS.value)
        INVISIBLE = int(
            (InfectionState.HOSPITALIZED | InfectionState.RECOVERED | InfectionState.REMOVED).value
        )
        placed = person_loc >= 0
        infectious = placed & ((pstate & INFECTIOUS) != 0) & ((pstate & INVISIBLE) == 0)

        # External force-of-infection: out-of-cluster visitors add a one-way
        # background emission to each room, W_ext[loc] = n_internal[loc]
        # * ext_ratio[loc] * P_ext, where ext_ratio = (1 - f_j)/f_j * emit_factor.
        # The externals are never agents (not in pstate / never susceptible /
        # never rendered), so this can seed or sustain transmission with zero
        # internal infectors present — which is exactly why we must NOT early-return
        # on infectious.any() when the term is active. Inert by default (flag off,
        # or external_prevalence 0, or ext_ratio unbuilt) -> golden path preserved.
        ext_on = (
            self.external_foi
            and self.external_prevalence > 0.0
            and store.ext_ratio is not None
        )
        if not infectious.any() and not ext_on:
            return

        # Emission weight per infector, summed per room (cheap O(N) numpy).
        inf_w = np.where(masked, 0.30, 1.0) * store.vax_trans_factor
        emit = np.where(infectious, inf_w, 0.0)
        W = np.bincount(
            person_loc[placed], weights=emit[placed], minlength=store.num_locations
        )
        if ext_on:
            # n_internal = realized internal occupancy per room (all placed people).
            n_internal = np.bincount(person_loc[placed], minlength=store.num_locations)
            W = W + store.ext_ratio * n_internal * self.external_prevalence

        # Restrict the expensive trials (exp + RNG + scheduling) to actually
        # exposed susceptibles — those placed in a room with infectors (or external
        # pressure). This keeps the kernel cheap at low prevalence (few eligible)
        # and at saturation (numpy), instead of drawing for all N every timestep.
        loc = np.where(placed, person_loc, 0)
        room_W = W[loc]
        eligible = (
            placed
            & ~store.infected_mask
            & (pstate == 0)
            & ((pstate & INVISIBLE) == 0)
            & (room_W > 0.0)
        )
        elig_idx = np.nonzero(eligible)[0]
        if elig_idx.size == 0:
            return

        intake = np.where(masked[elig_idx], 0.50, 1.0) * (
            1.0 - store.vax_inf_protection[elig_idx]
        )
        mean_quanta = store.base_quanta[loc[elig_idx]] * room_W[elig_idx] * intake
        prob = 1.0 - np.exp(-mean_quanta)
        draws = np.random.random(elig_idx.size)
        hits = elig_idx[draws < prob]
        if hits.size == 0:
            return

        infection_mgr = context.infection_manager
        infected_set = infection_mgr.infected
        idx_to_person = store.idx_to_person
        variant_bucket = context.variant_infected[variant]
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )
        for i in hits:
            target = idx_to_person[i]
            target_id = target.id
            infected_set.add(target_id)
            infection_mgr.schedule_infection(
                context.simulator,
                context.event_queue,
                target,
                variant,
                ts,
                context.people_with_timelines,
            )
            variant_bucket[target_id] = infected_state_value
            store.snap_state[i] = infected_state_value
            context.simulator.log_event(
                "log_infection_event", target, None, None, variant, ts
            )

    def _ventilation_rate(self, place, is_household: bool) -> float:
        """Wells-Riley ventilation term Q (m^3/hr).

        Households use a fixed 3000; facilities use a fixed 150 unless
        area-aware ventilation is enabled, in which case Q scales with the
        facility's physical floor area (Q = ventilation_coeff * clamp(area)),
        making per-contact risk inversely proportional to area. Facilities with
        no known area fall back to 150, so flag-off behaviour is bit-identical.
        """
        if is_household:
            return 3000.0
        if self.area_aware_ventilation:
            area = getattr(place, "area", None)
            if area is not None and area > 0:
                lo, hi = self.area_clamp
                return self.ventilation_coeff * min(max(float(area), lo), hi)
        return 150.0

    def process_infection_event(
        self,
        context: SimulationContext,
        ts: int,
        poi_id: str,
        is_household: bool,
    ) -> None:
        if self.aggregate_transmission:
            self._aggregate_transmission_event(context, ts, poi_id, is_household)
            return

        place = context.simulator.get_location(str(poi_id), is_household)
        if not place:
            return

        if self._soa_engine:
            store = context.simulator.membership
            loc_idx = store.loc_to_idx.get((str(poi_id), is_household))
            if loc_idx is None:
                return
            occ = context.occupancy.occupants_of(loc_idx)
            if len(occ) == 0:
                return
            idx_to_person = store.idx_to_person
            snapshot = [idx_to_person[i] for i in occ]
        else:
            if not place.population:
                return
            snapshot = list(place.population.values())

        infectious_people = [person for person in snapshot if person.is_infectious()]
        if not infectious_people:
            return

        exposure_hours = context.simulator.timestep / 60.0
        infection_mgr = context.infection_manager
        multidisease = infection_mgr.multidisease
        infected_set = infection_mgr.infected
        susceptible = InfectionState.SUSCEPTIBLE
        infectious_flag = InfectionState.INFECTIOUS
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )

        # Wells-Riley constants — see infection_models.v6_wells_riley.CAT.
        # Inlined here so the inner loop avoids the per-call function-call
        # overhead and the per-call hasattr/debug branches. Equivalent math,
        # equivalent RNG consumption (one random.random() per CAT-eligible
        # pair). CAT was called with indoor = not is_household; the outdoor
        # branch multiplies ventilation_rate by 20.
        _QUANTA_RATE = 20.0
        _BREATHING_RATE = 0.5
        ventilation_rate = self._ventilation_rate(place, is_household)
        base_quanta_per_pair = (
            _QUANTA_RATE * _BREATHING_RATE * exposure_hours
        ) / ventilation_rate

        with self._timed("infection_event/infection_pair_iteration"):
            for infector in infectious_people:
                infector_id = infector.id
                infector_masked = infector.masked
                # get_vaccination_protection short-circuits on
                # vaccination_status=False; skip the call entirely when we
                # already know there's no protection (avoids the getattr
                # chain for the common unvaccinated case).
                infector_factor = 1.0
                if infector.vaccination_status:
                    infector_factor = 1.0 - get_vaccination_protection(infector, 'transmission')

                for variant, state in infector.states.items():
                    if not (state & infectious_flag):
                        continue
                    variant_bucket = context.variant_infected[variant]

                    for target in snapshot:
                        target_id = target.id
                        if target_id == infector_id:
                            continue
                        if target.invisible:
                            continue
                        target_states = target.states
                        if target_states.get(variant, susceptible) != susceptible:
                            continue
                        if not multidisease:
                            # Inline the any() so we can break early on first
                            # non-susceptible state without paying generator overhead.
                            skip = False
                            for s in target_states.values():
                                if s != susceptible:
                                    skip = True
                                    break
                            if skip:
                                continue

                        # Inlined Wells-Riley transmission probability.
                        target_masked = target.masked
                        if infector_masked:
                            if target_masked:
                                mask_factor = 0.15  # 1 - 0.85
                            else:
                                mask_factor = 0.30  # 1 - 0.70
                        elif target_masked:
                            mask_factor = 0.50  # 1 - 0.50
                        else:
                            mask_factor = 1.0

                        if target.vaccination_status:
                            target_protection = get_vaccination_protection(target, 'infection')
                        else:
                            target_protection = 0.0

                        mean_quanta = (
                            base_quanta_per_pair
                            * mask_factor
                            * infector_factor
                            * (1.0 - target_protection)
                        )
                        # P = 1 - exp(-mean_quanta); infect iff
                        # random.random() < P. Match the original CAT's RNG
                        # draw order exactly so simdata stays byte-identical.
                        if random.random() >= 1.0 - math.exp(-mean_quanta):
                            continue

                        logger.info(
                            "[Infection] %s -> %s @ %s (t=%d, variant=%s)",
                            infector_id,
                            target_id,
                            poi_id,
                            ts,
                            variant,
                        )

                        if target_id not in infected_set:
                            infected_set.add(target_id)
                        elif not multidisease:
                            continue

                        infection_mgr.schedule_infection(
                            context.simulator,
                            context.event_queue,
                            target,
                            variant,
                            ts,
                            context.people_with_timelines,
                        )
                        variant_bucket[target_id] = infected_state_value
                        context.simulator.log_event(
                            "log_infection_event",
                            target,
                            infector,
                            place,
                            variant,
                            ts,
                        )

        self._log_contact_pairs(context, snapshot, place, ts, is_household)

    def _aggregate_transmission_event(
        self,
        context: SimulationContext,
        ts: int,
        poi_id: str,
        is_household: bool,
    ) -> None:
        """O(infectors + susceptibles) per-location Wells-Riley kernel.

        The well-mixed-room form of Wells-Riley: a susceptible's risk depends on
        the *total* quanta in the room (the sum over infectors), not on pairwise
        encounters. We sum each infectious person's emission weight once per
        location/variant (W), then draw a single infection trial per susceptible
        against P = 1 - exp(-base * W * susceptible_intake).

        This yields the same marginal infection probability per susceptible as
        the pairwise kernel in process_infection_event, because for independent
        per-infector Poisson exposures
            1 - prod_i (1 - p_i) == 1 - exp(-sum_i lambda_i),
        while doing O(infectors + susceptibles) work instead of
        O(infectors * susceptibles). Mask/vaccination factors separate cleanly
        into infector-side (mask 0.30 / vax transmission) and susceptible-side
        (mask 0.50 / vax infection) weights, so base * w_i * u_j reproduces the
        pairwise per-pair quanta exactly (e.g. both-masked 0.30 * 0.50 = 0.15).

        It consumes a *different* RNG stream than the pairwise path (one draw per
        susceptible/variant, not one per pair), so output is NOT byte-identical
        and is validated by ensemble equivalence rather than the golden hash.
        Enabled via INFECTION_MODEL["aggregate_transmission"] / the simdata
        "aggregate_transmission" field.
        """
        place = context.simulator.get_location(str(poi_id), is_household)
        if not place:
            return

        if self._soa_engine:
            store = context.simulator.membership
            loc_idx = store.loc_to_idx.get((str(poi_id), is_household))
            if loc_idx is None:
                return
            occ = context.occupancy.occupants_of(loc_idx)
            if len(occ) == 0:
                return
            idx_to_person = store.idx_to_person
            snapshot = [idx_to_person[i] for i in occ]
        else:
            if not place.population:
                return
            snapshot = list(place.population.values())

        infectious_people = [person for person in snapshot if person.is_infectious()]
        if not infectious_people:
            return

        exposure_hours = context.simulator.timestep / 60.0
        infection_mgr = context.infection_manager
        multidisease = infection_mgr.multidisease
        infected_set = infection_mgr.infected
        susceptible = InfectionState.SUSCEPTIBLE
        infectious_flag = InfectionState.INFECTIOUS
        infected_state_value = int(
            (InfectionState.INFECTED | InfectionState.INFECTIOUS).value
        )

        _QUANTA_RATE = 20.0
        _BREATHING_RATE = 0.5
        ventilation_rate = self._ventilation_rate(place, is_household)
        base_quanta = (_QUANTA_RATE * _BREATHING_RATE * exposure_hours) / ventilation_rate

        with self._timed("infection_event/aggregate_iteration"):
            # 1) Sum infector emission weights per variant — O(infectors).
            #    w_i = infector mask factor (0.30 masked, else 1.0) * infector
            #    vaccination transmission factor (same factors as the pairwise
            #    kernel, just summed instead of applied per pair).
            emission: dict[str, float] = {}
            for infector in infectious_people:
                infector_mask_factor = 0.30 if infector.masked else 1.0
                if infector.vaccination_status:
                    infector_factor = 1.0 - get_vaccination_protection(infector, 'transmission')
                else:
                    infector_factor = 1.0
                w_i = infector_mask_factor * infector_factor
                for variant, state in infector.states.items():
                    if state & infectious_flag:
                        emission[variant] = emission.get(variant, 0.0) + w_i

            if not emission:
                return

            # 2) One infection trial per susceptible per active variant against
            #    the summed room concentration — O(susceptibles).
            for target in snapshot:
                if target.invisible:
                    continue
                target_states = target.states
                if not multidisease:
                    skip = False
                    for s in target_states.values():
                        if s != susceptible:
                            skip = True
                            break
                    if skip:
                        continue

                target_mask_factor = 0.50 if target.masked else 1.0
                if target.vaccination_status:
                    target_protection = get_vaccination_protection(target, 'infection')
                else:
                    target_protection = 0.0
                # Susceptible intake weight u_j; the susceptible's protection is
                # constant across infectors, so it is computed once here rather
                # than once per pair as in the pairwise kernel.
                intake = target_mask_factor * (1.0 - target_protection)
                if intake <= 0.0:
                    continue

                target_id = target.id
                for variant, w_sum in emission.items():
                    if target_states.get(variant, susceptible) != susceptible:
                        continue
                    mean_quanta = base_quanta * w_sum * intake
                    if mean_quanta <= 0.0:
                        continue
                    if random.random() >= 1.0 - math.exp(-mean_quanta):
                        continue

                    logger.info(
                        "[Infection] (room) -> %s @ %s (t=%d, variant=%s)",
                        target_id, poi_id, ts, variant,
                    )

                    if target_id not in infected_set:
                        infected_set.add(target_id)
                    elif not multidisease:
                        continue

                    infection_mgr.schedule_infection(
                        context.simulator,
                        context.event_queue,
                        target,
                        variant,
                        ts,
                        context.people_with_timelines,
                    )
                    context.variant_infected[variant][target_id] = infected_state_value
                    context.simulator.log_event(
                        "log_infection_event",
                        target,
                        None,
                        place,
                        variant,
                        ts,
                    )

                    if not multidisease:
                        # First infection claims this susceptible for the
                        # timestep, mirroring the pairwise infected_set guard.
                        break

        self._log_contact_pairs(context, snapshot, place, ts, is_household)


    def _log_contact_pairs(self, context, snapshot, place, ts, is_household) -> None:
        """Emit pairwise contact-log events for a place (shared by both non-engine
        kernels). O(n^2) over the place population and a no-op when logging is off,
        so it is skipped entirely in that case (the prod default). Logging only --
        does not touch infection outcomes or RNG.
        """
        if not is_household and context.simulator.enable_logging:
            with self._timed("infection_event/contact_pair_logging"):
                for index, person_one in enumerate(snapshot):
                    for person_two in snapshot[index + 1:]:
                        context.simulator.log_event(
                            "log_contact_event",
                            person_one,
                            person_two,
                            place,
                            ts,
                        )
