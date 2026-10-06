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
    # the extremes, when they are not the end points, get a lighter label too (peak above, trough below)
    hi = max(rows, key=lambda r: r[value]); lo = min(rows, key=lambda r: r[value])
    extremes = [r for r in (hi, lo) if r["year"] not in (first, last)]
    layers = [
        {"mark": {"type": "line", "color": color, "strokeWidth": 2, "interpolate": "monotone"}, "encoding": {"x": x, "y": y}},
        {"mark": {"type": "point", "filled": True, "color": color, "size": 28}, "encoding": {"x": x, "y": y}},
        {"mark": {"type": "point", "filled": True, "color": color, "size": 60}, "transform": [ends], "encoding": {"x": x, "y": y}},
        {"mark": {"type": "text", "dy": -12, "color": color, "fontWeight": 600, "fontSize": 12}, "transform": [ends],
         "encoding": {"x": x, "y": y, "text": {"field": value, "format": fmt}}},
    ]
    for r in extremes:
        above = r is hi
        layers.append({"data": {"values": [r]}, "mark": {"type": "text", "dy": -12 if above else 14, "color": MUTED, "fontSize": 11.5},
                       "encoding": {"x": x, "y": y, "text": {"field": value, "format": fmt}}})
    spec["layer"] = layers + [
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


def ranked_bars(rows: list[dict], value: str = "papers", highlight: int = 3, *, show_change: bool = True) -> dict[str, Any]:
    """Horizontal bars, top `highlight` in red, value and share-change labelled at the end."""
    data = []
    for i, r in enumerate(rows):
        d = r["delta"]
        arrow = "▲" if d > 0.002 else ("▼" if d < -0.002 else "•")
        label = f"{r[value]:,}" + (f"  {arrow} {abs(d):.1%}" if show_change else "")
        data.append({**r, "rank": i, "label": label, "hi": i < highlight})
    spec = _base(22 * len(rows) + 10, {"left": 4, "right": 110, "top": 4, "bottom": 4})
    spec["data"] = {"values": data}
    # explicit order: a field-based sort is dropped when Streamlit re-serialises the data
    enc_y = {"field": "name", "type": "nominal", "sort": [r["name"] for r in rows], "axis": {"title": None, "labelLimit": 340, "labelColor": INK, "labelFontSize": 12.5}}
    enc_x = {"field": value, "type": "quantitative", "axis": None}
    spec["layer"] = [
        {"mark": {"type": "bar", "height": 14, "cornerRadiusEnd": 2},
         "encoding": {"y": enc_y, "x": enc_x, "color": {"field": "hi", "type": "nominal", "scale": {"domain": [True, False], "range": [RED, GREY]}},
                      "tooltip": [{"field": "name"}, {"field": "papers"}] + ([{"field": "early", "format": ".1%", "title": "early share"}, {"field": "late", "format": ".1%", "title": "late share"}] if show_change else [])}},
        {"mark": {"type": "text", "align": "left", "dx": 6, "fontSize": 12, "color": MUTED},
         "encoding": {"y": enc_y, "x": enc_x, "text": {"field": "label"}}},
    ]
    return spec


def inst_topic_heatmap(rows: list[dict], insts: list[str], topics: list[str]) -> dict[str, Any]:
    """institution × topic cells shaded by the share of the institution's papers in the
    topic (each row sums to one); the share is printed where it is large enough to read."""
    spec = _base(26 * len(insts) + 70, {"left": 4, "right": 4, "top": 4, "bottom": 4})
    spec["data"] = {"values": rows}
    enc_y = {"field": "name", "type": "nominal", "sort": insts, "axis": {"title": None, "labelColor": INK, "labelFontSize": 12.5, "labelLimit": 320}}
    # column labels: the first two words of the topic label are enough to tell the columns apart
    enc_x = {"field": "topic", "type": "nominal", "sort": topics, "axis": {"title": None, "orient": "top", "labelAngle": -30, "labelAlign": "left", "labelLimit": 200, "labelFontSize": 11.5, "labelPadding": 4,
                                                                           "labelExpr": "join(slice(split(datum.value, ' / '), 0, 2), ' / ')"}}
    spec["layer"] = [
        {"mark": {"type": "rect", "stroke": "#FCFBF8", "strokeWidth": 2, "cornerRadius": 2},
         "encoding": {
             "y": enc_y, "x": enc_x,
             "color": {"field": "share", "type": "quantitative", "scale": {"range": ["#F6F3EE", RED], "domain": [0, 0.6], "clamp": True}},
             "tooltip": [{"field": "name", "title": "institution"}, {"field": "topic"}, {"field": "share", "format": ".0%", "title": "of its papers"}, {"field": "papers"}],
         }},
        {"mark": {"type": "text", "fontSize": 11.5},
         "transform": [{"filter": "datum.share >= 0.1"}],
         "encoding": {"y": enc_y, "x": enc_x, "text": {"field": "share", "format": ".0%"},
                      "color": {"condition": {"test": "datum.share >= 0.3", "value": "#FFFFFF"}, "value": MUTED}}},
    ]
    return spec


def bump_chart(rows: list[dict], years: list[int], n: int) -> dict[str, Any]:
    """Rank of each institution per year among the leading ones; lines that climbed are
    red, lines that slipped are blue, the rest grey; names at the right edge."""
    last = years[-1]
    spec = _base(28 * n + 24, {"left": 20, "right": 240, "top": 8, "bottom": 4})
    spec["data"] = {"values": rows}
    ticks = sorted({*years[::3], last})
    x = {"field": "year", "type": "quantitative", "axis": {"format": "d", "title": None, "values": ticks}, "scale": {"domain": [years[0], last], "nice": False}}
    y = {"field": "rank", "type": "quantitative", "axis": {"title": None, "values": list(range(1, n + 1)), "format": "d", "grid": False, "labelColor": GREY}, "scale": {"domain": [n + 0.5, 0.5], "nice": False}}
    color = {"field": "tone", "type": "nominal", "scale": {"domain": ["up", "down", "flat"], "range": [RED, BLUE, GREY]}}
    tooltip = [{"field": "name"}, {"field": "year"}, {"field": "rank"}, {"field": "papers", "title": "papers (3-yr)"}]
    spec["layer"] = [
        {"mark": {"type": "line", "strokeWidth": 2.4, "interpolate": "monotone"}, "encoding": {"x": x, "y": y, "color": color, "detail": {"field": "name"}}},
        {"mark": {"type": "point", "filled": True, "size": 42, "stroke": "#FCFBF8", "strokeWidth": 1.2}, "encoding": {"x": x, "y": y, "color": color, "tooltip": tooltip}},
        {"mark": {"type": "text", "align": "left", "dx": 10, "fontSize": 12.5, "fontWeight": 500}, "transform": [{"filter": f"datum.year == {last}"}],
         "encoding": {"x": x, "y": y, "text": {"field": "label"},
                      "color": {"condition": {"test": "datum.tone == 'flat'", "value": INK}, "field": "tone", "type": "nominal", "scale": {"domain": ["up", "down", "flat"], "range": [RED, BLUE, GREY]}}}},
    ]
    return spec


WORLD_TOPOJSON = "https://cdn.jsdelivr.net/npm/vega-datasets@2.11.0/data/world-110m.json"


def world_map(rows: list[dict], height: int = 360, years: list[int] | None = None) -> dict[str, Any]:
    """Choropleth of the share of papers with at least one author in each country
    (single-hue sequential scale, square-root so the leader does not wash out the rest).
    With `years`, the rows carry rolling per-year fields (`s2019`, `n2019`) and a `year`
    signal (0 = the pooled view) picks which one is drawn; the page's controls set it."""
    years = years or []
    fields = ["name", "papers", "share"] + [f"{p}{y}" for y in years for p in ("s", "n")]
    vmax = max((r[f] for r in rows for f in fields if f.startswith("s")), default=0.1)
    topo = {"url": WORLD_TOPOJSON, "format": {"type": "topojson", "feature": "countries"}}
    spec = _base(height, {"left": 0, "right": 0, "top": 0, "bottom": 0})
    spec["projection"] = {"type": "equalEarth"}
    spec["config"] = {**CONFIG, "legend": {"disable": False, "labelColor": MUTED, "titleColor": MUTED, "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": "normal", "gradientThickness": 8, "gradientLength": 180}}
    pick = [{"calculate": "datum.share", "as": "v"}, {"calculate": "datum.papers", "as": "np"}]
    if years:
        spec["params"] = [{"name": "year", "value": 0}]
        pick = [{"calculate": "year == 0 ? datum.share : datum['s' + year]", "as": "v"},
                {"calculate": "year == 0 ? datum.papers : datum['n' + year]", "as": "np"}]
    spec["layer"] = [
        {"data": topo, "transform": [{"filter": "datum.id != 10"}], "mark": {"type": "geoshape", "fill": "#EFECE5", "stroke": "#FCFBF8", "strokeWidth": 0.6}},
        {
            "data": topo,
            "transform": [
                {"filter": "datum.id != 10"},
                {"lookup": "id", "from": {"data": {"values": rows}, "key": "id", "fields": fields}},
                {"filter": "isValid(datum.papers) && datum.papers > 0"},
                *pick,
                {"filter": "datum.np > 0"},
            ],
            "mark": {"type": "geoshape", "stroke": "#FCFBF8", "strokeWidth": 0.6},
            "encoding": {
                "color": {"field": "v", "type": "quantitative", "scale": {"type": "sqrt", "domain": [0, vmax], "range": ["#F6D6D4", RED]},
                          "legend": {"title": "share of papers", "orient": "bottom-left", "direction": "horizontal", "format": ".0%",
                                     "values": [0, round(vmax / 4, 2), round(vmax, 2)]}},
                "tooltip": [{"field": "name", "title": "country"}, {"field": "np", "title": "papers"}, {"field": "v", "format": ".1%", "title": "share"}],
            },
        },
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
