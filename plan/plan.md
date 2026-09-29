# PlotTTY direction A: ordered implementation plan

## 1. Target layout and design decisions

Use [the saved mockup](design/plottty-direction-a.png) as the visual reference.

The finished window will contain:

- **Top:** port, baud rate, connection status, Connect/Disconnect, and Settings.
- **Left:** a narrow series list with visibility checkboxes, matching colors, units, and an Edit rules button.
- **Center:** stacked plots with left-aligned names, latest values, quiet grids, and one shared time axis.
- **Bottom:** an expandable console with command input.
- **Footer:** concise recording status and receive rate.

Confirmed choices:

- Keep Qt Designer for the main window.
- Edit rules in a dialog with Apply/Cancel behavior.
- Start with the console collapsed; remember subsequent layout changes.

Use native Qt controls and the existing QPainter renderer. The image is a layout reference; decorative icons, artificial signals, and generated control details are not requirements.

## 2. Architecture and simplicity rules

Preserve the current division of responsibilities:

| Component | Responsibility |
|---|---|
| Main window | Connect UI actions to existing controllers; own applied rules and window layout preferences. |
| SerialSession | Connection, extraction, recording, and incoming data. |
| PlotWidget | Series visibility, plotting controls, colors, and refresh scheduling. |
| Plotter | Stored samples and small per-series metadata. |
| Rules dialog | Temporary rule edits, suggestions, and applying drafts. |
| ConsoleWidget | Existing buffered console rendering. |
| ProfileController | Existing profile load/save behavior. |

Keep the implementation small:

- Use `form.ui` as the main layout source; regenerate its Python output rather than editing generated code.
- Add one rules-dialog class that reuses `RulesTable`.
- Use a standard `QListWidget` for the sidebar; no custom model/view framework.
- Keep the existing single plot canvas and refresh timer.
- Use Qt signals for communication; do not add an event bus, application state framework, or generic docking system.
- Keep sample arrays in their existing storage. Sidebar rows contain identifiers and display metadata only.
- Preserve profile and capture file formats.

## 3. Implementation steps, in order

### Step 1 — Establish a baseline

Before editing:

- Run the existing unittest suite.
- Capture the current appearance with three and six series.
- Exercise connection, command sending, rule generation, profile loading, capture loading, zoom/pan, and export.
- Record a short performance baseline using the existing benchmark’s `current-widget` case.

Use the same machine, data, and window dimensions for the final comparison.

**Completion check:** existing behavior and performance are documented well enough to identify regressions.

### Step 2 — Move rules into a dedicated dialog

Do this before changing the main layout.

- Move sample input, Generate rules, the rules table, and add/remove controls into a resizable modal dialog.
- Build the small dialog in Python, matching the existing settings-dialog approach.
- Reuse `RulesTable` and `suggest_rules`; do not copy extraction or suggestion logic.
- Limit the sample input to roughly four to six visible lines and give remaining space to the table.
- Replace full-width add/remove buttons with compact controls.
- Enable row selection and keyboard focus so Remove selected works predictably.

Make the main window’s applied rule list the canonical UI state:

- Open the dialog with copies of the applied rules.
- Editing and generation affect only the draft.
- Provide **Apply, OK, and Cancel**.
- Apply commits the draft and leaves the dialog open.
- OK commits and closes.
- Cancel or closing the window discards edits made since the last Apply.
- Copy rules on commit so later draft edits cannot mutate active rules.
- Profile loading and dialog application use the same main-window method to update the session.
- Profile saving reads the applied rules, not an editor’s temporary contents.

Before applying, check regex syntax/capture groups and nonnegative integer field indexes. Show row-specific errors without closing the dialog. Preserve existing extraction modes and X-reference semantics.

Applying rules affects future samples and does not erase existing history.

**Completion check:** cancelling edits leaves parsing and saved profiles unchanged; applying updates parsing once.

### Step 3 — Replace the main window layout

Update the Designer form:

- Remove both tab widgets, the enclosing decorative frame, and the manual plot separator.
- Add a horizontal splitter containing the series sidebar and workspace.
- Start the sidebar at approximately 220 logical pixels, with a 160-pixel minimum.
- In the workspace, use a vertical splitter for plots and console.
- Keep the console toggle visible above the footer when its content is collapsed.
- Default an expanded console to approximately one-quarter of workspace height.
- Preserve the native window frame and existing File actions.

Use descriptive object names such as `SettingsButton`; replace names such as `pushButton` during this work.

Regenerate the main-window Python UI and update references immediately.

**Completion check:** all existing features remain reachable through the new layout, even before styling.

### Step 4 — Simplify connection controls

Move port and baud selection into the top bar.

- Make the top bar the only editor for port and baud.
- Keep advanced serial options, encoding, line endings, logging, raw capture, and console limits in Settings.
- Remove duplicate port/baud controls from Settings.
- Reuse the existing supported baud-rate values.
- Provide a compact port refresh action and preserve the selected port when refreshing.
- Disable connection-setting changes while connected, matching existing behavior.
- Show status with both text and a small colored indicator.
- Style Disconnect as an ordinary secondary action rather than a large red emphasis.

Keep all settings in the existing `SerialSettings` object. Use one helper to apply settings and refresh dependent controls.

**Completion check:** connection behavior is unchanged, and settings cannot become inconsistent between two editors.

### Step 5 — Add the series sidebar

Replace the plot’s Series menu with the sidebar.

- Populate rows from actual captured series, including series created dynamically by named-value parsing.
- Display a visibility checkbox, color swatch, label, and optional unit.
- Preserve series arrival order.
- Assign colors from that full order, so hiding a series never changes another series’s color.
- Make newly discovered series visible by default.
- Keep sidebar visibility separate from extraction-rule enablement: hiding a plot must not stop capture or recording.
- Show “Waiting for series” before data arrives and “No series selected” when all series are hidden.

Expose a small PlotWidget interface:

- `set_series_visible(label, visible)`
- `series_info()` returning label, unit, color, and visibility
- `seriesChanged` for additions, clearing, or capture replacement

The main window connects sidebar events to these methods. Rebuild sidebar rows only when their structure or metadata changes, not on every sample.

**Completion check:** live data, loaded captures, and visibility changes keep the sidebar and plots synchronized.

### Step 6 — Preserve units and exact latest values

The current capture values contain units, but plotting does not retain them.

- Add unit metadata and an exact latest-value accessor to `Plotter`.
- Extend sample ingestion with an optional unit argument while keeping existing two-argument callers valid.
- Update both live ingestion and background capture loading to provide units.
- Retain the latest nonempty unit for each series.
- Keep latest values in memory rather than reading disk during painting.

Display names on the left and latest values with units on the right of each plot header.

These values mean **latest captured sample**, even while viewing older history. Label or tooltip them accordingly. For loaded captures, show the final captured sample. Do not derive them from downsampled curves.

Preserve existing label-based series identity; changing that identity model is outside this redesign.

**Completion check:** identical live and loaded data produce identical units and latest-value readouts.

### Step 7 — Refine the plot canvas

Modify the current renderer rather than replacing it.

- Left-align headings and use muted axis text.
- Draw subtle grid lines and separators with minimal enclosing borders.
- Use approximately three readable Y ticks per plot, increasing only when space allows.
- Keep existing numeric formatting, Y-axis adjustments, and time navigation.
- Draw time labels once in a shared footer aligned with all plot areas.
- Keep the footer visible when the plot stack scrolls.
- Give each plot a minimum height of approximately 150 logical pixels; let smaller series counts expand to fill available space.
- Put the existing canvas in a vertical scroll area instead of introducing one widget and timer per series.

Centralize plot geometry calculations so painting, hit testing, zooming, and dragging use the same rectangles. Share horizontal range and tick calculations with the time-axis footer.

Keep the toolbar limited to the capture title, **Fit capture**, and **Auto scroll**. Rename Show All to Fit capture while retaining its current mutually exclusive mode behavior.

Preserve the existing refresh interval and bucketed data reduction. Do not add smoothing or change recorded values to imitate the mockup.

**Completion check:** three plots feel spacious; six or more remain readable through scrolling; navigation still works after resizing and scrolling.

### Step 8 — Complete console behavior

Reuse the existing console controller and buffered updates.

- Add a single-line command field and Send button.
- Route Enter and Send through the same command handler.
- Disable sending while disconnected.
- Keep collecting console text while collapsed, with the existing history-limit behavior.
- Make **Clear console** clear only console output.
- Add an explicit **Clear captured data** File action for the existing combined console/plot clear operation; it does not delete recordings.

Use one checkable View → Console action for both the menu and drawer toggle.

**Completion check:** collapsing the console loses no data, sending works by either method, and clearing console output preserves plots.

### Step 9 — Apply consistent styling and quieter status

Update the existing stylesheet and plot color constants.

- Use charcoal surfaces, off-white primary text, and muted secondary text.
- Use consistent 8/12/16-pixel spacing and restrained borders.
- Reserve accent colors for traces, focus, selection, and active states.
- Remove permanent green outlines from editable rule cells.
- Keep visible keyboard focus and readable disabled states.
- Remove obsolete tab/frame selectors and avoid per-widget inline styles.

Move point counts, downsampling ratios, and UI latency into a hidden-by-default diagnostics strip controlled by View → Diagnostics.

Show concise recording state in the footer, with full paths in tooltips. Expose recording paths through a small read-only session property; do not parse human-readable status messages to recover state.

**Completion check:** the plots dominate visually, while connection, recording, errors, and keyboard focus remain clear.

### Step 10 — Persist layout and handle resizing

Use `QSettings` with an explicit application namespace.

Save only:

- Window geometry.
- Splitter positions and last expanded console height.
- Console visibility.
- Sidebar visibility.
- Diagnostics visibility.

Use defaults on first launch and recover safely from invalid saved geometry or unavailable screens.

Keep UI preferences separate from profile JSON. Do not persist transient series identities, automatically connect, or restore a prior recording.

**Completion check:** reopening restores a usable layout without changing the capture/profile format.

## 4. Verification and acceptance

Add focused behavior tests using the existing unittest approach and Qt’s test utilities:

- Rules Apply/OK/Cancel, draft isolation, validation, and profile round trips.
- Series colors remain stable when other series are hidden.
- Hidden series continue accumulating samples.
- Units and exact latest values survive capture loading.
- Clearing console output preserves plotted history.
- Shared-axis navigation and Y-axis hit testing work after scrolling.
- Empty data, one series, and all-hidden series render safely.

Manually inspect:

- Three, six, and twelve series.
- Long labels, missing units, constant signals, and scientific notation.
- A 1280×720 window and a larger desktop window.
- 100%, 150%, and 200% display scaling.
- Connected/disconnected states, raw capture mode, loaded captures, and recording errors.
- Keyboard navigation through the sidebar, console, and dialogs.

Run the complete existing test suite and repeat the same `current-widget` performance comparison. Investigate repeatable regressions before considering the redesign complete.

Implement the numbered steps as small reviewable changes, keeping the application runnable after each step. The result should match direction A’s hierarchy while retaining the current storage, parsing, recording, and rendering foundations.
