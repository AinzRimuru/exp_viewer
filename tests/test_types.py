"""Tests for exp_viewer types module."""

from exp_viewer.types import FieldType, FieldValue, Experiment, ExperimentSet


class TestFieldType:
    def test_narrowest_common_single(self):
        assert FieldType.narrowest_common(FieldType.NUMERIC) == FieldType.NUMERIC

    def test_narrowest_common_same(self):
        assert FieldType.narrowest_common(FieldType.NUMERIC, FieldType.NUMERIC) == FieldType.NUMERIC

    def test_narrowest_common_bool_numeric(self):
        """BOOLEAN + NUMERIC -> NUMERIC"""
        assert FieldType.narrowest_common(FieldType.BOOLEAN, FieldType.NUMERIC) == FieldType.NUMERIC

    def test_narrowest_common_bool_string(self):
        """BOOLEAN + STRING -> STRING"""
        assert FieldType.narrowest_common(FieldType.BOOLEAN, FieldType.STRING) == FieldType.STRING

    def test_narrowest_common_numeric_percentage(self):
        """NUMERIC + PERCENTAGE -> PERCENTAGE"""
        assert FieldType.narrowest_common(FieldType.NUMERIC, FieldType.PERCENTAGE) == FieldType.PERCENTAGE

    def test_narrowest_common_all(self):
        """All types -> STRING"""
        assert FieldType.narrowest_common(
            FieldType.BOOLEAN, FieldType.NUMERIC, FieldType.PERCENTAGE, FieldType.STRING
        ) == FieldType.STRING

    def test_narrowest_common_empty(self):
        assert FieldType.narrowest_common() == FieldType.STRING
    def test_numeric_display(self):
        fv = FieldValue(value=0.032, field_type=FieldType.NUMERIC)
        assert fv.display_value == "0.0320"
        assert fv.numeric_value == 0.032
        assert fv.sort_value == 0.032

    def test_numeric_int_display(self):
        fv = FieldValue(value=42, field_type=FieldType.NUMERIC)
        assert fv.display_value == "42"
        assert fv.numeric_value == 42.0

    def test_percentage_display(self):
        fv = FieldValue(value=0.95, field_type=FieldType.PERCENTAGE)
        assert fv.display_value == "95.00%"
        assert fv.numeric_value == 0.95

    def test_percentage_above_one(self):
        fv = FieldValue(value=95.0, field_type=FieldType.PERCENTAGE)
        assert fv.display_value == "95.0%"
        assert fv.numeric_value == 0.95

    def test_boolean_display(self):
        fv = FieldValue(value=True, field_type=FieldType.BOOLEAN)
        assert fv.display_value == "True"
        assert fv.numeric_value == 1.0

        fv2 = FieldValue(value=False, field_type=FieldType.BOOLEAN)
        assert fv2.display_value == "False"
        assert fv2.numeric_value == 0.0

    def test_string_display(self):
        fv = FieldValue(value="adam", field_type=FieldType.STRING)
        assert fv.display_value == "adam"
        assert fv.numeric_value is None


class TestExperiment:
    def _make_exp(self, id="test", lr=0.001, acc=0.95):
        return Experiment(
            id=id,
            name=id,
            hyperparameters={"learning_rate": FieldValue(lr, FieldType.NUMERIC)},
            results={"accuracy": FieldValue(acc, FieldType.PERCENTAGE)},
        )

    def test_get_field(self):
        exp = self._make_exp()
        assert exp.get_field("learning_rate") is not None
        assert exp.get_field("accuracy") is not None
        assert exp.get_field("nonexistent") is None

    def test_get_field_hp_priority(self):
        exp = self._make_exp()
        # hyperparameters checked first
        fv = exp.get_field("learning_rate")
        assert fv.field_type == FieldType.NUMERIC


class TestExperimentSet:
    def _make_set(self):
        exps = [
            Experiment(
                id="a",
                name="A",
                hyperparameters={
                    "lr": FieldValue(0.1, FieldType.NUMERIC),
                    "opt": FieldValue("sgd", FieldType.STRING),
                },
                results={
                    "acc": FieldValue(0.8, FieldType.PERCENTAGE),
                },
            ),
            Experiment(
                id="b",
                name="B",
                hyperparameters={
                    "lr": FieldValue(0.01, FieldType.NUMERIC),
                    "opt": FieldValue("adam", FieldType.STRING),
                },
                results={
                    "acc": FieldValue(0.95, FieldType.PERCENTAGE),
                },
            ),
        ]
        return ExperimentSet(exps)

    def test_keys(self):
        es = self._make_set()
        assert es.all_hyperparameter_keys == ["lr", "opt"]
        assert es.all_result_keys == ["acc"]

    def test_sort_ascending(self):
        es = self._make_set()
        sorted_es = es.sort_by("lr")
        assert [e.id for e in sorted_es] == ["b", "a"]

    def test_sort_descending(self):
        es = self._make_set()
        sorted_es = es.sort_by("acc", descending=True)
        assert [e.id for e in sorted_es] == ["b", "a"]

    def test_filter(self):
        es = self._make_set()
        filtered = es.filter(lambda e: e.hyperparameters["lr"].value < 0.05)
        assert len(filtered) == 1
        assert filtered.experiments[0].id == "b"

    def test_to_dataframe(self):
        es = self._make_set()
        df = es.to_dataframe()
        assert "id" in df
        assert "hp:lr" in df
        assert "res:acc" in df
        assert len(df["id"]) == 2

    def test_len(self):
        es = self._make_set()
        assert len(es) == 2
