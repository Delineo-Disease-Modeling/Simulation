"""In-process Disease Modeling Platform (DMP) timeline provider.

By default the simulator asks the DMP for a disease-progression timeline
over HTTP — one POST to ``localhost:8000/simulate`` per infection. At ZIP
scale that is ~32k round-trips per run and dominates wall-clock, even
though the demographic space is tiny (~200 distinct keys) and the only
per-person randomness is the final state-machine sample.

This provider reaches the DMP's logic directly (the ``dmp/`` package that
ships inside the Simulation repo), skipping HTTP. It splits the work the
HTTP endpoint does atomically into two halves:

* deterministic — find the matching state machine and convert its graph to
  transition/timing matrices. Identical for everyone with the same
  demographics, so it is cached by demographic key (~200 entries).
* stochastic — ``run_simulation`` samples one path through those matrices.
  Cheap (~0.1ms) and must run per person to preserve biological variation.

The matched machine and matrices are exactly what the HTTP endpoint would
compute for the same demographics, and the per-person sample is the same
stochastic draw, so behaviour matches the HTTP path up to the RNG stream.

Construction raises if the ``dmp`` package or its state-machine DB cannot
be loaded; callers treat that as "in-process unavailable" and fall back to
the HTTP path.
"""
from __future__ import annotations

import contextlib
import io
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)

# Cached value meaning "looked this demographic up, nothing matched" — lets us
# cache misses so a no-match demographic doesn't re-query the DB 32k times.
_NO_MATCH = object()


def default_dmp_root() -> str:
    """Path to the dmp/ package that ships alongside the simulator package."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "dmp")


class InProcessDMP:
    """Cached, HTTP-free access to the DMP state-machine timelines."""

    def __init__(self, dmp_root: Optional[str] = None) -> None:
        root = dmp_root or default_dmp_root()
        if root not in sys.path:
            sys.path.insert(0, root)

        # Imported lazily (here, not at module top) so that importing this
        # module never hard-fails when dmp/ is absent — construction is the
        # single place that may raise, and callers catch it.
        from app.state_machine.utils.graph_utils import convert_graph_to_matrices
        from core.dmp_local import DMPLocal
        from core.simulation_functions import run_simulation

        self._convert = convert_graph_to_matrices
        self._run = run_simulation
        self._dmp = DMPLocal()
        # demographic key -> (matrices, states) | _NO_MATCH
        self._cache: dict = {}

    def _lookup(self, disease_name: str, model_path: Optional[str], demographics: dict):
        key = (
            disease_name,
            model_path,
            demographics.get("Age"),
            demographics.get("Sex"),
            demographics.get("Vaccination Status"),
            demographics.get("Variant"),
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # find_matching_state_machine emits diagnostic prints per call; silence
        # them (this runs at most once per demographic key).
        with contextlib.redirect_stdout(io.StringIO()):
            machine = self._dmp.find_matching_state_machine(
                disease_name, demographics, model_path
            )
        if not machine:
            self._cache[key] = _NO_MATCH
            return _NO_MATCH

        matrices = self._convert(machine["states"], machine["edges"])
        entry = (matrices, machine["states"])
        self._cache[key] = entry
        return entry

    def simulate(
        self,
        disease_name: str,
        model_path: Optional[str],
        demographics: dict,
    ) -> Optional[list]:
        """Sample a timeline for these demographics.

        Returns a list of ``(state_name, time_hours)`` tuples (same shape the
        HTTP endpoint returns under ``"timeline"``), or ``None`` when no state
        machine matches — letting the caller fall back.
        """
        entry = self._lookup(disease_name, model_path, demographics)
        if entry is _NO_MATCH:
            return None
        matrices, states = entry
        # initial_state_idx=0: states[0] is the machine's initial state, matching
        # the HTTP endpoint's default when no initial_state is supplied.
        return self._run(
            matrices["Transition Matrix"],
            matrices["Mean Matrix"],
            matrices["Standard Deviation Matrix"],
            matrices["Min Cutoff Matrix"],
            matrices["Max Cutoff Matrix"],
            matrices["Distribution Type Matrix"],
            0,
            states,
        )
