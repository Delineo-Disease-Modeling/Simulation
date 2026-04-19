from __future__ import annotations

import os
from typing import Optional

from .io import IncrementalJSONWriter


class SimulationSnapshotWriter:
    """Writes timestep snapshots either to gzip JSON files or in-memory dicts."""

    def __init__(self, output_dir: Optional[str] = None) -> None:
        self.output_dir = output_dir
        self._simdata_writer = None
        self._patterns_writer = None
        self._simdata_json: Optional[dict] = {} if not output_dir else None
        self._patterns_json: Optional[dict] = {} if not output_dir else None
        self._simdata_path: Optional[str] = None
        self._patterns_path: Optional[str] = None

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            self._simdata_path = os.path.join(output_dir, "simdata.json.gz")
            self._patterns_path = os.path.join(output_dir, "patterns.json.gz")
            self._simdata_writer = IncrementalJSONWriter(self._simdata_path)
            self._patterns_writer = IncrementalJSONWriter(self._patterns_path)

    def write(self, ts_str: str, movement: dict, result: dict) -> None:
        if self._patterns_writer and self._simdata_writer:
            self._patterns_writer.add(ts_str, movement)
            self._simdata_writer.add(ts_str, result)
            return

        self._patterns_json[ts_str] = movement
        self._simdata_json[ts_str] = result

    def close(self) -> None:
        if self._simdata_writer:
            self._simdata_writer.close()
            self._simdata_writer = None
        if self._patterns_writer:
            self._patterns_writer.close()
            self._patterns_writer = None

    def result(self) -> dict:
        if self.output_dir:
            return {
                "simdata": self._simdata_path,
                "patterns": self._patterns_path,
            }
        return {
            "movement": self._patterns_json,
            "result": self._simdata_json,
        }


def build_movement_snapshot(simulator) -> dict:
    return {
        "homes": {
            str(household.id): list(household.population.keys())
            for household in simulator.households.values()
            if household.population
        },
        "places": {
            str(facility.id): list(facility.population.keys())
            for facility in simulator.facilities.values()
            if facility.population
        },
    }


def build_infection_snapshot(variant_infected: dict[str, dict[str, int]]) -> dict:
    return {variant: dict(infected) for variant, infected in variant_infected.items()}
