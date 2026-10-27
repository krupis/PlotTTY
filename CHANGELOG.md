# Changelog

## Unreleased

- Added **View → Receive timestamps** to prefix new console lines with the host
  receive time in Unix seconds to millisecond precision. The setting is remembered
  between launches. Saved log files keep their existing format.

## 1.0.0

Initial release.

- Serial and J-Link RTT connections with a searchable text console and command sending.
- Numeric extraction from named values, delimited fields, the first number, or regex.
- Extraction rules generated from sample output, with optional device timestamps.
- Analog, Digital, and Dots plots with pan, zoom, auto scroll, and fit capture.
- Range selection with average, time range, and sample count.
- Console logging, `.plotty` capture recording and review, and CSV export.
- Saved extraction profiles, series colors, visibility, and window layout.
- Packaged builds for Windows x64, macOS Apple silicon and Intel, and Linux x64.
