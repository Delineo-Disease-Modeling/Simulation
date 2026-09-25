"""Unit tests for SoA-engine eligibility routing + graceful fallback.

The vectorized engine cannot run multi-variant, pairwise (non-aggregate) or
per-contact-logging configs correctly, so `_engine_eligibility` must report
those ineligible (→ the runner falls back to the non-engine path) instead of
silently producing wrong results. Movement interventions (capacity<1 /
lockdown / selfiso) are applied by the engine and stay eligible; their
behavior is covered in test_engine_movement_interventions.py.
"""
import unittest
from unittest import mock

from simulator.runner import SimulationRunner, _engine_disabled


def _iv(time=0, mask=0.0, vaccine=0.0, capacity=1.0, lockdown=0.0, selfiso=0.0):
    return {"time": time, "mask": mask, "vaccine": vaccine,
            "capacity": capacity, "lockdown": lockdown, "selfiso": selfiso}


def _runner(interventions, variants=("Delta",), enable_logging=False, agg=True):
    simdata = {
        "czone_id": 1, "length": 100, "interventions": list(interventions),
        "variants": list(variants), "aggregate_transmission": agg,
    }
    return SimulationRunner(simdata=simdata, enable_logging=enable_logging,
                            data_loader=lambda *a, **k: ({}, {}))


class EngineEligibilityTest(unittest.TestCase):
    def _eligible(self, runner):
        return runner._engine_eligibility(runner.simdata["variants"])

    def test_clean_single_variant_run_is_eligible(self):
        ok, reason = self._eligible(_runner([_iv()]))
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_no_interventions_is_eligible(self):
        ok, _ = self._eligible(_runner([]))
        self.assertTrue(ok)

    def test_mask_and_vaccine_only_is_eligible(self):
        # person-level interventions don't move people → engine applies them
        ok, _ = self._eligible(_runner([_iv(mask=0.8, vaccine=0.5)]))
        self.assertTrue(ok)

    def test_movement_interventions_are_eligible(self):
        for iv in (_iv(lockdown=0.7), _iv(capacity=0.5), _iv(selfiso=0.3),
                   _iv(capacity=0.5, lockdown=0.2, selfiso=0.9)):
            ok, reason = self._eligible(_runner([iv]))
            self.assertTrue(ok, iv)
            self.assertEqual(reason, "")

    def test_movement_intervention_scheduled_after_t0_is_detected(self):
        # The engine enables intervention-aware movement when ANY time point
        # needs it, so a lockdown that starts later must be detected.
        runner = _runner([_iv(time=0), _iv(time=5000, lockdown=0.4)])
        self.assertTrue(runner._movement_interventions_scheduled())
        self.assertFalse(_runner([_iv(time=0), _iv(time=5, mask=0.9)])
                         ._movement_interventions_scheduled())

    def test_multi_variant_is_ineligible(self):
        ok, reason = self._eligible(_runner([_iv()], variants=("Delta", "Omicron")))
        self.assertFalse(ok)
        self.assertIn("multi-variant", reason)

    def test_logging_on_is_ineligible(self):
        ok, reason = self._eligible(_runner([_iv()], enable_logging=True))
        self.assertFalse(ok)
        self.assertIn("logging", reason)

    def test_aggregate_off_is_ineligible(self):
        ok, reason = self._eligible(_runner([_iv()], agg=False))
        self.assertFalse(ok)
        self.assertIn("aggregate", reason)


class EngineKillSwitchEnvParseTest(unittest.TestCase):
    """The engine is ON BY DEFAULT; DELINEO_SOA_ENGINE=0/false/off is the kill
    switch. _engine_disabled() is True only for those explicit-off values."""

    def test_off_values_disable_engine(self):
        for val in ("0", "false", "FALSE", "no", "off"):
            with mock.patch.dict("os.environ", {"DELINEO_SOA_ENGINE": val}):
                self.assertTrue(_engine_disabled(), val)

    def test_unset_leaves_engine_on_by_default(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_engine_disabled())

    def test_on_values_leave_engine_enabled(self):
        for val in ("1", "true", "yes", "on", ""):
            with mock.patch.dict("os.environ", {"DELINEO_SOA_ENGINE": val}):
                self.assertFalse(_engine_disabled(), val)


if __name__ == "__main__":
    unittest.main()
