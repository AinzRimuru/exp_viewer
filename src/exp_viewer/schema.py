"""Type inference and data normalization for experiment records."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import orjson

from .types import Experiment, FieldType, FieldValue

# Field name substrings that hint at percentage type
_PERCENTAGE_HINTS = {"pct", "percent", "accuracy", "score", "ratio"}

# Name of the field type config file placed in the experiment root directory
FIELDS_CONFIG_FILENAME = "fields.json"


def load_fields_config(root: Path) -> dict[str, str]:
    """Load field type overrides from fields.json in the experiment root.

    Returns a dict mapping field_name -> type_string (e.g. {"accuracy": "percentage"}).
    Returns empty dict if the file does not exist.
    """
    config_path = root / FIELDS_CONFIG_FILENAME
    if not config_path.is_file():
        return {}
    try:
        data = orjson.loads(config_path.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return {}
    # Accept both flat {"field": "type"} and nested {"hyperparameters": {...}, "results": {...}}
    flat: dict[str, str] = {}
    for key, val in data.items():
        if isinstance(val, str):
            flat[key] = val
        elif isinstance(val, dict):
            for k2, v2 in val.items():
                if isinstance(v2, str):
                    flat[k2] = v2
    return flat


_TYPE_MAP = {
    "numeric": FieldType.NUMERIC,
    "percentage": FieldType.PERCENTAGE,
    "boolean": FieldType.BOOLEAN,
    "string": FieldType.STRING,
}


def _resolve_type(
    value: Any, field_name: str, overrides: dict[str, str]
) -> FieldType:
    """Determine FieldType considering explicit overrides, then inference."""
    if field_name in overrides:
        ft = _TYPE_MAP.get(overrides[field_name])
        if ft is not None:
            return ft
    return infer_type(value, field_name)


def infer_type(value: Any, field_name: str = "") -> FieldType:
    """Infer FieldType from a JSON value and optional field name hint.

    Rules:
    - bool -> BOOLEAN (must check before int, since bool is subclass of int)
    - int/float -> PERCENTAGE if field_name contains a hint substring, else NUMERIC
    - str -> STRING
    """
    if isinstance(value, bool):
        return FieldType.BOOLEAN
    if isinstance(value, (int, float)):
        name_lower = field_name.lower()
        if any(h in name_lower for h in _PERCENTAGE_HINTS):
            return FieldType.PERCENTAGE
        return FieldType.NUMERIC
    return FieldType.STRING


def infer_type_from_values(values: list[Any], field_name: str = "") -> FieldType:
    """Infer the narrowest common FieldType across a list of values.

    Collects per-value types then returns the minimum compatible type.
    None values are skipped.
    """
    inferred: list[FieldType] = []
    for v in values:
        if v is None:
            continue
        inferred.append(infer_type(v, field_name))
    if not inferred:
        return FieldType.STRING
    return FieldType.narrowest_common(*inferred)


def _value_matches_type(value: Any, ft: FieldType) -> bool:
    """Check if a raw value is compatible with the expected FieldType."""
    if isinstance(value, float) and math.isnan(value):
        return True  # NaN is always acceptable
    if ft == FieldType.STRING:
        return True  # STRING accepts everything
    if ft == FieldType.BOOLEAN:
        return isinstance(value, bool)
    if ft in (FieldType.NUMERIC, FieldType.PERCENTAGE):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def normalize_fields(
    raw: dict[str, Any], *, prefix: str = "",
    type_overrides: dict[str, str] | None = None,
    all_keys: list[str] | None = None,
) -> dict[str, FieldValue]:
    """Convert a raw dict into {key: FieldValue}.

    Types are determined by:
    1. Explicit type_overrides from fields.json
    2. Inference from value type and field name hints

    Args:
        raw: Raw field dict from JSON.
        prefix: Unused, kept for compatibility.
        type_overrides: Field name -> type string overrides.
        all_keys: If provided, pad missing keys with None-valued FieldValues.
    """
    overrides = type_overrides or {}
    result: dict[str, FieldValue] = {}

    for key, raw_val in raw.items():
        ft = _resolve_type(raw_val, key, overrides)
        # Type mismatch: value doesn't fit the declared/inferred type -> NaN
        if not _value_matches_type(raw_val, ft):
            result[key] = FieldValue(value=float("nan"), field_type=ft)
        else:
            result[key] = FieldValue(value=raw_val, field_type=ft)

    # Pad missing keys with None-valued FieldValues
    if all_keys:
        for key in all_keys:
            if key not in result:
                ft = _resolve_type(None, key, overrides) if key in overrides else None
                if ft is None:
                    # Infer from key name hints; default to STRING
                    ft = infer_type(None, key) if key else FieldType.STRING
                result[key] = FieldValue(value=None, field_type=ft)

    return result


def normalize_experiment(
    raw: dict[str, Any], *, default_id: str = "",
    type_overrides: dict[str, str] | None = None,
    all_hp_keys: list[str] | None = None,
    all_res_keys: list[str] | None = None,
) -> Experiment:
    """Normalize a raw experiment dict into an Experiment.

    Args:
        raw: Raw experiment data.
        default_id: Fallback ID if not in raw.
        type_overrides: Field name -> type string overrides.
        all_hp_keys: If provided, pad missing hyperparameters with None.
        all_res_keys: If provided, pad missing results with None.
    """
    exp_id = raw.get("id", default_id)
    name = raw.get("name", exp_id)
    created_at = raw.get("created_at", "")
    tags = raw.get("tags", [])

    hp_raw = raw.get("hyperparameters", {})
    res_raw = raw.get("results", {})

    return Experiment(
        id=exp_id,
        name=name,
        hyperparameters=normalize_fields(
            hp_raw, type_overrides=type_overrides, all_keys=all_hp_keys
        ),
        results=normalize_fields(
            res_raw, type_overrides=type_overrides, all_keys=all_res_keys
        ),
        created_at=created_at,
        tags=list(tags),
    )
