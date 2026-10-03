"""Default series palette shared by the rule editor and plots."""

SERIES_COLORS = ("#7cd1a8", "#89b4fa", "#f9c74f", "#f7768e", "#cba6f7", "#4dd0e1")


def default_series_color(index: int) -> str:
    return SERIES_COLORS[index % len(SERIES_COLORS)]
