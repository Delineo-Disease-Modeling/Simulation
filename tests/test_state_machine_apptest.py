"""Streamlit AppTest smoke tests for the state_machine UIs (manager + creator).

Renders dmp/app/graph_visualization.py headlessly via streamlit.testing and
asserts the tabs render without raising across the key session states. This is
the runtime safety net for the Stage 4 decomposition: the _render_* UI helpers
are not unit-testable, but AppTest exercises them end-to-end and catches any
exception they raise.

Uses the committed state_machines.db read-only (only .run(), never .click()), so
nothing is written. Tests that need a loaded machine skip if the DB is empty.
"""

import os
import sys
import unittest

import matplotlib
matplotlib.use("Agg")

# Only dmp/app is needed here (for the `state_machine` package import below). We
# deliberately do NOT add dmp/ to sys.path: graph_visualization.py adds it itself
# at runtime for its `core.*` imports, and adding it here would make `import app`
# resolve to the dmp/app package and mask the unrelated test_deploy_entrypoints bug.
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dmp", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from streamlit.testing.v1 import AppTest
from state_machine.state_machine_db import StateMachineDB

APP_FILE = os.path.join(APP_DIR, "graph_visualization.py")


def _run(seed=None, timeout=120):
    at = AppTest.from_file(APP_FILE, default_timeout=timeout)
    for k, v in (seed or {}).items():
        at.session_state[k] = v
    at.run()
    return at


def _first_machine():
    machines = StateMachineDB().list_state_machines()
    if not machines:
        return None
    return StateMachineDB().load_state_machine(machines[0][0])


class TestStateMachineAppRenders(unittest.TestCase):
    def assert_clean(self, at, label):
        exc = list(at.exception)
        self.assertEqual(exc, [], f"{label} raised: {exc}")

    def test_default_run(self):
        # Manager tab (filters + machine list) and creator tab (step 1) both execute.
        at = _run()
        self.assert_clean(at, "default")
        subs = [s.value for s in at.subheader]
        self.assertTrue(any("State Machines" in s for s in subs), subs)
        self.assertTrue(any("Step 1" in s for s in subs), subs)

    def test_creator_steps_2_and_3(self):
        for step in (2, 3):
            at = _run({"current_step": step})
            self.assert_clean(at, f"creator_step_{step}")

    def test_creator_step_4(self):
        # Step 4 needs the wizard state steps 1-3 normally set.
        m = _first_machine()
        if not m:
            self.skipTest("no saved machines in DB")
        at = _run({
            "current_step": 4, "disease_name": m["disease_name"] or "COVID-19",
            "model_category": "default", "variant_name": None, "vaccination_status": None,
            "editing_mode": "new", "states": m["states"], "graph_edges": m["edges"],
            "demographics": [],
        })
        self.assert_clean(at, "creator_step_4")

    def test_manager_loaded_detail(self):
        # Seed a loaded machine so the loaded-detail block + simulation tabs render.
        m = _first_machine()
        if not m:
            self.skipTest("no saved machines in DB")
        at = _run({
            "selected_machine": {"id": m["id"], "name": m["name"], "disease_name": m["disease_name"],
                                 "variant_name": m["variant_name"], "model_category": m["model_category"]},
            "states": m["states"], "graph_edges": m["edges"], "demographics": [],
        })
        self.assert_clean(at, "manager_loaded_detail")
        subs = [s.value for s in at.subheader]
        self.assertTrue(any("Loaded State Machine" in s for s in subs), subs)


if __name__ == "__main__":
    unittest.main()
