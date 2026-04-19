import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from simulator.event_queue import EventQueue
from simulator.infectionmgr import InfectionManager
from simulator.pap import Facility, Household, InfectionState, InfectionTimeline, Person
from simulator.runner import move_people
from simulator.snapshots import SimulationSnapshotWriter, build_movement_snapshot
from simulator.world import DiseaseSimulator


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
        self.assertEqual(people_with_timelines, {target.id})
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


if __name__ == "__main__":
    unittest.main()
