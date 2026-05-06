"""Tests for exp_viewer database module."""

import tempfile
from pathlib import Path

from exp_viewer.database import Database
from exp_viewer.types import Experiment, FieldType, FieldValue


def _make_exp(id="test1", lr=0.001, acc=0.95):
    return Experiment(
        id=id,
        name=id,
        hyperparameters={"lr": FieldValue(lr, FieldType.NUMERIC)},
        results={"acc": FieldValue(acc, FieldType.PERCENTAGE)},
        tags=["test"],
    )


class TestDatabase:
    def test_save_and_load(self):
        db = Database()
        exp = _make_exp()
        db.save(exp)
        loaded = db.load_by_id("test1")
        assert loaded is not None
        assert loaded.id == "test1"
        assert loaded.hyperparameters["lr"].value == 0.001
        assert loaded.results["acc"].field_type == FieldType.PERCENTAGE

    def test_load_all(self):
        db = Database()
        db.save(_make_exp("a"))
        db.save(_make_exp("b"))
        es = db.load_all()
        assert len(es) == 2
        ids = {e.id for e in es}
        assert ids == {"a", "b"}

    def test_delete(self):
        db = Database()
        db.save(_make_exp("a"))
        assert db.delete("a") is True
        assert db.load_by_id("a") is None
        assert db.delete("nonexistent") is False

    def test_clear(self):
        db = Database()
        db.save(_make_exp("a"))
        db.save(_make_exp("b"))
        db.clear()
        assert len(db.load_all()) == 0

    def test_persistence_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = Path(f.name)

        db = Database(db_path)
        db.save(_make_exp("saved"))
        db.close()

        db2 = Database(db_path)
        loaded = db2.load_by_id("saved")
        assert loaded is not None
        assert loaded.id == "saved"
        db2.close()

        db_path.unlink()

    def test_save_and_load_project(self):
        db = Database()
        exp = _make_exp("proj_test")
        exp.project = "my_project"
        db.save(exp)
        loaded = db.load_by_id("proj_test")
        assert loaded is not None
        assert loaded.project == "my_project"
