"""Unit tests for SoA-engine eligibility routing + graceful fallback.

The vectorized engine cannot apply movement-altering interventions
(capacity<1 / lockdown / selfiso) or run multi-variant correctly, so
`_engine_eligibility` must report those configs ineligible (→ the runner falls
back to the non-engine path) instead of silently producing wrong results.
"""
import unittest
from unittest import mock

from simulator.runner import SimulationRunner, _engine_requested


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

    def test_lockdown_is_ineligible(self):
        ok, reason = self._eligible(_runner([_iv(lockdown=0.7)]))
        self.assertFalse(ok)
        self.assertIn("movement", reason)

    def test_capacity_cap_is_ineligible(self):
        ok, reason = self._eligible(_runner([_iv(capacity=0.5)]))
        self.assertFalse(ok)
        self.assertIn("movement", reason)

    def test_selfiso_is_ineligible(self):
        ok, _ = self._eligible(_runner([_iv(selfiso=0.3)]))
        self.assertFalse(ok)

    def test_movement_intervention_scheduled_after_t0_is_caught(self):
        # a clean t=0 plus a lockdown that kicks in later must still be caught
        ok, reason = self._eligible(_runner([_iv(time=0), _iv(time=5000, lockdown=0.4)]))
        self.assertFalse(ok)
        self.assertIn("5000", reason)

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


class EngineRequestedEnvParseTest(unittest.TestCase):
    def test_truthy_values_request_engine(self):
        for val in ("1", "true", "TRUE", "yes", "on"):
            with mock.patch.dict("os.environ", {"DELINEO_SOA_ENGINE": val}):
                self.assertTrue(_engine_requested(), val)

    def test_zero_disables_engine(self):
        # the old bool(os.environ.get(...)) was truthy-on-presence: "0" wrongly ON
        with mock.patch.dict("os.environ", {"DELINEO_SOA_ENGINE": "0"}):
            self.assertFalse(_engine_requested())

    def test_unset_disables_engine(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(_engine_requested())


if __name__ == "__main__":
    unittest.main()
