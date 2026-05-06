"""Tests for exp_viewer discovery module."""

from pathlib import Path

from exp_viewer.discovery import scan_directory, register_from_directory
from exp_viewer.schema import extract_type_overrides, load_fields_config
from exp_viewer.types import FieldType

FIXTURES = Path(__file__).parent / "fixtures"


class TestRegisterFromDirectory:
    def test_load_run1(self):
        # register_from_directory without overrides uses name-based inference
        exp = register_from_directory(FIXTURES / "exp_run1")
        assert exp.id == "exp_run1"
        assert "learning_rate" in exp.hyperparameters
        assert "accuracy" in exp.results
        assert exp.results["accuracy"].field_type == FieldType.PERCENTAGE
        assert exp.hyperparameters["use_augmentation"].field_type == FieldType.BOOLEAN

    def test_load_run1_with_overrides(self):
        overrides = extract_type_overrides(load_fields_config(FIXTURES))
        exp = register_from_directory(FIXTURES / "exp_run1", type_overrides=overrides)
        assert exp.results["accuracy"].field_type == FieldType.PERCENTAGE
        assert exp.results["loss"].field_type == FieldType.NUMERIC
        assert exp.results["converged"].field_type == FieldType.BOOLEAN

    def test_load_run3_with_metadata(self):
        exp = register_from_directory(FIXTURES / "exp_run3")
        assert exp.id == "exp_large_lr"
        assert exp.name == "Large LR Experiment"
        assert "sweep" in exp.tags


class TestScanDirectory:
    def test_scan_all(self):
        experiments = scan_directory(FIXTURES)
        assert len(experiments) == 3
        ids = {e.id for e in experiments}
        assert "exp_run1" in ids
        assert "exp_run2" in ids
        assert "exp_large_lr" in ids

    def test_scan_with_fields_json(self):
        """scan_directory auto-loads fields.json and applies type overrides."""
        experiments = scan_directory(FIXTURES)
        exp1 = next(e for e in experiments if e.id == "exp_run1")
        # fields.json specifies accuracy=percentage, loss=numeric, converged=boolean
        assert exp1.results["accuracy"].field_type == FieldType.PERCENTAGE
        assert exp1.results["loss"].field_type == FieldType.NUMERIC
        assert exp1.results["converged"].field_type == FieldType.BOOLEAN

    def test_scan_cross_experiment_type_widening(self, tmp_path):
        """When same field has different types across experiments, use common type."""
        # exp_a: lr is numeric (0.01)
        (tmp_path / "exp_a").mkdir()
        (tmp_path / "exp_a" / "config.json").write_text('{"lr": 0.01}')
        (tmp_path / "exp_a" / "results.json").write_text('{"loss": 0.5}')
        # exp_b: lr is string ("auto")
        (tmp_path / "exp_b").mkdir()
        (tmp_path / "exp_b" / "config.json").write_text('{"lr": "auto"}')
        (tmp_path / "exp_b" / "results.json").write_text('{"loss": 0.3}')

        experiments = scan_directory(tmp_path)
        assert len(experiments) == 2
        # lr: NUMERIC + STRING -> STRING (minimum common)
        for exp in experiments:
            assert exp.hyperparameters["lr"].field_type == FieldType.STRING
        # loss: all NUMERIC -> stays NUMERIC
        for exp in experiments:
            assert exp.results["loss"].field_type == FieldType.NUMERIC

    def test_scan_fields_json_overrides_inference(self, tmp_path):
        """fields.json should override cross-experiment inference."""
        (tmp_path / "exp_a").mkdir()
        (tmp_path / "exp_a" / "config.json").write_text('{"lr": 0.01}')
        (tmp_path / "exp_a" / "results.json").write_text('{"loss": 0.5}')
        (tmp_path / "exp_b").mkdir()
        (tmp_path / "exp_b" / "config.json").write_text('{"lr": "auto"}')
        (tmp_path / "exp_b" / "results.json").write_text('{"loss": 0.3}')
        # Force lr to be string via fields.json
        (tmp_path / "fields.json").write_text('{"lr": "string"}')

        experiments = scan_directory(tmp_path)
        for exp in experiments:
            assert exp.hyperparameters["lr"].field_type == FieldType.STRING

    def test_scan_missing_field_padded_with_none(self, tmp_path):
        """Experiments missing a field get it padded with None."""
        # exp_a has dropout, exp_b doesn't
        (tmp_path / "exp_a").mkdir()
        (tmp_path / "exp_a" / "config.json").write_text('{"lr": 0.01, "dropout": 0.3}')
        (tmp_path / "exp_a" / "results.json").write_text('{"loss": 0.5}')
        (tmp_path / "exp_b").mkdir()
        (tmp_path / "exp_b" / "config.json").write_text('{"lr": 0.001}')
        (tmp_path / "exp_b" / "results.json").write_text('{"loss": 0.3}')

        experiments = scan_directory(tmp_path)
        exp_a = next(e for e in experiments if e.id == "exp_a")
        exp_b = next(e for e in experiments if e.id == "exp_b")

        # exp_b should have dropout with None value
        assert "dropout" in exp_b.hyperparameters
        assert exp_b.hyperparameters["dropout"].value is None
        # exp_a should have dropout with actual value
        assert exp_a.hyperparameters["dropout"].value == 0.3

    def test_scan_type_mismatch_becomes_nan(self, tmp_path):
        """Value incompatible with field's resolved type becomes NaN."""
        import math
        # exp_a: accuracy is numeric (0.95 -> PERCENTAGE by name)
        (tmp_path / "exp_a").mkdir()
        (tmp_path / "exp_a" / "config.json").write_text('{"lr": 0.01}')
        (tmp_path / "exp_a" / "results.json").write_text('{"accuracy": 0.95}')
        # exp_b: accuracy is a string (breaks the PERCENTAGE type)
        (tmp_path / "exp_b").mkdir()
        (tmp_path / "exp_b" / "config.json").write_text('{"lr": 0.001}')
        (tmp_path / "exp_b" / "results.json").write_text('{"accuracy": "N/A"}')

        experiments = scan_directory(tmp_path)
        # accuracy field type should widen to STRING
        for exp in experiments:
            assert exp.results["accuracy"].field_type == FieldType.STRING

    def test_scan_nonexistent(self):
        import pytest
        with pytest.raises(ValueError, match="Not a directory"):
            scan_directory(Path("/nonexistent"))

    def test_scan_with_project(self, tmp_path):
        """scan_directory assigns project label to experiments."""
        (tmp_path / "exp_a").mkdir()
        (tmp_path / "exp_a" / "config.json").write_text('{"lr": 0.01}')
        (tmp_path / "exp_a" / "results.json").write_text('{"loss": 0.5}')

        experiments = scan_directory(tmp_path, project="custom_project")
        assert len(experiments) == 1
        assert experiments[0].project == "custom_project"

    def test_scan_project_defaults_to_dirname(self, tmp_path):
        """scan_directory defaults project to root directory name."""
        root = tmp_path / "my_experiments"
        root.mkdir()
        (root / "exp_a").mkdir()
        (root / "exp_a" / "config.json").write_text('{"lr": 0.01}')
        (root / "exp_a" / "results.json").write_text('{"loss": 0.5}')

        experiments = scan_directory(root)
        assert experiments[0].project == "my_experiments"
