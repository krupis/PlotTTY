# J-Link RTT implementation summary

This note documents the local RTT-related changes so they can be reviewed and
reimplemented cleanly if desired. The existing serial workflow is retained.

## Design

PlotTTY now selects one transport at a time:

- **Serial**: the original `QSerialPort` implementation.
- **J-Link RTT**: a native connection through the SEGGER J-Link DLL, accessed
  by the `pylink-square` Python package.

RTT receives data from an RTT *up* channel, passes it through the existing
console, decoder, extraction rules, plotting, and recording pipeline, and
sends console commands to an RTT *down* channel. It does not automate or
connect through J-Link RTT Viewer; PlotTTY owns the J-Link debug connection.

## Changed files

### `modules/core/serial_transport.py`

- Extended `SerialSettings` with `connection_type` plus RTT target, probe,
  interface, speed, control-block address, and up/down channel settings.
- Kept the existing `SerialTransport` unchanged for serial operation.
- Added `RttTransport`:
  - Imports `pylink` lazily, so serial-only use does not load RTT support.
  - Opens the selected/default J-Link probe, selects SWD or JTAG, sets the
    debug speed, connects to the configured target, and starts RTT.
  - Polls the selected RTT up channel every 10 ms and emits the same
    `bytesReceived(bytes, timestamp)` signal used by serial.
  - Writes text plus the configured line ending to the RTT down channel.
  - Stops RTT and closes the J-Link connection on disconnect.

### `modules/controllers/serial_session.py`

- Chooses `SerialTransport` or `RttTransport` from
  `settings.connection_type`.
- Uses the existing session signals, line decoder, extraction engine, rate
  counter, console text, and recording code for both transports.
- RTT connection/status text identifies the target and RTT up channel.
- Recordings use the RTT target name in their filename rather than a COM port.
- Send-command wording now covers both serial and RTT connections.

### `mainwindow.py`

- Added a top-bar connection-type combobox with **Serial** and **J-Link RTT**.
- In RTT mode the port selector becomes an editable **RTT target** field.
- Serial-only controls (port refresh and baud rate) are hidden in RTT mode.
- Switching back to Serial restores COM-port enumeration and baud-rate UI.
- The connection-type selector is disabled while a connection is active, like
  the other connection controls.

### `modules/widgets/serial_settings_dialog.py`

- Added RTT settings fields:
  - Target device name (for example `STM32G474VE`)
  - Optional J-Link probe serial number
  - SWD/JTAG interface
  - Interface speed in kHz
  - Optional RTT control-block address
  - RTT up and down channel numbers
- Values are returned with the existing settings fields when the dialog is
  accepted. The RTT fields are currently shown even while Serial is selected;
  a future cleanup could show them only in RTT mode.

### `requirements.txt`

- Added `pylink-square>=1.4.0`, the Python wrapper for the locally installed
  SEGGER J-Link DLL.

### `pysidedeploy.spec`

- Added Nuitka `--include-package=pylink` because RTT imports `pylink` at
  runtime. Without this, a standalone Windows build can omit the package.
- The SEGGER DLL itself is intentionally not bundled: it comes from the
  separately installed J-Link Software and Documentation Pack.

### `package_windows.py`

- Added `pylink-square` to packaged dependency license/version processing, so
  its notice and version are included in a Windows release.

### `README.md`

- Added a J-Link RTT setup/use section.
- Notes the installed J-Link tools/DLL requirement, settings to configure, and
  that RTT Viewer, J-Link Commander, or another debugger must not already hold
  the same probe.
- Added the `pylink-square` dependency/license mention.

### `THIRD_PARTY_NOTICES.txt`

- Added a short entry for the bundled `pylink-square` Apache-2.0 notice.

## Installation and use

1. Install the SEGGER **J-Link Software and Documentation Pack**.
2. Ensure `JLinkARM.dll` can be found through `PATH` (the normal SEGGER
   installer does this).
3. Install Python dependencies: `pip install -r requirements.txt`.
4. In PlotTTY select **J-Link RTT**, enter the target device name, open
   **Settings**, then set probe/interface/speed/channels as needed.
5. Connect. Close any other tool currently using that J-Link probe first.

## Verification performed and remaining work

- `python3 -m py_compile` passed for the changed Python modules.
- The local shell environment did not have PySide6 installed, so the Qt test
  suite could not run there.
- No physical J-Link/RTT target was available for an end-to-end test.

Recommended follow-up validation:

1. Connect to a known RTT target using channel 0 and confirm console output.
2. Confirm plotted/extracted values and both recording formats.
3. Test RTT down-channel command input if the firmware supports it.
4. Confirm reconnect/error behavior after unplugging the probe or resetting
   the target.
5. Build the standalone Windows release and verify `pylink` is included while
   `JLinkARM.dll` is resolved from the installed SEGGER tools.
