"""Static HTML export for experiment data."""

from __future__ import annotations

from html import escape
from pathlib import Path

import plotly.graph_objects as go

from ..types import ExperimentSet
from .charts import CHART_BUILDERS, bar_chart, parallel_coordinates, scatter_plot, box_plot, violin_plot, scatter_3d, pie_chart, histogram_chart, contour_chart, radar_chart, area_chart, funnel_chart
from .table import build_table_html


_PLOTLY_CDN = '<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>'

_STYLE = """\
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
       background: #f8f9fa; color: #212529; padding: 1rem; }
h1 { margin-bottom: 0.5rem; font-size: 1.5rem; }
h2 { margin: 1.5rem 0 0.5rem; font-size: 1.2rem; color: #495057; }
.tabs { display: flex; gap: 0; border-bottom: 2px solid #dee2e6; margin-bottom: 1rem; }
.tab { padding: 0.5rem 1rem; cursor: pointer; border: 1px solid transparent;
       border-bottom: none; background: #fff; font-size: 0.9rem; }
.tab.active { border-color: #dee2e6 #dee2e6 #fff; border-top: 2px solid #0d6efd;
              font-weight: 600; color: #0d6efd; }
.tab-content { display: none; background: #fff; padding: 1rem; border: 1px solid #dee2e6;
               border-top: none; }
.tab-content.active { display: block; }
.chart-container { margin: 1rem 0; }
table.exp-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
table.exp-table th, table.exp-table td { padding: 0.4rem 0.6rem; border: 1px solid #dee2e6; }
table.exp-table th { background: #e9ecef; position: sticky; top: 0; cursor: pointer;
                     user-select: none; white-space: nowrap; }
table.exp-table tbody tr:hover { background: #f1f3f5; }
.group-hp { background: #dbeafe !important; }
.group-res { background: #dcfce7 !important; }
.col-id { font-weight: 600; max-width: 120px; overflow: hidden; text-overflow: ellipsis; }
.num { font-variant-numeric: tabular-nums; text-align: right; }
.pct { font-variant-numeric: tabular-nums; text-align: right; color: #059669; }
.bool-true { color: #16a34a; font-weight: 600; }
.bool-false { color: #dc2626; }
.missing { color: #adb5bd; }
.nan { color: #d97706; font-style: italic; }
</style>
"""

_TAB_SCRIPT = """\
<script>
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(tabId).classList.add('active');
  document.querySelector('[data-tab="'+tabId+'"]').classList.add('active');
}
</script>
"""


def _build_default_charts(exp_set: ExperimentSet) -> list[tuple[str, go.Figure]]:
    """Build a default set of charts for export."""
    charts: list[tuple[str, go.Figure]] = []
    res_keys = exp_set.all_result_keys
    hp_keys = exp_set.all_hyperparameter_keys

    if res_keys:
        # Bar chart of first result by experiment id
        charts.append(
            (
                f"Results Overview",
                bar_chart(exp_set, "id", res_keys[0]),
            )
        )

    if len(res_keys) >= 2:
        charts.append(
            (
                f"{res_keys[0]} vs {res_keys[1]}",
                scatter_plot(exp_set, res_keys[0], res_keys[1], hover_fields=hp_keys[:3]),
            )
        )

    if hp_keys and res_keys:
        all_dims = hp_keys[:6] + res_keys[:3]
        charts.append(
            (
                "Parameter Comparison",
                parallel_coordinates(exp_set, all_dims, color_field=res_keys[0]),
            )
        )

    return charts


def export_html(
    experiment_set: ExperimentSet,
    output_path: Path | str,
    title: str = "Experiment Viewer",
    include_charts: bool = True,
    chart_configs: list[dict] | None = None,
) -> Path:
    """Generate a self-contained HTML file with embedded Plotly charts.

    Args:
        experiment_set: The experiments to export.
        output_path: Output file path.
        title: Page title.
        include_charts: Whether to include charts.
        chart_configs: Optional list of chart configs:
            [{"type": "scatter", "x": "field1", "y": "field2"}, ...]

    Returns:
        Path to the generated file.
    """
    output_path = Path(output_path)

    # Build charts
    figures: list[tuple[str, go.Figure]] = []
    if include_charts:
        if chart_configs:
            for cfg in chart_configs:
                chart_type = cfg.get("type", "bar")
                builder = CHART_BUILDERS.get(chart_type)
                if builder is None:
                    continue
                kwargs = {k: v for k, v in cfg.items() if k != "type"}
                try:
                    fig = builder(experiment_set, **kwargs)
                    label = cfg.get("title", chart_type.title() + " Chart")
                    figures.append((label, fig))
                except Exception:
                    pass
        else:
            figures = _build_default_charts(experiment_set)

    # Build table
    table_html = build_table_html(experiment_set)

    # Assemble page
    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'><head>",
        f"<meta charset='utf-8'><title>{escape(title)}</title>",
        _PLOTLY_CDN,
        _STYLE,
        "</head><body>",
        f"<h1>{escape(title)}</h1>",
        f"<p>Experiments: {len(experiment_set)}</p>",
    ]

    # Tabs
    if figures:
        parts.append('<div class="tabs">')
        parts.append('<div class="tab active" data-tab="tab-table" onclick="switchTab(\'tab-table\')">Table</div>')
        for i, (label, _) in enumerate(figures):
            tab_id = f"tab-chart-{i}"
            safe_label = escape(label)
            parts.append(
                f'<div class="tab" data-tab="{tab_id}" onclick="switchTab(\'{tab_id}\')">'
                f'{safe_label}</div>'
            )
        parts.append("</div>")

        # Table tab
        parts.append('<div id="tab-table" class="tab-content active">')
        parts.append(table_html)
        parts.append("</div>")

        # Chart tabs
        for i, (label, fig) in enumerate(figures):
            tab_id = f"tab-chart-{i}"
            parts.append(f'<div id="{tab_id}" class="tab-content">')
            parts.append(f'<div class="chart-container" id="chart-{i}"></div>')
            parts.append("</div>")

        parts.append(_TAB_SCRIPT)

        # Chart initialization scripts
        for i, (_, fig) in enumerate(figures):
            json_str = fig.to_json()
            parts.append(
                f'<script>Plotly.newPlot("chart-{i}", {json_str});</script>'
            )
    else:
        parts.append(table_html)

    parts.append("</body></html>")

    output_path.write_text("\n".join(parts), encoding="utf-8")
    return output_path


def comparison_html(
    experiment_set: ExperimentSet,
    selected_ids: list[str] | None = None,
    highlight_field: str | None = None,
) -> str:
    """Generate a comparison page fragment as HTML.

    Includes side-by-side table, parallel coordinates, and scatter matrix.
    """
    if selected_ids:
        id_set = set(selected_ids)
        exp_set = experiment_set.filter(lambda e: e.id in id_set)
    else:
        exp_set = experiment_set

    parts: list[str] = []
    parts.append(f"<h2>Comparison of {len(exp_set)} experiments</h2>")

    # Table
    parts.append(build_table_html(exp_set))

    # Parallel coordinates
    hp_keys = exp_set.all_hyperparameter_keys
    res_keys = exp_set.all_result_keys
    if hp_keys or res_keys:
        dims = hp_keys[:8] + res_keys[:4]
        fig = parallel_coordinates(
            exp_set, dims, color_field=highlight_field or (res_keys[0] if res_keys else None)
        )
        parts.append('<div class="chart-container">')
        parts.append(fig.to_html(full_html=False, include_plotlyjs=False))
        parts.append("</div>")

    # Scatter of first two result keys
    if len(res_keys) >= 2:
        fig = scatter_plot(
            exp_set, res_keys[0], res_keys[1], hover_fields=hp_keys[:3],
            color_field=highlight_field,
        )
        parts.append('<div class="chart-container">')
        parts.append(fig.to_html(full_html=False, include_plotlyjs=False))
        parts.append("</div>")

    return "\n".join(parts)
