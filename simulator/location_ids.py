"""Location-id normalization shared across the runner and its extracted modules."""
from __future__ import annotations


def normalize_location_id(value) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()
