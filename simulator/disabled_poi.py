"""Disabled-POI reroute: rewrite movement patterns so visits to disabled POIs
become stays at the visitor's home, BEFORE precompute/event-queue, so both the
SoA engine (binary loc_matrix) and the legacy dict path honor it. Extracted from
runner.py (pure code-motion). See the disabled-POI backend work (#19).
"""
from __future__ import annotations

import numpy as np

from .location_ids import normalize_location_id
from .patterns_codec import BinaryPatterns


def _person_home_id(person_data) -> str:
    if not isinstance(person_data, dict):
        return ""
    return normalize_location_id(
        person_data.get("home") or person_data.get("household_id")
    )


def _normalize_person_ids(person_ids) -> list[str]:
    if not isinstance(person_ids, (list, tuple, set)):
        return []
    return [
        normalized_id
        for normalized_id in (normalize_location_id(person_id) for person_id in person_ids)
        if normalized_id
    ]


def _home_id_by_person(people_data) -> dict:
    return {
        normalize_location_id(person_id): home_id
        for person_id, person_data in (people_data or {}).items()
        if (home_id := _person_home_id(person_data))
    }


def _reroute_binary_patterns(
    binary: BinaryPatterns,
    people_data: dict,
    disabled: set,
) -> BinaryPatterns:
    """Reroute disabled-POI visits in the dense ``loc_matrix`` representation.

    The binary patterns carry a ``[T, N]`` matrix of producer location indices
    (index < ``n_homes`` is a home). We send every (person, timestep) entry that
    sits at a disabled place back to that person's home index, vectorized — which
    preserves the engine's binary fast path (``precompute_movement`` reads
    ``loc_matrix`` directly, and the non-engine ``.items()`` reconstruction reads
    it too). People whose home isn't in this run's location table are left in
    place rather than dropped.
    """
    loc_ids = binary.loc_ids
    n_homes = binary.n_homes
    # Homes and places share one id table disambiguated ONLY by position
    # (index < n_homes is a home), and their id strings can collide -- the codec
    # keys its own remap by (id, is_home) for exactly this reason. So we must
    # resolve a disabled-POI id against PLACES and a person's home against HOMES,
    # never a single id->index map (that would mis-resolve a colliding id).
    home_id_to_idx: dict = {}
    place_id_to_idx: dict = {}
    for idx, loc_id in enumerate(loc_ids):
        nid = normalize_location_id(loc_id)
        if idx < n_homes:
            home_id_to_idx.setdefault(nid, idx)
        else:
            place_id_to_idx.setdefault(nid, idx)

    disabled_idx = sorted(
        {
            idx
            for disabled_id in disabled
            if (idx := place_id_to_idx.get(disabled_id)) is not None
        }
    )
    if not disabled_idx:
        return binary

    home_id_by_person = _home_id_by_person(people_data)
    home_idx_by_col = np.full(len(binary.pids), -1, dtype=np.int64)
    for col, pid in enumerate(binary.pids):
        home_id = home_id_by_person.get(normalize_location_id(pid))
        if home_id:
            home_idx = home_id_to_idx.get(home_id)
            if home_idx is not None:
                home_idx_by_col[col] = home_idx
    has_home = home_idx_by_col >= 0
    if not has_home.any():
        return binary

    disabled_arr = np.array(disabled_idx, dtype=binary.loc_matrix.dtype)
    at_disabled = np.isin(binary.loc_matrix, disabled_arr)
    mask = at_disabled & has_home[np.newaxis, :]
    if not mask.any():
        return binary

    home_row = home_idx_by_col.astype(binary.loc_matrix.dtype)
    binary.loc_matrix = np.where(
        mask, np.broadcast_to(home_row, binary.loc_matrix.shape), binary.loc_matrix
    )
    return binary


def reroute_disabled_poi_visits(
    patterns_data,
    people_data: dict,
    disabled_poi_ids,
):
    """Send visits to ``disabled_poi_ids`` back to each visitor's home.

    Operates on the loaded movement patterns *before* they feed the engine or
    the non-engine path, so the disabling is honored by both. Handles the dense
    binary representation (``BinaryPatterns``, the prod default) in-place and
    vectorized, and the legacy ``{ts: {homes, places}}`` dict by rebuilding it.
    """
    disabled = {
        normalized_id
        for normalized_id in (
            normalize_location_id(value) for value in (disabled_poi_ids or [])
        )
        if normalized_id
    }
    if not disabled:
        return patterns_data

    if isinstance(patterns_data, BinaryPatterns):
        return _reroute_binary_patterns(patterns_data, people_data, disabled)

    home_by_person = _home_id_by_person(people_data)
    if not home_by_person:
        return patterns_data

    rerouted: dict = {}
    for timestep, timestep_data in (patterns_data or {}).items():
        if not isinstance(timestep_data, dict):
            rerouted[timestep] = timestep_data
            continue

        raw_homes = timestep_data.get("homes") or {}
        homes = {
            normalize_location_id(home_id): _normalize_person_ids(person_ids)
            for home_id, person_ids in raw_homes.items()
            if normalize_location_id(home_id)
        }
        seen_by_home = {
            home_id: set(person_ids) for home_id, person_ids in homes.items()
        }

        places: dict[str, list[str]] = {}
        raw_places = timestep_data.get("places") or {}
        for place_id, person_ids in raw_places.items():
            place_key = normalize_location_id(place_id)
            normalized_people = _normalize_person_ids(person_ids)
            if not place_key:
                continue

            if place_key not in disabled:
                places[place_key] = normalized_people
                continue

            for person_id in normalized_people:
                home_id = home_by_person.get(person_id)
                if not home_id:
                    continue
                home_people = homes.setdefault(home_id, [])
                seen = seen_by_home.setdefault(home_id, set(home_people))
                if person_id not in seen:
                    home_people.append(person_id)
                    seen.add(person_id)

        rerouted[timestep] = {
            **timestep_data,
            "homes": homes,
            "places": places,
        }

    return rerouted
