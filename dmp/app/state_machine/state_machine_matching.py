"""Shared state-machine matching.

Both reachable disease-timeline paths resolve a state machine the same way:

  - the live in-process engine path (``core.dmp_local.DMPLocal.find_matching_state_machine``,
    called from ``simulator/dmp_inprocess.py``), and
  - the HTTP API fallback (``dmp/api/dmp_api_v2.py``).

These were byte-for-byte copies of the model-path search, demographic-compatibility
loop, age-range test, and specificity sort. A divergence between the two would
silently produce a *different disease timeline* depending on which path served, so
the logic lives here once and both callers delegate to it.

The ``disease_configurations`` helpers (which import Streamlit) are imported lazily
inside ``_build_search_paths`` to keep import timing identical to the original
``dmp_local`` behavior — importing this module stays Streamlit-free.
"""
from typing import Dict, List, Optional


def age_in_range(age_value: str, age_range: str) -> bool:
    """Check if a single age value falls within an age range (e.g. "5-14", "65+", "*")."""
    try:
        # Convert age value to integer
        age = int(age_value)

        # Parse age range (e.g., "5-14", "65+", "0-18")
        if age_range == "*":
            return True

        if "+" in age_range:
            # Handle ranges like "65+"
            min_age = int(age_range.replace("+", ""))
            return age >= min_age

        if "-" in age_range:
            # Handle ranges like "5-14", "0-18"
            min_age, max_age = map(int, age_range.split("-"))
            return min_age <= age <= max_age

        # Single age value (e.g., "25")
        range_age = int(age_range)
        return age == range_age

    except (ValueError, TypeError):
        # If parsing fails, fall back to exact string matching
        return age_value == age_range


def _build_search_paths(disease_name: str, model_path: Optional[str]) -> List[str]:
    """Model paths to try, in priority order: exact path, its parents, then the default."""
    # Lazily imported (pulls Streamlit via disease_configurations) so importing this
    # module stays headless — mirrors the original dmp_local deferred import.
    from .disease_configurations import get_parent_model_path, get_default_model_path

    search_paths: List[str] = []

    if model_path:
        # Start with the exact model path
        search_paths.append(model_path)

        # Add parent paths for fallback (e.g., variant.Delta if variant.Delta.general not found)
        current_path = model_path
        while True:
            parent_path = get_parent_model_path(disease_name, current_path)
            if parent_path:
                search_paths.append(parent_path)
                current_path = parent_path
            else:
                break

    # Add default model path as final fallback
    default_path = get_default_model_path(disease_name)
    if default_path and default_path not in search_paths:
        search_paths.append(default_path)

    return search_paths


# Demographic schema reconciliation. The state-machine DB mixes two authoring
# conventions: newer machines key on "Vaccination Status" (values
# "Vaccinated"/"Unvaccinated"); legacy age/sex machines key on "Vaccination" and
# Sex "Male"/"Female", while the engine request emits Sex "M"/"F". Left as-is, a
# legacy machine's constraint silently degrades to a wildcard (different key) or
# never matches (different value) — so age/sex stratification never engages AND a
# vaccinated agent can leak into an unvaccinated machine. Canonicalize BOTH sides
# before comparison so every constraint is actually enforced regardless of which
# convention authored it.
_KEY_ALIASES = {"Vaccination": "Vaccination Status"}
_SEX_VALUE_CANON = {"M": "Male", "F": "Female", "MALE": "Male", "FEMALE": "Female"}


def _canonicalize_demographics(demographics: Dict[str, str]) -> Dict[str, str]:
    """Normalize legacy/alternate demographic keys and Sex values to one schema."""
    canon: Dict[str, str] = {}
    for key, value in demographics.items():
        ckey = _KEY_ALIASES.get(key, key)
        cval = value
        if ckey == "Sex" and isinstance(value, str):
            cval = _SEX_VALUE_CANON.get(value.strip().upper(), value)
        canon[ckey] = cval
    return canon


def _demographics_compatible(request_demographics: Dict[str, str],
                             machine_demographics: Dict[str, str]) -> bool:
    """A machine is compatible if every demographic it defines matches the request.

    Demographics the machine does not define are treated as wildcards. ``Age`` keys
    use range matching; all others use exact string equality. Both sides are
    canonicalized first (see ``_canonicalize_demographics``) so legacy "Vaccination"
    / "Male"/"Female" machines are matched against the request's "Vaccination
    Status" / "M"/"F" without silently dropping the constraint.
    """
    request = _canonicalize_demographics(request_demographics)
    machine = _canonicalize_demographics(machine_demographics)
    for key, value in request.items():
        if key in machine:
            # Machine has this demographic defined - must match
            if key == "Age":
                if not age_in_range(str(value), machine[key]):
                    return False
            else:
                if machine[key] != str(value):
                    return False
        # If machine doesn't have this demographic defined, it's OK (wildcard)
    return True


def find_matching_state_machine(db, disease_name: str, demographics: Dict[str, str],
                                model_path: Optional[str] = None) -> Optional[Dict]:
    """Find the most-specific state machine matching ``disease_name`` + ``demographics``.

    Searches ``model_path`` then its parents then the disease default; within a path,
    collects demographically-compatible machines and returns the one with the most
    explicitly-defined (non-``"*"``) demographics. Returns ``None`` if nothing matches.

    ``db`` is a ``StateMachineDB`` (or any object exposing ``list_state_machines()`` and
    ``load_state_machine(id)``). Errors are NOT swallowed here — callers decide whether
    to surface (HTTP 500) or fall back to ``None``.
    """
    saved_machines = db.list_state_machines()
    search_paths = _build_search_paths(disease_name, model_path)
    print(f"Search paths (in order): {search_paths}")

    # Search for matching state machines using simple rules
    for search_path in search_paths:
        compatible_machines = []

        # First, collect all compatible machines for this search path
        for machine in saved_machines:
            machine_data = db.load_state_machine(machine[0])
            if not machine_data:
                continue

            # Check disease name
            if machine_data["disease_name"] != disease_name:
                continue

            # Check if this machine matches the current search path
            machine_model_path = machine_data.get("model_path", "default")
            if machine_model_path != search_path:
                continue

            if _demographics_compatible(demographics, machine_data["demographics"]):
                compatible_machines.append(machine_data)

        # If we found compatible machines, pick the most specific one
        if compatible_machines:
            # Sort by specificity: machines with more defined demographics are more specific
            compatible_machines.sort(
                key=lambda m: len([k for k in m["demographics"].keys() if m["demographics"][k] != "*"]),
                reverse=True
            )

            matching_machine = compatible_machines[0]
            print(f"Found matching machine: {matching_machine['name']} with path: {search_path}")
            print(f"Demographics: {matching_machine['demographics']}")
            return matching_machine

    # No matching machine found
    print(f"No matching state machine found for {disease_name} with demographics {demographics}")
    return None
