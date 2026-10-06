# PlotTTY working rules

This application is pre-release. For all changes, do not preserve backwards compatibility unless the user explicitly requests it. This applies to UI workflows, APIs, settings, profiles, and file formats as well as refactors.

Prefer the simplest current implementation. Do not add compatibility shims, legacy fallbacks, migration layers, or duplicate implementations solely to support previous behavior or formats.

When replacing a workflow, remove its superseded UI, code paths, shims, and tests. Prefer a smaller single implementation over dual-mode compatibility layers.

Prioritize plotting performance and UI responsiveness when designing any change that could meaningfully affect them. Only run performance benchmarks and latency tests for such changes; skip them for simple cosmetic changes such as icons, labels, or styling that have no meaningful performance impact. For changes that could meaningfully affect performance, measure a baseline and test the changed implementation with comparable data, window size, and workload before declaring the work complete. Check both plot refresh/pan/zoom timings and UI event-loop latency under load, including the feature's own interactions where relevant.

Report any observed performance regression to the user, including measurements, test conditions, and limitations. Investigate noisy results before claiming a regression or improvement. Do not silently accept a slowdown or claim live-device performance from synthetic or offscreen tests. Keep temporary benchmark outputs and screenshots under the ignored `tmp/` directory.
