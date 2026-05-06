"""CLI entry point for exp_viewer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="exp-viewer", description="Experiment data visualization toolkit"
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start interactive web server")
    serve_parser.add_argument("paths", nargs="+", help="Paths to experiment directories or SQLite DB")
    serve_parser.add_argument("--labels", help="Comma-separated project labels (one per path)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8050, help="Bind port (default: 8050)")
    serve_parser.add_argument("--db", help="SQLite database path (default: in-memory)")

    # export
    export_parser = subparsers.add_parser("export", help="Export to static HTML")
    export_parser.add_argument("path", help="Path to experiments directory or SQLite DB")
    export_parser.add_argument("-o", "--output", default="experiments.html", help="Output HTML file")
    export_parser.add_argument("--title", default="Experiment Viewer", help="Page title")

    # scan
    scan_parser = subparsers.add_parser("scan", help="Scan directory and build SQLite database")
    scan_parser.add_argument("path", help="Path to experiments root directory")
    scan_parser.add_argument("-o", "--output", default="experiments.db", help="SQLite output path")

    # info
    info_parser = subparsers.add_parser("info", help="Print summary of experiments")
    info_parser.add_argument("path", help="Path to experiments directory or SQLite DB")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "serve":
        _cmd_serve(args)
    elif args.command == "export":
        _cmd_export(args)
    elif args.command == "scan":
        _cmd_scan(args)
    elif args.command == "info":
        _cmd_info(args)


def _resolve_path(path: str) -> tuple[Path | None, Path | None]:
    """Resolve a path to (experiments_root, db_path)."""
    p = Path(path)
    if p.is_file() and p.suffix == ".db":
        return None, p
    if p.is_dir():
        return p, None
    print(f"Error: {path} is not a directory or .db file", file=sys.stderr)
    sys.exit(1)


def _resolve_paths(
    paths: list[str], labels: list[str] | None = None
) -> list[tuple[Path, str]]:
    """Resolve multiple paths to [(root, project_label), ...]."""
    result: list[tuple[Path, str]] = []
    for i, p in enumerate(paths):
        path = Path(p)
        label = labels[i] if labels and i < len(labels) else path.name
        if path.is_dir():
            result.append((path, label))
        elif path.is_file() and path.suffix == ".db":
            result.append((path, label))
        else:
            print(f"Error: {p} is not a directory or .db file", file=sys.stderr)
            sys.exit(1)
    return result


def _load_experiments(args):
    """Load experiments from args.path, return ExperimentSet."""
    from .database import Database
    from .discovery import scan_directory
    from .types import ExperimentSet

    root, db_path = _resolve_path(args.path)
    if db_path:
        db = Database(db_path)
        return db.load_all(), db

    experiments = scan_directory(root or Path(args.path))
    return ExperimentSet(experiments), None


def _cmd_serve(args) -> None:
    import uvicorn
    from .server.app import create_app

    # Single .db file: backward compatible
    if len(args.paths) == 1:
        p = Path(args.paths[0])
        if p.is_file() and p.suffix == ".db":
            root, db_path = _resolve_path(args.paths[0])
            app = create_app(experiments_root=root, db_path=db_path)
            if root:
                app.state.experiments_root = root
            print(f"Starting server at http://{args.host}:{args.port}")
            uvicorn.run(app, host=args.host, port=args.port)
            return

    labels = args.labels.split(",") if args.labels else None
    roots = _resolve_paths(args.paths, labels)
    app = create_app(experiments_roots=roots)

    print(f"Starting server at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


def _cmd_export(args) -> None:
    from .render.export import export_html

    exp_set, db = _load_experiments(args)
    output = export_html(exp_set, args.output, title=args.title)
    print(f"Exported {len(exp_set)} experiments to {output}")

    if db:
        db.close()


def _cmd_scan(args) -> None:
    from .database import Database
    from .discovery import scan_directory

    root = Path(args.path)
    if not root.is_dir():
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    db = Database(args.output)
    experiments = scan_directory(root)
    for exp in experiments:
        db.save(exp, directory=str(root / exp.id))

    print(f"Scanned {len(experiments)} experiments into {args.output}")
    db.close()


def _cmd_info(args) -> None:
    exp_set, db = _load_experiments(args)

    print(f"Experiments: {len(exp_set)}")
    hp_keys = exp_set.all_hyperparameter_keys
    res_keys = exp_set.all_result_keys
    print(f"Hyperparameter keys: {', '.join(hp_keys) if hp_keys else '(none)'}")
    print(f"Result keys: {', '.join(res_keys) if res_keys else '(none)'}")
    print()

    for exp in exp_set:
        print(f"  [{exp.id}] {exp.name}")
        if exp.tags:
            print(f"    tags: {', '.join(exp.tags)}")
        for k, fv in exp.hyperparameters.items():
            print(f"    hp.{k} = {fv.display_value}")
        for k, fv in exp.results.items():
            print(f"    res.{k} = {fv.display_value}")
        print()

    if db:
        db.close()


if __name__ == "__main__":
    main()
