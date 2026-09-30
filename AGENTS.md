# PlotTTY working rules

This application is pre-release. Do not preserve legacy compatibility during refactors unless the user explicitly requests it.

When replacing a workflow, remove its superseded UI, code paths, shims, and tests. Prefer a smaller single implementation over dual-mode compatibility layers.
