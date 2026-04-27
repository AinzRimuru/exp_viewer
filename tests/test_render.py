"""Tests for exp_viewer render module."""

from pathlib import Path

from exp_viewer.discovery import scan_directory
from exp_viewer.render.table import build_table_html, parse_filter_params
from exp_viewer.render.charts import bar_chart, scatter_plot, parallel_coordinates
from exp_viewer.render.export import export_html

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixtures():
    return scan_directory(FIXTURES)


class TestTable:
    def test_basic_table(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es)
        assert "<table" in html
        assert "exp_run1" in html
        assert "exp_run2" in html
        assert "exp_large_lr" in html

    def test_sorted_table(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es, sort_by="accuracy", sort_desc=True)
        assert "<table" in html

    def test_filtered_table(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        html = build_table_html(es, filters={"accuracy": ("gt", "0.9")})
        # Only run1 (0.95) and run3 (0.97) should pass
        assert "exp_run1" in html
        assert "exp_large_lr" in html
        assert "exp_run2" not in html

    def test_parse_filter_params(self):
        params = {"accuracy": "gt:0.9", "optimizer": "eq:adam"}
        filters = parse_filter_params(params)
        assert filters == {"accuracy": ("gt", "0.9"), "optimizer": ("eq", "adam")}


class TestCharts:
    def test_bar_chart(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        fig = bar_chart(es, "id", "accuracy")
        assert fig is not None
        json_str = fig.to_json()
        assert "accuracy" in json_str

    def test_scatter_plot(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        fig = scatter_plot(es, "learning_rate", "accuracy")
        assert fig is not None

    def test_parallel_coordinates(self):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        fig = parallel_coordinates(es, ["learning_rate", "batch_size", "accuracy"])
        assert fig is not None


class TestExport:
    def test_export_html(self, tmp_path):
        from exp_viewer.types import ExperimentSet

        es = ExperimentSet(_load_fixtures())
        output = export_html(es, tmp_path / "test.html")
        assert output.exists()
        content = output.read_text()
        assert "plotly" in content.lower()
        assert "exp_run1" in content
