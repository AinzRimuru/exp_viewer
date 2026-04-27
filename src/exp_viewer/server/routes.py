"""FastAPI route definitions for exp_viewer server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from ..render.charts import CHART_BUILDERS
from ..render.export import comparison_html, export_html
from ..render.table import build_table_html, parse_filter_params

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _get_db(request: Request):
    return request.app.state.db


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    db = _get_db(request)
    exp_set = db.load_all()
    fields = _get_field_info(exp_set)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"experiment_count": len(exp_set), "fields": fields},
    )


@router.get("/api/experiments")
async def list_experiments(request: Request):
    """Return all experiments as JSON."""
    db = _get_db(request)
    exp_set = db.load_all()
    experiments = []
    for exp in exp_set:
        experiments.append({
            "id": exp.id,
            "name": exp.name,
            "created_at": exp.created_at,
            "tags": exp.tags,
            "hyperparameters": {
                k: {"value": fv.value, "type": fv.field_type.value}
                for k, fv in exp.hyperparameters.items()
            },
            "results": {
                k: {"value": fv.value, "type": fv.field_type.value}
                for k, fv in exp.results.items()
            },
        })
    return JSONResponse(experiments)


@router.get("/experiments/{exp_id}", response_class=HTMLResponse)
async def experiment_detail(request: Request, exp_id: str):
    """Render experiment detail page."""
    db = _get_db(request)
    exp = db.load_by_id(exp_id)
    if exp is None:
        return HTMLResponse("<h1>Not Found</h1>", status_code=404)
    return templates.TemplateResponse(
        request,
        "experiment.html",
        {"experiment": exp},
    )


@router.get("/api/experiments/{exp_id}")
async def get_experiment(request: Request, exp_id: str):
    """Return a single experiment by id."""
    db = _get_db(request)
    exp = db.load_by_id(exp_id)
    if exp is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({
        "id": exp.id,
        "name": exp.name,
        "created_at": exp.created_at,
        "tags": exp.tags,
        "hyperparameters": {
            k: {"value": fv.value, "type": fv.field_type.value}
            for k, fv in exp.hyperparameters.items()
        },
        "results": {
            k: {"value": fv.value, "type": fv.field_type.value}
            for k, fv in exp.results.items()
        },
    })


@router.get("/api/fields")
async def list_fields(request: Request):
    """Return all field names and types."""
    db = _get_db(request)
    exp_set = db.load_all()
    return JSONResponse(_get_field_info(exp_set))


@router.get("/api/table", response_class=HTMLResponse)
async def get_table(
    request: Request,
    sort_by: str | None = Query(None),
    sort_desc: bool = Query(False),
    columns: str | None = Query(None),
):
    """Return the experiment table as an HTML fragment."""
    db = _get_db(request)
    exp_set = db.load_all()

    # Collect filter params
    filter_params = {}
    for key, value in request.query_params.items():
        if key.startswith("filter_"):
            field_key = key[7:]  # strip "filter_"
            filter_params[field_key] = value

    filters = parse_filter_params(filter_params) if filter_params else None
    cols = columns.split(",") if columns else None

    html = build_table_html(
        exp_set,
        columns=cols,
        sort_by=sort_by,
        sort_desc=sort_desc,
        filters=filters,
    )
    return HTMLResponse(html)


@router.get("/api/chart/{chart_type}")
async def get_chart(
    request: Request,
    chart_type: str,
    x: str | None = Query(None),
    y: str | None = Query(None),
    color: str | None = Query(None),
    size: str | None = Query(None),
    dimensions: str | None = Query(None),
    title: str = Query(""),
):
    """Return a Plotly chart as JSON."""
    builder = CHART_BUILDERS.get(chart_type)
    if builder is None:
        return JSONResponse(
            {"error": f"Unknown chart type: {chart_type}. Available: {list(CHART_BUILDERS)}"},
            status_code=400,
        )

    db = _get_db(request)
    exp_set = db.load_all()

    try:
        if chart_type == "bar":
            fig = builder(exp_set, x_field=x or "id", y_field=y or "", color_field=color, title=title)
        elif chart_type == "line":
            y_fields = y.split(",") if y else []
            fig = builder(exp_set, x_field=x or "id", y_fields=y_fields, title=title)
        elif chart_type == "scatter":
            fig = builder(
                exp_set, x_field=x or "", y_field=y or "",
                size_field=size, color_field=color, title=title,
            )
        elif chart_type == "parallel_coordinates":
            dims = dimensions.split(",") if dimensions else []
            fig = builder(exp_set, dimensions=dims, color_field=color, title=title)
        elif chart_type == "heatmap":
            fig = builder(
                exp_set, x_field=x or "", y_field=y or "",
                value_field=size or "", title=title,
            )
        else:
            fig = builder(exp_set, title=title)

        return JSONResponse(fig.to_dict())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.post("/api/scan")
async def rescan(request: Request):
    """Re-scan the experiment directory and reload the database."""
    db = _get_db(request)
    root = getattr(request.app.state, "experiments_root", None)
    if root is None:
        return JSONResponse({"error": "No experiment root configured"}, status_code=400)

    db.clear()
    experiments = scan_directory(root)
    for exp in experiments:
        db.save(exp)
    return JSONResponse({"loaded": len(experiments)})


@router.get("/export")
async def download_export(request: Request):
    """Download a static HTML export."""
    import tempfile

    db = _get_db(request)
    exp_set = db.load_all()

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        path = export_html(exp_set, f.name)

    from fastapi.responses import FileResponse
    return FileResponse(
        path, media_type="text/html", filename="experiments.html"
    )


def _get_field_info(exp_set) -> dict[str, Any]:
    """Extract field names and types for the frontend."""
    hp_keys = exp_set.all_hyperparameter_keys
    res_keys = exp_set.all_result_keys
    fields = {}
    for k in hp_keys:
        for exp in exp_set:
            fv = exp.hyperparameters.get(k)
            if fv:
                fields[k] = {"type": fv.field_type.value, "category": "hyperparameter"}
                break
    for k in res_keys:
        for exp in exp_set:
            fv = exp.results.get(k)
            if fv:
                fields[k] = {"type": fv.field_type.value, "category": "result"}
                break
    return {
        "hyperparameters": hp_keys,
        "results": res_keys,
        "fields": fields,
    }
