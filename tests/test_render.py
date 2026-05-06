"""Tests for exp_viewer render module."""

from pathlib import Path

from exp_viewer.discovery import scan_directory
from exp_viewer.render.charts import (
    CHART_BUILDERS,
    area_chart,
    bar_chart,
    box_plot,
    contour_chart,
    funnel_chart,
    histogram_chart,
    parallel_coordinates,
    pie_chart,
    radar_chart,
    scatter_3d,
    scatter_plot,
    violin_plot,
)
from exp_viewer.render.export import export_html
from exp_viewer.render.table import build_table_html, parse_filter_params
from exp_viewer.types import ExperimentSet

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixtures():
    return scan_directory(FIXTURES)


class TestTable:
    def test_basic_table(self):
        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es)
        assert "<table" in html
        assert "exp_run1" in html
        assert "exp_run2" in html
        assert "exp_large_lr" in html

    def test_sorted_table(self):
        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es, sort_by="accuracy", sort_desc=True)
        assert "<table" in html

    def test_filtered_table(self):
        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es, filters={"accuracy": ("gt", "0.9")})
        assert "exp_run1" in html
        assert "exp_large_lr" in html
        assert "exp_run2" not in html

    def test_parse_filter_params(self):
        params = {"accuracy": "gt:0.9", "optimizer": "eq:adam"}
        filters = parse_filter_params(params)
        assert filters == {"accuracy": ("gt", "0.9"), "optimizer": ("eq", "adam")}


class TestCharts:
    def test_bar_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = bar_chart(es, "id", "accuracy")
        assert fig is not None
        assert "accuracy" in fig.to_json()

    def test_bar_chart_stacked(self):
        es = ExperimentSet(_load_fixtures())
        fig = bar_chart(es, "id", "accuracy", color_field="optimizer",
                        group_mode="stacked")
        assert fig is not None
        layout = fig.layout
        assert layout.barmode == "stack"

    def test_scatter_plot(self):
        es = ExperimentSet(_load_fixtures())
        fig = scatter_plot(es, "learning_rate", "accuracy")
        assert fig is not None

    def test_parallel_coordinates(self):
        es = ExperimentSet(_load_fixtures())
        fig = parallel_coordinates(es, ["learning_rate", "batch_size", "accuracy"])
        assert fig is not None

    def test_box_plot(self):
        es = ExperimentSet(_load_fixtures())
        fig = box_plot(es, y_field="accuracy")
        assert fig is not None
        assert len(fig.data) >= 1

    def test_box_plot_grouped(self):
        es = ExperimentSet(_load_fixtures())
        fig = box_plot(es, y_field="accuracy", group_field="optimizer")
        assert fig is not None
        # Should have one trace per unique optimizer value
        assert len(fig.data) >= 2

    def test_violin_plot(self):
        es = ExperimentSet(_load_fixtures())
        fig = violin_plot(es, y_field="accuracy")
        assert fig is not None

    def test_violin_grouped(self):
        es = ExperimentSet(_load_fixtures())
        fig = violin_plot(es, y_field="accuracy", group_field="optimizer")
        assert fig is not None
        assert len(fig.data) >= 2

    def test_scatter_3d(self):
        es = ExperimentSet(_load_fixtures())
        fig = scatter_3d(es, "learning_rate", "batch_size", "accuracy")
        assert fig is not None
        assert len(fig.data) == 1

    def test_pie_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = pie_chart(es, values_field="accuracy")
        assert fig is not None
        assert len(fig.data) == 1

    def test_histogram_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = histogram_chart(es, x_field="accuracy")
        assert fig is not None

    def test_histogram_stacked(self):
        es = ExperimentSet(_load_fixtures())
        fig = histogram_chart(es, x_field="accuracy", color_field="optimizer",
                              group_mode="stack")
        assert fig is not None
        assert fig.layout.barmode == "stack"

    def test_contour_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = contour_chart(es, "learning_rate", "batch_size", "accuracy")
        assert fig is not None

    def test_radar_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = radar_chart(es, dimensions=["accuracy", "f1_score", "loss"])
        assert fig is not None
        assert len(fig.data) == len(es)

    def test_area_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = area_chart(es, x_field="id", y_fields=["accuracy", "f1_score"])
        assert fig is not None
        assert len(fig.data) == 2

    def test_funnel_chart(self):
        es = ExperimentSet(_load_fixtures())
        fig = funnel_chart(es, values_field="accuracy")
        assert fig is not None
        assert len(fig.data) == 1

    def test_chart_builders_registry(self):
        """All 14 chart types are registered."""
        expected = {"bar", "line", "scatter", "parallel_coordinates", "heatmap",
                    "box", "violin", "scatter_3d", "pie", "histogram",
                    "contour", "radar", "area", "funnel"}
        assert set(CHART_BUILDERS.keys()) == expected


class TestExport:
    def test_export_html(self, tmp_path):
        es = ExperimentSet(_load_fixtures())
        output = export_html(es, tmp_path / "test.html")
        assert output.exists()
        content = output.read_text()
        assert "plotly" in content.lower()
        assert "exp_run1" in content
