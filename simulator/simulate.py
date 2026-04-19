from __future__ import annotations

from typing import Callable, Optional

from .event_queue import EventQueue
from .runner import SimulationRunner, move_people
from .world import DiseaseSimulator


def run_simulator(
    simdata: dict,
    enable_logging: bool = True,
    output_dir: Optional[str] = None,
    progress_callback: Optional[Callable] = None,
) -> dict:
    return SimulationRunner(
        simdata=simdata,
        enable_logging=enable_logging,
        output_dir=output_dir,
        progress_callback=progress_callback,
    ).run()


__all__ = [
    "DiseaseSimulator",
    "EventQueue",
    "move_people",
    "run_simulator",
]
