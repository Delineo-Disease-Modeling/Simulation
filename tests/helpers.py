"""
Test helpers for running simulations and analyzing results.
Importable from any test file.
"""
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

# Add project roots to path so we can import the simulation engine
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from simulator.config import INFECTION_MODEL, SIMULATION
from simulator.pap import InfectionState, InfectionTimeline, VaccinationState
from simulator.runner import SimulationRunner


DEFAULT_INTERVENTION = {
    "time": 0,
    "mask": 0.0,
    "vaccine": 0.0,
    "capacity": 1.0,
    "lockdown": 0.0,
    "selfiso": 0.0,
    "randseed": False,
}


def resolve_fixture_path(*relative_paths: str) -> Path:
    """Resolve a fixture path from the repo-owned Simulation test fixtures."""
    attempted = []
    for relative_path in relative_paths:
        candidate = (ROOT / relative_path).resolve()
        attempted.append(str(candidate))
        if candidate.exists():
            return candidate

    attempted_text = "\n".join(f"- {path}" for path in attempted)
    raise FileNotFoundError(f"Missing test fixture. Tried:\n{attempted_text}")


def load_json_fixture(path: str | os.PathLike[str]) -> Any:
    with Path(path).open() as handle:
        return json.load(handle)


def _build_local_loader(papdata: dict, patterns: dict):
    def loader(_url: str, timeout: int = 360):  # noqa: ARG001
        return papdata, patterns

    return loader


def _sort_person_id(value: str) -> tuple[int, int | str]:
    text = str(value)
    if text.isdigit():
        return (0, int(text))
    return (1, text)


def _normalize_interventions(interventions: dict | None) -> tuple[list[dict], bool]:
    merged = dict(DEFAULT_INTERVENTION)
    if interventions:
        merged.update(interventions)
    return [merged], bool(merged["randseed"])


def _reset_seeded_state(context) -> None:
    context.people_with_timelines.clear()
    context.infection_manager.infected.clear()
    for infected in context.variant_infected.values():
        infected.clear()

    context.event_queue._queue.clear()
    context.event_queue._queued.clear()
    context.event_queue._registry.clear()

    for person in context.simulator.people.values():
        person.states = {}
        person.timeline = {}
        person.invisible = False


def _choose_initial_infected_ids(
    people_ids: list[str],
    initial_infected_count: int | None,
    initial_infected_ids: list[str] | None,
    randseed: bool,
) -> list[str]:
    people_set = {str(pid) for pid in people_ids}

    if initial_infected_ids is not None:
        if not isinstance(initial_infected_ids, list):
            raise ValueError("initial_infected_ids must be a JSON list")
        return [str(pid) for pid in initial_infected_ids if str(pid) in people_set]

    if initial_infected_count is None:
        initial_infected_count = len(SIMULATION["variants"])

    try:
        count = int(initial_infected_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("initial_infected_count must be an integer") from exc

    if count < 0:
        raise ValueError("initial_infected_count must be >= 0")
    if count == 0:
        return []

    default_pool = [pid for pid in SIMULATION["default_infected_ids"] if pid in people_set]
    extras = [pid for pid in people_ids if pid not in set(default_pool)]

    if randseed:
        pool = list(default_pool)
        random.shuffle(pool)
        random.shuffle(extras)
        pool.extend(extras)
    else:
        pool = list(default_pool)
        pool.extend(sorted(extras, key=_sort_person_id))

    return pool[:count]


def _seed_initial_people(
    context,
    initial_infected_count: int | None,
    initial_infected_ids: list[str] | None,
    randseed: bool,
) -> None:
    infected_ids = _choose_initial_infected_ids(
        list(context.simulator.people.keys()),
        initial_infected_count,
        initial_infected_ids,
        randseed,
    )
    if not infected_ids:
        return

    initial_duration = INFECTION_MODEL["initial_timeline"]["duration"]
    recovery_duration = INFECTION_MODEL["fallback_timeline"]["recovery_duration"]
    infected_state = InfectionState.INFECTED | InfectionState.INFECTIOUS

    for index, pid in enumerate(infected_ids):
        person = context.simulator.get_person(pid)
        if person is None:
            continue

        variant = context.variants[index % len(context.variants)]
        person.states[variant] = infected_state
        person.timeline[variant] = {
            InfectionState.INFECTED: InfectionTimeline(0, initial_duration),
            InfectionState.INFECTIOUS: InfectionTimeline(0, initial_duration),
            InfectionState.RECOVERED: InfectionTimeline(
                initial_duration,
                initial_duration + recovery_duration,
            ),
        }
        context.people_with_timelines.add(person.id)
        context.infection_manager.infected.add(person.id)
        context.variant_infected[variant][person.id] = int(infected_state.value)
        context.event_queue.register_infectious(person.id, variant, 0, initial_duration)


def _restore_people_state(
    context,
    restore_state_file: str | os.PathLike[str],
    restore_time_offset: int | None = None,
) -> int:
    state = load_json_fixture(restore_state_file)
    saved_people = state.get("people", {})
    metadata = state.get("metadata", {})
    time_offset = restore_time_offset

    if time_offset is None:
        time_offset = metadata.get("length_minutes")
    if time_offset is None:
        time_offset = metadata.get("end_time", 0)

    try:
        time_offset = int(time_offset)
    except (TypeError, ValueError):
        time_offset = 0

    restored_count = 0
    for pid, saved_person in saved_people.items():
        person = context.simulator.get_person(pid)
        if person is None:
            continue

        person.states = {
            variant: InfectionState(int(value))
            for variant, value in saved_person.get("states", {}).items()
        }
        person.timeline = {}

        for disease, state_timelines in saved_person.get("timeline", {}).items():
            adjusted_timelines = {}
            for state_value, times in state_timelines.items():
                start = int(times["start"]) - time_offset
                end = int(times["end"]) - time_offset
                if end < 0:
                    continue

                state = InfectionState(int(state_value))
                adjusted_timelines[state] = InfectionTimeline(start, end)

            if adjusted_timelines:
                person.timeline[disease] = adjusted_timelines
                context.people_with_timelines.add(person.id)

                infectious = adjusted_timelines.get(InfectionState.INFECTIOUS)
                if infectious is not None:
                    context.event_queue.register_infectious(
                        person.id,
                        disease,
                        infectious.start,
                        infectious.end,
                    )

        person.invisible = bool(saved_person.get("invisible", person.invisible))
        person.masked = bool(saved_person.get("masked", person.masked))

        if "vaccination_state" in saved_person:
            try:
                person.vaccination_state = VaccinationState(int(saved_person["vaccination_state"]))
            except (TypeError, ValueError):
                person.vaccination_state = VaccinationState.NONE

        for variant, state in person.states.items():
            if state != InfectionState.SUSCEPTIBLE:
                context.infection_manager.infected.add(person.id)
                context.variant_infected[variant][person.id] = int(state.value)

        restored_count += 1

    return restored_count


def _serialize_people_state(simulator) -> dict[str, dict]:
    serialized = {}
    for pid, person in simulator.people.items():
        serialized[str(pid)] = {
            "id": str(person.id),
            "sex": person.sex,
            "age": person.age,
            "home": str(person.household.id) if person.household else None,
            "location": str(person.location.id) if person.location else None,
            "invisible": person.invisible,
            "masked": person.masked,
            "vaccination_state": int(person.vaccination_state.value),
            "states": {
                variant: int(state.value)
                for variant, state in person.states.items()
            },
            "timeline": {
                disease: {
                    str(int(state.value)): {
                        "start": timeline.start,
                        "end": timeline.end,
                    }
                    for state, timeline in state_timelines.items()
                }
                for disease, state_timelines in person.timeline.items()
            },
        }
    return serialized


def _normalize_timestep_keys(series: dict) -> dict:
    normalized = {}
    for timestep, payload in series.items():
        try:
            key = int(timestep)
        except (TypeError, ValueError):
            key = timestep
        if key == 0:
            continue
        normalized[key] = payload
    return normalized


def _disable_dmp_calls(context) -> None:
    context.infection_manager.create_timeline = (
        lambda person, disease, curtime: context.infection_manager._fallback_timeline(
            disease,
            curtime,
        )
    )


def run_sim(papdata, patterns, max_length=240, interventions=None,
            initial_infected_count=1, initial_infected_ids=None, **kwargs):
    """
    Run a simulation directly (no HTTP, no DB, no DMP API).
    Returns the result dict with keys: result, movement, papdata, people_state.
    """
    restore_state_file = kwargs.pop("restore_state_file", None)
    restore_time_offset = kwargs.pop("restore_time_offset", None)
    czone_id = int(kwargs.pop("czone_id", 0))
    enable_logging = bool(kwargs.pop("enable_logging", False))
    if kwargs:
        unexpected = ", ".join(sorted(kwargs))
        raise TypeError(f"Unsupported run_sim kwargs: {unexpected}")

    normalized_interventions, randseed = _normalize_interventions(interventions)
    simdata = {
        "czone_id": czone_id,
        "length": int(max_length),
        "randseed": randseed,
        "interventions": normalized_interventions,
    }

    runner = SimulationRunner(
        simdata=simdata,
        enable_logging=enable_logging,
        output_dir=None,
        data_loader=_build_local_loader(papdata, patterns),
    )
    runner._seed_random()
    loaded = runner.load_data()
    context = runner.build_context(loaded)
    _disable_dmp_calls(context)
    _reset_seeded_state(context)

    if restore_state_file:
        _restore_people_state(
            context,
            restore_state_file=restore_state_file,
            restore_time_offset=restore_time_offset,
        )
    else:
        _seed_initial_people(
            context,
            initial_infected_count=initial_infected_count,
            initial_infected_ids=initial_infected_ids,
            randseed=randseed,
        )

    runner.run_queue(context)
    result = runner.finalize(context)
    result["movement"] = _normalize_timestep_keys(result["movement"])
    result["result"] = _normalize_timestep_keys(result["result"])
    result["papdata"] = papdata
    result["people_state"] = _serialize_people_state(context.simulator)
    return result


def count_infected_at_timestep(result, timestep, variant=None):
    """Count people with any non-zero (non-susceptible) state at a timestep."""
    ts_data = result["result"].get(timestep)
    if ts_data is None:
        ts_data = result["result"].get(str(timestep))
    if ts_data is None:
        return 0
    count = 0
    for v, people in ts_data.items():
        if variant and v != variant:
            continue
        for pid, state_val in people.items():
            if state_val != 0:
                count += 1
    return count


def get_total_ever_infected(result, variant=None):
    """Count unique people who were ever in a non-susceptible state."""
    infected_pids = set()
    for ts, ts_data in result["result"].items():
        for v, people in ts_data.items():
            if variant and v != variant:
                continue
            for pid, state_val in people.items():
                if state_val & 1:
                    infected_pids.add(pid)
    return len(infected_pids)


def get_peak_infected(result, variant=None):
    """Get the maximum number of simultaneously infected people and when it occurs."""
    peak = 0
    peak_time = 0
    for ts in sorted(result["result"].keys(), key=lambda value: int(value)):
        count = count_infected_at_timestep(result, ts, variant)
        if count > peak:
            peak = count
            peak_time = ts
    return peak, peak_time


def get_infection_curve(result, variant=None):
    """Return a list of (timestep, infected_count) tuples."""
    curve = []
    for ts in sorted(result["result"].keys(), key=lambda value: int(value)):
        count = count_infected_at_timestep(result, ts, variant)
        curve.append((ts, count))
    return curve


def get_final_state_counts(result):
    """At the last timestep, count people in each infection state category."""
    if not result["result"]:
        return {}
    
    last_ts = max(result["result"].keys(), key=lambda value: int(value))
    ts_data = result["result"][last_ts]
    
    counts = {
        "susceptible": 0, "infected": 0, "infectious": 0,
        "symptomatic": 0, "hospitalized": 0, "recovered": 0, "removed": 0,
    }
    
    seen_pids = set()
    for variant, people in ts_data.items():
        for pid, state_val in people.items():
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            if state_val == 0:
                counts["susceptible"] += 1
            if state_val & 1:
                counts["infected"] += 1
            if state_val & 2:
                counts["infectious"] += 1
            if state_val & 4:
                counts["symptomatic"] += 1
            if state_val & 8:
                counts["hospitalized"] += 1
            if state_val & 16:
                counts["recovered"] += 1
            if state_val & 32:
                counts["removed"] += 1

    return counts


def get_population_size(result):
    """Get total population from the result's papdata."""
    return len(result["papdata"]["people"])
