"""Tests for the dmp state_machine refactor.

Covers the pure logic extracted into ``state_machine.logic`` and the
``StateMachineDB`` CRUD layer. Mirrors ``tests/test_simulator_refactor.py``:
unit tests for behavior + characterization (round-trip) tests for contracts.

These tests deliberately import only the Streamlit-free modules
(``state_machine.logic.*`` and ``state_machine.state_machine_db``) so they run
headless — no ``streamlit`` / ``core`` runtime required. See finding #6 in the
refactor plan: ``dmp/app`` must be on ``sys.path`` for the ``state_machine``
package root to resolve.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

import matplotlib
matplotlib.use("Agg")  # headless: no display backend
import matplotlib.figure

# Put dmp/app on the path so `state_machine` resolves (mirrors graph_visualization.py).
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dmp", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from state_machine.logic.transition_math import (
    validate_transition_probabilities,
    calculate_aggregated_probabilities,
    analyze_simulation_results,
    create_visualizations,
)
from state_machine.state_machine_db import StateMachineDB
from state_machine.logic.edge_json import edges_to_json_payload, parse_edges_json
from state_machine.logic.machine_naming import build_demographics_dict, build_machine_name_and_path
from state_machine.logic.machine_filters import filter_machines


def edge(source, target, prob, mean=5, std=1.0, dist="normal", mn=0.0, mx=10.0):
    """Build an edge in the {'data': {...}} shape the app uses."""
    return {
        "data": {
            "source": source,
            "target": target,
            "transition_prob": prob,
            "mean_time": mean,
            "std_dev": std,
            "distribution_type": dist,
            "min_cutoff": mn,
            "max_cutoff": mx,
        }
    }


def machine_row(id=1, name="M", disease="COVID-19", variant=None, category="default",
                model_path="default.general", created="2024-01-01", updated="2024-01-01",
                demographics="{}"):
    """Build a StateMachineDB.list_state_machines() row tuple."""
    return (id, name, disease, variant, category, model_path, created, updated, demographics)


class TestValidateTransitionProbabilities(unittest.TestCase):
    def test_outgoing_probs_summing_to_one_are_valid(self):
        states = ["A", "B", "C"]
        edges = [edge("A", "B", 0.3), edge("A", "C", 0.7)]  # source A sums to 1.0
        result = validate_transition_probabilities(states, edges)
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["errors"], [])

    def test_outgoing_probs_not_summing_to_one_are_flagged(self):
        states = ["A", "B"]
        edges = [edge("A", "B", 0.7)]  # source A sums to 0.7
        result = validate_transition_probabilities(states, edges)
        self.assertFalse(result["is_valid"])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("'A'", result["errors"][0])
        self.assertIn("0.700", result["errors"][0])

    def test_tolerance_boundary(self):
        states = ["A", "B", "C"]
        # 0.5 + 0.5005 = 1.0005, diff 0.0005 < 0.001 -> valid
        self.assertTrue(
            validate_transition_probabilities(states, [edge("A", "B", 0.5), edge("A", "C", 0.5005)])["is_valid"]
        )
        # 0.5 + 0.51 = 1.01, diff 0.01 > 0.001 -> invalid
        self.assertFalse(
            validate_transition_probabilities(states, [edge("A", "B", 0.5), edge("A", "C", 0.51)])["is_valid"]
        )

    def test_states_without_outgoing_edges_are_not_checked(self):
        # Terminal states (no outgoing edges) must not produce errors.
        states = ["A", "B"]
        edges = [edge("A", "B", 1.0)]  # B has no outgoing edges
        self.assertTrue(validate_transition_probabilities(states, edges)["is_valid"])


class TestCalculateAggregatedProbabilities(unittest.TestCase):
    def test_empty_edges_returns_empty_dict(self):
        self.assertEqual(calculate_aggregated_probabilities(["A", "B"], []), {})

    def test_deterministic_chain_reaches_every_state(self):
        states = ["A", "B", "C"]
        edges = [edge("A", "B", 1.0), edge("B", "C", 1.0)]
        result = calculate_aggregated_probabilities(states, edges)
        for s in states:
            self.assertAlmostEqual(result[s], 1.0, places=6)

    def test_branch_splits_probability(self):
        states = ["A", "B", "C"]
        edges = [edge("A", "B", 0.3), edge("A", "C", 0.7)]
        result = calculate_aggregated_probabilities(states, edges)
        self.assertAlmostEqual(result["A"], 1.0, places=6)
        self.assertAlmostEqual(result["B"], 0.3, places=6)
        self.assertAlmostEqual(result["C"], 0.7, places=6)

    def test_probability_is_capped_at_one_in_a_cycle(self):
        # A<->B cycle would accumulate >1 without the min(1.0, ...) cap.
        states = ["A", "B"]
        edges = [edge("A", "B", 1.0), edge("B", "A", 1.0)]
        result = calculate_aggregated_probabilities(states, edges)
        self.assertLessEqual(result["A"], 1.0)
        self.assertLessEqual(result["B"], 1.0)


class TestAnalyzeSimulationResults(unittest.TestCase):
    def test_empty_input_returns_none(self):
        self.assertIsNone(analyze_simulation_results(None, ["A"]))
        self.assertIsNone(analyze_simulation_results([], ["A"]))

    def test_statistics_over_hand_built_timelines(self):
        states = ["A", "B", "C", "D"]  # D is never visited
        sim1 = [("A", 0), ("B", 5), ("C", 12)]  # durations: A=5, B=7, C=0 (final)
        sim2 = [("A", 0), ("C", 8)]              # durations: A=8, C=0 (final)
        stats = analyze_simulation_results([sim1, sim2], states)

        self.assertEqual(stats["total_simulations"], 2)
        self.assertEqual(stats["final_state_distribution"], {"C": 2})

        self.assertAlmostEqual(stats["total_duration_stats"]["mean"], 10.0)
        self.assertAlmostEqual(stats["total_duration_stats"]["min"], 8.0)
        self.assertAlmostEqual(stats["total_duration_stats"]["max"], 12.0)

        self.assertAlmostEqual(stats["state_visit_rates"]["A"], 100.0)
        self.assertAlmostEqual(stats["state_visit_rates"]["B"], 50.0)
        self.assertAlmostEqual(stats["state_visit_rates"]["C"], 100.0)
        self.assertAlmostEqual(stats["state_visit_rates"]["D"], 0.0)

        # A: non-zero durations [5, 8] -> mean 6.5
        self.assertAlmostEqual(stats["state_time_stats"]["A"]["mean_time"], 6.5)
        # B: single non-zero duration [7]
        self.assertAlmostEqual(stats["state_time_stats"]["B"]["mean_time"], 7.0)
        # C: visited twice but only as final state -> all-zero branch
        self.assertEqual(stats["state_time_stats"]["C"]["non_zero_visits"], 0)
        self.assertEqual(stats["state_time_stats"]["C"]["mean_time"], 0)
        self.assertEqual(stats["state_time_stats"]["C"]["visit_count"], 2)
        # D: never visited -> empty branch
        self.assertEqual(stats["state_time_stats"]["D"]["visit_count"], 0)
        self.assertEqual(stats["state_time_stats"]["D"]["mean_time"], 0)


class TestCreateVisualizations(unittest.TestCase):
    def test_none_stats_returns_none(self):
        self.assertIsNone(create_visualizations(None, [[("A", 0)]], ["A"]))
        self.assertIsNone(create_visualizations({"x": 1}, [], ["A"]))

    def test_returns_a_four_axis_figure(self):
        states = ["A", "B", "C"]
        # >= 5 sims so the histogram's bins = min(20, len//5) is positive.
        sims = []
        for i in range(10):
            if i % 2 == 0:
                sims.append([("A", 0), ("B", 4), ("C", 10 + i)])
            else:
                sims.append([("A", 0), ("C", 6 + i)])
        stats = analyze_simulation_results(sims, states)
        fig = create_visualizations(stats, sims, states)
        self.assertIsInstance(fig, matplotlib.figure.Figure)
        self.assertEqual(len(fig.axes), 4)
        matplotlib.pyplot.close(fig)


class TestStateMachineDB(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test_state_machines.db")
        self.db = StateMachineDB(db_path=self.db_path)
        self.states = ["A", "B", "C"]
        self.edges = [edge("A", "B", 0.5, mean=5), edge("A", "C", 0.5, mean=9)]

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_list_load_round_trip(self):
        sm_id = self.db.save_state_machine(
            "M1", self.states, self.edges,
            demographics={"Sex": "Male"},
            disease_name="COVID-19", variant_name="Delta",
            model_category="variant", model_path="variant.Delta.general",
            update_existing=False,
        )
        listed = self.db.list_state_machines()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0][1], "M1")        # name
        self.assertEqual(listed[0][2], "COVID-19")  # disease_name

        loaded = self.db.load_state_machine(sm_id)
        self.assertEqual(loaded["states"], self.states)
        self.assertEqual(loaded["demographics"], {"Sex": "Male"})
        self.assertEqual(loaded["disease_name"], "COVID-19")
        self.assertEqual(loaded["variant_name"], "Delta")
        self.assertEqual(loaded["model_category"], "variant")
        self.assertEqual(loaded["model_path"], "variant.Delta.general")

        self.assertEqual(len(loaded["edges"]), 2)
        # Structural fields round-trip (ignore the regenerated display label).
        by_target = {e["data"]["target"]: e["data"] for e in loaded["edges"]}
        self.assertAlmostEqual(by_target["B"]["transition_prob"], 0.5)
        self.assertEqual(by_target["B"]["mean_time"], 5)
        self.assertEqual(by_target["C"]["mean_time"], 9)

    def test_update_existing_updates_in_place(self):
        id1 = self.db.save_state_machine("M1", self.states, self.edges, disease_name="COVID-19")
        new_edges = [edge("A", "B", 1.0, mean=3)]
        id2 = self.db.save_state_machine("M1", self.states, new_edges, disease_name="COVID-19", update_existing=True)
        self.assertEqual(id1, id2)
        self.assertEqual(len(self.db.list_state_machines()), 1)
        loaded = self.db.load_state_machine(id2)
        self.assertEqual(len(loaded["edges"]), 1)
        self.assertEqual(loaded["edges"][0]["data"]["mean_time"], 3)

    def test_duplicate_name_without_update_raises(self):
        self.db.save_state_machine("M1", self.states, self.edges)
        with self.assertRaises(ValueError):
            self.db.save_state_machine("M1", self.states, self.edges, update_existing=False)

    def test_delete_removes_machine(self):
        sm_id = self.db.save_state_machine("M1", self.states, self.edges)
        self.db.delete_state_machine(sm_id)
        self.assertEqual(self.db.list_state_machines(), [])
        self.assertIsNone(self.db.load_state_machine(sm_id))

    def test_get_unique_diseases_excludes_unknown(self):
        self.db.save_state_machine("M1", self.states, self.edges, disease_name="COVID-19")
        self.db.save_state_machine("M2", self.states, self.edges)  # disease defaults to "Unknown"
        self.assertEqual(self.db.get_unique_diseases(), ["COVID-19"])

    def test_load_missing_returns_none(self):
        self.assertIsNone(self.db.load_state_machine(99999))

    def test_construction_is_idempotent(self):
        # Re-opening the same DB path must not raise (covers _create_tables/_migrate_database).
        self.db.save_state_machine("M1", self.states, self.edges)
        reopened = StateMachineDB(db_path=self.db_path)
        self.assertEqual(len(reopened.list_state_machines()), 1)


class TestEdgeJson(unittest.TestCase):
    def test_payload_strips_label(self):
        e = edge("A", "B", 1.0)
        e["data"]["label"] = "p=1.000"
        payload = edges_to_json_payload([e])
        self.assertNotIn("label", payload)
        self.assertEqual(json.loads(payload)[0]["source"], "A")

    def test_parse_ok_round_trip(self):
        edges = [edge("A", "B", 0.5, mean=5), edge("A", "C", 0.5, mean=9)]
        status, new_edges, errors = parse_edges_json(edges_to_json_payload(edges), ["A", "B", "C"])
        self.assertEqual(status, "ok")
        self.assertEqual(errors, [])
        self.assertEqual(len(new_edges), 2)
        self.assertEqual(new_edges[0]["data"]["mean_time"], 5)
        self.assertIn("label", new_edges[0]["data"])

    def test_parse_mean_time_coerced_to_int(self):
        payload = json.dumps([{
            "source": "A", "target": "B", "transition_prob": 1.0,
            "mean_time": 10.0, "std_dev": 2.0, "distribution_type": "triangular",
            "min_cutoff": 7.0, "max_cutoff": 14.0,
        }])
        status, new_edges, _ = parse_edges_json(payload, ["A", "B"])
        self.assertEqual(status, "ok")
        self.assertIsInstance(new_edges[0]["data"]["mean_time"], int)
        self.assertEqual(new_edges[0]["data"]["mean_time"], 10)

    def test_parse_not_a_list_is_invalid(self):
        status, new_edges, errors = parse_edges_json("{}", ["A"])
        self.assertEqual(status, "invalid")
        self.assertIsNone(new_edges)
        self.assertIn("list", errors[0])

    def test_parse_element_not_dict_is_invalid(self):
        status, _, errors = parse_edges_json("[1]", ["A"])
        self.assertEqual(status, "invalid")
        self.assertIn("JSON object", errors[0])

    def test_parse_missing_fields_is_invalid(self):
        status, _, errors = parse_edges_json('[{"source": "A", "target": "B"}]', ["A", "B"])
        self.assertEqual(status, "invalid")
        self.assertIn("Missing required fields", errors[0])

    def test_parse_unknown_source_and_target_are_invalid(self):
        s1, _, e1 = parse_edges_json(edges_to_json_payload([edge("X", "B", 1.0)]), ["A", "B"])
        self.assertEqual(s1, "invalid")
        self.assertIn("Source state", e1[0])
        s2, _, e2 = parse_edges_json(edges_to_json_payload([edge("A", "Z", 1.0)]), ["A", "B"])
        self.assertEqual(s2, "invalid")
        self.assertIn("Target state", e2[0])

    def test_parse_malformed_json_is_error(self):
        # Exceptions map to 'error' (the original showed the error but did NOT halt the page).
        status, new_edges, errors = parse_edges_json("not json", ["A"])
        self.assertEqual(status, "error")
        self.assertIsNone(new_edges)
        self.assertIn("Invalid JSON format", errors[0])

    def test_parse_bad_numeric_is_error(self):
        payload = json.dumps([{
            "source": "A", "target": "B", "transition_prob": "abc",
            "mean_time": 5, "std_dev": 1.0, "distribution_type": "normal",
            "min_cutoff": 0.0, "max_cutoff": 10.0,
        }])
        status, _, errors = parse_edges_json(payload, ["A", "B"])
        self.assertEqual(status, "error")
        self.assertIn("Invalid data type", errors[0])


class TestBuildDemographicsDict(unittest.TestCase):
    def test_standard_rows(self):
        rows = [{"key": "Sex", "value": "Male"}, {"key": "Age", "value": "30"}]
        self.assertEqual(build_demographics_dict(rows), {"Sex": "Male", "Age": "30"})

    def test_custom_row_uses_custom_key_value(self):
        rows = [{"key": "Custom", "custom_key": "Region", "custom_value": "West"}]
        self.assertEqual(build_demographics_dict(rows), {"Region": "West"})

    def test_incomplete_rows_are_skipped(self):
        rows = [
            {"key": "", "value": "x"},                                 # empty key
            {"key": "Sex", "value": ""},                               # empty value
            {"key": "Custom", "custom_key": "", "custom_value": "v"},  # incomplete custom
            {"key": "Custom"},                                         # missing custom keys (uses .get)
        ]
        self.assertEqual(build_demographics_dict(rows), {})


class TestFilterMachines(unittest.TestCase):
    def test_all_passes_through_sorted_by_updated_desc(self):
        rows = [machine_row(1, updated="2024-01-01"),
                machine_row(2, updated="2024-03-01"),
                machine_row(3, updated="2024-02-01")]
        out = filter_machines(rows, "All Diseases", "All Categories", None, None, [])
        self.assertEqual([m[0] for m in out], [2, 3, 1])

    def test_disease_filter(self):
        rows = [machine_row(1, disease="COVID-19"), machine_row(2, disease="Measles")]
        out = filter_machines(rows, "COVID-19", "All Categories", None, None, [])
        self.assertEqual([m[0] for m in out], [1])

    def test_category_filter_matches_model_path_prefix(self):
        model_categories = [{"name": "Variant", "id": "variant"}]
        rows = [machine_row(1, model_path="variant.Delta.general"),
                machine_row(2, model_path="default.general")]
        out = filter_machines(rows, "COVID-19", "Variant", None, None, model_categories)
        self.assertEqual([m[0] for m in out], [1])

    def test_variant_filter(self):
        rows = [machine_row(1, model_path="variant.Delta.general"),
                machine_row(2, model_path="variant.Omicron.general")]
        out = filter_machines(rows, "COVID-19", "All Categories", "Delta", None, [])
        self.assertEqual([m[0] for m in out], [1])

    def test_vaccination_filter_is_measles_only(self):
        rows = [machine_row(1, disease="Measles", model_path="vaccination.Fully Vaccinated.general"),
                machine_row(2, disease="Measles", model_path="vaccination.Unvaccinated.general")]
        out = filter_machines(rows, "Measles", "All Categories", None, "Fully Vaccinated", [])
        self.assertEqual([m[0] for m in out], [1])

    def test_does_not_mutate_input_list(self):
        rows = [machine_row(1, updated="2024-01-01"), machine_row(2, updated="2024-03-01")]
        before = list(rows)
        filter_machines(rows, "All Diseases", "All Categories", None, None, [])
        self.assertEqual(rows, before)


class TestBuildMachineNameAndPath(unittest.TestCase):
    def test_covid_variant(self):
        name, path = build_machine_name_and_path("COVID-19", "variant", "Delta", None, {})
        self.assertEqual(path, "variant.Delta.general")
        self.assertIn("variant=Delta", name)

    def test_covid_default(self):
        name, path = build_machine_name_and_path("COVID-19", "default", None, None, {})
        self.assertEqual(path, "default.general")
        self.assertEqual(name, "COVID-19 | Default")

    def test_measles_vaccination(self):
        name, path = build_machine_name_and_path("Measles", "vaccination", None, "Fully Vaccinated", {})
        self.assertEqual(path, "vaccination.Fully Vaccinated.general")
        self.assertIn("vaccination=Fully Vaccinated", name)

    def test_other_disease_defaults(self):
        name, path = build_machine_name_and_path("Influenza", "default", None, None, {})
        self.assertEqual(path, "default.general")
        self.assertEqual(name, "Influenza | Default")

    def test_demographics_appended_to_name(self):
        name, path = build_machine_name_and_path("COVID-19", "variant", "Delta", None, {"Sex": "Male"})
        self.assertIn("variant=Delta", name)
        self.assertIn("Sex=Male", name)


if __name__ == "__main__":
    unittest.main()
