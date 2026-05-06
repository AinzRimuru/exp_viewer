"""Directory scanning and JSON loading for experiment discovery."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import orjson

from .schema import extract_type_overrides, infer_type_from_values, load_fields_config, normalize_experiment

logger = logging.getLogger(__name__)


def _read_json(path: Path) -> dict | None:
    """Read a JSON file, returning None on failure."""
    try:
        return orjson.loads(path.read_bytes())
    except (OSError, orjson.JSONDecodeError):
        return None


def register_from_directory(
    path: Path, *, type_overrides: dict[str, str] | None = None
) -> "Experiment":
    """Load a single experiment from a directory.

    Reads config.json (hyperparameters) and results.json (results).
    Optionally reads metadata.json for id, name, tags, created_at.

    The directory name is used as the default experiment id.
    """
    from .types import Experiment

    path = Path(path)
    dir_name = path.name

    config = _read_json(path / "config.json")
    results = _read_json(path / "results.json")
    metadata = _read_json(path / "metadata.json")

    if config is None and results is None:
        raise ValueError(f"No config.json or results.json found in {path}")

    config = config or {}
    results = results or {}

    # Build raw experiment dict
    raw: dict = {
        "hyperparameters": config,
        "results": results,
    }

    if metadata:
        raw.update(metadata)
    else:
        raw["id"] = dir_name
        raw["name"] = dir_name
        # Use directory modification time as created_at
        try:
            stat = path.stat()
            dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            raw["created_at"] = dt.isoformat()
        except OSError:
            raw["created_at"] = ""

    return normalize_experiment(raw, default_id=dir_name, type_overrides=type_overrides)


def scan_directory(root: Path, *, project: str = "") -> "list[Experiment]":
    """Scan a root directory for experiment subdirectories.

    A valid experiment directory must contain at least one of:
    config.json, results.json.

    Type resolution order:
    1. Explicit overrides from fields.json (in root directory)
    2. Cross-experiment inference: for each field, collect all values across
       experiments and pick the narrowest common type
    3. Per-value name-based inference (fallback)

    Args:
        root: Path to directory containing experiment subdirectories.
        project: Project label for all experiments. Defaults to root directory name.

    Returns a list of Experiment objects. Skips invalid directories with a warning.
    """
    from .types import Experiment

    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    if not project:
        project = root.name

    # Phase 1: load raw data from all experiment directories
    field_configs = load_fields_config(root)
    type_overrides = extract_type_overrides(field_configs)

    raw_experiments: list[tuple[str, dict]] = []  # (dir_name, raw_dict)

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        has_config = (child / "config.json").is_file()
        has_results = (child / "results.json").is_file()
        if not has_config and not has_results:
            continue
        try:
            raw = _load_raw_from_directory(child)
            raw_experiments.append((child.name, raw))
        except Exception as e:
            logger.warning("Skipping %s: %s", child, e)

    if not raw_experiments:
        return []

    # Phase 2: collect all values per field across experiments, infer common type
    inferred_types = _infer_cross_experiment_types(raw_experiments, type_overrides)

    # Phase 3: normalize each experiment using combined overrides + inferred types
    combined_overrides = {**inferred_types, **type_overrides}

    # Collect union of all field keys across experiments for padding
    all_hp_keys = sorted({
        k for _, raw in raw_experiments for k in raw.get("hyperparameters", {})
    })
    all_res_keys = sorted({
        k for _, raw in raw_experiments for k in raw.get("results", {})
    })

    experiments: list[Experiment] = []
    for dir_name, raw in raw_experiments:
        exp = normalize_experiment(
            raw,
            default_id=dir_name,
            type_overrides=combined_overrides,
            all_hp_keys=all_hp_keys,
            all_res_keys=all_res_keys,
            project=project,
        )
        experiments.append(exp)

    return experiments


def _load_raw_from_directory(path: Path) -> dict:
    """Load raw experiment data from a directory without normalization."""
    path = Path(path)
    dir_name = path.name

    config = _read_json(path / "config.json")
    results = _read_json(path / "results.json")
    metadata = _read_json(path / "metadata.json")

    if config is None and results is None:
        raise ValueError(f"No config.json or results.json found in {path}")

    raw: dict = {
        "hyperparameters": config or {},
        "results": results or {},
    }

    if metadata:
        raw.update(metadata)
    else:
        raw["id"] = dir_name
        raw["name"] = dir_name
        try:
            stat = path.stat()
            dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            raw["created_at"] = dt.isoformat()
        except OSError:
            raw["created_at"] = ""

    return raw


def _infer_cross_experiment_types(
    raw_experiments: list[tuple[str, dict]],
    explicit_overrides: dict[str, str],
) -> dict[str, str]:
    """For each field not in explicit_overrides, infer the narrowest common type
    across all experiments.

    Returns a dict of field_name -> type_string for fields needing inference.
    """
    from .types import FieldType

    # Collect all values per field
    hp_values: dict[str, list[Any]] = {}
    res_values: dict[str, list[Any]] = {}

    for _, raw in raw_experiments:
        for k, v in raw.get("hyperparameters", {}).items():
            hp_values.setdefault(k, []).append(v)
        for k, v in raw.get("results", {}).items():
            res_values.setdefault(k, []).append(v)

    inferred: dict[str, str] = {}

    for field_name, values in {**hp_values, **res_values}.items():
        if field_name in explicit_overrides:
            continue
        ft = infer_type_from_values(values, field_name)
        inferred[field_name] = ft.value

    return inferred
