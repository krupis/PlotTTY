# PlotTTY

PlotTTY is a UART-first serial console with configurable value extraction.

The goal is to keep normal firmware `printf()` output useful. PlotTTY shows raw
serial text, lets you send and save common commands, extracts numeric values from
incoming lines, and captures those values in a table.

## Current Foundation

- `plottty/core/` - Qt-independent models, line decoding, extraction rules,
  serial transport, and JSON profiles.
- `plottty/widgets/` - PySide6 widgets for connection settings, console output,
  commands, captured values, and extraction rules.
- `plottty/app/` - application bootstrap and main window wiring.
- `examples/` - starter profile and sample serial log.
- `tests/` - focused tests for parser-oriented core behavior.

The old FCT station routine/execution/database modules were removed because
PlotTTY does not need manufacturing routines, script steps, result persistence,
or YAML validation as its foundation.

Live plotting is intentionally out of the first simplified foundation. The app
currently focuses on receiving serial text and proving that extraction rules can
capture the values users care about.

## Run

Install dependencies into your environment, then run:

```bash
python run_plottty.py
```

## Extraction Rules

The default rule detects common key/value text such as:

```text
Temperature:30.7 C
Humidity:50%
Voltage=3.31 V
```

The **Rules** tab has a simple setup flow for pasting example device output,
detecting values, previewing what will be captured, and applying the selected
values as rules. The advanced rules table is still available for direct control.
Regex rules use the first capture group as the value, such as `temp=([0-9.]+)`.
Delimiter rules capture values by position from separated lines such as
`23.4,51,3.31`. The delimiter is configured on the rule.
