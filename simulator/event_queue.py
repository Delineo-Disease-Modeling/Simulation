from __future__ import annotations

import heapq

POI_TYPES = [("homes", True), ("places", False)]


class EventQueue:
    """Priority queue plus buffered movement data for infection-triggered POI checks."""

    def __init__(self, stream_iterator) -> None:
        self._queue: list[tuple[int, str, bool]] = []
        self._queued: set[tuple[int, str, bool]] = set()
        self._registry: dict[str, list[tuple[str, int, int]]] = {}
        self._buffer: dict[str, dict] = {}
        self._person_index: dict[str, list[tuple[int, str, bool]]] = {}
        self._stream = stream_iterator
        self._stream_exhausted = False

    @property
    def buffer(self) -> dict[str, dict]:
        return self._buffer

    @property
    def registry(self) -> dict[str, list[tuple[str, int, int]]]:
        return self._registry

    def __bool__(self) -> bool:
        return bool(self._queue)

    def __len__(self) -> int:
        return len(self._queue)

    def peek(self) -> tuple[int, str, bool]:
        return self._queue[0]

    def pop(self) -> tuple[int, str, bool]:
        entry = heapq.heappop(self._queue)
        self._queued.discard(entry)
        return entry

    def enqueue(self, timestep: int, poi_id: str, is_household: bool) -> None:
        key = (timestep, str(poi_id), is_household)
        if key not in self._queued:
            heapq.heappush(self._queue, key)
            self._queued.add(key)

    def register_infectious(self, person_id: str, variant: str, start: int, end: int) -> None:
        pid = str(person_id)
        self._registry.setdefault(pid, []).append((variant, start, end))

        for ts, poi_id, is_hh in self._person_index.get(pid, ()):
            if start <= ts <= end:
                self.enqueue(ts, poi_id, is_hh)

    def ingest_patterns(self, patterns: dict) -> None:
        self._ingest_patterns(patterns)

    def _ingest_patterns(self, patterns: dict) -> None:
        for ts_str, data in patterns.items():
            self._buffer[ts_str] = data
            if not isinstance(data, dict):
                continue

            ts = int(ts_str)
            for poi_type, is_hh in POI_TYPES:
                for poi_id, person_ids in data.get(poi_type, {}).items():
                    poi_id_str = str(poi_id)
                    for pid in person_ids:
                        pid_str = str(pid)
                        self._person_index.setdefault(pid_str, []).append((ts, poi_id_str, is_hh))
                        if pid_str in self._registry:
                            for _, inf_start, inf_end in self._registry[pid_str]:
                                if inf_start <= ts <= inf_end:
                                    self.enqueue(ts, poi_id_str, is_hh)
                                    break

    def _read_stream_chunk(self) -> bool:
        if self._stream_exhausted:
            return False

        try:
            chunk = next(self._stream)
        except StopIteration:
            self._stream_exhausted = True
            return False

        if "patterns" in chunk:
            self._ingest_patterns(chunk["patterns"])
        return True

    def buffer_until(self, target_ts: int) -> None:
        target_str = str(target_ts)
        while target_str not in self._buffer:
            if not self._read_stream_chunk():
                break

    def drain_stream(self) -> None:
        while self._read_stream_chunk():
            pass

    def consume_pattern(self, ts_str: str) -> None:
        self._buffer.pop(ts_str, None)
