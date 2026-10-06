"""Render static report pages: `paper-trends report data/ectc.jsonl --name "..." --short ECTC`."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from ..store import parse_years, read_jsonl, read_provenance
from . import charts
from .build import build_report
from ..i18n import language, tr, report_copy, chart_labels

HERE = Path(__file__).parent
TAGLINE = "Publication trends for any academic conference"
# Preset conferences, grouped by field. The tool is not tied to these: they are the pages
# that exist ready-made, and the mix (heavy on semiconductors, where the maintainer works)
# is a choice of examples, not a scope.
GROUPS = [
    ("Semiconductor packaging", ["ectc", "eptc", "icept", "itherm", "irps", "eurosime"]),
    ("Devices & circuits", ["iedm", "isscc", "vlsi", "imw"]),
    ("Computer vision", ["cvpr"]),
    ("Speech", ["interspeech"]),
    ("Robotics", ["icra"]),
    ("Signal processing", ["icassp"]),
    ("Biomedical engineering", ["embc"]),
    ("Security", ["sp"]),
    ("Communications", ["globecom"]),
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
    "icra": "International Conference on Robotics and Automation",
    "icassp": "International Conference on Acoustics, Speech and Signal Processing",
    "embc": "Annual International Conference of the IEEE Engineering in Medicine and Biology Society",
    "sp": "IEEE Symposium on Security and Privacy",
    "globecom": "Global Communications Conference",
}
SHORT = {"ectc": "ECTC", "eptc": "EPTC", "icept": "ICEPT", "itherm": "ITherm", "irps": "IRPS", "eurosime": "EuroSimE", "iedm": "IEDM",
         "isscc": "ISSCC", "vlsi": "VLSI", "imw": "IMW", "cvpr": "CVPR", "interspeech": "Interspeech", "icra": "ICRA",
         "icassp": "ICASSP", "embc": "EMBC", "sp": "IEEE S&P", "globecom": "GLOBECOM"}


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
    if r["topics"] and len(years) > 1:
        specs["fig-topics"] = charts.streamgraph(r["topic_rows"], [t["label"] for t in r["topics"]], years)
    specs["fig-map"] = charts.world_map(r["country_map"], years=years if r.get("map_lines") else None)
    specs["fig-inst"] = charts.ranked_bars(r["institutions"], show_change=len(years) > 1)
    specs["fig-country"] = charts.ranked_bars(r["countries"], show_change=len(years) > 1)
    if r.get("inst_topic"):
        specs["fig-heat"] = charts.inst_topic_heatmap(r["inst_topic"], r["inst_topic_insts"], r["inst_topic_topics"])
    if r.get("inst_ranks"):
        specs["fig-bump"] = charts.bump_chart(r["inst_ranks"], years, len({x["name"] for x in r["inst_ranks"]}))
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
    return Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=True)


def _css() -> str:
    return (HERE / "static" / "report.css").read_text(encoding="utf-8")


def render_page(r: dict[str, Any], nav: list | None = None, *, embedded: bool = False, app_links: bool = False, lang: str = "en") -> str:
    """HTML for one report. `embedded=True` inlines the CSS (for a Streamlit iframe);
    `app_links=True` makes masthead links reload the hosting app (`?conference=<slug>`)."""
    lang = language(lang)
    return _env().get_template("report.html.j2").render(
        r=report_copy(r, lang), lang=lang, _=lambda s: tr(s, lang), nav=nav or [], tagline=TAGLINE, specs=chart_labels(figure_specs(r), lang), topic_colors=charts.TOPIC_COLORS, other_color=charts.OTHER,
        embedded=embedded, inline_css=_css() if embedded else None, app_links=app_links,
        entities=r.get("entities"), map_lines=r.get("map_lines") or {},
        entities_js=(HERE / "static" / "entities.js").read_text(encoding="utf-8"),
        explorer_js=(HERE / "static" / "explorer.js").read_text(encoding="utf-8"),
    )


def render_index(nav_full: list, *, embedded: bool = False, app_links: bool = False, lang: str = "en") -> str:
    lang = language(lang)
    return _env().get_template("index.html.j2").render(nav=nav_full, lang=lang, _=lambda s: tr(s, lang), tagline=TAGLINE, embedded=embedded, inline_css=_css() if embedded else None, app_links=app_links)


def render_site(reports: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    env = _env()
    available = {r["slug"]: r for r in reports}
    nav_full = nav_for(available)
    nav_short = [(g, [(s, short) for s, short, _, _ in items]) for g, items in nav_full]
    for r in reports:
        (out / f"{r['slug']}.html").write_text(render_page(r, nav_short), encoding="utf-8")
        (out / f"{r['slug']}.zh.html").write_text(render_page(r, nav_short, lang="zh"), encoding="utf-8")
        (out / f"{r['slug']}.json").write_text(json.dumps({k: v for k, v in r.items() if k not in ("topic_rows", "entities")}, ensure_ascii=False), encoding="utf-8")
    (out / "index.html").write_text(render_index(nav_full), encoding="utf-8")
    (out / "index.zh.html").write_text(render_index(nav_full, lang="zh"), encoding="utf-8")
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
        try:
            reports.append(build_report(read_jsonl(path), name=name, slug=slug, years=yrs, n_topics=args.n_topics,
                                        provenance=read_provenance(path)))
        except ValueError as exc:
            print(f"[report] {slug}: {exc}", file=sys.stderr)
            return 2
    render_site(reports, args.out)
    print(f"[report] wrote {len(reports)} page(s) + index.html -> {args.out}/", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
