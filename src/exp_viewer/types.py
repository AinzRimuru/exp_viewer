"""Core data model for exp_viewer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class FieldType(Enum):
    NUMERIC = "numeric"
    PERCENTAGE = "percentage"
    BOOLEAN = "boolean"
    STRING = "string"

    @staticmethod
    def narrowest_common(*types: FieldType) -> FieldType:
        """Return the narrowest type that is compatible with all given types.

        Compatibility (narrow → wide): BOOLEAN ⊂ NUMERIC ⊂ PERCENTAGE ⊂ STRING
        """
        _WIDTH = {
            FieldType.BOOLEAN: 0,
            FieldType.NUMERIC: 1,
            FieldType.PERCENTAGE: 2,
            FieldType.STRING: 3,
        }
        if not types:
            return FieldType.STRING
        max_width = max(_WIDTH[t] for t in types)
        return [ft for ft, w in _WIDTH.items() if w == max_width][0]


@dataclass
class FieldValue:
    """A typed experiment field value."""

    value: Any
    field_type: FieldType

    @property
    def numeric_value(self) -> float | None:
        """Return a float representation for numeric-like types, None for strings."""
        if self.field_type == FieldType.STRING:
            return None
        if self.field_type == FieldType.BOOLEAN:
            return 1.0 if self.value else 0.0
        if self.field_type == FieldType.PERCENTAGE:
            v = float(self.value)
            return v if v <= 1.0 else v / 100.0
        return float(self.value)

    @property
    def display_value(self) -> str:
        """Human-readable string for display."""
        if self.field_type == FieldType.PERCENTAGE:
            v = float(self.value)
            if v <= 1.0:
                return f"{v:.2%}"
            return f"{v:.1f}%"
        if self.field_type == FieldType.BOOLEAN:
            return "True" if self.value else "False"
        if self.field_type == FieldType.NUMERIC:
            v = self.value
            if isinstance(v, float):
                if abs(v) < 0.001 or abs(v) >= 1e6:
                    return f"{v:.4e}"
                return f"{v:.4f}"
            return str(v)
        return str(self.value)

    @property
    def sort_value(self) -> Any:
        """Value suitable for sorting: numeric for numbers, string for others."""
        if self.field_type in (FieldType.NUMERIC, FieldType.PERCENTAGE):
            return float(self.value)
        if self.field_type == FieldType.BOOLEAN:
            return 1 if self.value else 0
        return str(self.value)


@dataclass
class Experiment:
    """A single experiment with hyperparameters and results."""

    id: str
    name: str
    hyperparameters: dict[str, FieldValue]
    results: dict[str, FieldValue]
    created_at: str = ""
    tags: list[str] = field(default_factory=list)

    def get_field(self, key: str) -> FieldValue | None:
        """Look up a field by key, checking hyperparameters then results."""
        if key in self.hyperparameters:
            return self.hyperparameters[key]
        if key in self.results:
            return self.results[key]
        return None

    def all_fields(self) -> dict[str, FieldValue]:
        """Return merged dict of all hyperparameters and results."""
        return {**self.hyperparameters, **self.results}


@dataclass
class ExperimentSet:
    """A collection of experiments with filtering and sorting."""

    experiments: list[Experiment]

    @property
    def all_hyperparameter_keys(self) -> list[str]:
        """Union of all hyperparameter keys across experiments, in stable order."""
        seen: dict[str, None] = {}
        for exp in self.experiments:
            for k in exp.hyperparameters:
                seen.setdefault(k)
        return list(seen)

    @property
    def all_result_keys(self) -> list[str]:
        """Union of all result keys across experiments, in stable order."""
        seen: dict[str, None] = {}
        for exp in self.experiments:
            for k in exp.results:
                seen.setdefault(k)
        return list(seen)

    def filter(self, predicate: Callable[[Experiment], bool]) -> ExperimentSet:
        """Return a new ExperimentSet with experiments matching the predicate."""
        return ExperimentSet([e for e in self.experiments if predicate(e)])

    def sort_by(
        self, key: str, descending: bool = False, is_result: bool | None = None
    ) -> ExperimentSet:
        """Return a new ExperimentSet sorted by a field.

        Args:
            key: Field name to sort by.
            descending: Sort in descending order.
            is_result: If True, only look in results; if False, only hyperparameters.
                       If None, try both (hyperparameters first).
        """
        def sort_key(exp: Experiment) -> Any:
            if is_result is True:
                fv = exp.results.get(key)
            elif is_result is False:
                fv = exp.hyperparameters.get(key)
            else:
                fv = exp.hyperparameters.get(key) or exp.results.get(key)
            if fv is None:
                return (1, "")  # missing values sort last
            sv = fv.sort_value
            return (0, sv)

        sorted_exps = sorted(self.experiments, key=sort_key, reverse=descending)
        return ExperimentSet(sorted_exps)

    def to_dataframe(self) -> dict[str, list[Any]]:
        """Convert to columnar dict suitable for Plotly / tabular rendering.

        Columns: id, name, tags, created_at, then all hyperparameter keys, then all result keys.
        """
        hp_keys = self.all_hyperparameter_keys
        res_keys = self.all_result_keys
        columns: dict[str, list[Any]] = {
            "id": [],
            "name": [],
            "tags": [],
            "created_at": [],
        }
        for k in hp_keys:
            columns[f"hp:{k}"] = []
        for k in res_keys:
            columns[f"res:{k}"] = []

        for exp in self.experiments:
            columns["id"].append(exp.id)
            columns["name"].append(exp.name)
            columns["tags"].append(exp.tags)
            columns["created_at"].append(exp.created_at)
            for k in hp_keys:
                fv = exp.hyperparameters.get(k)
                columns[f"hp:{k}"].append(fv.value if fv else None)
            for k in res_keys:
                fv = exp.results.get(k)
                columns[f"res:{k}"].append(fv.value if fv else None)

        return columns

    def __len__(self) -> int:
        return len(self.experiments)

    def __iter__(self):
        return iter(self.experiments)
