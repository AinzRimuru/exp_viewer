"""SQLite persistence layer for experiments."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import orjson

from .types import Experiment, ExperimentSet, FieldValue


class Database:
    """SQLite-backed storage for experiments."""

    def __init__(self, path: Path | str = ":memory:") -> None:
        self.path = Path(path) if path != ":memory:" else path
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                directory TEXT,
                created_at TEXT NOT NULL DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS hyperparameters (
                experiment_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value_text TEXT,
                value_type TEXT NOT NULL DEFAULT 'string',
                PRIMARY KEY (experiment_id, key),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS results (
                experiment_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value_text TEXT,
                value_type TEXT NOT NULL DEFAULT 'string',
                PRIMARY KEY (experiment_id, key),
                FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
            );
        """)
        self._conn.commit()

    def save(self, experiment: Experiment, *, directory: str | None = None) -> None:
        """Save or update an experiment."""
        project = experiment.project or directory
        self._conn.execute(
            """INSERT OR REPLACE INTO experiments (id, name, directory, created_at, tags)
               VALUES (?, ?, ?, ?, ?)""",
            (
                experiment.id,
                experiment.name,
                project,
                experiment.created_at,
                orjson.dumps(experiment.tags).decode(),
            ),
        )
        self._save_fields("hyperparameters", experiment.id, experiment.hyperparameters)
        self._save_fields("results", experiment.id, experiment.results)
        self._conn.commit()

    def _save_fields(
        self, table: str, exp_id: str, fields: dict[str, FieldValue]
    ) -> None:
        self._conn.execute(
            f"DELETE FROM {table} WHERE experiment_id = ?", (exp_id,)
        )
        rows = [
            (exp_id, key, orjson.dumps(fv.value).decode(), fv.field_type.value)
            for key, fv in fields.items()
        ]
        if rows:
            self._conn.executemany(
                f"INSERT INTO {table} (experiment_id, key, value_text, value_type) VALUES (?, ?, ?, ?)",
                rows,
            )

    def load_all(self) -> ExperimentSet:
        """Load all experiments from the database."""
        rows = self._conn.execute(
            "SELECT id, name, directory, created_at, tags FROM experiments ORDER BY id"
        ).fetchall()
        experiments = [self._load_experiment(r) for r in rows]
        return ExperimentSet(experiments)

    def load_by_id(self, exp_id: str) -> Experiment | None:
        """Load a single experiment by id."""
        row = self._conn.execute(
            "SELECT id, name, directory, created_at, tags FROM experiments WHERE id = ?",
            (exp_id,),
        ).fetchone()
        if row is None:
            return None
        return self._load_experiment(row)

    def _load_experiment(self, row: tuple) -> Experiment:
        from .types import FieldType

        exp_id, name, directory, created_at, tags_json = row
        tags = orjson.loads(tags_json) if tags_json else []

        hp = self._load_fields("hyperparameters", exp_id)
        res = self._load_fields("results", exp_id)

        return Experiment(
            id=exp_id,
            name=name,
            hyperparameters=hp,
            results=res,
            created_at=created_at or "",
            tags=tags,
            project=directory or "",
        )

    def _load_fields(self, table: str, exp_id: str) -> dict[str, FieldValue]:
        from .types import FieldType

        rows = self._conn.execute(
            f"SELECT key, value_text, value_type FROM {table} WHERE experiment_id = ?",
            (exp_id,),
        ).fetchall()
        result: dict[str, FieldValue] = {}
        for key, value_text, type_str in rows:
            value = orjson.loads(value_text) if value_text is not None else None
            ft = FieldType(type_str)
            result[key] = FieldValue(value=value, field_type=ft)
        return result

    def delete(self, exp_id: str) -> bool:
        """Delete an experiment by id. Returns True if deleted."""
        cursor = self._conn.execute(
            "DELETE FROM experiments WHERE id = ?", (exp_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Delete all experiments."""
        self._conn.executescript(
            "DELETE FROM results; DELETE FROM hyperparameters; DELETE FROM experiments;"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
