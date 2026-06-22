"""simdata normalization + movement-intervention triviality check.

normalize_simdata coerces a raw simdata dict into the canonical shape the runner
consumes; _trivial_movement_interventions detects intervention sets that do not
alter movement (so the SoA engine fast-path stays eligible). Extracted from
runner.py (pure code-motion).
"""
from __future__ import annotations

from .config import DMP_API, INFECTION_MODEL, SIMULATION
from .infectionmgr import VALID_DMP_MODES
from .location_ids import normalize_location_id


def _trivial_movement_interventions(interventions: dict) -> bool:
    """True when no intervention redirects movement (so a pure person_loc
    scatter equals move_people). Masking/vaccination don't move people."""
    return (
        float(interventions.get("capacity", 1.0)) >= 1.0
        and float(interventions.get("lockdown", 0.0)) <= 0.0
        and float(interventions.get("selfiso", 0.0)) <= 0.0
    )


def normalize_simdata(simdata: dict) -> dict:
    normalized = dict(simdata)

    normalized["randseed"] = bool(
        normalized.get("randseed", SIMULATION["default_interventions"]["randseed"])
    )
    normalized["initial_infected_count"] = max(
        0,
        int(
            normalized.get(
                "initial_infected_count",
                SIMULATION["default_initial_infected_count"],
            )
        ),
    )
    normalized["disease_name"] = str(
        normalized.get("disease_name") or SIMULATION["disease_name"]
    )

    raw_variants = normalized.get("variants") or SIMULATION["variants"]
    if isinstance(raw_variants, str):
        raw_variants = [raw_variants]
    variants = [
        str(variant).strip()
        for variant in raw_variants
        if str(variant).strip()
    ]
    normalized["variants"] = variants or list(SIMULATION["variants"])

    raw_mode = str(normalized.get("dmp_mode") or DMP_API["mode"]).lower()
    normalized["dmp_mode"] = raw_mode if raw_mode in VALID_DMP_MODES else "auto"

    normalized["aggregate_transmission"] = bool(
        normalized.get(
            "aggregate_transmission", INFECTION_MODEL.get("aggregate_transmission", False)
        )
    )

    normalized["area_aware_ventilation"] = bool(
        normalized.get(
            "area_aware_ventilation",
            INFECTION_MODEL.get("area_aware_ventilation", False),
        )
    )

    normalized["external_foi"] = bool(
        normalized.get("external_foi", INFECTION_MODEL.get("external_foi", False))
    )
    normalized["external_prevalence"] = float(
        normalized.get(
            "external_prevalence", INFECTION_MODEL.get("external_prevalence", 0.0)
        )
    )
    normalized["external_emit_factor"] = float(
        normalized.get(
            "external_emit_factor", INFECTION_MODEL.get("external_emit_factor", 1.0)
        )
    )

    raw_model_paths = normalized.get("model_path_by_variant") or {}
    model_path_by_variant = {}
    if isinstance(raw_model_paths, dict):
        for variant, model_path in raw_model_paths.items():
            if model_path is None:
                model_path_by_variant[str(variant)] = None
                continue
            model_path_str = str(model_path).strip()
            if model_path_str:
                model_path_by_variant[str(variant)] = model_path_str
    normalized["model_path_by_variant"] = model_path_by_variant

    raw_csv = normalized.get("matrix_csv_by_variant") or {}
    matrix_csv_by_variant: dict[str, str] = {}
    if isinstance(raw_csv, dict):
        for variant, csv_content in raw_csv.items():
            if isinstance(csv_content, str) and csv_content.strip():
                matrix_csv_by_variant[str(variant)] = csv_content
    normalized["matrix_csv_by_variant"] = matrix_csv_by_variant

    raw_disabled_poi_ids = normalized.get("disabled_poi_ids") or []
    if isinstance(raw_disabled_poi_ids, (str, int, float)):
        raw_disabled_poi_ids = [raw_disabled_poi_ids]
    if not isinstance(raw_disabled_poi_ids, (list, tuple, set)):
        raw_disabled_poi_ids = []
    normalized["disabled_poi_ids"] = sorted(
        {
            normalized_id
            for normalized_id in (
                normalize_location_id(value) for value in raw_disabled_poi_ids
            )
            if normalized_id
        }
    )

    return normalized
