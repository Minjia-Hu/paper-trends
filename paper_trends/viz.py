"""Chart palette and Altair theme shared by the Streamlit app.

Categorical hues are assigned in this fixed order and never cycled: beyond eight series,
fold the rest into "Other". Validated for colour-vision deficiency on a light surface.
"""

from __future__ import annotations

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
OTHER = "#9a9a96"
PRIMARY = CATEGORICAL[0]
SEQUENTIAL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"
GRID = "#e6e5e1"
MAX_SERIES = 8


def series_colors(names: list[str]) -> tuple[list[str], list[str]]:
    """(domain, range) for an Altair colour scale; 'Other' always gets the neutral grey."""
    domain, rng = [], []
    slot = 0
    for n in names:
        if n == "Other":
            domain.append(n)
            rng.append(OTHER)
        elif slot < MAX_SERIES:
            domain.append(n)
            rng.append(CATEGORICAL[slot])
            slot += 1
    return domain, rng


def altair_theme() -> dict:
    return {
        "config": {
            "background": "transparent",
            "view": {"stroke": None},
            "font": "Inter, system-ui, sans-serif",
            "axis": {
                "labelColor": TEXT_MUTED,
                "titleColor": TEXT_MUTED,
                "gridColor": GRID,
                "domainColor": GRID,
                "tickColor": GRID,
                "labelFontSize": 11,
                "titleFontSize": 11,
                "titleFontWeight": "normal",
            },
            "axisX": {"labelAngle": 0},
            "legend": {"labelColor": TEXT, "titleColor": TEXT_MUTED, "labelFontSize": 11, "symbolSize": 80},
            "line": {"strokeWidth": 2},
            "point": {"size": 64, "filled": True},
            "bar": {"cornerRadiusEnd": 4},
            "range": {"category": CATEGORICAL},
        }
    }
