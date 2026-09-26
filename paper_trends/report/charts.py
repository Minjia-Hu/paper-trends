"""Vega-Lite specs for the report. One focus colour, grey context, direct labels, no legends."""

from __future__ import annotations

from typing import Any

RED = "#E3120B"
INK = "#1B1B1B"
MUTED = "#5C5C5C"
GREY = "#B8B5AE"
GRID = "#ECE9E2"
BLUE = "#1F4E79"
TOPIC_COLORS = ["#E3120B", "#1F4E79", "#E8A33D", "#3C8D7A", "#8C6BB1", "#C4607A"]
OTHER = "#CFCCC4"
FONT = "IBM Plex Sans, system-ui, sans-serif"

CONFIG: dict[str, Any] = {
    "background": "transparent",
    "font": FONT,
    "view": {"stroke": None},
    "axis": {
        "domain": False, "ticks": False, "gridColor": GRID, "gridDash": [2, 3],
        "labelColor": MUTED, "labelFontSize": 12, "labelFont": FONT,
        "titleColor": MUTED, "titleFontWeight": "normal", "titleFontSize": 12, "titleFont": FONT, "labelPadding": 6,
    },
    "axisX": {"grid": False, "labelAngle": 0},
    "legend": {"disable": True},
    "text": {"font": FONT, "fontSize": 12, "color": INK},
}


def _base(height: int, padding: dict | None = None) -> dict[str, Any]:
    spec: dict[str, Any] = {"$schema": "https://vega.github.io/schema/vega-lite/v5.json", "width": "container", "height": height, "config": CONFIG}
    if padding:
        spec["padding"] = padding
    return spec


def small_multiple(series: list[dict], years: list[int], ymax: float, color: str = RED) -> dict[str, Any]:
    """One term: a single line with the final value labelled at its end."""
    last = years[-1]
    spec = _base(110, {"left": 4, "right": 44, "top": 8, "bottom": 4})
    spec["data"] = {"values": series}
    x = {"field": "year", "type": "quantitative", "axis": {"format": "d", "values": [years[0], last], "title": None}, "scale": {"domain": [years[0], last], "nice": False}}
    y = {"field": "share", "type": "quantitative", "axis": {"format": ".0%", "title": None, "tickCount": 2}, "scale": {"domain": [0, ymax]}}
    spec["layer"] = [
        {"mark": {"type": "line", "color": color, "strokeWidth": 2.2, "interpolate": "monotone"}, "encoding": {"x": x, "y": y}},
        {"mark": {"type": "point", "filled": True, "color": color, "size": 60}, "transform": [{"filter": f"datum.year == {last}"}], "encoding": {"x": x, "y": y}},
        {"mark": {"type": "text", "align": "left", "dx": 7, "color": color, "fontWeight": 600, "fontSize": 12}, "transform": [{"filter": f"datum.year == {last}"}],
         "encoding": {"x": x, "y": y, "text": {"field": "share", "format": ".1%"}}},
        {"mark": {"type": "rule", "color": "transparent", "strokeWidth": 12}, "encoding": {"x": x, "tooltip": [{"field": "year", "title": "year"}, {"field": "share", "format": ".1%", "title": "share"}, {"field": "papers", "title": "papers"}]}},
    ]
    return spec


def papers_bars(rows: list[dict], value: str = "papers", fmt: str = "d", height: int = 90) -> dict[str, Any]:
    """Quiet grey bars per year (papers, or any per-year value such as coverage)."""
    spec = _base(height, {"left": 4, "right": 4, "top": 4, "bottom": 4})
    spec["data"] = {"values": rows}
    spec["mark"] = {"type": "bar", "color": GREY, "cornerRadiusEnd": 2}
    spec["encoding"] = {
        "x": {"field": "year", "type": "ordinal", "axis": {"title": None, "labelExpr": "datum.value % 3 == 0 ? datum.value : ''"}},
        "y": {"field": value, "type": "quantitative", "axis": {"title": None, "tickCount": 2, "format": fmt}},
        "tooltip": [{"field": "year"}, {"field": value, "format": fmt}],
    }
    return spec


def trend_line(rows: list[dict], value: str = "papers", fmt: str = ",d", height: int = 120, color: str = INK) -> dict[str, Any]:
    """One quantity over the years as a line, first and last values labelled — for "how
    much" over time, where bars of near-equal height would say nothing."""
    years = [r["year"] for r in rows]
    first, last = years[0], years[-1]
    vmax = max(r[value] for r in rows)
    spec = _base(height, {"left": 20, "right": 24, "top": 14, "bottom": 4})
    spec["data"] = {"values": rows}
    x = {"field": "year", "type": "quantitative", "axis": {"format": "d", "title": None, "values": years, "domain": True, "domainColor": GRID}, "scale": {"domain": [first - 0.3, last + 0.3], "nice": False}}
    # no y axis: the first and last values are written on the line; a dot marks every year
    y = {"field": value, "type": "quantitative", "axis": None, "scale": {"domain": [0, vmax * 1.25]}}
    ends = {"filter": f"datum.year == {first} || datum.year == {last}"}
    spec["layer"] = [
        {"mark": {"type": "line", "color": color, "strokeWidth": 2, "interpolate": "monotone"}, "encoding": {"x": x, "y": y}},
        {"mark": {"type": "point", "filled": True, "color": color, "size": 28}, "encoding": {"x": x, "y": y}},
        {"mark": {"type": "point", "filled": True, "color": color, "size": 60}, "transform": [ends], "encoding": {"x": x, "y": y}},
        {"mark": {"type": "text", "dy": -12, "color": color, "fontWeight": 600, "fontSize": 12}, "transform": [ends],
         "encoding": {"x": x, "y": y, "text": {"field": value, "format": fmt}}},
        {"mark": {"type": "rule", "color": "transparent", "strokeWidth": 14}, "encoding": {"x": x, "tooltip": [{"field": "year"}, {"field": value, "format": fmt}]}},
    ]
    return spec


def multi_line(rows: list[dict], names: list[str], years: list[int], title: str | None = None, height: int = 220) -> dict[str, Any]:
    """Several series (e.g. conferences) on one chart: fixed palette, direct end labels, no legend."""
    last = years[-1]
    colors = (TOPIC_COLORS + [OTHER])[: len(names)]
    spec = _base(height, {"left": 4, "right": 150, "top": 8, "bottom": 4})
    spec["data"] = {"values": rows}
    x = {"field": "year", "type": "quantitative", "axis": {"format": "d", "title": None, "tickCount": min(len(years), 10)}, "scale": {"domain": [years[0], last], "nice": False}}
    y = {"field": "share", "type": "quantitative", "axis": {"format": ".0%", "title": None, "tickCount": 3}}
    color = {"field": "name", "type": "nominal", "scale": {"domain": names, "range": colors}, "legend": None}
    spec["layer"] = [
        {"mark": {"type": "line", "strokeWidth": 2.2, "interpolate": "monotone"}, "encoding": {"x": x, "y": y, "color": color}},
        {"mark": {"type": "point", "filled": True, "size": 55}, "transform": [{"filter": f"datum.year == {last}"}], "encoding": {"x": x, "y": y, "color": color}},
        {"mark": {"type": "text", "align": "left", "dx": 8, "fontSize": 12, "fontWeight": 500}, "transform": [{"filter": f"datum.year == {last}"}],
         "encoding": {"x": x, "y": y, "color": color, "text": {"field": "name"}}},
        {"mark": {"type": "rule", "color": "transparent", "strokeWidth": 14}, "encoding": {"x": x, "tooltip": [{"field": "name"}, {"field": "year"}, {"field": "share", "format": ".1%"}, {"field": "papers"}]}},
    ]
    if title:
        spec["title"] = {"text": title, "anchor": "start", "font": "Newsreader, Georgia, serif", "fontSize": 17, "fontWeight": 500, "color": INK, "offset": 12}
    return spec


def streamgraph(rows: list[dict], topics: list[str], years: list[int]) -> dict[str, Any]:
    """Stacked shares, top topics coloured, the rest folded to grey, labels at the right edge."""
    colored = topics[: len(TOPIC_COLORS)]
    label_of = {t: (t if t in colored else "Other") for t in topics}
    folded: dict[tuple[str, int], float] = {}
    for r in rows:
        key = (label_of[r["topic"]], r["year"])
        folded[key] = folded.get(key, 0.0) + r["share"]
    order = colored + (["Other"] if len(topics) > len(colored) else [])
    data = [{"topic": t, "year": y, "share": folded.get((t, y), 0.0), "rank": i} for i, t in enumerate(order) for y in years]
    # end labels: midpoint of each band at the last year (stack from the bottom in rank order)
    last = years[-1]
    cum = 0.0
    labels = []
    for t in order:
        s = folded.get((t, last), 0.0)
        labels.append({"topic": t, "year": last, "ymid": cum + s / 2, "share": s})
        cum += s
    colors = TOPIC_COLORS[: len(colored)] + ([OTHER] if "Other" in order else [])
    spec = _base(320, {"left": 4, "right": 230, "top": 8, "bottom": 4})
    spec["layer"] = [
        {
            "data": {"values": data},
            "mark": {"type": "area", "interpolate": "monotone", "stroke": "#FCFBF8", "strokeWidth": 1},
            "encoding": {
                "x": {"field": "year", "type": "quantitative", "axis": {"format": "d", "title": None, "tickCount": len(years)}, "scale": {"domain": [years[0], last], "nice": False}},
                "y": {"field": "share", "type": "quantitative", "stack": "zero", "axis": {"format": ".0%", "title": None, "tickCount": 4}},
                "color": {"field": "topic", "type": "nominal", "scale": {"domain": order, "range": colors}},
                "order": {"field": "rank", "type": "quantitative", "sort": "ascending"},  # rank 0 at the bottom, matching the label positions
                "tooltip": [{"field": "topic"}, {"field": "year"}, {"field": "share", "format": ".1%"}],
            },
        },
        {
            "data": {"values": labels},
            "mark": {"type": "text", "align": "left", "dx": 10, "fontSize": 12.5, "fontWeight": 500},
            "encoding": {
                "x": {"field": "year", "type": "quantitative"},
                "y": {"field": "ymid", "type": "quantitative"},
                "text": {"field": "topic"},
                "color": {"field": "topic", "type": "nominal", "scale": {"domain": order, "range": colors}},
            },
        },
    ]
    return spec


def ranked_bars(rows: list[dict], value: str = "papers", highlight: int = 3) -> dict[str, Any]:
    """Horizontal bars, top `highlight` in red, value and share-change labelled at the end."""
    data = []
    for i, r in enumerate(rows):
        d = r["delta"]
        arrow = "▲" if d > 0.002 else ("▼" if d < -0.002 else "•")
        data.append({**r, "rank": i, "label": f"{r[value]:,}  {arrow} {abs(d):.1%}", "hi": i < highlight})
    spec = _base(22 * len(rows) + 10, {"left": 4, "right": 110, "top": 4, "bottom": 4})
    spec["data"] = {"values": data}
    # explicit order: a field-based sort is dropped when Streamlit re-serialises the data
    enc_y = {"field": "name", "type": "nominal", "sort": [r["name"] for r in rows], "axis": {"title": None, "labelLimit": 340, "labelColor": INK, "labelFontSize": 12.5}}
    enc_x = {"field": value, "type": "quantitative", "axis": None}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 14, "cornerRadiusEnd": 2},
         "encoding": {"y": enc_y, "x": enc_x, "color": {"field": "hi", "type": "nominal", "scale": {"domain": [True, False], "range": [RED, GREY]}},
                      "tooltip": [{"field": "name"}, {"field": "papers"}, {"field": "early", "format": ".1%", "title": "early share"}, {"field": "late", "format": ".1%", "title": "late share"}]}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12, "color": MUTED},
         "encoding": {"y": enc_y, "x": enc_x, "text": {"field": "label"}}},
    ]
    return spec


def emerging_heatmap(rows: list[dict], years: list[int]) -> dict[str, Any]:
    """term × year cells shaded by share, first appearance marked."""
    data = []
    for e in rows:
        for s in e["series"]:
            data.append({"term": e["term"], "year": s["year"], "share": s["share"], "first": s["year"] == e["first"]})
    spec = _base(24 * len(rows) + 30, {"left": 4, "right": 4, "top": 4, "bottom": 4})
    spec["data"] = {"values": data}
    spec["layer"] = [
        {"mark": {"type": "rect", "stroke": "#FCFBF8", "strokeWidth": 2, "cornerRadius": 2},
         "encoding": {
             "y": {"field": "term", "type": "nominal", "sort": None, "axis": {"title": None, "labelColor": INK, "labelFontSize": 12.5, "labelLimit": 220}},
             "x": {"field": "year", "type": "ordinal", "axis": {"title": None, "labelExpr": "datum.value % 3 == 0 ? datum.value : ''"}},
             "color": {"field": "share", "type": "quantitative", "scale": {"range": ["#F3F1EC", "#F6C4C1", RED], "domain": [0, 0.005, 0.03], "clamp": True}},
             "tooltip": [{"field": "term"}, {"field": "year"}, {"field": "share", "format": ".1%"}],
         }},
        {"mark": {"type": "text", "fontSize": 10, "color": INK, "text": "✚"}, "transform": [{"filter": "datum.first"}],
         "encoding": {"y": {"field": "term", "type": "nominal", "sort": None}, "x": {"field": "year", "type": "ordinal"}}},
    ]
    return spec
