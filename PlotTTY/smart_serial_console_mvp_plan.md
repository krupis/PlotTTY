# Smart Serial Console MVP Development Plan

## 1. Product Vision

Build a **UART-first serial console with smart plotting**.

The core idea is simple:

> A user can keep their existing `printf()` debug output, and the app can extract numeric values from it for live plotting.

Example firmware output:

```text
Temperature:30.7°
Humidity:50%
Voltage=3.31 V
```

The app should detect or allow the user to configure these as plot signals:

```text
Temperature → 30.7
Humidity → 50
Voltage → 3.31
```

The MVP should feel like a better version of Arduino Serial Monitor, Arduino Serial Plotter, Termite, PuTTY, and simple custom Python scripts.

---

## 2. MVP Goal

The first public version should let a user:

1. Connect to a UART device.
2. View raw serial output.
3. Send text commands.
4. Automatically detect simple numeric signals from text.
5. Manually configure extraction rules.
6. Plot extracted values live.
7. Save logs.
8. Export plotted data to CSV.
9. Save and reload project/profile settings.
10. Optionally use the same parser/plotter with basic TCP and UDP inputs.

---

## 3. Non-Goals for MVP

Do **not** include these in the first MVP:

- Protobuf support
- Binary protocol decoding
- CAN bus
- BLE
- RTT/SWO
- Modbus
- Firmware flashing
- Device database
- Plugin marketplace
- Cloud sync
- Complex scripting engine
- Multi-device dashboards
- Custom embedded hardware

These can be added later after the simple UART + plotting workflow is solid.

---

## 4. Target User

Primary users:

- Embedded firmware developers
- Electronics hobbyists
- Arduino/ESP32/STM32/RP2040 users
- Test engineers debugging UART logs
- Developers currently using simple serial terminals and custom Python scripts

Typical pain points:

- Arduino Serial Plotter is too limited.
- Generic serial terminals cannot plot values.
- Existing plotting tools often require strict CSV or a specific format.
- Engineers already have debug prints and do not want to rewrite firmware output.
- Custom scripts are quick to write but annoying to maintain and share.

---

## 5. Core User Story

```text
As an embedded developer,
I want to connect to my board over UART,
see my existing debug output,
select numeric values from that output,
and plot them live without changing my firmware protocol.
```

Example:

Firmware prints:

```text
Temperature:30.7°
Humidity:50%
```

User opens the app, connects to UART, and sees:

```text
Detected signals:
[x] Temperature    30.7 °C
[x] Humidity       50 %
```

Then the user clicks **Plot Selected Signals** and sees live graphs.

---

## 6. Recommended Tech Stack

Recommended:

```text
Python 3.11+
PySide6 or PyQt6
pyserial
pyqtgraph
numpy
pydantic
platformdirs
pytest
ruff
```

Optional later:

```text
orjson
qasync
python-can
bleak
construct
protobuf
nuitka
pyinstaller
```

### PyQt vs PySide

If this is mainly an open-source project and you are already comfortable with PyQt, PyQt6 is fine.

If you want easier commercial flexibility later, consider PySide6 because of Qt's official LGPL/commercial distribution model.

---

## 7. High-Level Architecture

Keep these concepts separate:

```text
Transport ≠ Parser ≠ Signal ≠ Plot
```

### Data Flow

```text
UART / TCP / UDP
    ↓
TransportReader
    ↓ bytes
LineDecoder
    ↓ text lines
ConsoleModel
    ↓ raw output display
ExtractionEngine
    ↓ SignalSample(name, value, timestamp)
SignalStore
    ↓
PlotWidget
```

### Main Components

```text
Transport layer
    SerialTransport
    TcpClientTransport
    UdpListenerTransport

Decoder layer
    ByteBuffer
    LineDecoder

Parser/extraction layer
    AutoKeyValueExtractor
    FirstNumberExtractor
    RegexExtractor
    CsvExtractor

Data layer
    RawLine
    SignalSample
    SignalBuffer
    SessionRecorder
    ProfileManager

UI layer
    MainWindow
    ConnectionPanel
    ConsoleWidget
    SignalListWidget
    PlotWidget
    RuleEditorDialog
    ReplayControls
```

---

## 8. Suggested Repository Structure

```text
smartserial/
  pyproject.toml
  README.md
  LICENSE
  .gitignore

  smartserial/
    __init__.py

    app/
      main.py
      main_window.py

    core/
      transport.py
      serial_transport.py
      tcp_transport.py
      udp_transport.py
      line_decoder.py
      extraction.py
      signal_store.py
      recording.py
      profiles.py

    widgets/
      connection_panel.py
      console_widget.py
      signal_list_widget.py
      plot_widget.py
      extraction_rules_widget.py
      rule_editor_dialog.py

    examples/
      arduino_temperature_humidity.ino
      stm32_printf_example.c
      sample_log.txt
      sample_profile.json

    tests/
      test_line_decoder.py
      test_extraction.py
      test_profiles.py
```

---

## 9. Core Data Models

Use small, testable data classes.

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class RawLine:
    timestamp: float
    source: str
    text: str


@dataclass
class SignalSample:
    timestamp: float
    name: str
    value: float
    unit: Optional[str] = None
    raw_line: Optional[str] = None


@dataclass
class ExtractionRule:
    name: str
    enabled: bool
    mode: str  # "auto_key_value", "first_number", "regex", "csv"
    contains: Optional[str] = None
    pattern: Optional[str] = None
    value_group: Optional[str] = "value"
    channel_group: Optional[str] = None
    unit: Optional[str] = None
```

---

## 10. Extraction Strategy

The MVP should support extraction from normal text output, without requiring a strict firmware protocol.

### Level 1: Auto Key-Value Detection

Default parser should detect common formats:

```text
Temperature:30.7°
Humidity:50%
Voltage = 3.31 V
Motor RPM: 1240 rpm
ADC value = 1832
```

Recommended generic regex:

```regex
^(?P<name>[A-Za-z_][A-Za-z0-9_ .-]*)\s*[:=]\s*(?P<value>[-+]?\d+(?:[.,]\d+)?)
```

Expected output:

```text
Temperature → 30.7
Humidity → 50
Voltage → 3.31
Motor RPM → 1240
ADC value → 1832
```

### Level 2: First Number in Matching Line

Useful for lines like:

```text
Temperature is now 30.7 degrees
Humidity is currently around 50 percent
```

Rule example:

```text
Signal name: Temperature
Line contains: Temperature
Extract: first number
Unit: °C
```

### Level 3: Regex Rule

Useful for messy custom lines:

```text
T_air=[30.7C], RH=[50%]
```

Regex:

```regex
T_air=\[(?P<value>[-+]?\d+(?:\.\d+)?)C\]
```

### Level 4: CSV Rule

Useful for Arduino-plotter-style output:

```text
30.7,50,3.31
```

Configuration:

```text
Column 0: Temperature
Column 1: Humidity
Column 2: Voltage
```

### Level 5: JSON Rule

Optional after MVP, but useful:

```json
{"temperature":30.7,"humidity":50,"voltage":3.31}
```

---

## 11. UI Layout

Suggested first layout:

```text
+----------------------------------------------------------------+
| Toolbar: Connect | Record | Replay | Save Profile | Settings   |
+-------------------------+--------------------------------------+
| Connection Panel        | Plot Area                            |
| Port, baud, connect     |                                      |
+-------------------------+                                      |
| Raw Console             |                                      |
|                         |                                      |
|                         |                                      |
+-------------------------+--------------------------------------+
| Detected Signals        | Extraction Rules / Latest Values      |
+-------------------------+--------------------------------------+
```

Alternative:

- Use `QSplitter` so users can resize console and plot sections.
- Put detected signals in a dockable panel.
- Put extraction rules in another dockable panel.
- Keep the raw console always visible.

---

## 12. MVP Phases

## Phase 0 — Project Setup

### Goal

Create a clean base application.

### Tasks

- Create Git repository.
- Add `pyproject.toml`.
- Add formatter/linter setup with `ruff`.
- Add `pytest`.
- Add basic package structure.
- Add empty `MainWindow`.
- Add GitHub Actions for tests.

### Acceptance Criteria

Running this opens an empty app window:

```bash
python -m smartserial.app.main
```

---

## Phase 1 — UART Connection and Raw Console

### Goal

Build a usable basic serial terminal.

### Features

Connection panel:

```text
Port dropdown
Refresh ports
Baud rate selector
Data bits
Parity
Stop bits
Connect / Disconnect
```

Console:

```text
Raw received text
Optional timestamps
Auto-scroll toggle
Clear console
Save raw log
Send text input
Line ending selector: none / LF / CR / CRLF
```

### Implementation Notes

- Use `pyserial` for UART.
- Read UART data in a worker thread.
- Never block the GUI thread.
- Use Qt signals to pass received bytes into the main thread.
- Start with `QPlainTextEdit` for the console.

### Acceptance Criteria

- User can connect to a serial port.
- User can see incoming text.
- User can send text commands.
- App does not freeze while data is coming in.

---

## Phase 2 — Line Decoder and Logging

### Goal

Turn incoming byte streams into timestamped lines.

### Features

Line splitting modes:

```text
LF
CRLF
CR
Auto-detect
```

Each received line becomes:

```python
RawLine(timestamp, source, text)
```

Add log export:

```text
Plain text log
CSV log: timestamp,source,text
```

### Acceptance Criteria

Given incoming data:

```text
Temperature:30.7
Humidity:50
```

The app stores:

```csv
timestamp,source,text
0.001,uart,Temperature:30.7
0.205,uart,Humidity:50
```

---

## Phase 3 — Auto Signal Extraction

### Goal

Create the first “magic moment”.

### Features

- Add auto key-value parser.
- Detect numeric signals automatically.
- Show detected signals in a sidebar.
- Show latest value per signal.
- Allow user to enable/disable signals.

### Example

Input:

```text
Temperature:30.7
Humidity:50
Voltage=3.31
```

Detected signals:

```text
Temperature    30.7
Humidity       50
Voltage        3.31
```

### Acceptance Criteria

- Without manual configuration, common key-value lines become named signals.
- The latest value is visible in the UI.
- Signal detection does not interfere with the raw console.

---

## Phase 4 — Live Plotting

### Goal

Make plotting significantly better than Arduino Serial Plotter.

### Features

- Multiple named signals on one plot.
- Toggle signal visibility.
- Rolling time window:
  - 10 seconds
  - 30 seconds
  - 60 seconds
  - Unlimited
- Pause/resume plot updates.
- Clear plot.
- Show latest value.
- Export plotted samples to CSV.

### Implementation Notes

Use `pyqtgraph`.

Store values in buffers:

```python
from collections import deque

class SignalBuffer:
    def __init__(self, max_samples: int = 10000):
        self.timestamps = deque(maxlen=max_samples)
        self.values = deque(maxlen=max_samples)
```

### Acceptance Criteria

Input:

```text
Temperature:30.7
Humidity:50
Temperature:30.8
Humidity:51
Temperature:31.0
Humidity:52
```

Creates live curves for:

```text
Temperature
Humidity
```

---

## Phase 5 — Manual Extraction Rules

### Goal

Allow users to handle custom text output.

### Rule Types

#### First Number Rule

```text
Signal name: Temperature
Line contains: Temperature
Extract: first number
Unit: °C
```

Works with:

```text
Temperature is now 30.7 degrees
```

#### Regex Rule

```text
Signal name: Air Temperature
Pattern: T_air=\[(?P<value>[-+]?\d+(?:\.\d+)?)C\]
Value group: value
Unit: °C
```

Works with:

```text
T_air=[30.7C], RH=[50%]
```

#### CSV Rule

```text
Column 0: Temperature
Column 1: Humidity
Column 2: Voltage
```

Works with:

```text
30.7,50,3.31
```

### Rule Test UI

The rule editor should include:

```text
Sample input line
Detected value preview
Validation result
```

Example:

```text
Sample line:
Temperature:30.7°

Result:
Temperature = 30.7 °C
```

### Acceptance Criteria

- User can add a manual extraction rule.
- User can test the rule before saving.
- Rule output appears in detected signals.
- Rule output can be plotted.

---

## Phase 6 — Profiles and Settings

### Goal

Users can save and reuse their setup.

### Profile Should Store

```text
Connection settings
Extraction rules
Enabled plot signals
Plot window length
Console settings
Line ending settings
```

Example profile:

```json
{
  "name": "STM32 Sensor Board",
  "transport": {
    "type": "serial",
    "port": "COM5",
    "baudrate": 115200
  },
  "rules": [
    {
      "name": "Temperature",
      "enabled": true,
      "mode": "first_number",
      "contains": "Temperature",
      "unit": "°C"
    },
    {
      "name": "Humidity",
      "enabled": true,
      "mode": "first_number",
      "contains": "Humidity",
      "unit": "%"
    }
  ]
}
```

### Acceptance Criteria

- User can save a profile.
- User can load a profile.
- Extraction rules and connection settings are restored.

---

## Phase 7 — Session Recording and Replay

### Goal

Make debugging, demos, and bug reports easier.

### Recording Format

Use line-delimited JSON for replay sessions:

```json
{"t":0.000,"source":"uart","data":"Temperature:30.7\n"}
{"t":0.205,"source":"uart","data":"Humidity:50\n"}
```

### Replay Pipeline

Replay should feed the normal app pipeline:

```text
ReplayTransport
    ↓
LineDecoder
    ↓
Console
    ↓
ExtractionEngine
    ↓
Plot
```

### Features

```text
Start recording
Stop recording
Save session
Open session
Replay at original speed
Replay faster/slower later
```

### Acceptance Criteria

- User can record a serial session.
- User can replay it without hardware connected.
- Console and plots behave the same during replay.

---

## Phase 8 — TCP and UDP Support

### Goal

Support basic network-based device logs while keeping UART as the main focus.

### Transport Interface

```python
class Transport:
    def open(self) -> None:
        ...

    def close(self) -> None:
        ...

    def write(self, data: bytes) -> None:
        ...
```

### TCP MVP

```text
TCP client mode
Host
Port
Connect/disconnect
Send text
Receive text
```

### UDP MVP

```text
UDP listener
Listen port
Receive datagrams
Optional send-to host/port
```

### Acceptance Criteria

- The same console, parser, and plotter work with UART.
- The same console, parser, and plotter work with TCP.
- The same console, parser, and plotter work with UDP.

---

## Phase 9 — Packaging and Release

### Goal

Make the app easy to try.

### Tasks

- Create README.
- Add screenshots.
- Add short demo GIF/video.
- Add example firmware output.
- Add example profiles.
- Package Windows executable.
- Package Linux AppImage or simple Python install path.
- Create GitHub release.

### MVP Release Artifacts

```text
Source code
Windows executable
Linux instructions
Example Arduino sketch
Example STM32 printf snippet
Sample log file
Sample profile
```

### Acceptance Criteria

A new user can:

1. Download the app.
2. Connect to a board.
3. Print `Temperature:30.7`.
4. See a live plot within a few minutes.

---

## 13. Suggested 8-Week Timeline

## Week 1 — Basic Application and UART Console

Deliverables:

```text
Main window
Serial port list
Connect/disconnect
Raw console output
Send text input
```

## Week 2 — Line Decoder and Logging

Deliverables:

```text
Line decoder
Timestamps
Plain text log export
CSV raw log export
Stable serial reading
```

## Week 3 — Auto Signal Detection

Deliverables:

```text
Auto key-value parser
Detected signals sidebar
Latest value display
Basic signal store
```

## Week 4 — Live Plotting

Deliverables:

```text
pyqtgraph plot widget
Multiple signals
Rolling time window
Pause/resume
Clear plot
CSV export of plotted data
```

## Week 5 — Manual Extraction Rules

Deliverables:

```text
First-number rules
Regex rules
CSV rules
Rule editor
Rule test preview
```

## Week 6 — Profiles and Replay

Deliverables:

```text
Save/load profiles
Session recording
Session replay
Sample replay file
```

## Week 7 — TCP/UDP and UI Polish

Deliverables:

```text
TCP client transport
UDP listener transport
Improved error messages
Connection status indicators
Basic settings persistence
```

## Week 8 — Packaging and Release

Deliverables:

```text
README
Screenshots
Demo video/GIF
Example firmware files
First packaged release
GitHub v0.1 tag
```

---

## 14. First Vertical Slice

Before building the full MVP, build this exact path:

```text
Open app
Connect to UART
Receive line: Temperature:30.7
Auto-detect Temperature as a signal
Show it in signal list
Plot it live
```

This is the first milestone that proves the product.

Everything else should come after this.

---

## 15. Example Firmware for Testing

### Arduino / ESP32 Style

```cpp
void setup() {
  Serial.begin(115200);
}

void loop() {
  float temp = 25.0 + random(-100, 100) / 10.0;
  int hum = 50 + random(-5, 5);
  float voltage = 3.3 + random(-10, 10) / 100.0;

  Serial.print("Temperature:");
  Serial.println(temp);

  Serial.print("Humidity:");
  Serial.println(hum);

  Serial.print("Voltage=");
  Serial.println(voltage);

  delay(500);
}
```

### STM32 / C printf Style

```c
printf("Temperature:%.2f\r\n", temperature);
printf("Humidity:%u\r\n", humidity);
printf("Voltage=%.3f\r\n", voltage);
```

### CSV Style

```c
printf("%.2f,%u,%.3f\r\n", temperature, humidity, voltage);
```

---

## 16. Example Extraction Rules

### Temperature Rule

```json
{
  "name": "Temperature",
  "enabled": true,
  "mode": "first_number",
  "contains": "Temperature",
  "unit": "°C"
}
```

### Humidity Rule

```json
{
  "name": "Humidity",
  "enabled": true,
  "mode": "first_number",
  "contains": "Humidity",
  "unit": "%"
}
```

### Regex Rule

```json
{
  "name": "Air Temperature",
  "enabled": true,
  "mode": "regex",
  "pattern": "T_air=\\[(?P<value>[-+]?\\d+(?:\\.\\d+)?)C\\]",
  "value_group": "value",
  "unit": "°C"
}
```

### Generic Key-Value Rule

```json
{
  "name": "Generic key-value",
  "enabled": true,
  "mode": "regex",
  "pattern": "^(?P<name>[A-Za-z_][A-Za-z0-9_ .-]*)\\s*[:=]\\s*(?P<value>[-+]?\\d+(?:[.,]\\d+)?)",
  "channel_group": "name",
  "value_group": "value"
}
```

---

## 17. Basic Test Plan

### Unit Tests

Test line decoding:

```text
LF input
CRLF input
Partial lines
Multiple lines in one byte chunk
Non-UTF8 bytes
```

Test extraction:

```text
Temperature:30.7
Humidity:50%
Voltage = 3.31 V
Negative values
Comma decimals
Regex group extraction
CSV column extraction
```

Test profiles:

```text
Save profile
Load profile
Missing fields
Invalid rule
```

### Manual Tests

```text
Connect/disconnect repeatedly
Unplug serial adapter while connected
Reconnect after unplug
Receive high-frequency lines
Pause/resume plotting
Save and reload profile
Record and replay session
```

---

## 18. Risk List

### Risk: GUI freezes under high data rate

Mitigation:

- Use worker threads for transport.
- Batch UI updates.
- Limit console buffer length.
- Limit plot sample buffers.

### Risk: Regex rules are too hard for users

Mitigation:

- Provide simple rule modes first.
- Add rule test preview.
- Auto-suggest rules from selected console text.

### Risk: Console becomes slow with long logs

Mitigation:

- Limit visible console lines.
- Keep full recording on disk separately.
- Use `QPlainTextEdit` first, optimize later if necessary.

### Risk: Scope creep

Mitigation:

- Do not add binary protocols before v0.1.
- Do not add CAN/BLE/RTT before the UART text workflow is excellent.
- Keep TCP/UDP basic.

### Risk: Packaging Python desktop apps is annoying

Mitigation:

- Delay packaging until the MVP works.
- Start with source install for developers.
- Add Windows build first because many embedded users use Windows.
- Consider Nuitka if PyInstaller false positives become painful.

---

## 19. Future Features After MVP

Potential v0.2/v0.3 features:

```text
JSON field plotting
More advanced CSV handling
Multiple plot tabs
Math channels, e.g. power = voltage * current
Threshold alerts
Annotations
Protocol profiles
Binary frame parser
COBS/SLIP support
Protobuf support
CAN via python-can
BLE via bleak
RTT/SWO support
Modbus RTU/TCP
Firmware flashing integration
AI-assisted regex/rule generation
```

---

## 20. Recommended v0.1 Definition

Call it `v0.1` only when the app supports:

```text
UART connection
Raw text console
Send text commands
Auto key-value signal detection
Manual first-number rule
Manual regex rule
Manual CSV rule
Live plotting with pyqtgraph
Signal enable/disable
CSV export
Profile save/load
Session record/replay
Basic TCP client
Basic UDP listener
```

---

## 21. Success Criteria

The MVP is successful if a user can do this without reading a long manual:

1. Open the app.
2. Select a serial port.
3. Connect.
4. See raw firmware logs.
5. Print `Temperature:30.7` from firmware.
6. See `Temperature` appear as a detected signal.
7. Click it.
8. See a live plot.

That is the core product.

---

## 22. Best First Milestone

Build this first:

```text
PyQt/PySide window
Serial connection
Raw console
Auto key-value extraction
Detected signal list
Live plot for selected signal
```

This is the smallest version that proves the idea.

Do not start with project files, TCP, UDP, replay, or packaging. Add those after the core loop feels good.
