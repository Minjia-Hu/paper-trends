"""Chart palette and Altair theme shared by the Streamlit app.

Categorical hues are assigned in this fixed order and never cycled: beyond eight series,
fold the rest into "Other". Validated for colour-vision deficiency on a light surface.
"""

from __future__ import annotations

# Same tokens as the report pages (paper_trends/report/charts.py): one red focus colour,
# a short categorical run for multi-series views, grey for context.
CATEGORICAL = ["#E3120B", "#1F4E79", "#E8A33D", "#3C8D7A", "#8C6BB1", "#C4607A", "#6B7A8F", "#A0522D"]
OTHER = "#CFCCC4"
PRIMARY = CATEGORICAL[0]
SEQUENTIAL = ["#F3F1EC", "#F6C4C1", "#EE8F8A", "#E3120B", "#B30E09", "#7D0A06", "#4A0604"]
TEXT = "#1B1B1B"
TEXT_MUTED = "#5C5C5C"
GRID = "#ECE9E2"
FONT = "IBM Plex Sans, system-ui, sans-serif"
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
            "font": FONT,
            "title": {"font": "Newsreader, Georgia, serif", "fontSize": 17, "fontWeight": 500, "anchor": "start", "color": TEXT, "offset": 14},
            "axis": {
                "domain": False,
                "ticks": False,
                "labelColor": TEXT_MUTED,
                "titleColor": TEXT_MUTED,
                "gridColor": GRID,
                "gridDash": [2, 3],
                "labelFontSize": 12,
                "titleFontSize": 12,
                "titleFontWeight": "normal",
                "labelPadding": 6,
            },
            "axisX": {"labelAngle": 0, "grid": False},
            "legend": {"labelColor": TEXT, "titleColor": TEXT_MUTED, "labelFontSize": 12, "symbolSize": 70, "symbolType": "circle"},
            "line": {"strokeWidth": 2.2, "interpolate": "monotone"},
            "point": {"size": 50, "filled": True},
            "bar": {"cornerRadiusEnd": 2},
            "range": {"category": CATEGORICAL},
        }
    }
