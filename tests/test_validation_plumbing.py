"""Validation plumbing: per-run random_seed + ventilation_coeff pass-through.

Enables the calibration driver to (a) run reproducible-but-distinct ensemble
replicates by passing a per-replicate random_seed (seeds BOTH Python and NumPy —
the live kernel and DMP sampling draw from NumPy), and (b) vary ventilation_coeff
per run for the movement×ventilation ridge diagnostic without relying on the
import-time env read.
"""
import random
import unittest

import numpy as np

from simulator.config import INFECTION_MODEL
from simulator.runner import DETERMINISTIC_RANDOM_SEED, SimulationRunner
from simulator.simdata import normalize_simdata


def _runner(**overrides):
    simdata = {"czone_id": 1, "length": 1, "interventions": [{"time": 0}]}
    simdata.update(overrides)
    return SimulationRunner(simdata, enable_logging=False)


class NormalizeSimdataTest(unittest.TestCase):
    def test_new_fields_default_to_none(self):
        d = normalize_simdata({"czone_id": 1, "length": 1, "interventions": [{"time": 0}]})
        self.assertIsNone(d["random_seed"])
        self.assertIsNone(d["ventilation_coeff"])

    def test_new_fields_pass_through(self):
        d = normalize_simdata({
            "czone_id": 1, "length": 1, "interventions": [{"time": 0}],
            "random_seed": 7, "ventilation_coeff": 12.5,
        })
        self.assertEqual(d["random_seed"], 7)
        self.assertEqual(d["ventilation_coeff"], 12.5)


class SeedRandomTest(unittest.TestCase):
    def _first_draws(self, **overrides):
        runner = _runner(**overrides)
        runner._seed_random()
        return (random.random(), float(np.random.random()))

    def test_explicit_seed_is_reproducible_and_seeds_numpy(self):
        # Equal NumPy draws across two independent seedings proves NumPy is seeded
        # (not just Python) — without the numpy seed the second call would continue
        # the advanced global stream and differ.
        self.assertEqual(
            self._first_draws(random_seed=7, randseed=True),
            self._first_draws(random_seed=7, randseed=True),
        )

    def test_distinct_seeds_give_distinct_draws(self):
        self.assertNotEqual(
            self._first_draws(random_seed=7),
            self._first_draws(random_seed=8),
        )

    def test_explicit_seed_overrides_randseed_true(self):
        # randseed=True alone leaves RNGs unseeded (stochastic); an explicit
        # random_seed must force reproducibility regardless.
        self.assertEqual(
            self._first_draws(random_seed=3, randseed=True),
            self._first_draws(random_seed=3, randseed=True),
        )

    def test_deterministic_mode_still_works_without_explicit_seed(self):
        self.assertEqual(
            self._first_draws(randseed=False),
            self._first_draws(randseed=False),
        )


class VentilationCoeffTest(unittest.TestCase):
    def test_simdata_override_takes_effect(self):
        self.assertEqual(_runner(ventilation_coeff=13.0).ventilation_coeff, 13.0)

    def test_defaults_to_config_when_absent(self):
        self.assertEqual(
            _runner().ventilation_coeff,
            float(INFECTION_MODEL.get("ventilation_coeff", 9.0)),
        )


if __name__ == "__main__":
    unittest.main()
