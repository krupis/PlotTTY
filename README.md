# PlotTTY

**Serial, J-Link RTT, TCP/IP, and UDP monitoring and plotting.**

PlotTTY displays device output over Serial, J-Link RTT, TCP/IP, and UDP and plots numeric values in real time.


[**Download PlotTTY**](https://github.com/krupis/QT_PlotTTY/releases/latest)
· [Changelog](CHANGELOG.md)
· [Get started](#get-started) · [Plot controls](#use-the-plots) · [Run from source](#run-from-source)

[![PlotTTY showing extraction rules, three plotted signals, and a selected range with its average](docs/images/plottty-capture.png)](docs/images/plottty-capture.png)



| Feature | What you can do |
| --- | --- |
| Serial, J-Link RTT, TCP/IP, and UDP | Read device output and inspect incoming text in the console. |
| Flexible extraction | Generate rules from sample output, or use named values, delimited fields, first-number matching, and regex. |
| Live plots | Switch between Analog, Digital, and Dots; pan, zoom, and follow incoming samples. |
| Range measurements | Drag across a signal to see its average, time range, and sample count. |
| Record and review | Save console logs and `.plotty` captures, reopen captures, and export CSV. |

## Data rates and plot capacity

| Item | Details |
| --- | --- |
| Serial baud rates | 9,600, 19,200, 38,400, 57,600, 115,200, 230,400, 460,800, and 921,600. Available rates depend on the device and driver. |
| Measured USB CDC input | About **690–720 kB/s** at **10,000 text records/s**, with five plotted values per record (**50,000 values/s**), console output, and file recording enabled. |
| Stored points | Synthetic plotting tests covered **1,000,000 points across five series** (200,000 per series). There is no fixed point-count limit; available memory and disk space limit capture size. |
| Plot refresh | Scheduled every **33 ms**. Actual refresh speed depends on the data, plot mode, window size, and computer. |
| Large captures | Raw samples are stored in temporary files. Wide views draw fewer points while preserving peaks; zoom in to inspect individual samples. Averages use the original samples. |

The USB measurements are from Windows tests with a physical STM32 device sending
simulated data, a 1280 × 720 window, and repeated pan/zoom. They are measured rates,
not a guaranteed maximum. Some console search, scroll, and copy stress tests had
occasional missing records. The point-count tests used synthetic data separately
from live acquisition.

USB CDC throughput can exceed the selected baud rate when the device sends USB
packets directly. For a physical UART using 8N1, 115,200 baud allows at most
11,520 payload bytes/s; 921,600 baud allows 92,160 bytes/s. The status bar shows
received **bytes per second**, rather than baud or extracted values per second.

## Get started

Download the archive for your platform from the
[latest release](https://github.com/krupis/QT_PlotTTY/releases/latest) and extract it
before launching. Packaged releases include Python and the application dependencies.

| Platform | Package | Launch |
| --- | --- | --- |
| Windows x64 | `windows-x64.zip` | Run `PlotTTY.exe`; keep the `app/` folder and supporting files beside it. |
| macOS Apple silicon | `macos-arm64.zip` | Open `PlotTTY.app`. |
| macOS Intel | `macos-x64.zip` | Open `PlotTTY.app`. |
| Linux x64 | `linux-x64.tar.gz` | Run `./PlotTTY` from the extracted folder. |

1. Choose **Serial**, **J-Link RTT**, **TCP/IP**, or **UDP** in the connection bar.
2. Open **Settings**, configure your connection, then choose **Save settings**.
3. Enable **File → Log to file** if you want a permanent recording.
4. Click **Connect**. Open **View → Console** to see incoming text.
5. Paste a sample line into the extraction sidebar, click **Generate rules**,
   review the fields, then click **Apply rules** to start plotting.

For Serial, select a port and baud rate. Use **Rescan** if the port is missing.
Settings also include encoding and the line ending used when sending commands.

For RTT, install SEGGER's J-Link Software and Documentation Pack, make its library
available (`JLinkARM.dll` on Windows), and enter the target device in Settings.
Close other software using the probe before connecting.

For TCP/IP, enter the server hostname or IP address and port. PlotTTY acts as a
TCP client. Connecting is asynchronous; **Cancel** stops a pending connection.

For UDP, choose the local bind IP address and port (`0.0.0.0` listens on all IPv4
interfaces; `::` listens on IPv6). An optional destination host and port lets you
send commands; each command is sent as one datagram. The destination must use the
same IP family as the bind address. Without a destination, UDP receives only.
UDP can lose, duplicate, or reorder datagrams. No TCP server or UDP multicast mode
is provided.

Both network connections use the same encoding, command line endings, extraction
rules, console, and recording as Serial and RTT. Incoming text records must end
with a newline to produce plot values. UDP datagram boundaries do not add newlines.

## Extract values

Plots appear after extraction rules are applied. Use **Add** and **Remove** to
edit rules manually, or open an example from [profiles/](profiles/).

| Method | Use it for |
| --- | --- |
| Named values | Pairs such as `Voltage: 3.31, Current: 0.12`. Each name becomes a series. |
| Delimited values | CSV or similar output. Choose a delimiter and field: **0 is the first field**. |
| First number | The first numeric value on each line. |
| Regex pattern | Custom text formats. The first capture group supplies the numeric value. |

Choose **Plot** to create a series, or **Time** to read device timestamps in seconds.
Without a Time rule, PlotTTY uses receive times. With one, lines missing a valid
timestamp stay in the console but do not add plot samples.

Use **Show** to hide a series while it continues collecting data. Click a color
dot to change its color, or right-click it to restore automatic colors.
Click **Apply rules** after editing. Changes affect future samples.

## Use the plots

Use each signal's **Mode** selector: **Analog** connects samples, **Digital** holds
each value until the next sample, and **Dots** shows sample positions.
Modes affect display only.

| Control | Action |
| --- | --- |
| Left-drag across a signal | Select a time range and calculate its average on release. |
| Click the plot or press Escape | Clear the selection. |
| Shift + drag or middle-button drag | Pan time. Dragging the bottom time axis also pans. |
| Mouse wheel | Zoom time around the cursor. |
| Drag / wheel over the Y axis | Pan / zoom that signal's value range. |
| Double-click the Y axis | Reset its value range. |
| **Auto scroll** | Follow the newest samples. |
| **Fit capture** | Show the full captured time range. |

Hover over a signal to read cursor coordinates. The value in each plot header
is the latest captured value, even when viewing older history.

Selections show the time range, average, and sample count on the plot. Averages use
the original captured samples. Non-finite values are skipped. Selecting pauses
automatic time navigation while data collection continues.

Wide views reduce the number of points drawn. Zoom in for individual samples.
**View → Diagnostics** shows point counts and downsampling. **View → Raw point
limits** changes the downsampling thresholds for each mode.

## Console and layout

- **View → Receive timestamps** prefixes new received lines with Unix seconds
  to millisecond precision, for example `[1793128867.123] 136984,3,3.251200`.
  The time comes from the host's
  transport read, before text processing. Lines in the same read share a time;
  a line received in chunks keeps its first displayed chunk's time. The switch is
  off by default, is remembered between launches, and affects future lines only.
  Extraction uses the original text. Console log files retain their existing
  timestamped RX/TX format.
- **Ctrl+F** opens console search. Use **Previous** and **Next** to move through matches.
- Send a command with **Enter** or **Send**. **Up/Down** recalls sent commands.
- **View** shows or hides panels. Drag the dividers to resize them.
- The console's **Clear** clears text. The plot's **Clear** clears plotted data.
  **File → Clear captured data** clears both. Saved recordings are kept.

Console history is temporary and is deleted when the app closes. Search covers
the complete history. Selection and copying apply to the currently loaded text.
Window layout is remembered between launches.

## Profiles and recordings

- **File → Save profile / Open profile** saves and restores applied extraction
  rules, colors, and series visibility in a JSON file.
- **File → Log to file** records each connection to a console `.log` and a
  `.plotty` capture containing extracted values, timestamps, labels, and source text.
  Set this option before connecting. Disconnect to finish the recording.
- **File → Load capture** opens a saved `.plotty` file for review.
- **File → Export capture as CSV** exports a finished capture for other tools.
  CSV import is not supported.

Recordings go into `logs/` under the app's working directory. Hover over
**Log to file** for the full folder path, or the recording status for file paths.
Loading and exporting can be cancelled.

## Run from source

With Python 3.13 installed, run these commands from the project folder on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe mainwindow.py
```

## License

[MIT License](LICENSE). See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt)
and the licenses included with packaged releases for dependency notices.
