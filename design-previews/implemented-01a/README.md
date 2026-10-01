# Implemented Graphite & teal workspace

These PNGs are captures of the actual Qt widgets, rendered offscreen with Segoe UI
and Consolas loaded from Windows. They use synthetic serial values and a simulated
connected UI state; they are not evidence of a physical serial-device session.

- `workspace-1672.png`: five series, three visible plots, applied rules, expanded console.
- `workspace-1280.png`: the same workspace at 1280 × 800; plots scroll vertically.
- `empty-1280.png`: disconnected state with the console collapsed.

The design implements concept 01A's graphite surfaces, teal actions, brighter text,
and panel boundaries. Subdued Extraction, Plot, and Console headers identify
each panel. The sidebar groups full-width Generate/Apply buttons and a table that
grows with its rows above Add/Remove, with spare space below the controls. Apply
is disabled when there are no draft changes. Add, Remove, Apply, and Send use
small outline icons alongside their labels. Surface and accent colors
were sampled from the generated 01A image rather than its prompt palette.
The production UI retains per-rule
extraction methods and zero-based fields, and displays actual latest values rather
than the mockup's illustrative minimum/maximum statistics.

Validation: 55 unit tests pass, including draft/apply behavior, adaptive table sizing, visible validation
feedback, serial recording through a fake transport,
console search and commands, capture import/export, and plot navigation. Screenshots
were reviewed at 1672 × 941 and 1280 × 800. No physical device or packaged executable
was exercised for this visual change.
