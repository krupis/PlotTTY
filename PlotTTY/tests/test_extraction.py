from plottty.core.extraction import ExtractionEngine
from plottty.core.models import ExtractionRule


def test_auto_key_value_extracts_multiple_values():
    values = ExtractionEngine().extract("Temperature:30.7 C Humidity:50%", timestamp=1.0)

    assert [value.label for value in values] == ["Temperature", "Humidity"]
    assert [value.value for value in values] == [30.7, 50.0]


def test_regex_rule_uses_first_capture_group():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="RPM",
                mode="regex",
                extra_setting=r"speed=(\d+)\s*rpm",
            )
        ]
    )

    values = engine.extract("speed=1250 rpm", timestamp=1.0)

    assert len(values) == 1
    assert values[0].label == "RPM"
    assert values[0].value == 1250
    assert values[0].unit == ""


def test_regex_rule_uses_first_capture_group_with_decimal_value():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Temperature",
                mode="regex",
                extra_setting=r"temp=([-+]?\d+(?:\.\d+)?)",
            )
        ]
    )

    values = engine.extract("temp=23.4 humidity=51", timestamp=1.0)

    assert len(values) == 1
    assert values[0].label == "Temperature"
    assert values[0].value == 23.4


def test_delimiter_column_rule_extracts_selected_position():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Humidity",
                mode="delimiter_column",
                extra_setting="1",
                delimiter=",",
            )
        ]
    )

    values = engine.extract("23.4,51,3.31", timestamp=1.0)

    assert len(values) == 1
    assert values[0].label == "Humidity"
    assert values[0].value == 51


def test_delimiter_column_zero_rule_supplies_delimited_value_timestamps():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Sequence",
                mode="delimiter_column",
                sample_counter=True,
                extra_setting="0",
                delimiter=",",
            ),
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter=",",
            ),
        ]
    )

    values = engine.extract("42,3,3.31", timestamp=1000.0)

    assert [value.label for value in values] == ["Voltage"]
    assert values[0].timestamp == 42.0
    assert values[0].value == 3.31


def test_delimiter_column_zero_rule_uses_host_timestamp_when_not_sample_counter():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Sequence",
                mode="delimiter_column",
                extra_setting="0",
                delimiter=",",
            ),
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter=",",
            ),
        ]
    )

    values = engine.extract("42,3,3.31", timestamp=1000.0)

    assert [value.timestamp for value in values] == [1000.0, 1000.0]


def test_sample_counter_rule_supplies_timestamps_without_being_plotted():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Sequence",
                mode="delimiter_column",
                sample_counter=True,
                extra_setting="0",
                delimiter=",",
            ),
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter=",",
            ),
        ]
    )

    values = engine.extract("42,3,3.31", timestamp=1000.0)

    assert [value.label for value in values] == ["Voltage"]
    assert values[0].timestamp == 42.0


def test_sample_counter_can_use_any_delimited_position():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Sequence",
                mode="delimiter_column",
                sample_counter=True,
                extra_setting="1",
                delimiter=",",
            ),
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter=",",
            ),
        ]
    )

    values = engine.extract("3,42,3.31", timestamp=1000.0)

    assert [value.label for value in values] == ["Voltage"]
    assert values[0].timestamp == 42.0
    assert values[0].value == 3.31


def test_regex_rule_can_supply_sample_counter_timestamp():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Sequence",
                mode="regex",
                sample_counter=True,
                extra_setting=r"seq=(\d+)",
            ),
            ExtractionRule(
                label="Voltage",
                mode="regex",
                extra_setting=r"v=([-+]?\d+(?:\.\d+)?)",
            ),
        ]
    )

    values = engine.extract("seq=42 v=3.31", timestamp=1000.0)

    assert [value.label for value in values] == ["Voltage"]
    assert values[0].timestamp == 42.0
    assert values[0].value == 3.31


def test_delimiter_column_rule_handles_semicolon_and_tab_separators():
    semicolon_engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter=";",
            )
        ]
    )
    tab_engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Voltage",
                mode="delimiter_column",
                extra_setting="2",
                delimiter="\t",
            )
        ]
    )

    semicolon_values = semicolon_engine.extract("23.4;51;3.31", timestamp=1.0)
    tab_values = tab_engine.extract("23.4\t51\t3.31", timestamp=1.0)

    assert semicolon_values[0].value == 3.31
    assert tab_values[0].value == 3.31


def test_delimiter_column_rule_uses_only_configured_delimiter():
    engine = ExtractionEngine(
        [
            ExtractionRule(
                label="Humidity",
                mode="delimiter_column",
                extra_setting="1",
                delimiter=",",
            )
        ]
    )

    values = engine.extract("23.4;51;3.31", timestamp=1.0)

    assert values == []


def test_empty_rule_list_captures_nothing():
    values = ExtractionEngine([]).extract("Temperature:30.7", timestamp=1.0)

    assert values == []
