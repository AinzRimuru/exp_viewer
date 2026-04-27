"""FastAPI application factory for exp_viewer server."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..database import Database
from ..discovery import scan_directory
from ..types import ExperimentSet


def create_app(
    experiments_root: Path | None = None,
    db_path: Path | None = None,
) -> FastAPI:
    """Create a FastAPI application.

    Args:
        experiments_root: Directory to scan for experiments on startup.
        db_path: Path to an existing SQLite database.
    """
    db: Database | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal db
        if db_path:
            db = Database(db_path)
        elif experiments_root:
            db = Database(":memory:")
            experiments = scan_directory(experiments_root)
            for exp in experiments:
                db.save(exp)
        else:
            db = Database(":memory:")

        app.state.db = db
        yield
        if db:
            db.close()

    app = FastAPI(title="Experiment Viewer", lifespan=lifespan)

    # Static files and templates
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from .routes import router
    app.include_router(router)

    return app
