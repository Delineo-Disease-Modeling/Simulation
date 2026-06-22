"""Tests for the shared state-machine matcher (state_machine.state_machine_matching).

This logic was previously duplicated byte-for-byte between the live in-process path
(dmp_local) and the HTTP API (dmp_api_v2); both now delegate here, so these tests
guard the single implementation. Headless: stubs the (Streamlit-importing)
disease_configurations path helpers via monkeypatch.
"""
import os
import sys

# Put dmp/app on the path so `state_machine` resolves (mirrors test_state_machine_refactor).
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dmp", "app"))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import matplotlib
matplotlib.use("Agg")  # headless

import pytest

from state_machine import disease_configurations as dc
from state_machine.state_machine_matching import age_in_range, find_matching_state_machine


class FakeDB:
    """Minimal StateMachineDB stand-in: list_state_machines() ids + load_state_machine(id)."""

    def __init__(self, machines):
        self._machines = machines  # list of machine_data dicts

    def list_state_machines(self):
        return [(i,) for i in range(len(self._machines))]

    def load_state_machine(self, machine_id):
        return self._machines[machine_id]


def _machine(name, disease="COVID", model_path="default", demographics=None):
    return {
        "name": name,
        "disease_name": disease,
        "model_path": model_path,
        "demographics": demographics or {},
        "states": [],
        "edges": [],
    }


# --------------------------- age_in_range ---------------------------

@pytest.mark.parametrize("age,rng,expected", [
    ("10", "*", True),       # wildcard
    ("70", "65+", True),     # open-ended, in range
    ("64", "65+", False),    # open-ended, below
    ("10", "5-14", True),    # closed range, inside
    ("4", "5-14", False),    # closed range, below
    ("14", "5-14", True),    # closed range, inclusive upper
    ("25", "25", True),      # single exact age
    ("25", "26", False),     # single exact age, mismatch
    ("abc", "5-14", False),  # unparseable value -> exact string compare
    ("5-14", "5-14", True),  # unparseable value -> exact string compare matches
])
def test_age_in_range(age, rng, expected):
    assert age_in_range(age, rng) is expected


# -------------------- find_matching_state_machine --------------------

@pytest.fixture(autouse=True)
def _stub_path_helpers(monkeypatch):
    # Default: no parent paths, default model path "default". Individual tests override.
    monkeypatch.setattr(dc, "get_parent_model_path", lambda disease, path: None)
    monkeypatch.setattr(dc, "get_default_model_path", lambda disease: "default")


def test_returns_none_when_disease_does_not_match():
    db = FakeDB([_machine("flu", disease="FLU")])
    assert find_matching_state_machine(db, "COVID", {}) is None


def test_picks_most_specific_compatible_machine():
    db = FakeDB([
        _machine("wildcard", demographics={}),
        _machine("age-kid", demographics={"Age": "0-18"}),
    ])
    # A 10-year-old is compatible with both; the more-specific (Age-defined) wins.
    assert find_matching_state_machine(db, "COVID", {"Age": "10"})["name"] == "age-kid"
    # A 40-year-old is incompatible with the Age machine, so the wildcard serves.
    assert find_matching_state_machine(db, "COVID", {"Age": "40"})["name"] == "wildcard"


def test_age_demographic_uses_range_matching():
    db = FakeDB([_machine("seniors", demographics={"Age": "65+"})])
    assert find_matching_state_machine(db, "COVID", {"Age": "70"})["name"] == "seniors"
    assert find_matching_state_machine(db, "COVID", {"Age": "30"}) is None


def test_non_age_demographic_uses_exact_match():
    db = FakeDB([_machine("vax", demographics={"Vaccinated": "yes"})])
    assert find_matching_state_machine(db, "COVID", {"Vaccinated": "yes"})["name"] == "vax"
    assert find_matching_state_machine(db, "COVID", {"Vaccinated": "no"}) is None


def test_model_path_falls_back_through_parents_then_default(monkeypatch):
    parents = {"variant.Delta.general": "variant.Delta", "variant.Delta": None}
    monkeypatch.setattr(dc, "get_parent_model_path", lambda disease, path: parents.get(path))
    monkeypatch.setattr(dc, "get_default_model_path", lambda disease: "default")
    db = FakeDB([_machine("delta", model_path="variant.Delta")])
    # The exact path (variant.Delta.general) has no machine; its parent does.
    assert find_matching_state_machine(db, "COVID", {}, "variant.Delta.general")["name"] == "delta"


def test_exact_model_path_preferred_over_default():
    db = FakeDB([
        _machine("default-machine", model_path="default"),
        _machine("exact-machine", model_path="variant.Omicron"),
    ])
    # variant.Omicron is searched before the "default" fallback, so it wins.
    assert find_matching_state_machine(db, "COVID", {}, "variant.Omicron")["name"] == "exact-machine"
