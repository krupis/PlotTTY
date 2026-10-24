# TODO

- [ ] Remove the PyQtGraph runtime dependency by replacing `create_qpolygonf` and
  `ndarray_from_qpolygonf` with a direct PySide6/NumPy point-buffer bridge.
  Preserve bulk Analog, Digital, and Dots drawing and safe buffer lifetimes.
  Benchmark refresh, pan/zoom, and UI event-loop latency before and after with
  identical data and window dimensions; confirm comparable performance and
  rendering correctness, then update requirements and dependency documentation.
