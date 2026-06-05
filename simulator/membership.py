"""Struct-of-arrays location membership (Step 1 scaffolding).

`MembershipStore` holds the canonical *location membership* of every person in
parallel NumPy arrays instead of the per-`Location` `population` dict:

    person_loc:  int32[N]  -- current location index per person (-1 = unplaced)
    arrival_seq: int64[N]  -- monotonic counter stamped on each placement

`occupancy_view()` groups people by location with a single counting sort,
producing contiguous per-location slices (`occupants[start:start+count]`). The
secondary sort key is `arrival_seq`, so within a location the order reproduces
the dict's insertion order (= arrival order, since `move_people` does
remove-then-append). That stable ordering is what keeps the movement snapshot
byte-identical when consumers switch from the dict to this view.

This module is wiring only: in Step 1 it runs in *shadow* mode alongside the
dicts (behind `DELINEO_SOA_SHADOW`) so we can assert the two agree before any
consumer reads from it.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np


class OccupancyView(NamedTuple):
    """People grouped by location for one timestep.

    For location index ``l``, its occupant person-indices (in arrival order) are
    ``occupants[starts[l] : starts[l] + counts[l]]``.
    """

    counts: np.ndarray   # int32[L]
    starts: np.ndarray   # int32[L]   (exclusive prefix sum of counts)
    occupants: np.ndarray  # int32[num_placed]  person indices, grouped by loc

    def occupants_of(self, loc_idx: int) -> np.ndarray:
        start = self.starts[loc_idx]
        return self.occupants[start : start + self.counts[loc_idx]]


class MembershipStore:
    def __init__(self, person_ids: list[str], location_keys: list[tuple[str, bool]]) -> None:
        # Person index space.
        self.idx_to_pid: list[str] = [str(p) for p in person_ids]
        self.pid_to_idx: dict[str, int] = {pid: i for i, pid in enumerate(self.idx_to_pid)}
        # Location index space (households + facilities share one space; the key
        # is (id, is_household) because a household and a facility can share an id).
        self.idx_to_loc: list[tuple[str, bool]] = list(location_keys)
        self.loc_to_idx: dict[tuple[str, bool], int] = {
            key: i for i, key in enumerate(self.idx_to_loc)
        }

        n = len(self.idx_to_pid)
        self.person_loc: np.ndarray = np.full(n, -1, dtype=np.int32)
        self.arrival_seq: np.ndarray = np.zeros(n, dtype=np.int64)
        self._seq: int = 0

    @property
    def num_locations(self) -> int:
        return len(self.idx_to_loc)

    def note_placement(self, pid: str, loc_idx: int) -> None:
        """Record that person ``pid`` is now at location index ``loc_idx``."""
        pidx = self.pid_to_idx[str(pid)]
        self.person_loc[pidx] = loc_idx
        self.arrival_seq[pidx] = self._seq
        self._seq += 1

    def occupancy_view(self) -> OccupancyView:
        placed_mask = self.person_loc >= 0
        placed_idx = np.nonzero(placed_mask)[0].astype(np.int32)
        locs = self.person_loc[placed_idx]
        seqs = self.arrival_seq[placed_idx]
        # Primary key location, secondary key arrival_seq -> within-location order
        # matches dict insertion order.
        order = np.lexsort((seqs, locs))
        occupants = placed_idx[order]
        counts = np.bincount(locs, minlength=self.num_locations).astype(np.int32)
        starts = np.zeros(self.num_locations, dtype=np.int32)
        if self.num_locations > 1:
            np.cumsum(counts[:-1], out=starts[1:])
        return OccupancyView(counts=counts, starts=starts, occupants=occupants)
