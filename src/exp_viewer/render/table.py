"""HTML table generation for experiments."""

from __future__ import annotations

from html import escape
from typing import Any

from ..types import ExperimentSet, FieldType, FieldValue

_FILTER_OPS = {"eq", "ne", "gt", "lt", "gte", "lte", "contains", "in"}


def _apply_filter(
    experiments: ExperimentSet,
    filters: dict[str, tuple[str, Any]],
) -> ExperimentSet:
    """Apply filters to an ExperimentSet.

    filters: {field_name: (operator, value)}
    Supported operators: eq, ne, gt, lt, gte, lte, contains, in
    """

    def matches(exp) -> bool:
        for field_key, (op, target) in filters.items():
            fv = exp.get_field(field_key)
            if fv is None:
                return False
            v = fv.value
            if op == "eq":
                if v != target:
                    return False
            elif op == "ne":
                if v == target:
                    return False
            elif op in ("gt", "lt", "gte", "lte"):
                try:
                    vf = float(v)
                    tf = float(target)
                except (TypeError, ValueError):
                    return False
                if op == "gt" and not (vf > tf):
                    return False
                if op == "lt" and not (vf < tf):
                    return False
                if op == "gte" and not (vf >= tf):
                    return False
                if op == "lte" and not (vf <= tf):
                    return False
            elif op == "contains":
                if str(target).lower() not in str(v).lower():
                    return False
            elif op == "in":
                if v not in target:
                    return False
        return True

    return experiments.filter(matches)


def parse_filter_params(params: dict[str, str]) -> dict[str, tuple[str, Any]]:
    """Parse filter query parameters like {field: 'gt:0.5', field2: 'eq:adam'}."""
    filters: dict[str, tuple[str, Any]] = {}
    for key, val in params.items():
        if ":" in val:
            op, _, target = val.partition(":")
            if op in _FILTER_OPS:
                filters[key] = (op, target)
            else:
                filters[key] = ("eq", val)
        else:
            filters[key] = ("eq", val)
    return filters


def build_table_html(
    experiment_set: ExperimentSet,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    sort_desc: bool = False,
    filters: dict[str, tuple[str, Any]] | None = None,
) -> str:
    """Generate an HTML table from an ExperimentSet.

    Args:
        experiment_set: The experiments to display.
        columns: Field keys to include. None = all hyperparameters + all results.
        sort_by: Field key to sort by.
        sort_desc: Sort descending.
        filters: {field_key: (operator, value)} filters.

    Returns:
        HTML string of the table.
    """
    if filters:
        experiment_set = _apply_filter(experiment_set, filters)
    if sort_by:
        experiment_set = experiment_set.sort_by(sort_by, descending=sort_desc)

    hp_keys = experiment_set.all_hyperparameter_keys
    res_keys = experiment_set.all_result_keys

    if columns is None:
        display_keys = hp_keys + res_keys
    else:
        display_keys = columns

    # Group keys for column grouping
    hp_display = [k for k in display_keys if k in hp_keys]
    res_display = [k for k in display_keys if k in res_keys]

    rows: list[str] = []
    rows.append('<table class="exp-table">')

    # Header
    has_projects = any(exp.project for exp in experiment_set)
    rows.append("<thead><tr>")
    rows.append('<th class="col-select" rowspan="2"><input type="checkbox" id="select-all" title="Select all"></th>')
    rows.append('<th class="col-id" rowspan="2">ID</th>')
    rows.append('<th class="col-name" rowspan="2">Name</th>')
    if has_projects:
        rows.append('<th class="col-project" rowspan="2">Project</th>')
    if hp_display:
        rows.append(f'<th colspan="{len(hp_display)}" class="group-hp">Hyperparameters</th>')
    if res_display:
        rows.append(f'<th colspan="{len(res_display)}" class="group-res">Results</th>')
    rows.append("</tr><tr>")

    for k in hp_display:
        rows.append(
            f'<th class="col-hp" data-sort="{escape(k)}" title="{escape(k)}">{escape(k)}</th>'
        )
    for k in res_display:
        rows.append(
            f'<th class="col-res" data-sort="{escape(k)}" title="{escape(k)}">{escape(k)}</th>'
        )
    rows.append("</tr></thead>")

    # Body
    rows.append("<tbody>")
    for exp in experiment_set:
        rows.append(f'<tr data-id="{escape(exp.id)}">')
        rows.append(f'<td class="col-select"><input type="checkbox" class="exp-check" value="{escape(exp.id)}"></td>')
        rows.append(f'<td class="col-id"><a href="/experiments/{escape(exp.id)}">{escape(exp.id)}</a></td>')
        rows.append(f'<td class="col-name">{escape(exp.name)}</td>')
        if has_projects:
            rows.append(f'<td class="col-project">{escape(exp.project)}</td>')
        for k in hp_display:
            fv = exp.hyperparameters.get(k)
            rows.append(f"<td>{_render_cell(fv)}</td>")
        for k in res_display:
            fv = exp.results.get(k)
            rows.append(f"<td>{_render_cell(fv)}</td>")
        rows.append("</tr>")
    rows.append("</tbody></table>")

    return "\n".join(rows)


def _render_cell(fv: FieldValue | None) -> str:
    """Render a single table cell."""
    if fv is None:
        return '<span class="missing">—</span>'
    if fv.value is None:
        return '<span class="missing">—</span>'
    if isinstance(fv.value, float) and fv.value != fv.value:  # NaN check
        return '<span class="nan">NaN</span>'
    if fv.field_type == FieldType.BOOLEAN:
        cls = "bool-true" if fv.value else "bool-false"
        return f'<span class="{cls}">{fv.display_value}</span>'
    if fv.field_type == FieldType.PERCENTAGE:
        return f'<span class="pct">{escape(fv.display_value)}</span>'
    if fv.field_type == FieldType.NUMERIC:
        return f'<span class="num">{escape(fv.display_value)}</span>'
    return escape(fv.display_value)
