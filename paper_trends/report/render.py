"""Render static report pages: `paper-trends report data/ectc.jsonl --name "..." --short ECTC`."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..store import parse_years, read_jsonl
from . import charts
from .build import build_report

HERE = Path(__file__).parent
GROUPS = [
    ("Packaging", ["ectc", "eptc", "icept", "itherm", "irps", "eurosime"]),
    ("Devices & circuits", ["iedm", "isscc", "vlsi", "imw"]),
    ("Other fields", ["cvpr", "interspeech"]),
]
FULL = {
    "ectc": "Electronic Components and Technology Conference",
    "eptc": "Electronics Packaging Technology Conference",
    "icept": "International Conference on Electronic Packaging Technology",
    "itherm": "ITherm: Thermal and Thermomechanical Phenomena in Electronic Systems",
    "irps": "International Reliability Physics Symposium",
    "eurosime": "EuroSimE: Thermal, Mechanical and Multi-Physics Simulation in Microelectronics",
    "iedm": "International Electron Devices Meeting",
    "isscc": "International Solid-State Circuits Conference",
    "vlsi": "Symposium on VLSI Technology and Circuits",
    "imw": "International Memory Workshop",
    "cvpr": "Conference on Computer Vision and Pattern Recognition",
    "interspeech": "Interspeech",
}
SHORT = {"ectc": "ECTC", "eptc": "EPTC", "icept": "ICEPT", "itherm": "ITherm", "irps": "IRPS", "eurosime": "EuroSimE", "iedm": "IEDM",
         "isscc": "ISSCC", "vlsi": "VLSI", "imw": "IMW", "cvpr": "CVPR", "interspeech": "Interspeech"}


def figure_specs(r: dict[str, Any]) -> dict[str, dict]:
    years = r["years"]
    specs: dict[str, dict] = {"fig-papers": charts.trend_line(r["papers_per_year"])}
    for kind, key in (("rise", "rising"), ("fall", "falling")):
        items = r[key]
        ymax = max((s["share"] for t in items for s in t["series"]), default=0.1) * 1.15
        for i, t in enumerate(items, 1):
            specs[f"fig-{kind}-{i}"] = charts.small_multiple(t["series"], years, ymax, charts.RED if kind == "rise" else charts.BLUE)
    if r["emerging"]:
        specs["fig-emerging"] = charts.emerging_heatmap(r["emerging"], years)
    specs["fig-topics"] = charts.streamgraph(r["topic_rows"], [t["label"] for t in r["topics"]], years)
    specs["fig-map"] = charts.world_map(r["country_map"])
    specs["fig-inst"] = charts.ranked_bars(r["institutions"])
    specs["fig-country"] = charts.ranked_bars(r["countries"])
    return specs


def nav_for(available: dict[str, dict]) -> list[tuple[str, list]]:
    nav = []
    for group, slugs in GROUPS:
        items = [(s, SHORT.get(s, s.upper()), available[s]["name"], available[s]["n_papers"]) for s in slugs if s in available]
        if items:
            nav.append((group, items))
    extra = [(s, SHORT.get(s, s.upper()), r["name"], r["n_papers"]) for s, r in available.items() if not any(s in g for _, g in GROUPS)]
    if extra:
        nav.append(("More", extra))
    return nav


def _env() -> Environment:
    return Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))


def _css() -> str:
    return (HERE / "static" / "report.css").read_text(encoding="utf-8")


def render_page(r: dict[str, Any], nav: list | None = None, *, embedded: bool = False, app_links: bool = False) -> str:
    """HTML for one report. `embedded=True` inlines the CSS (for a Streamlit iframe);
    `app_links=True` makes masthead links reload the hosting app (`?conference=<slug>`)."""
    return _env().get_template("report.html.j2").render(
        r=r, nav=nav or [], specs_json=json.dumps(figure_specs(r)), topic_colors=charts.TOPIC_COLORS, other_color=charts.OTHER,
        embedded=embedded, inline_css=_css() if embedded else None, app_links=app_links,
    )


def render_index(nav_full: list, *, embedded: bool = False, app_links: bool = False) -> str:
    return _env().get_template("index.html.j2").render(nav=nav_full, embedded=embedded, inline_css=_css() if embedded else None, app_links=app_links)


def render_site(reports: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    env = _env()
    available = {r["slug"]: r for r in reports}
    nav_full = nav_for(available)
    nav_short = [(g, [(s, short) for s, short, _, _ in items]) for g, items in nav_full]
    for r in reports:
        (out / f"{r['slug']}.html").write_text(render_page(r, nav_short), encoding="utf-8")
        (out / f"{r['slug']}.json").write_text(json.dumps({k: v for k, v in r.items() if k != "topic_rows"}, ensure_ascii=False), encoding="utf-8")
    (out / "index.html").write_text(render_index(nav_full), encoding="utf-8")
    shutil.copy(HERE / "static" / "report.css", out / "report.css")


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends report", description="Render static report pages (HTML) for one or more corpora.")
    p.add_argument("jsonl", type=Path, nargs="+", help="corpus files; the slug is the file stem")
    p.add_argument("--name", action="append", default=[], help="display name per corpus, in order (default: the slug upper-cased)")
    p.add_argument("--years", help="year range, e.g. 2016-2025")
    p.add_argument("--n-topics", type=int, default=8)
    p.add_argument("--out", type=Path, default=Path("site"))
    args = p.parse_args(argv)

    yrs = parse_years(args.years)
    reports = []
    for i, path in enumerate(args.jsonl):
        slug = path.stem
        name = args.name[i] if i < len(args.name) else FULL.get(slug, slug.upper())
        print(f"[report] {slug}: analysing…", file=sys.stderr)
        reports.append(build_report(read_jsonl(path), name=name, slug=slug, years=yrs, n_topics=args.n_topics))
    render_site(reports, args.out)
    print(f"[report] wrote {len(reports)} page(s) + index.html -> {args.out}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
