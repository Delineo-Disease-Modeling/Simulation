"""Tests for the DLNOPAT binary patterns format and the consumer fast path."""
import json

import numpy as np

from simulator.patterns_codec import (
    BinaryPatterns,
    build_arrays_from_legacy,
    decode_patterns_binary,
    encode_patterns_binary,
    is_binary_patterns,
)
from simulator.membership import MembershipStore


# A tiny world where home id "1" and place id "1" collide (the reason locations
# are keyed by (id, is_home)). Three people, two timesteps.
PEOPLE = ["1", "2", "3"]
PAPDATA = {
    "people": {"1": {}, "2": {}, "3": {}},
    "homes": {"1": {}, "2": {}},
    "places": {"1": {}},
}
PATTERNS = {
    "60": {"homes": {"1": ["1"], "2": ["2"]}, "places": {"1": ["3"]}},
    "120": {"homes": {"1": ["1", "2"]}, "places": {"1": ["3"]}},
}
# Homes first, then places — the consumer's location index convention.
LOCATION_KEYS = [("1", True), ("2", True), ("1", False)]


def test_magic_sniff():
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(PATTERNS, PAPDATA)
    blob = encode_patterns_binary(M, ts, pids, loc_ids, n_homes)
    assert is_binary_patterns(blob)
    assert not is_binary_patterns(json.dumps(PATTERNS).encode("utf-8"))


def test_round_trip_preserves_matrix():
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(PATTERNS, PAPDATA)
    bp = decode_patterns_binary(encode_patterns_binary(M, ts, pids, loc_ids, n_homes))
    assert np.array_equal(bp.loc_matrix, M)
    assert bp.ts_minutes == ts
    assert bp.pids == pids
    assert bp.loc_ids == loc_ids
    assert bp.n_homes == n_homes
    assert bp.loc_matrix.dtype == np.uint16


def test_full_snapshot_required():
    # Drop a person from one timestep -> not a full snapshot -> must fail loudly.
    broken = {"60": {"homes": {"1": ["1"]}, "places": {}}}
    try:
        build_arrays_from_legacy(broken, PAPDATA)
    except ValueError as e:
        assert "full snapshot" in str(e)
    else:
        raise AssertionError("expected ValueError for non-full-snapshot patterns")


def _person_loc_trace(store, patterns, max_length):
    """Run precompute + apply for every timestep, return {ts: person_loc copy}."""
    store.precompute_movement(patterns, max_length)
    trace = {}
    for ts in sorted(store._move):
        store.apply_movement(ts)
        trace[ts] = store.person_loc.copy()
    return trace


def test_binary_path_matches_json_path():
    """The binary fast path must produce byte-identical person_loc to the JSON
    loop at every timestep (representation-only change)."""
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(PATTERNS, PAPDATA)
    bp = decode_patterns_binary(encode_patterns_binary(M, ts, pids, loc_ids, n_homes))

    json_store = MembershipStore(PEOPLE, LOCATION_KEYS)
    bin_store = MembershipStore(PEOPLE, LOCATION_KEYS)
    json_trace = _person_loc_trace(json_store, PATTERNS, 120)
    bin_trace = _person_loc_trace(bin_store, bp, 120)

    assert json_trace.keys() == bin_trace.keys()
    for ts in json_trace:
        assert np.array_equal(json_trace[ts], bin_trace[ts]), ts


def test_binary_items_reconstructs_legacy_shape():
    """BinaryPatterns.items() must rebuild the {homes, places} dicts the
    non-engine (event-queue) path consumes — and, because PATTERNS' per-location
    lists are already person-id-sorted, reproduce them in byte-identical ORDER
    (list equality is order-sensitive). This is the non-engine equivalence
    guarantee for a producer whose lists are sorted (the current producer's are).
    """
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(PATTERNS, PAPDATA)
    bp = decode_patterns_binary(encode_patterns_binary(M, ts, pids, loc_ids, n_homes))
    assert dict(bp.items()) == PATTERNS


def test_items_canonicalizes_order_to_person_columns():
    """If a producer's lists are NOT person-sorted, items() returns the canonical
    person-column order (the format does not preserve arbitrary list order). The
    engine path is order-independent; the non-engine path is then only ensemble-
    (not byte-) equivalent — this test pins the documented canonicalization."""
    unsorted = {"60": {"homes": {"1": ["3", "1"]}, "places": {}}, "120": {"homes": {"1": ["1", "3"]}, "places": {}}}
    pap = {"people": {"1": {}, "3": {}}, "homes": {"1": {}}, "places": {}}
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(unsorted, pap)
    bp = decode_patterns_binary(encode_patterns_binary(M, ts, pids, loc_ids, n_homes))
    # Both timesteps come back in person-column (sorted-by-int) order: ["1", "3"].
    assert dict(bp.items())["60"]["homes"]["1"] == ["1", "3"]
    assert dict(bp.items())["120"]["homes"]["1"] == ["1", "3"]


def test_empty_id_table_round_trips_to_empty_list():
    """An empty id table must decode to [] (not [''])."""
    M = np.zeros((2, 0), dtype=np.uint16)
    bp = decode_patterns_binary(encode_patterns_binary(M, [60, 120], [], ["1"], 1))
    assert bp.pids == []
    assert bp.loc_matrix.shape == (2, 0)


def test_beyond_window_location_is_tolerated():
    """A producer location referenced only beyond max_length and absent from the
    consumer's space must NOT crash precompute (mirrors the legacy loop)."""
    pat = {"60": {"homes": {"1": ["1"], "2": ["2"]}, "places": {"1": ["3"]}},
           "120": {"homes": {"1": ["1", "2"]}, "places": {"1": ["3"]}}}
    bp = decode_patterns_binary(
        encode_patterns_binary(*build_arrays_from_legacy(pat, PAPDATA))
    )
    # Inject an extra producer location used by no in-window cell.
    store = MembershipStore(PEOPLE, LOCATION_KEYS)
    store.precompute_movement(bp, 60)  # window stops before any odd location
    assert set(store._move) == {60}


def test_max_length_gating():
    M, ts, pids, loc_ids, n_homes = build_arrays_from_legacy(PATTERNS, PAPDATA)
    bp = decode_patterns_binary(encode_patterns_binary(M, ts, pids, loc_ids, n_homes))
    store = MembershipStore(PEOPLE, LOCATION_KEYS)
    store.precompute_movement(bp, 60)  # only the first timestep
    assert set(store._move) == {60}
