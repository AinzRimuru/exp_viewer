"""Tests for exp_viewer schema module."""

from pathlib import Path

from exp_viewer.schema import (
    FIELDS_CONFIG_FILENAME,
    infer_type,
    infer_type_from_values,
    load_fields_config,
    normalize_experiment,
    normalize_fields,
)
from exp_viewer.types import FieldType

FIXTURES = Path(__file__).parent / "fixtures"


class TestInferTypeFromValues:
    def test_all_numeric(self):
        assert infer_type_from_values([1, 2.0, 3], "loss") == FieldType.NUMERIC

    def test_mixed_bool_numeric(self):
        """bool + int -> NUMERIC (minimum common type)"""
        assert infer_type_from_values([True, 1, 2], "field") == FieldType.NUMERIC

    def test_mixed_numeric_string(self):
        """int + str -> STRING"""
        assert infer_type_from_values([1, "two", 3], "field") == FieldType.STRING

    def test_mixed_bool_string(self):
        """bool + str -> STRING"""
        assert infer_type_from_values([True, "yes"], "field") == FieldType.STRING

    def test_with_none_skipped(self):
        """None values are skipped"""
        assert infer_type_from_values([None, 1, None, 2.0], "field") == FieldType.NUMERIC

    def test_all_none(self):
        assert infer_type_from_values([None, None], "field") == FieldType.STRING

    def test_name_hint_still_applies(self):
        """Name hint affects individual inference before widening"""
        assert infer_type_from_values([0.9, 0.95], "accuracy") == FieldType.PERCENTAGE

    def test_name_hint_with_mismatch(self):
        """accuracy (PERCENTAGE) + string -> STRING"""
        assert infer_type_from_values([0.9, "N/A"], "accuracy") == FieldType.STRING


class TestInferType:
    def test_bool(self):
        assert infer_type(True) == FieldType.BOOLEAN
        assert infer_type(False) == FieldType.BOOLEAN

    def test_int(self):
        assert infer_type(42) == FieldType.NUMERIC
        assert infer_type(0) == FieldType.NUMERIC

    def test_float(self):
        assert infer_type(0.5) == FieldType.NUMERIC

    def test_percentage_by_name(self):
        assert infer_type(0.95, "accuracy") == FieldType.PERCENTAGE
        assert infer_type(0.95, "my_score") == FieldType.PERCENTAGE
        assert infer_type(0.8, "train_pct") == FieldType.PERCENTAGE
        assert infer_type(0.1, "dropout") == FieldType.NUMERIC  # no hint in name

    def test_string(self):
        assert infer_type("adam") == FieldType.STRING


class TestLoadFieldsConfig:
    def test_load_from_fixtures(self):
        config = load_fields_config(FIXTURES)
        assert config["accuracy"] == "percentage"
        assert config["loss"] == "numeric"
        assert config["optimizer"] == "string"
        assert config["converged"] == "boolean"

    def test_missing_file(self):
        config = load_fields_config(FIXTURES / "exp_run1")
        assert config == {}


class TestNormalizeFields:
    def test_shorthand(self):
        fields = normalize_fields({"lr": 0.001, "opt": "adam", "aug": True})
        assert fields["lr"].field_type == FieldType.NUMERIC
        assert fields["opt"].field_type == FieldType.STRING
        assert fields["aug"].field_type == FieldType.BOOLEAN

    def test_with_overrides(self):
        fields = normalize_fields(
            {"accuracy": 0.95, "loss": 0.032},
            type_overrides={"accuracy": "percentage", "loss": "numeric"},
        )
        assert fields["accuracy"].field_type == FieldType.PERCENTAGE
        assert fields["loss"].field_type == FieldType.NUMERIC

    def test_override_takes_priority(self):
        """Override wins even when name-based inference would differ."""
        fields = normalize_fields(
            {"dropout": 0.3},
            type_overrides={"dropout": "percentage"},
        )
        assert fields["dropout"].field_type == FieldType.PERCENTAGE

    def test_type_mismatch_becomes_nan(self):
        """Value that doesn't match declared type is replaced with NaN."""
        import math
        fields = normalize_fields(
            {"accuracy": "not_a_number"},
            type_overrides={"accuracy": "percentage"},
        )
        assert fields["accuracy"].field_type == FieldType.PERCENTAGE
        assert math.isnan(fields["accuracy"].value)

    def test_bool_in_numeric_field_becomes_nan(self):
        """Boolean in a NUMERIC field is replaced with NaN."""
        import math
        fields = normalize_fields(
            {"loss": True},
            type_overrides={"loss": "numeric"},
        )
        assert fields["loss"].field_type == FieldType.NUMERIC
        assert math.isnan(fields["loss"].value)

    def test_string_in_boolean_field_becomes_nan(self):
        """String in a BOOLEAN field is replaced with NaN."""
        import math
        fields = normalize_fields(
            {"converged": "yes"},
            type_overrides={"converged": "boolean"},
        )
        assert fields["converged"].field_type == FieldType.BOOLEAN
        assert math.isnan(fields["converged"].value)

    def test_number_in_string_field_is_ok(self):
        """Number in STRING field is allowed (widened)."""
        fields = normalize_fields(
            {"note": 42},
            type_overrides={"note": "string"},
        )
        assert fields["note"].field_type == FieldType.STRING
        assert fields["note"].value == 42

    def test_missing_keys_padded_with_none(self):
        """all_keys pads missing keys with None value."""
        fields = normalize_fields(
            {"lr": 0.01},
            type_overrides={"lr": "numeric", "dropout": "percentage"},
            all_keys=["lr", "dropout", "optimizer"],
        )
        assert fields["lr"].value == 0.01
        assert fields["dropout"].value is None
        assert fields["optimizer"].value is None


class TestNormalizeExperiment:
    def test_shorthand_experiment(self):
        raw = {
            "id": "test1",
            "hyperparameters": {"lr": 0.01, "opt": "sgd"},
            "results": {"accuracy": 0.9},
        }
        exp = normalize_experiment(raw)
        assert exp.id == "test1"
        assert exp.name == "test1"
        assert "lr" in exp.hyperparameters
        assert "accuracy" in exp.results
        assert exp.results["accuracy"].field_type == FieldType.PERCENTAGE

    def test_with_type_overrides(self):
        raw = {
            "id": "test1",
            "hyperparameters": {"lr": 0.01},
            "results": {"accuracy": 0.9, "loss": 0.5},
        }
        exp = normalize_experiment(
            raw,
            type_overrides={"accuracy": "percentage", "loss": "numeric"},
        )
        assert exp.results["accuracy"].field_type == FieldType.PERCENTAGE
        assert exp.results["loss"].field_type == FieldType.NUMERIC

    def test_default_id(self):
        raw = {
            "hyperparameters": {"lr": 0.01},
            "results": {"loss": 0.5},
        }
        exp = normalize_experiment(raw, default_id="fallback_id")
        assert exp.id == "fallback_id"

    def test_with_metadata(self):
        raw = {
            "id": "exp1",
            "name": "My Experiment",
            "tags": ["sweep", "lr"],
            "created_at": "2026-01-01",
            "hyperparameters": {"lr": 0.01},
            "results": {"loss": 0.5},
        }
        exp = normalize_experiment(raw)
        assert exp.name == "My Experiment"
        assert exp.tags == ["sweep", "lr"]
        assert exp.created_at == "2026-01-01"
