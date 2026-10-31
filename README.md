# PlotTTY

PlotTTY reads text from your device and plots the numbers in it. Connect over
Serial, J-Link RTT, TCP/IP, or UDP, then choose the values you want to follow.

[**Download PlotTTY**](https://github.com/krupis/QT_PlotTTY/releases/latest)
· [Changelog](CHANGELOG.md)
· [Get started](#get-started) · [Plot controls](#use-the-plots) · [Run from source](#run-from-source)

[![PlotTTY showing extraction rules, three plotted signals, and a selected range with its average](docs/images/plottty-capture.png)](docs/images/plottty-capture.png)

## Features

- **Connections:** Serial, J-Link RTT, TCP/IP, and UDP. Each connection gets its
  own tab with separate settings, plots, and console.
- **Extraction rules:** Named values, delimited fields, first-number matching,
  and regex. Generate rules from sample text or [set them up manually](#extract-values).
- **Plots:** Analog, Digital, and Dots modes, with pan, zoom, and auto scroll.
- **Measurements:** Select a time range for its average and sample count,
  calculated from the original samples.
- **Console:** Text search, receive timestamps, and command history.
- **Recordings:** Save console logs and `.plotty` captures. Reopen captures
  or export their values as CSV.

## Get started

Download your platform's package from the
[latest release](https://github.com/krupis/QT_PlotTTY/releases/latest) and extract it.
Python and the required packages are included.

| Platform | Package | Launch |
| --- | --- | --- |
| Windows x64 | `windows-x64.zip` | Run `PlotTTY.exe`; keep the `app/` folder and supporting files beside it. |
| macOS Apple silicon | `macos-arm64.zip` | Open `PlotTTY.app`. |
| macOS Intel | `macos-x64.zip` | Open `PlotTTY.app`. |
| Linux x64 | `linux-x64.tar.gz` | Run `./PlotTTY` from the extracted folder. |

1. Choose **Serial**, **J-Link RTT**, **TCP/IP**, or **UDP** in the connection bar.
2. Open **Settings**, enter your connection details, and click **Save settings**.
3. Turn on **File → Log to file** if you want to save the session.
4. Click **Connect**. Open **View → Console** to see incoming text.
5. Paste a sample line into the extraction sidebar, click **Generate rules**,
   check the suggested rules, then click **Apply rules** to start plotting.

### Connection settings

**Serial:** Choose a port and baud rate. Click **Rescan** if your port is missing.
You can also choose the text encoding and the line ending for commands you send.

**J-Link RTT:** Install SEGGER's **J-Link Software and Documentation Pack**, then
restart PlotTTY. In RTT Settings, enter your microcontroller's device name.
Close any other software using the J-Link probe before connecting.

The SEGGER installer includes the library needed to use the probe. On Windows,
PlotTTY looks in the standard SEGGER installation folders, so you usually don't
need to copy any DLLs. The file is `JLink_x64.dll` for 64-bit Python or
`JLinkARM.dll` for 32-bit Python.

Alternatively, add the SEGGER J-Link directory containing the DLL to your Windows
`%PATH%`, then restart PlotTTY.

**TCP/IP:** Enter the server's hostname or IP address and port. PlotTTY connects
as a client. You can click **Cancel** while it's trying to connect.

**UDP:** Choose the local IP address and port to listen on. Use `0.0.0.0` to
listen on all IPv4 interfaces, or `::` for IPv6. To send commands too, enter a
destination host and port using the same IP family (IPv4 or IPv6). Each command
is sent as one datagram. Leave the destination empty to receive only.

UDP doesn't guarantee delivery or order; datagrams may be lost or duplicated.
PlotTTY doesn't support UDP multicast or running as a TCP server.

TCP/IP and UDP use the same text settings, extraction rules, console, and recording
as Serial and RTT. Each incoming line needs a newline before PlotTTY can extract
values from it. A UDP datagram ending doesn't count as a newline.

### Multiple connections

Click **+** or press **Ctrl+T** to open another tab. For example, you can monitor
COM14 in one tab and COM15 in another. Each tab has its own settings, rules,
plots, console history, sent commands, and recordings.

Other tabs keep receiving and recording while you're away from them. Their
displays update when you return. The **File** and **View** menus apply to the
selected tab.

Close a tab with **Ctrl+W** or its close button to disconnect and finish its
recordings. Closing PlotTTY disconnects all tabs.

## Extract values

Extraction rules tell PlotTTY which numbers to take from each line. Paste a sample
line and click **Generate rules** to get started, or use **Add** and **Remove** to
set up rules yourself.

To create a rule manually:

1. Click **Add** in the extraction sidebar.
2. Leave **Function** set to **Plot** and choose a **Method**.
3. Fill in the settings shown in an example below. Keep **Show** checked.
4. Click **Apply rules**. New matching lines will add points to the plots.

Each example below shows a line your device might send and the settings to read it.
The line must end with a newline for PlotTTY to process it.

<details>
<summary><strong>Named values: plot every name/value pair in a line</strong></summary>

Device output:

```text
Voltage: 3.31, Current: 0.12, Temperature: 24.5
```

Add **one rule** with **Function → Plot** and **Method → Named values**.
This method takes the labels from the line, so the rule's **Label** doesn't
rename them. No delimiter or field number is needed.

That one rule creates three signals:

| Signal | Value |
| --- | --- |
| Voltage | 3.31 |
| Current | 0.12 |
| Temperature | 24.5 |

Both `Voltage: 3.31` and `Voltage=3.31` work. You don't need a Named values rule
for each pair; adding more would read the same values again.

</details>

<details>
<summary><strong>Delimited values: pick columns from CSV or similar text</strong></summary>

Device output:

```text
12.5,3.31,0.12
```

Here the fields are device time in seconds, voltage, and current. Field numbers
start at **0**, so add these rules:

| Function | Label | Method | Delimiter | Field |
| --- | --- | --- | --- | --- |
| Time | Device time | Delimited values | `,` | `0` |
| Plot | Voltage | Delimited values | `,` | `1` |
| Plot | Current | Delimited values | `,` | `2` |

This plots Voltage = **3.31** and Current = **0.12**, both with a timestamp of
**12.5 seconds**. The Time rule sets the timestamp; it doesn't create a plot.
Leave it out if you want to use the computer's receive time instead.

For `12.5;3.31;0.12`, use `;` as the delimiter. For tab-separated output, enter
`\t`. Add one Plot rule for each field you want to see.

</details>

<details>
<summary><strong>First number: read a single measurement from each line</strong></summary>

Device output:

```text
Voltage: 3.31 V
```

| Function | Label | Method |
| --- | --- | --- |
| Plot | Voltage | First number |

This plots **3.31** under the label **Voltage**. No other settings are needed.

It always reads the first number, even if that number is a counter or timestamp.
For example, `Sample 42: Voltage 3.31 V` would give **42**. Use a field rule or
regex when you need a later number in the line.

</details>

<details>
<summary><strong>Regex pattern: pick a number out of custom text</strong></summary>

Device output:

```text
sensor 2 | temp -4.5 C | status OK
```

Add a rule with **Function → Plot**, **Label → Temperature**, and
**Method → Regex pattern**. Enter this in **Pattern** (or **Pattern / delim.**
if you also have delimited rules):

```regex
temp\s+([-+]?\d+(?:\.\d+)?)
```

This plots **-4.5** as **Temperature**, skipping the sensor number **2**.

The pattern looks for `temp`, followed by whitespace and a number.
The first capture group—the outer parentheses around the number—chooses the
value to plot. `[-+]?` allows a sign, and `(?:\.\d+)?` allows a decimal part
without creating another capture group.

A line without a matching temperature adds no point for this rule. Paste the
pattern as shown, without quotes or extra backslashes.

</details>

Choose **Plot** for a signal or **Time** for a device timestamp in seconds.
Without a Time rule, PlotTTY timestamps samples when it receives them. If you use
a Time rule, lines without a valid timestamp still appear in the console but
won't add points to the plots.

Uncheck **Show** to hide a signal; it will keep collecting data. Click its color
dot to choose a color, or right-click the dot to use automatic colors again.
Click **Apply rules** when you're done editing. The rules apply to new samples;
they don't reprocess earlier data.

## Use the plots

Each signal has a **Mode** selector. **Analog** joins the points with lines,
**Digital** draws steps, and **Dots** shows the individual points. Changing the
mode doesn't change the recorded data.

| Control | Action |
| --- | --- |
| Left-drag across a signal | Select a time range. Release to see its average. |
| Click the plot or press Escape | Clear the selection. |
| Shift + drag or middle-button drag | Move backward or forward in time. You can also drag the bottom time axis. |
| Mouse wheel | Zoom in or out around the cursor. |
| Drag the Y axis | Move the signal's value range up or down. |
| Mouse wheel over the Y axis | Zoom the signal's value range. |
| Double-click the Y axis | Reset the signal's value range. |
| **Auto scroll** | Follow the newest samples. |
| **Fit capture** | Show the whole recording. |

Hover over a plot to read the time and value at the cursor. The number in the
plot header always shows the latest sample, even when you're looking at older data.

Selecting a range shows its start and end times, average, and sample count.
The average uses the original samples and skips NaN and infinity. While a range
is selected, the time view stays in place, but incoming data is still collected.

When you're zoomed out, PlotTTY draws fewer points to keep the plots responsive
while preserving peaks. Zoom in to see individual samples.
**View → Diagnostics** shows how many points are stored and drawn.
**View → Raw point limits** sets when each plot mode starts drawing fewer points.

## Console and layout

- Press **Ctrl+F** to search the console. Use **Previous** and **Next** to move
  between matches.
- Type a command and press **Enter** or click **Send**. Use **Up/Down** to recall
  commands you've sent.
- Use the **View** menu to show or hide panels. Drag the dividers to resize them.
- Use **Clear** in the console to clear text, or **Clear** in a plot to clear
  plotted data. **File → Clear captured data** clears both. Your saved recordings
  are kept.

Console history is deleted when you close the app, so turn on file logging if
you need to keep it. Search looks through the whole history. You can select and
copy the text currently loaded in the console. PlotTTY remembers your window layout.

### Receive timestamps

Turn on **View → Receive timestamps** to add a time before each new line:

```text
[1793128867.123] 136984,3,3.251200
```

This is the time your computer received the data, in Unix seconds with three
decimal places. Lines received together share a timestamp. If a line arrives in
chunks, it keeps the time of the first chunk shown in the console.

The setting is off by default. PlotTTY remembers your choice, and changing it
only affects new lines. These display timestamps don't change the text used by
extraction rules or the separate RX/TX timestamps in console log files.

## Profiles and recordings

Use **File → Save profile** to save your applied rules, colors, and which signals
are shown. **File → Open profile** restores them from the saved JSON file.

File logging is off by default. To record a session, turn on **File → Log to file**
before connecting. PlotTTY writes two files for each connection:

- A `.log` file with the console text.
- A `.plotty` file with the extracted values, timestamps, labels, and source text.

Disconnect to finish the recording. Use **File → Load capture** to open a
`.plotty` file, or **File → Export capture as CSV** to use its values in another
tool. CSV export needs a finished recording; CSV import isn't supported.

Recordings are saved in `logs/` under the app's working directory. Hover over
**Log to file** to see the full folder path, or over the recording status to see
the file paths. You can cancel loading or exporting a capture.

## Data rates and plot capacity

Serial baud rate choices are 9,600, 19,200, 38,400, 57,600, 115,200, 230,400,
460,800, and 921,600. Which rates work depends on your device and driver.

The status bar shows received **bytes per second**. That's different from baud
rate or the number of plotted values per second. USB CDC devices can send faster
than the selected baud rate when they send USB packets directly. For a physical
UART using 8N1, 115,200 baud allows up to 11,520 payload bytes/s; 921,600 baud
allows 92,160 bytes/s.

### What we've tested

| Test | Result |
| --- | --- |
| USB CDC input | About **690–720 kB/s** at **10,000 text records/s**, with five plotted values per record (**50,000 values/s**). Console output and file recording were enabled. |
| Stored points | **1,000,000 points across five signals** (200,000 each) in synthetic plotting tests. |
| Plot refresh | A refresh is scheduled every **33 ms**. Actual timing depends on the data, plot mode, window size, and computer. |

The USB test ran on Windows with a physical STM32 sending simulated data, a
1280 × 720 window, and repeated panning and zooming. These figures aren't a
guaranteed maximum. Some console search, scroll, and copy stress tests had
occasional missing records. The million-point test used synthetic data separately
from live recording.

There's no fixed limit on the number of stored points; available memory and disk
space set the practical limit. PlotTTY keeps raw samples in temporary files and
draws fewer points when zoomed out. Zooming in shows individual samples, and
averages always use the original data.

## Run from source

Install Python 3.13, then run these commands from the project folder on Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe mainwindow.py
```

## License

PlotTTY is licensed under the [MIT License](LICENSE). Third-party licenses are
listed in [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) and included with
packaged releases.
