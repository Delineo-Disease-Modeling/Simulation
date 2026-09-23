"""Validity guard for the bundled default disease-progression matrix.

``simulator/config_data/combined_matrices.csv`` is the default DMP matrix; the
Fullstack app ships a byte-identical copy (``public/data/matrices/
combined_default.csv``) and sends it as ``matrix_csv_by_variant``. The CSV DMP
path never validates it: ``run_simulation`` hands each transition row straight to
``np.random.choice``, which raises on a row that doesn't sum to 1, and
``InfectionManager._csv_timeline`` swallows that and uses the 4h-latent / 20h-
infectious fallback timeline. Block 1 (0-18, Vaccinated, M, Delta) shipped with a
first row summing to 1.05, so that whole group silently lost its natural history
(no symptomatic / hospital / ICU / death). These tests keep every block valid.
"""
import contextlib
import io
import math
import os
import re
import unittest

import numpy as np

from dmp_functions import DMPContext, initialize_dmp_from_string, run_dmp_simulation

CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "simulator", "config_data"))
MATRICES_PATH = os.path.join(CONFIG_DIR, "combined_matrices.csv")
STATES_PATH = os.path.join(CONFIG_DIR, "custom_states.txt")

TERMINAL_STATES = {"Recovered", "Deceased"}
SUBMATRICES = 6  # transition, distribution type, mean, std, min cut-off, max cut-off
EXPECTED_BLOCKS = 24  # 3 ages x 2 vaccination x 2 sex x 2 variants
TOL = 1e-9


def _states():
    with open(STATES_PATH) as f:
        return [line.strip() for line in f if line.strip()]


def _blocks():
    """[(header, rows)] — one entry per ``#`` header, rows as float lists."""
    blocks = []
    with open(MATRICES_PATH) as f:
        for line in f:
            stripped = line.strip()
            if stripped.startswith("#"):
                blocks.append((stripped, []))
            elif stripped:
                blocks[-1][1].append([float(v) for v in stripped.rstrip(",").split(",")])
    return blocks


class DefaultMatrixRowSumsTest(unittest.TestCase):
    def test_block_structure(self):
        n = len(_states())
        blocks = _blocks()
        self.assertEqual(len(blocks), EXPECTED_BLOCKS)
        for header, rows in blocks:
            with self.subTest(block=header):
                self.assertEqual(len(rows), SUBMATRICES * n)
                self.assertTrue(all(len(r) == n for r in rows))

    def test_transition_rows_are_probability_distributions(self):
        states = _states()
        for header, rows in _blocks():
            for state, row in zip(states, rows[: len(states)]):
                with self.subTest(block=header, state=state, row=row):
                    self.assertTrue(all(0.0 <= p <= 1.0 for p in row))
                    expected = 0.0 if state in TERMINAL_STATES else 1.0
                    self.assertLessEqual(abs(math.fsum(row) - expected), TOL)

    def test_every_block_samples_through_csv_dmp(self):
        # The real in-memory loader + sampler used by InfectionManager._csv_timeline:
        # each header must resolve to its own block and sample without raising.
        with open(MATRICES_PATH) as f:
            csv_content = f.read()
        ctx = DMPContext()
        initialize_dmp_from_string(ctx, csv_content)
        np.random.seed(0)
        for i, (header, _) in enumerate(_blocks()):
            age, vacc, sex, variant = [p.strip() for p in header[1:].split(",")][:4]
            demographics = {
                "Age": re.match(r"\d+", age).group(),
                "Vaccination Status": vacc,
                "Sex": sex,
                "Variant": variant,
            }
            with self.subTest(block=header):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = run_dmp_simulation(ctx, demographics)
                self.assertEqual(result["matrix_set"], f"Matrix_Set_{i + 1}")
                self.assertIn(result["timeline"][-1][0], TERMINAL_STATES)


if __name__ == "__main__":
    unittest.main()
