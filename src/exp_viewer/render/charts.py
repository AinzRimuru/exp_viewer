"""Plotly chart builders for experiment data."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from ..types import ExperimentSet, FieldType


def _resolve_field(
    exp_set: ExperimentSet, key: str
) -> tuple[list[Any], FieldType | None]:
    """Extract a column of values for a field key from the experiment set.

    Special keys: 'id', 'name', 'tags', 'created_at' are resolved from experiment metadata.
    Keys prefixed with 'hp:' force hyperparameter lookup, 'res:' force result lookup.
    Plain keys try hyperparameters first, then results.
    """
    _META_KEYS = {"id", "name", "created_at"}

    source: str | None = None
    clean_key = key
    if key.startswith("hp:"):
        source = "hp"
        clean_key = key[3:]
    elif key.startswith("res:"):
        source = "res"
        clean_key = key[4:]

    # Metadata keys
    if source is None and clean_key in _META_KEYS:
        values = [getattr(exp, clean_key) for exp in exp_set]
        return values, FieldType.STRING

    values: list[Any] = []
    field_type: FieldType | None = None

    for exp in exp_set:
        fv = None
        if source == "hp":
            fv = exp.hyperparameters.get(clean_key)
        elif source == "res":
            fv = exp.results.get(clean_key)
        else:
            fv = exp.hyperparameters.get(clean_key) or exp.results.get(clean_key)

        if fv is not None:
            values.append(fv.value)
            if field_type is None:
                field_type = fv.field_type
        else:
            values.append(None)

    return values, field_type


def _clean_key(key: str) -> str:
    """Remove hp:/res: prefix for display."""
    if key.startswith("hp:") or key.startswith("res:"):
        return key[4:]
    return key


def _categorize_axis(
    values: list[Any], field_type: FieldType | None
) -> tuple[list[Any], dict | None]:
    """Prepare axis values and layout kwargs for Plotly.

    For STRING/BOOLEAN types: use category axis (unique values as categories).
    For NUMERIC/PERCENTAGE: pass through as-is.

    Returns (plot_values, axis_kwargs_or_None).
    """
    if field_type not in (FieldType.STRING, FieldType.BOOLEAN):
        return values, None

    # Use string values directly with category axis type
    str_vals = [str(v) if v is not None else "" for v in values]
    return str_vals, dict(type="category")


def bar_chart(
    experiment_set: ExperimentSet,
    x_field: str,
    y_field: str,
    color_field: str | None = None,
    title: str = "",
) -> go.Figure:
    """Bar chart comparing a metric across experiments."""
    x_vals, x_ft = _resolve_field(experiment_set, x_field)
    y_vals, _ = _resolve_field(experiment_set, y_field)

    x_plot, x_axis = _categorize_axis(x_vals, x_ft)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=x_plot,
            y=y_vals,
            text=[f"{v:.4f}" if isinstance(v, float) else str(v) for v in y_vals],
            textposition="auto",
        )
    )
    layout_kwargs: dict[str, Any] = dict(
        title=title or f"{_clean_key(y_field)} by {_clean_key(x_field)}",
        xaxis_title=_clean_key(x_field),
        yaxis_title=_clean_key(y_field),
    )
    if x_axis:
        layout_kwargs["xaxis"] = x_axis
    fig.update_layout(**layout_kwargs)
    return fig


def line_chart(
    experiment_set: ExperimentSet,
    x_field: str,
    y_fields: list[str],
    title: str = "",
) -> go.Figure:
    """Line chart with multiple y fields."""
    x_vals, x_ft = _resolve_field(experiment_set, x_field)
    x_plot, x_axis = _categorize_axis(x_vals, x_ft)

    fig = go.Figure()
    for yf in y_fields:
        y_vals, _ = _resolve_field(experiment_set, yf)
        fig.add_trace(
            go.Scatter(
                x=x_plot,
                y=y_vals,
                mode="lines+markers",
                name=_clean_key(yf),
            )
        )
    layout_kwargs: dict[str, Any] = dict(
        title=title or "Metrics over " + _clean_key(x_field),
        xaxis_title=_clean_key(x_field),
        yaxis_title="Value",
    )
    if x_axis:
        layout_kwargs["xaxis"] = x_axis
    fig.update_layout(**layout_kwargs)
    return fig


def scatter_plot(
    experiment_set: ExperimentSet,
    x_field: str,
    y_field: str,
    size_field: str | None = None,
    color_field: str | None = None,
    hover_fields: list[str] | None = None,
    title: str = "",
) -> go.Figure:
    """Scatter plot of two fields."""
    x_vals, x_ft = _resolve_field(experiment_set, x_field)
    y_vals, y_ft = _resolve_field(experiment_set, y_field)
    ids = [exp.id for exp in experiment_set]

    x_plot, x_axis = _categorize_axis(x_vals, x_ft)
    y_plot, y_axis = _categorize_axis(y_vals, y_ft)

    kwargs: dict[str, Any] = dict(
        x=x_plot, y=y_plot, mode="markers", text=ids, textposition="top center"
    )

    if size_field:
        size_vals, _ = _resolve_field(experiment_set, size_field)
        kwargs["marker"] = dict(
            size=[max(5, (v or 0) * 30) for v in size_vals], sizemode="diameter"
        )

    if color_field:
        color_vals, _ = _resolve_field(experiment_set, color_field)
        kwargs["marker"] = kwargs.get("marker", {})
        kwargs["marker"]["color"] = color_vals
        kwargs["marker"]["colorbar"] = dict(title=_clean_key(color_field))
        kwargs["marker"]["showscale"] = True

    if hover_fields:
        hover_texts = []
        for i, exp in enumerate(experiment_set):
            parts = [f"ID: {exp.id}"]
            for hf in hover_fields:
                fv = exp.get_field(hf)
                if fv:
                    parts.append(f"{_clean_key(hf)}: {fv.display_value}")
            hover_texts.append("<br>".join(parts))
        kwargs["hovertext"] = hover_texts
        kwargs["hoverinfo"] = "text"

    fig = go.Figure()
    fig.add_trace(go.Scatter(**kwargs))
    layout_kwargs: dict[str, Any] = dict(
        title=title or f"{_clean_key(y_field)} vs {_clean_key(x_field)}",
        xaxis_title=_clean_key(x_field),
        yaxis_title=_clean_key(y_field),
    )
    if x_axis:
        layout_kwargs["xaxis"] = x_axis
    if y_axis:
        layout_kwargs["yaxis"] = y_axis
    fig.update_layout(**layout_kwargs)
    return fig


def parallel_coordinates(
    experiment_set: ExperimentSet,
    dimensions: list[str],
    color_field: str | None = None,
    title: str = "",
) -> go.Figure:
    """Parallel coordinates chart for multi-dimensional comparison."""
    dim_data = []
    for d in dimensions:
        vals, ft = _resolve_field(experiment_set, d)
        if ft == FieldType.STRING:
            unique = sorted(set(v for v in vals if v is not None))
            mapping = {v: i for i, v in enumerate(unique)}
            numeric_vals = [mapping.get(v, -1) for v in vals]
            dim_data.append(
                dict(
                    label=_clean_key(d),
                    values=numeric_vals,
                    tickvals=list(range(len(unique))),
                    ticktext=unique,
                )
            )
        elif ft == FieldType.BOOLEAN:
            numeric_vals = [1 if v else 0 for v in vals]
            dim_data.append(
                dict(
                    label=_clean_key(d),
                    values=numeric_vals,
                    tickvals=[0, 1],
                    ticktext=["False", "True"],
                )
            )
        else:
            dim_data.append(dict(label=_clean_key(d), values=vals))

    kwargs: dict[str, Any] = dict(dimensions=dim_data)
    if color_field:
        color_vals, _ = _resolve_field(experiment_set, color_field)
        kwargs["line"] = dict(
            color=color_vals,
            colorscale="Viridis",
            showscale=True,
            colorbar=dict(title=_clean_key(color_field)),
        )

    fig = go.Figure(go.Parcoords(**kwargs))
    fig.update_layout(title=title or "Parallel Coordinates")
    return fig


def heatmap_chart(
    experiment_set: ExperimentSet,
    x_field: str,
    y_field: str,
    value_field: str,
    title: str = "",
) -> go.Figure:
    """Heatmap showing value_field for each (x, y) pair."""
    x_vals, _ = _resolve_field(experiment_set, x_field)
    y_vals, _ = _resolve_field(experiment_set, y_field)
    z_vals, _ = _resolve_field(experiment_set, value_field)

    # Pivot into matrix
    x_unique = sorted(set(str(v) for v in x_vals if v is not None))
    y_unique = sorted(set(str(v) for v in y_vals if v is not None))

    z_matrix = [[None] * len(x_unique) for _ in range(len(y_unique))]
    for xv, yv, zv in zip(x_vals, y_vals, z_vals):
        if xv is None or yv is None:
            continue
        xi = x_unique.index(str(xv))
        yi = y_unique.index(str(yv))
        z_matrix[yi][xi] = zv

    fig = go.Figure(
        go.Heatmap(
            x=x_unique,
            y=y_unique,
            z=z_matrix,
            texttemplate="%{z}",
            colorscale="Viridis",
        )
    )
    fig.update_layout(
        title=title
        or f"{_clean_key(value_field)} ({_clean_key(x_field)} x {_clean_key(y_field)})",
        xaxis_title=_clean_key(x_field),
        yaxis_title=_clean_key(y_field),
    )
    return fig


# Map chart type names to builder functions
CHART_BUILDERS = {
    "bar": bar_chart,
    "line": line_chart,
    "scatter": scatter_plot,
    "parallel_coordinates": parallel_coordinates,
    "heatmap": heatmap_chart,
}
