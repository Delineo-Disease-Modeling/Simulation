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

        # Filled by set_person_refs once Person objects exist; lets the
        # transmission kernel map an occupancy person-index back to its Person
        # via an O(1) list index instead of a dict lookup.
        self.idx_to_person: list = [None] * n
        # Monotonic ever-infected mask (set via mark_infected at every
        # schedule_infection); powers the numeric per-location infected count.
        self.infected_mask: np.ndarray = np.zeros(n, dtype=bool)
        # Hot per-person scalars mirrored for the (future) vectorized kernel.
        # pstate holds the single-variant InfectionState value (0 = SUSCEPTIBLE);
        # maintained in update_people_states. masked / vax factors default to the
        # no-intervention case and are updated when interventions apply.
        self.pstate: np.ndarray = np.zeros(n, dtype=np.int8)
        self.masked: np.ndarray = np.zeros(n, dtype=bool)
        self.vax_trans_factor: np.ndarray = np.ones(n, dtype=np.float32)
        self.vax_inf_protection: np.ndarray = np.zeros(n, dtype=np.float32)
        # Households occupy the first n_homes location indices (see how
        # location_keys is built: households then facilities).
        self.n_homes: int = sum(1 for _, is_hh in self.idx_to_loc if is_hh)
        # pid-string array for fast snapshot gather (idx_to_pid as object array).
        self._pid_arr: np.ndarray = np.array(self.idx_to_pid, dtype=object)
        # Per-timestep movement, precomputed from patterns (see precompute_movement):
        #   _move[ts] = (person_idx int32[], loc_idx int32[])
        self._move: dict[int, tuple] = {}

    @property
    def num_locations(self) -> int:
        return len(self.idx_to_loc)

    def set_person_refs(self, get_person) -> None:
        """Populate idx_to_person and stamp each Person with its store index."""
        for i, pid in enumerate(self.idx_to_pid):
            person = get_person(pid)
            self.idx_to_person[i] = person
            if person is not None:
                person._soa_idx = i

    def precompute_movement(self, patterns: dict, max_length: int) -> None:
        """Convert patterns into per-timestep (person_idx, loc_idx) arrays.

        Each timestep's patterns list every person at their location, so applying
        these arrays fully sets person_loc (a vectorized scatter) — replacing the
        per-person dict remove/add loop in move_people. Done once at build.
        """
        pid_to_idx = self.pid_to_idx
        loc_to_idx = self.loc_to_idx
        for ts_str, data in patterns.items():
            ts = int(ts_str)
            if ts > max_length or not isinstance(data, dict):
                continue
            persons: list[int] = []
            locs: list[int] = []
            for poi_type, is_hh in (("homes", True), ("places", False)):
                for loc_id, pids in data.get(poi_type, {}).items():
                    loc_idx = loc_to_idx[(str(loc_id), is_hh)]
                    for pid in pids:
                        pidx = pid_to_idx.get(str(pid))
                        if pidx is not None:
                            persons.append(pidx)
                            locs.append(loc_idx)
            self._move[ts] = (
                np.asarray(persons, dtype=np.int32),
                np.asarray(locs, dtype=np.int32),
            )

    def mark_infected(self, pid: str) -> None:
        idx = self.pid_to_idx.get(str(pid))
        if idx is not None:
            self.infected_mask[idx] = True

    def movement_snapshot_numeric(self) -> dict:
        """Per-location [count, infected] in homes/places order, via two
        bincounts — O(N) numpy, ~50x cheaper than materializing pid lists.

        Output: {"h": [c0,i0, c1,i1, ...], "p": [...]} matching the map-cache
        shape the Next sim-processor builds, so the frontend consumes it directly.
        """
        pl = self.person_loc
        placed = pl >= 0
        locs = pl[placed]
        L = self.num_locations
        counts = np.bincount(locs, minlength=L)
        inf = np.bincount(
            locs, weights=self.infected_mask[placed], minlength=L
        ).astype(np.int64)
        H = self.n_homes
        h = np.empty(2 * H, dtype=np.int64)
        h[0::2] = counts[:H]
        h[1::2] = inf[:H]
        p = np.empty(2 * (L - H), dtype=np.int64)
        p[0::2] = counts[H:]
        p[1::2] = inf[H:]
        return {"h": h.tolist(), "p": p.tolist()}

    def apply_movement(self, ts: int) -> bool:
        """Vectorized scatter: place everyone listed at timestep ts. No-op-safe."""
        entry = self._move.get(ts)
        if entry is None:
            return False
        person_idx, loc_idx = entry
        self.person_loc[person_idx] = loc_idx
        return True

    def movement_snapshot(self, view: "OccupancyView | None" = None) -> dict:
        """Build the pid-string movement snapshot from person_loc (numpy gather).

        UI-compatible (same {homes,places: {loc_id: [pids]}} shape). The numeric
        form is ~50x cheaper but needs the consumer to change; this keeps the
        engine win (vectorized movement) independent of the frontend. Pass a
        prebuilt OccupancyView to avoid recomputing it.
        """
        if view is None:
            view = self.occupancy_view()
        pid_arr = self._pid_arr
        counts, starts, occupants = view.counts, view.starts, view.occupants
        homes: dict = {}
        places: dict = {}
        for loc_idx, (loc_id, is_hh) in enumerate(self.idx_to_loc):
            count = counts[loc_idx]
            if count == 0:
                continue
            start = starts[loc_idx]
            pids = pid_arr[occupants[start : start + count]].tolist()
            (homes if is_hh else places)[loc_id] = pids
        return {"homes": homes, "places": places}

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
