import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import requests

from simulator.event_queue import EventQueue
from simulator.infectionmgr import InfectionManager
from simulator.pap import Facility, Household, InfectionState, InfectionTimeline, Person, VaccinationState
from simulator.runner import (
    LoadedSimulationData,
    SimulationRunner,
    apply_person_interventions,
    move_people,
    normalize_simdata,
    reroute_disabled_poi_visits,
)
from simulator.patterns_codec import BinaryPatterns
from simulator.snapshots import SimulationSnapshotWriter, build_movement_snapshot
from simulator.world import DiseaseSimulator, build_locations, seed_population
from simulator.infection_models.v6_wells_riley import CAT, get_vaccination_protection


def make_simulator():
    return DiseaseSimulator(
        timestep=60,
        intervention_weights=[
            {
                "time": 0,
                "mask": 0.0,
                "vaccine": 0.0,
                "capacity": 1.0,
                "lockdown": 0.0,
                "selfiso": 0.0,
            }
        ],
        enable_logging=False,
    )


class TestSimulatorRefactor(unittest.TestCase):
    def test_event_queue_registers_matching_visits_without_duplicates(self):
        event_queue = EventQueue(iter(()))
        event_queue.register_infectious("p1", "Delta", 60, 120)
        event_queue.ingest_patterns(
            {
                "60": {"homes": {}, "places": {"work": ["p1", "p2"]}},
                "120": {"homes": {}, "places": {"work": ["p1"]}},
            }
        )
        event_queue.register_infectious("p1", "Omicron", 60, 120)

        self.assertEqual(len(event_queue), 2)
        self.assertEqual(event_queue.pop(), (60, "work", False))
        self.assertEqual(event_queue.pop(), (120, "work", False))

    def test_move_people_redirects_home_when_facility_is_at_capacity(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        facility = Facility("work", "cbg-work", "Work", capacity=1)
        simulator.add_household(home)
        simulator.add_facility(facility)

        worker = Person("worker", 0, 30, home)
        occupant = Person("occupant", 0, 41, home)
        simulator.add_person(worker)
        simulator.add_person(occupant)
        home.add_member(worker)
        home.add_member(occupant)

        home.remove_member(occupant.id)
        facility.add_member(occupant)
        occupant.location = facility

        move_people(
            simulator,
            [("work", [worker.id])],
            False,
            "60",
            {
                "time": 0,
                "mask": 0.0,
                "vaccine": 0.0,
                "capacity": 1.0,
                "lockdown": 0.0,
                "selfiso": 0.0,
            },
        )

        self.assertIs(worker.location, home)
        self.assertIn(worker.id, home.population)
        self.assertNotIn(worker.id, facility.population)

    def test_schedule_infection_registers_future_infectious_visits(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        simulator.add_household(home)

        target = Person("p1", 0, 30, home)
        simulator.add_person(target)
        home.add_member(target)

        event_queue = EventQueue(iter(()))
        event_queue.ingest_patterns(
            {
                "60": {"homes": {}, "places": {"work": ["p1"]}},
                "120": {"homes": {}, "places": {"work": ["p1"]}},
            }
        )

        manager = InfectionManager(infected_ids=[])
        timeline = {
            "Delta": {
                InfectionState.INFECTED: InfectionTimeline(0, 120),
                InfectionState.INFECTIOUS: InfectionTimeline(60, 120),
            }
        }

        with mock.patch.object(manager, "create_timeline", return_value=timeline):
            people_with_timelines = set()
            returned_timeline = manager.schedule_infection(
                simulator,
                event_queue,
                target,
                "Delta",
                0,
                people_with_timelines,
            )

        self.assertIs(returned_timeline, timeline)
        self.assertIs(simulator.people[target.id].timeline, timeline)
        self.assertEqual(people_with_timelines, {target})
        self.assertEqual(len(event_queue), 2)
        self.assertEqual(event_queue.pop(), (60, "work", False))
        self.assertEqual(event_queue.pop(), (120, "work", False))

    def test_snapshot_writer_writes_expected_gzip_output(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        facility = Facility("work", "cbg-work", "Work", capacity=10)
        simulator.add_household(home)
        simulator.add_facility(facility)

        resident = Person("resident", 0, 29, home)
        visitor = Person("visitor", 1, 35, home)
        simulator.add_person(resident)
        simulator.add_person(visitor)
        home.add_member(resident)
        facility.add_member(visitor)
        visitor.location = facility

        movement = build_movement_snapshot(simulator)
        result = {"Delta": {"resident": 3}, "Omicron": {}}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            writer = SimulationSnapshotWriter(str(output_dir))
            writer.write("60", movement, result)
            writer.close()

            with gzip.open(output_dir / "patterns.json.gz", "rt", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"60": movement})

            with gzip.open(output_dir / "simdata.json.gz", "rt", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), {"60": result})

            self.assertEqual(
                writer.result(),
                {
                    "simdata": str(output_dir / "simdata.json.gz"),
                    "patterns": str(output_dir / "patterns.json.gz"),
                },
            )

    def test_seed_population_honors_initial_infected_count_and_variants(self):
        simulator = make_simulator()
        people_data = {
            str(i): {"sex": i % 2, "age": 30 + i, "home": "home"}
            for i in range(6)
        }
        build_locations(simulator, {"home": {"cbg": "cbg-home"}}, {})
        event_queue = EventQueue(iter(()))
        event_queue.ingest_patterns(
            {
                "60": {"homes": {"home": list(people_data.keys())}, "places": {}},
                "120": {"homes": {"home": list(people_data.keys())}, "places": {}},
            }
        )
        manager = InfectionManager(infected_ids=[], dmp_mode="off")

        result = seed_population(
            simulator,
            people_data,
            ["Delta", "Omicron"],
            event_queue,
            manager,
            5,
        )

        self.assertEqual(len(result.initial_infected_ids), 5)
        self.assertEqual(len(result.people_with_timelines), 5)
        seeded_variants = [
            next(iter(simulator.people[pid].timeline.keys()))
            for pid in result.initial_infected_ids
        ]
        self.assertEqual(seeded_variants, ["Delta", "Omicron", "Delta", "Omicron", "Delta"])

    def test_dmp_off_uses_fallback_without_calling_api(self):
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)
        manager = InfectionManager(infected_ids=[], dmp_mode="off")

        with mock.patch("simulator.infectionmgr._dmp_session.post") as post:
            timeline = manager.create_timeline(person, "Delta", 0)

        post.assert_not_called()
        self.assertIn("Delta", timeline)
        self.assertEqual(manager.timeline_source_counts["fallback"], 1)

    def test_dmp_required_raises_when_api_unavailable(self):
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)
        manager = InfectionManager(infected_ids=[], dmp_mode="required")
        # Exercise the HTTP fallback path: disable the in-process provider so
        # this verifies the API-unavailable behavior, not the local DB.
        manager._inprocess = None

        with mock.patch(
            "simulator.infectionmgr._dmp_session.post",
            side_effect=requests.exceptions.ConnectionError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                manager.create_timeline(person, "Delta", 0)

    def test_dmp_request_uses_runtime_disease_and_model_path(self):
        home = Household("cbg-home", "home")
        person = Person("p1", 1, 30, home)
        manager = InfectionManager(
            infected_ids=[],
            disease_name="Influenza",
            dmp_mode="required",
            model_path_by_variant={"H1N1": "flu.h1n1.general"},
        )
        # This test asserts on the HTTP request payload, so force the HTTP path.
        manager._inprocess = None
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "timeline": [
                ("Infected", 0),
                ("Infectious", 24),
                ("Recovered", 96),
            ]
        }

        with mock.patch(
            "simulator.infectionmgr._dmp_session.post",
            return_value=response,
        ) as post:
            timeline = manager.create_timeline(person, "H1N1", 0)

        self.assertIn("H1N1", timeline)
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["disease_name"], "Influenza")
        self.assertEqual(payload["model_path"], "flu.h1n1.general")
        self.assertEqual(payload["demographics"]["Variant"], "H1N1")
        self.assertEqual(manager.timeline_source_counts["dmp"], 1)

    def test_inprocess_dmp_resolves_timeline_without_http(self):
        manager = InfectionManager(
            infected_ids=[], disease_name="COVID-19", dmp_mode="auto"
        )
        if manager._inprocess is None:
            self.skipTest("in-process DMP unavailable (state-machine DB not present)")

        home = Household("cbg-home", "home")
        person = Person("p1", 0, 35, home)

        with mock.patch("simulator.infectionmgr._dmp_session.post") as post:
            timeline = manager.create_timeline(person, "Delta", 0)

        # In-process path must not touch the HTTP API, and must produce a real
        # DMP timeline (not the fallback).
        post.assert_not_called()
        self.assertIn("Delta", timeline)
        # The infectious window may be keyed INFECTIOUS or INFECTIOUS|SYMPTOMATIC
        # (a symptomatic course now sets both bits), so assert the bit is present
        # in some window rather than the exact flag.
        self.assertTrue(
            any(InfectionState.INFECTIOUS in state for state in timeline["Delta"]),
            f"no infectious window in timeline {timeline['Delta']}",
        )
        self.assertEqual(manager.timeline_source_counts["dmp"], 1)
        self.assertEqual(manager.timeline_source_counts["fallback"], 0)

    def test_vaccination_state_feeds_active_transmission_model(self):
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)

        self.assertEqual(get_vaccination_protection(person, "infection"), 0.0)
        person.set_vaccinated(VaccinationState.IMMUNIZED)

        self.assertGreater(get_vaccination_protection(person, "infection"), 0.0)
        self.assertGreater(get_vaccination_protection(person, "transmission"), 0.0)

    def test_vaccination_changes_wells_riley_probability_path(self):
        home = Household("cbg-home", "home")
        susceptible = Person("susceptible", 0, 30, home)
        infector = Person("infector", 0, 30, home)

        with mock.patch(
            "simulator.infection_models.v6_wells_riley.random.random",
            return_value=0.03,
        ):
            self.assertTrue(CAT(susceptible, indoor=True, exposure_hours=1.0))

        susceptible.set_vaccinated(VaccinationState.IMMUNIZED)
        with mock.patch(
            "simulator.infection_models.v6_wells_riley.random.random",
            return_value=0.03,
        ):
            self.assertFalse(CAT(susceptible, indoor=True, exposure_hours=1.0))

        susceptible.set_vaccinated(VaccinationState.NONE)
        infector.set_vaccinated(VaccinationState.IMMUNIZED)
        with mock.patch(
            "simulator.infection_models.v6_wells_riley.random.random",
            return_value=0.04,
        ):
            self.assertFalse(
                CAT(
                    susceptible,
                    indoor=True,
                    exposure_hours=1.0,
                    infector=infector,
                )
            )

    def test_masking_intervention_unmasks_when_policy_is_lowered(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)
        person.iv_threshold = 0.3

        apply_person_interventions(
            simulator,
            person,
            {"mask": 0.5, "vaccine": 0.0},
            "0",
        )
        self.assertTrue(person.is_masked())

        apply_person_interventions(
            simulator,
            person,
            {"mask": 0.2, "vaccine": 0.0},
            "60",
        )
        self.assertFalse(person.is_masked())

    def test_vaccination_intervention_does_not_re_randomize_doses(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)
        person.iv_threshold = 0.1
        person.set_vaccinated(VaccinationState.PARTIAL)

        apply_person_interventions(
            simulator,
            person,
            {"mask": 0.0, "vaccine": 0.5},
            "60",
        )

        self.assertEqual(person.get_vaccinated(), VaccinationState.PARTIAL)

    def test_vaccination_intervention_assigns_doses_on_first_application(self):
        simulator = make_simulator()
        home = Household("cbg-home", "home")
        person = Person("p1", 0, 30, home)
        person.iv_threshold = 0.1

        with mock.patch("simulator.runner.random.randint", return_value=2):
            apply_person_interventions(
                simulator,
                person,
                {"mask": 0.0, "vaccine": 0.5},
                "0",
            )

        self.assertEqual(person.get_vaccinated(), VaccinationState.IMMUNIZED)

    def test_normalize_simdata_exposes_runtime_contract_defaults(self):
        normalized = normalize_simdata({
            "czone_id": 1,
            "length": 60,
            "interventions": [],
        })

        self.assertEqual(normalized["initial_infected_count"], 1)
        self.assertEqual(normalized["disease_name"], "COVID-19")
        self.assertEqual(normalized["variants"], ["Delta"])
        self.assertEqual(normalized["dmp_mode"], "auto")
        self.assertEqual(normalized["disabled_poi_ids"], [])

    def test_normalize_simdata_deduplicates_disabled_poi_ids(self):
        normalized = normalize_simdata({
            "czone_id": 1,
            "length": 60,
            "interventions": [],
            "disabled_poi_ids": ["poi-2", 1, "poi-2", "", None],
        })

        self.assertEqual(normalized["disabled_poi_ids"], ["1", "poi-2"])

    def test_reroute_disabled_poi_visits_moves_people_home(self):
        patterns = {
            "60": {
                "homes": {"h1": ["p0", "p1"], "h2": []},
                "places": {
                    "poi-a": ["p1", "p2", "missing"],
                    "poi-b": ["p3"],
                },
                "unchanged": True,
            },
        }
        people = {
            "p0": {"home": "h1"},
            "p1": {"home": "h1"},
            "p2": {"home": "h2"},
            "p3": {"home": "h3"},
        }

        rerouted = reroute_disabled_poi_visits(patterns, people, ["poi-a"])

        self.assertEqual(
            rerouted["60"],
            {
                "homes": {"h1": ["p0", "p1"], "h2": ["p2"]},
                "places": {"poi-b": ["p3"]},
                "unchanged": True,
            },
        )
        # input is not mutated in place
        self.assertIn("poi-a", patterns["60"]["places"])

    def test_reroute_disabled_poi_visits_handles_binary_patterns(self):
        # loc indices: 0,1 are homes (n_homes=2); 2,3 are places.
        # Layout per timestep row: [p0, p1, p2] columns.
        # row0: p0@h0, p1@place2(disabled), p2@place3 -> p1 should go to its home (h1=idx1)
        loc_matrix = np.array(
            [
                [0, 2, 3],
                [2, 2, 0],
            ],
            dtype=np.uint16,
        )
        binary = BinaryPatterns(
            loc_matrix=loc_matrix.copy(),
            ts_minutes=[60, 120],
            pids=["p0", "p1", "p2"],
            loc_ids=["h0", "h1", "place2", "place3"],
            n_homes=2,
        )
        people = {
            "p0": {"home": "h0"},
            "p1": {"home": "h1"},
            "p2": {"home": "place3-resident-home"},  # home absent from loc_ids -> leave in place
        }

        rerouted = reroute_disabled_poi_visits(binary, people, ["place2"])

        # p1 (col 1) rerouted from place2(2) to its home h1(1) wherever it was at place2.
        # p0 (col 0) at place2 in row1 -> rerouted to its home h0(0).
        # p2 (col 2) has no mappable home -> untouched even though it never visits place2 here.
        self.assertTrue(np.array_equal(
            rerouted.loc_matrix,
            np.array(
                [
                    [0, 1, 3],
                    [0, 1, 0],
                ],
                dtype=np.uint16,
            ),
        ))

    def test_reroute_binary_disambiguates_colliding_home_place_ids(self):
        # Real fixtures share an id space between homes and places (person home
        # "1" AND place "1" both exist). loc_ids: idx 0,1 = homes "1","2";
        # idx 2,3 = places "1","3". The disabled PLACE "1" (idx 2) must be
        # disabled without touching HOME "1" (idx 0).
        binary = BinaryPatterns(
            loc_matrix=np.array(
                [
                    [2, 3],  # pA @ place"1"(idx2, disabled), pB @ place"3"(idx3)
                    [0, 2],  # pA @ home"1"(idx0, NOT disabled), pB @ place"1"(idx2)
                ],
                dtype=np.uint16,
            ),
            ts_minutes=[60, 120],
            pids=["pA", "pB"],
            loc_ids=["1", "2", "1", "3"],
            n_homes=2,
        )
        people = {"pA": {"home": "1"}, "pB": {"home": "2"}}

        rerouted = reroute_disabled_poi_visits(binary, people, ["1"])

        # pA's place"1" visit -> home idx 0; pA's home"1" stay (idx0) untouched;
        # pB's place"1" visit -> home idx 1.
        self.assertTrue(np.array_equal(
            rerouted.loc_matrix,
            np.array(
                [
                    [0, 3],
                    [0, 1],
                ],
                dtype=np.uint16,
            ),
        ))

    def test_load_data_applies_reroute_so_engine_sees_disabling(self):
        # Guards the silent-bypass failure mode: the reroute must land on the
        # engine-facing patterns (the dense loc_matrix), not just the legacy dict.
        papdata = {
            "people": {"p0": {"home": "h0"}, "p1": {"home": "h1"}},
            "homes": {"h0": {}, "h1": {}},
            "places": {"shop": {}},
        }
        binary = BinaryPatterns(
            loc_matrix=np.array([[2, 2]], dtype=np.uint16),  # both at "shop" (idx 2)
            ts_minutes=[60],
            pids=["p0", "p1"],
            loc_ids=["h0", "h1", "shop"],
            n_homes=2,
        )

        def fake_loader(url, timeout=None):
            return papdata, binary

        runner = SimulationRunner(
            {"czone_id": 1, "length": 60, "interventions": [], "disabled_poi_ids": ["shop"]},
            enable_logging=False,
            data_loader=fake_loader,
        )
        loaded = runner.load_data()

        # both visitors to the disabled "shop" are sent to their homes (idx 0, 1)
        self.assertIsInstance(loaded.patterns_data, BinaryPatterns)
        self.assertTrue(np.array_equal(
            loaded.patterns_data.loc_matrix,
            np.array([[0, 1]], dtype=np.uint16),
        ))

    def test_runner_uses_runtime_variants_and_records_provenance(self):
        simdata = {
            "czone_id": 1,
            "length": 120,
            "randseed": False,
            "initial_infected_count": 4,
            "disease_name": "Influenza",
            "variants": ["H1N1", "H3N2", "Victoria"],
            "dmp_mode": "off",
            "model_path_by_variant": {"H1N1": "flu.h1n1.general"},
            "disabled_poi_ids": ["clinic"],
            "interventions": [
                {
                    "time": 0,
                    "mask": 0.0,
                    "vaccine": 0.0,
                    "capacity": 1.0,
                    "lockdown": 0.0,
                    "selfiso": 0.0,
                }
            ],
        }
        loaded = LoadedSimulationData(
            people_data={
                str(i): {"sex": i % 2, "age": 30 + i, "home": "home"}
                for i in range(6)
            },
            homes_data={"home": {"cbg": "cbg-home"}},
            places_data={},
            patterns_data={
                "60": {"homes": {"home": [str(i) for i in range(6)]}, "places": {}},
                "120": {"homes": {"home": [str(i) for i in range(6)]}, "places": {}},
            },
        )
        runner = SimulationRunner(simdata, enable_logging=False)
        runner._seed_random()

        context = runner.build_context(loaded)
        seeded_variants = [
            next(iter(context.simulator.people[pid].timeline.keys()))
            for pid in context.initial_infected_ids
        ]
        result = runner.finalize(context)

        self.assertEqual(context.variants, ["H1N1", "H3N2", "Victoria"])
        self.assertEqual(seeded_variants, ["H1N1", "H3N2", "Victoria", "H1N1"])
        self.assertEqual(result["metadata"]["disease_name"], "Influenza")
        self.assertEqual(result["metadata"]["variants"], ["H1N1", "H3N2", "Victoria"])
        self.assertEqual(result["metadata"]["dmp_mode"], "off")
        self.assertEqual(result["metadata"]["initial_infected_count"], 4)
        self.assertEqual(result["metadata"]["timeline_source_counts"]["fallback"], 4)
        self.assertEqual(result["metadata"]["random_seed_behavior"], "deterministic:0")
        self.assertEqual(result["metadata"]["disabled_poi_ids"], ["clinic"])


if __name__ == "__main__":
    unittest.main()
