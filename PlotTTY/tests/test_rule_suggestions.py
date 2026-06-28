from plottty.core.extraction import ExtractionEngine
from plottty.core.rule_suggestions import suggest_rules_from_samples


def test_suggests_key_value_rules_from_samples():
    suggestions = suggest_rules_from_samples("temp=23.4 humidity=51\ntemp=23.6 humidity=52")

    assert [suggestion.label for suggestion in suggestions] == ["temp", "humidity"]
    assert suggestions[0].how_found == 'after "temp"'
    assert "(?P<value>" not in suggestions[0].rule.extra_setting

    values = ExtractionEngine([suggestions[0].rule]).extract("temp=24.1 humidity=55", timestamp=1.0)

    assert len(values) == 1
    assert values[0].label == "temp"
    assert values[0].value == 24.1


def test_suggests_delimiter_column_rules_when_no_key_values_exist():
    suggestions = suggest_rules_from_samples("23.4,51,3.31\n23.6,52,3.30")

    assert [suggestion.label for suggestion in suggestions] == ["Value 1", "Value 2", "Value 3"]
    assert [suggestion.example_value for suggestion in suggestions] == ["23.4", "51", "3.31"]
    assert [suggestion.rule.mode for suggestion in suggestions] == [
        "delimiter_column",
        "delimiter_column",
        "delimiter_column",
    ]
    assert [suggestion.rule.delimiter for suggestion in suggestions] == [",", ",", ","]


def test_suggests_first_number_when_only_one_number_is_visible():
    suggestions = suggest_rules_from_samples("reading is 23.4 C")

    assert len(suggestions) == 1
    assert suggestions[0].label == "Value"
    assert suggestions[0].rule.mode == "first_number"
