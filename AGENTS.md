# PlotTTY working rules

This application is pre-release. For all changes, do not preserve backwards compatibility unless the user explicitly requests it. This applies to UI workflows, APIs, settings, profiles, and file formats as well as refactors.

Prefer the simplest current implementation. Do not add compatibility shims, legacy fallbacks, migration layers, or duplicate implementations solely to support previous behavior or formats.

When replacing a workflow, remove its superseded UI, code paths, shims, and tests. Prefer a smaller single implementation over dual-mode compatibility layers.
