"""paper-trends — Streamlit UI. Run with:  uv run streamlit run app.py"""

from __future__ import annotations

import os
import threading
from urllib.parse import urlencode
from pathlib import Path

import pandas as pd
import streamlit as st

from paper_trends import compare, frames
from paper_trends.report import charts
from paper_trends.fetch import coverage_table, fetch_conference, resolve_venue
from paper_trends.keywords import compute_trends, papers_with
from paper_trends.openalex import OpenAlex, OpenAlexError
from paper_trends.rank import ENTITIES, compute_ranking
from paper_trends.report.build import build_report, country_name
from paper_trends.report.render import FULL, SHORT, nav_for, render_page
from paper_trends.store import filter_years, read_jsonl, write_jsonl
from paper_trends.text import load_stopwords
from paper_trends.topics import compute_nmf, compute_openalex

DATA_DIR = Path("data")
PRESETS = {
    # ---- packaging, assembly, thermal, reliability -----------------------------------
    "Packaging · ECTC — Electronic Components and Technology Conference": {
        "query": "Electronic Components and Technology Conference", "doi_prefixes": ["10.1109/ectc"], "slug": "ectc",
    },
    "Packaging · EPTC — Electronics Packaging Technology Conference": {
        "query": "Electronics Packaging Technology Conference", "doi_prefixes": ["10.1109/eptc"], "slug": "eptc",
    },
    "Packaging · ICEPT — International Conference on Electronic Packaging Technology": {
        "query": "International Conference on Electronic Packaging Technology", "doi_prefixes": ["10.1109/icept"], "slug": "icept",
    },
    "Packaging · ITherm — Thermal and Thermomechanical Phenomena in Electronic Systems": {
        "query": "Thermal and Thermomechanical Phenomena in Electronic Systems", "doi_prefixes": ["10.1109/itherm"], "slug": "itherm",
    },
    "Packaging · IRPS — International Reliability Physics Symposium": {
        "query": "International Reliability Physics Symposium", "doi_prefixes": ["10.1109/irps"], "slug": "irps",
    },
    "Packaging · EuroSimE — Thermal, Mechanical and Multi-Physics Simulation in Microelectronics": {
        "query": "Thermal, Mechanical and Multi-Physics Simulation and Experiments in Microelectronics and Microsystems",
        "doi_prefixes": ["10.1109/eurosime"], "slug": "eurosime",
    },
    # ---- devices and circuits ----------------------------------------------------------
    "Devices · IEDM — International Electron Devices Meeting": {
        "query": "International Electron Devices Meeting", "doi_prefixes": ["10.1109/iedm"], "slug": "iedm",
    },
    "Circuits · ISSCC — International Solid-State Circuits Conference": {
        "query": "International Solid-State Circuits Conference", "doi_prefixes": ["10.1109/isscc"], "slug": "isscc",
    },
    "Devices · VLSI Symposium — Symposium on VLSI Technology and Circuits": {
        "query": "Symposium on VLSI Technology and Circuits",
        # the DOI prefix changed almost every year (IEEE / JSAP alternate as publisher)
        "doi_prefixes": [f"{reg}/{acr}" for reg in ("10.1109", "10.23919")
                         for acr in ("vlsit", "vlsic", "vlsitechnology", "vlsicircuits", "vlsitechnologyandcir")],
        "slug": "vlsi",
    },
    "Devices · IMW — International Memory Workshop": {
        "query": "International Memory Workshop", "doi_prefixes": ["10.1109/imw"], "slug": "imw",
    },
    # ---- other fields: the tool is not semiconductor-specific ---------------------------
    "Other fields · CVPR — Conference on Computer Vision and Pattern Recognition": {
        "query": "Conference on Computer Vision and Pattern Recognition", "doi_prefixes": ["10.1109/cvpr"], "slug": "cvpr",
    },
    "Other fields · Interspeech — Conference of the International Speech Communication Association": {
        "query": "Interspeech", "doi_prefixes": ["10.21437/interspeech"], "slug": "interspeech",
    },
}
FETCH_YEARS = (2016, 2026)

st.set_page_config(page_title="paper-trends", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
    #MainMenu, [data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; height: 2.6rem; pointer-events: none; }
    [data-testid="stToolbar"] { pointer-events: none; }
    .block-container { padding-top: 0.2rem; padding-bottom: 0; max-width: 1240px; }
    iframe[title="st.iframe"] { display: block; }
    /* masthead rendered by Streamlit (outside the iframe, so links can change the query string) */
    .pt-masthead { display: flex; align-items: baseline; gap: 28px; flex-wrap: wrap; padding: 10px 24px 12px; margin: 0; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", system-ui, sans-serif; }
    .pt-masthead .brand { font-family: Newsreader, Georgia, serif; font-size: 20px; font-weight: 600; color: #1B1B1B; text-decoration: none; letter-spacing: -0.01em; }
    .pt-masthead .venues { display: flex; gap: 4px 18px; flex-wrap: wrap; font-size: 13.5px; color: #5C5C5C; }
    .pt-masthead .group { color: #8A877F; text-transform: uppercase; letter-spacing: 0.08em; font-size: 11px; margin-right: 2px; }
    .pt-masthead a { color: inherit; text-decoration: none; padding-bottom: 2px; border-bottom: 2px solid transparent; }
    .pt-masthead a:hover { color: #E3120B; }
    .pt-masthead a.current { color: #E3120B; border-bottom-color: #E3120B; }
    [data-testid="stExpandSidebarButton"] { display: none !important; }
    .st-key-controls_search { padding: 10px 24px 0; }
    .st-key-controls_row { padding: 6px 24px 0; }
    /* search box: white, hairline border, red underline on focus */
    .st-key-controls_search div[data-baseweb="input"], .st-key-controls_search div[data-baseweb="input"] > div, .st-key-controls_search div[data-baseweb="base-input"] { background-color: #FFFFFF !important; border-color: #E6E3DC !important; border-radius: 2px !important; }
    .st-key-controls_search div[data-baseweb="input"]:focus-within { border-color: #1B1B1B !important; box-shadow: none !important; }
    .st-key-controls_search input { font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 14.5px !important; color: #1B1B1B !important; background: #FFFFFF !important; }
    /* buttons: ink, square corners, quiet */
    .st-key-fetch_btn button, .st-key-fetch_prefix_btn button { font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 13.5px !important; border-radius: 2px !important; border: 1px solid #E6E3DC !important; background: #FFFFFF !important; color: #1B1B1B !important; box-shadow: none !important; }
    .st-key-fetch_btn button, .st-key-fetch_prefix_btn button { background: #1B1B1B !important; color: #FFFFFF !important; border-color: #1B1B1B !important; padding: 6px 18px !important; letter-spacing: 0.02em; }
    .st-key-fetch_btn button:hover, .st-key-fetch_prefix_btn button:hover { background: #E3120B !important; border-color: #E3120B !important; }
    /* controls row: text links, no widgets */
    .pt-controls { font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 13.5px; color: #5C5C5C; padding: 12px 24px 0; display: flex; align-items: baseline; flex-wrap: wrap; gap: 2px 14px; }
    .pt-controls .lbl { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #8A877F; margin-right: 4px; }
    .pt-controls .lbl.gap { margin-left: 22px; }
    .pt-controls a { color: #5C5C5C; text-decoration: none; padding-bottom: 2px; border-bottom: 2px solid transparent; }
    .pt-controls a:hover { color: #E3120B; }
    .pt-controls a.current { color: #E3120B; border-bottom-color: #E3120B; }
    .st-key-custom_period { padding: 4px 24px 0; max-width: 520px; }
    .st-key-options_form { margin: 10px 24px 0; padding: 12px 18px 6px; border: 1px solid #E6E3DC; border-radius: 2px; background: #FFFFFF; }
    .pt-options-head { font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #8A877F; margin-bottom: 4px; }
    .pt-options-head a { color: #E3120B; text-decoration: none; margin-left: 12px; text-transform: none; letter-spacing: 0; font-size: 13px; }
    .st-key-options_form label p, .st-key-options_form label { font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 13px !important; color: #5C5C5C !important; }
    .st-key-options_form div[data-baseweb="input"], .st-key-options_form div[data-baseweb="input"] > div, .st-key-options_form div[data-baseweb="base-input"], .st-key-options_form div[data-baseweb="textarea"], .st-key-options_form textarea { background-color: #FCFBF8 !important; border-color: #E6E3DC !important; border-radius: 2px !important; font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 14px !important; }
    .st-key-refresh_btn button { font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 13px !important; border-radius: 2px !important; border: 1px solid #E6E3DC !important; background: #FFFFFF !important; color: #1B1B1B !important; }
    .st-key-refresh_btn button:hover { border-color: #1B1B1B !important; }
    /* explore view header, in the report's voice */
    .pt-head { font-family: "IBM Plex Sans", system-ui, sans-serif; padding: 34px 24px 0; }
    .pt-head .kicker { font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin-bottom: 14px; }
    .pt-head h1 { font-family: Newsreader, Georgia, serif; font-weight: 500; font-size: clamp(34px, 4.6vw, 54px); line-height: 1.05; letter-spacing: -0.015em; margin: 0 0 18px; max-width: 18ch; color: #1B1B1B; padding: 0; }
    .pt-head .meta { color: #5C5C5C; font-size: 14.5px; display: flex; gap: 22px; flex-wrap: wrap; padding-bottom: 28px; border-bottom: 1px solid #1B1B1B; }
    .pt-head .meta b { color: #1B1B1B; font-weight: 600; }
    .pt-sections { padding-top: 16px !important; padding-bottom: 8px; }
    .pt-h2 { font-family: Newsreader, Georgia, serif !important; font-weight: 500 !important; font-size: 26px !important; letter-spacing: -0.01em; margin: 26px 0 4px !important; padding: 0 !important; color: #1B1B1B; }
    .pt-lede { font-family: "IBM Plex Sans", system-ui, sans-serif; color: #5C5C5C; font-size: 14px; max-width: 72ch; margin: 0 0 12px; }
    .block-container [data-testid="stMarkdownContainer"] p { font-family: "IBM Plex Sans", system-ui, sans-serif; }
    /* explore widgets: quiet */
    .block-container label p, .block-container label { font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 12.5px !important; color: #5C5C5C !important; }
    .block-container div[data-baseweb="select"] > div, .block-container div[data-baseweb="input"] > div, .block-container div[data-baseweb="textarea"] { background-color: #FFFFFF !important; border-color: #E6E3DC !important; border-radius: 2px !important; font-family: "IBM Plex Sans", system-ui, sans-serif !important; font-size: 14px !important; }
    .block-container [data-testid="stDataFrame"] { border: 1px solid #E6E3DC; border-radius: 2px; }
    .block-container [data-testid="stToggle"] label p { font-size: 13px !important; }
    .block-container [data-testid="stSlider"] { padding-top: 4px; }
    /* figures in Explore, same anatomy as the report */
    .pt-fig { display: flex; flex-direction: column; gap: 2px; margin: 8px 0 6px; font-family: "IBM Plex Sans", system-ui, sans-serif; }
    .pt-fig .headline { font-family: Newsreader, Georgia, serif; font-size: 19px; font-weight: 500; line-height: 1.25; color: #1B1B1B; }
    .pt-fig .sub { color: #5C5C5C; font-size: 13.5px; }
    .pt-source { font-family: "IBM Plex Sans", system-ui, sans-serif; color: #8A877F; font-size: 12.5px; margin: 2px 0 14px; }
    .pt-sm { border-top: 2px solid #1B1B1B; padding-top: 6px; margin-top: 10px; font-family: "IBM Plex Sans", system-ui, sans-serif; }
    .pt-sm .term { font-family: Newsreader, Georgia, serif; font-size: 17px; font-weight: 500; line-height: 1.2; margin: 0 0 2px; color: #1B1B1B; }
    .pt-sm .move { font-size: 12.5px; color: #5C5C5C; margin: 0; }
    [data-testid="stVegaLiteChart"] { margin-top: -6px; }
    /* resolution card */
    .pt-found { font-family: "IBM Plex Sans", system-ui, sans-serif; margin: 14px 24px 0; padding: 4px 0 4px 18px; border-left: 3px solid #E3120B; max-width: 820px; }
    .pt-found .kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin-bottom: 4px; }
    .pt-found .name { font-family: Newsreader, Georgia, serif; font-size: 26px; font-weight: 500; line-height: 1.15; color: #1B1B1B; letter-spacing: -0.01em; }
    .pt-found .meta { color: #5C5C5C; font-size: 14px; margin-top: 6px; }
    .pt-found .warn { color: #1B1B1B; font-size: 14px; margin-top: 8px; }
    .pt-found .warn b { color: #E3120B; }
    .st-key-fetch_row { padding: 10px 24px 4px 45px; }
    .pt-note { font-family: "IBM Plex Sans", system-ui, sans-serif; color: #5C5C5C; font-size: 14px; padding: 4px 24px 0; }
    /* home page, rendered by Streamlit so its links can change the query string */
    .pt-home { font-family: "IBM Plex Sans", system-ui, sans-serif; color: #1B1B1B; padding: 8px 24px 40px; max-width: 1120px; }
    .pt-home .kicker { font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin: 12px 0 14px; }
    .pt-home h1 { font-family: Newsreader, Georgia, serif; font-weight: 500; font-size: clamp(34px, 4.6vw, 54px); line-height: 1.05; letter-spacing: -0.015em; margin: 0 0 18px; max-width: 18ch; color: #1B1B1B; }
    .pt-home .lede { color: #5C5C5C; font-size: 16px; max-width: 66ch; margin: 0 0 28px; padding-bottom: 28px; border-bottom: 1px solid #1B1B1B; }
    .pt-home h2 { font-family: Newsreader, Georgia, serif; font-weight: 500; font-size: 30px; letter-spacing: -0.01em; margin: 44px 0 8px; color: #1B1B1B; }
    .pt-home ul { list-style: none; margin: 0; padding: 0; max-width: 58ch; font-family: Newsreader, Georgia, serif; font-size: 22px; line-height: 1.45; }
    .pt-home li { padding: 14px 0; border-bottom: 1px solid #E6E3DC; }
    .pt-home li:first-child { border-top: 1px solid #E6E3DC; }
    .pt-home li a { color: #1B1B1B; text-decoration: none; border-bottom: 1px solid #E6E3DC; }
    .pt-home li a:hover { border-bottom-color: #E3120B; }
    .pt-home li a em { font-style: normal; color: #E3120B; font-weight: 600; }
    .pt-home li .n { color: #8A877F; font-family: "IBM Plex Sans", system-ui, sans-serif; font-size: 14px; margin-left: 8px; }
    .pt-home p { font-size: 16px; color: #5C5C5C; max-width: 66ch; }
    </style>""",
    unsafe_allow_html=True,
)


def home_page(available: dict[str, dict]) -> str:
    parts = [
        '<div class="pt-home"><div class="kicker">Publication trends for academic conferences</div>',
        "<h1>What a field talks about, year by year</h1>",
        '<p class="lede">Every paper of a conference from OpenAlex, read as rising and fading phrases, topic shifts and who publishes. Pick a conference.</p>',
    ]
    for group, items in nav_for(available):
        parts.append(f"<h2>{group}</h2><ul>")
        for slug_, short, name, n in items:
            parts.append(f'<li><a href="?conference={slug_}" target="_self"><em>{short}</em> — {name}</a><span class="n">{n:,} papers</span></li>')
        parts.append("</ul>")
    parts.append(
        "<h2>Your own conference</h2><p>Type any conference name in the search box above, as OpenAlex spells it, and press Enter; if the name "
        "does not match an OpenAlex source, add its DOI prefix under Options. Fetching takes a minute or two for most venues, and the data stays "
        "cached on this machine. On a conference page, switch the view to <b>Explore</b> for tables, the papers behind any term, and cross-conference comparison.</p></div>"
    )
    return "".join(parts)


def masthead(available: dict[str, dict], current: str) -> str:
    parts = ['<nav class="pt-masthead"><a class="brand" href="?" target="_self">paper-trends</a><div class="venues">']
    for group, items in nav_for(available):
        parts.append(f'<span class="group">{group}</span>')
        for slug_, short, _, _ in items:
            cls = ' class="current"' if slug_ == current else ""
            parts.append(f'<a href="?conference={slug_}" target="_self"{cls}>{short}</a>')
    parts.append("</div></nav>")
    return "".join(parts)

# OpenAlex credentials: environment first, then Streamlit secrets (hosted demo).
for _var in ("OPENALEX_MAILTO", "OPENALEX_API_KEY"):
    if not os.environ.get(_var):
        try:
            os.environ[_var] = st.secrets[_var]
        except Exception:
            pass


# ---- data access -------------------------------------------------------------------


@st.cache_resource
def fetch_lock() -> threading.Lock:
    return threading.Lock()


def corpus_path(slug: str) -> Path:
    return DATA_DIR / f"{slug}.jsonl"


@st.cache_data(show_spinner=False)
def load_records(path: str, mtime: float) -> list[dict]:
    return read_jsonl(Path(path))


@st.cache_data(show_spinner=False)
def corpus_size(path: str, mtime: float) -> int:
    with open(path, "rb") as fh:
        return sum(1 for line in fh if line.strip())


def available_corpora() -> dict[str, dict]:
    """Preset conferences that have data on this machine, for the masthead and the home page."""
    out = {}
    for label, cfg in PRESETS.items():
        cp = corpus_path(cfg["slug"])
        if cp.exists():
            out[cfg["slug"]] = {"name": cfg["query"] if cfg["slug"] not in FULL else FULL[cfg["slug"]], "n_papers": corpus_size(str(cp), cp.stat().st_mtime)}
    return out


def records_for(slug: str) -> list[dict] | None:
    p = corpus_path(slug)
    if not p.exists():
        return None
    return load_records(str(p), p.stat().st_mtime)


def run_fetch(query: str, doi_prefixes: list[str], slug: str) -> None:
    lock = fetch_lock()
    if not lock.acquire(blocking=False):
        st.warning("Another fetch is running on this server. Please retry in a minute.")
        return
    try:
        with st.status(f"Fetching “{query}” from OpenAlex…", expanded=True) as status:
            lines: list[str] = []
            box = st.empty()

            def log(msg: str) -> None:
                lines.append(msg)
                box.code("\n".join(lines[-12:]))

            client = OpenAlex()
            records = fetch_conference(client, query, doi_prefix=doi_prefixes, years=FETCH_YEARS, log=log)
            write_jsonl(records, corpus_path(slug))
            status.update(label=f"Fetched {len(records)} papers → {corpus_path(slug)}", state="complete", expanded=False)
        st.code(coverage_table(records))
        load_records.clear()
        st.rerun()
    except OpenAlexError as e:
        st.error(str(e))
    except Exception as e:  # never dump a traceback (it would include request URLs) into the UI
        st.error(f"Fetch failed: {type(e).__name__}. Check your network and try again in a minute.")
    finally:
        lock.release()


# ---- cached analyses ---------------------------------------------------------------


@st.cache_data(show_spinner="Counting keywords…")
def cached_keywords(path: str, mtime: float, years: tuple[int, int], text: str, ngram: tuple[int, int], extra_stop: str):
    recs = filter_years(load_records(path, mtime), years)
    stop = load_stopwords(extra_stop.split())
    return compute_trends(recs, text=text, n_min=ngram[0], n_max=ngram[1], stopwords=stop)


@st.cache_data(show_spinner="Searching papers…")
def cached_papers_with(path: str, mtime: float, years: tuple[int, int], term: str, text: str):
    return papers_with(filter_years(load_records(path, mtime), years), term, text)


@st.cache_data(show_spinner="Fitting topic model…")
def cached_topics(path: str, mtime: float, years: tuple[int, int], method: str, n_topics: int, extra_stop: str):
    recs = filter_years(load_records(path, mtime), years)
    if method == "nmf":
        return compute_nmf(recs, n_topics=n_topics, stopwords=load_stopwords(extra_stop.split()))
    return compute_openalex(recs, level="subfield" if method.endswith("subfield") else "topic")


@st.cache_data(show_spinner="Looking the conference up in OpenAlex…", ttl=3600)
def cached_resolve(text: str) -> dict | None:
    try:
        return resolve_venue(OpenAlex(), text)
    except OpenAlexError as e:
        return {"error": str(e)}


@st.cache_data(show_spinner="Writing the report…")
def cached_report_html(path: str, mtime: float, years: tuple[int, int], name: str, slug: str, extra_stop: str) -> str:
    recs = load_records(path, mtime)
    r = build_report(recs, name=name, slug=slug, years=years, stopwords=load_stopwords(extra_stop.split()))
    return render_page(r, None, embedded=True, app_links=True)


@st.cache_data(show_spinner="Ranking…")
def cached_ranking(path: str, mtime: float, years: tuple[int, int], entity: str, roll_up: bool = False):
    return compute_ranking(filter_years(load_records(path, mtime), years), entity, roll_up=roll_up)


# ---- charts: the report's Vega-Lite specs, rendered by Streamlit -------------------------


def vl(spec: dict, key: str | None = None) -> None:
    st.vega_lite_chart(spec, width="stretch", theme=None, key=key)


def source_line() -> None:
    st.markdown('<p class="pt-source">Source: OpenAlex · paper-trends</p>', unsafe_allow_html=True)


def figure_head(title: str, sub: str | None = None) -> None:
    st.markdown(f'<div class="pt-fig"><span class="headline">{title}</span>' + (f'<span class="sub">{sub}</span>' if sub else "") + "</div>", unsafe_allow_html=True)


def small_multiples(items: list[dict], years: list[int], color: str, per_row: int = 4) -> None:
    """items: {term, early, late, series}. Same layout as the report's rising/fading grids."""
    ymax = max((pt["share"] for it in items for pt in it["series"]), default=0.1) * 1.15
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, it in zip(cols, items[i : i + per_row]):
            with col:
                st.markdown(f'<div class="pt-sm" style="border-top-color: {color}"><p class="term">{it["term"]}</p>'
                            f'<p class="move">{it["early"]:.1%} → <span style="color: {color}; font-weight: 600">{it["late"]:.1%}</span></p></div>', unsafe_allow_html=True)
                vl(charts.small_multiple(it["series"], years, ymax, color), key=f"sm-{color}-{it['term']}")


def ranking_rows(rk, keys: list[str], value: str = "papers") -> list[dict]:
    rows = []
    for k in keys:
        e, l, d = rk.momentum(k)
        rows.append({"name": rk.names[k], "papers": rk.total(k), "citations": rk.citations.get(k, 0), "early": e, "late": l, "delta": d})
    return rows


def pct_cols(df: pd.DataFrame, cols) -> dict:
    return {c: st.column_config.NumberColumn(format="%.1f%%") for c in cols}


def as_pct(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = out[c] * 100
    return out


# ---- sidebar -----------------------------------------------------------------------

# ---- selection: ?conference=<preset slug> | ?q=<custom name>[&prefix=...] | nothing = home ---------
wanted = st.query_params.get("conference", "")
custom_q = st.query_params.get("q", "")
custom_prefix = st.query_params.get("prefix", "")
available = available_corpora()

masthead_slot = st.empty()  # filled after the search row is resolved, so a new search un-highlights the old venue

# search row: any conference in OpenAlex (the only Streamlit widget on the page)
with st.container(key="controls_search"):
    typed = st.text_input("Search", value=custom_q, placeholder="Any conference in OpenAlex — an acronym like DAC or ISCAS, or the name as OpenAlex spells it",
                          label_visibility="collapsed", key="search")
    if typed.strip() and typed.strip() != custom_q:
        # a new search replaces whatever was selected; update the URL in this run (no st.rerun —
        # a rerun issued right after changing query params can drop the URL update)
        st.query_params.clear()
        shortcut = next((v["slug"] for k, v in PRESETS.items() if typed.strip().lower() in {v["slug"], k.split(" — ")[0].split("· ")[-1].lower(), v["query"].lower()}), None)
        if shortcut:
            st.query_params["conference"] = shortcut
            wanted, custom_q, custom_prefix = shortcut, "", ""
        else:
            st.query_params["q"] = typed.strip()
            custom_q, wanted, custom_prefix = typed.strip(), "", ""

# URL state beyond the selection
period_key = st.query_params.get("period", "10")
view_key = st.query_params.get("view", "report")
show_options = st.query_params.get("options") == "1"


def link(**changes: str | None) -> str:
    """Current URL with some query parameters changed; None removes one."""
    params = {k: v for k, v in st.query_params.to_dict().items()}
    for k, v in changes.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = v
    return "?" + urlencode(params) if params else "?"


def links_row(items: list[tuple[str, str, bool]]) -> str:
    """items: (label, href, is_current)."""
    return "".join(f'<a href="{h}" target="_self" class="{"current" if c else ""}">{l}</a>' for l, h, c in items)


# options form (DOI prefix, stopwords, refresh) — shown only when asked for
extra_stop = st.session_state.get("extra_stop_saved", "")
doi_prefix_in = custom_prefix
opt_refresh = False
if show_options:
    with st.container(key="options_form"):
        st.markdown('<div class="pt-options-head">Options <a href="' + link(options=None) + '" target="_self">close</a></div>', unsafe_allow_html=True)
        o1, o2 = st.columns([1, 1])
        doi_prefix_in = o1.text_input("DOI prefix(es) for a custom conference, space-separated", value=custom_prefix, placeholder="10.1109/dac")
        if doi_prefix_in.strip() != custom_prefix:
            st.query_params["prefix"] = doi_prefix_in.strip()
        stop_in = o2.text_area("Extra stopwords, one per line", value=extra_stop, height=68, help="Words to ignore in keyword and topic analyses, e.g. your field's boilerplate.")
        if stop_in != extra_stop:
            st.session_state["extra_stop_saved"] = stop_in
            extra_stop = stop_in
        opt_refresh = st.button("Refresh data from OpenAlex", key="refresh_btn")

masthead_slot.markdown(masthead(available, wanted), unsafe_allow_html=True)
preset = next((v for v in PRESETS.values() if v["slug"] == wanted), None)
if preset:
    query, doi_prefixes, slug = preset["query"], preset["doi_prefixes"], preset["slug"]
elif custom_q:
    resolved = cached_resolve(custom_q) or {}
    if "error" in resolved:
        st.markdown(f'<div class="pt-note">{resolved["error"]}</div>', unsafe_allow_html=True)
        resolved = {}
    query = resolved.get("name") or custom_q
    doi_prefixes = (doi_prefix_in or custom_prefix).split() or resolved.get("doi_prefixes", [])
    slug = resolved.get("slug") or "".join(ch for ch in custom_q.lower().replace(" ", "-") if ch.isalnum() or ch == "-")[:40]
else:
    query = slug = ""
    doi_prefixes = []

records = records_for(slug) if slug else None

if opt_refresh and slug:
    run_fetch(query, doi_prefixes, slug)

if not records:
    if slug and custom_q and not resolved:
        st.markdown(f'<div class="pt-found"><div class="kicker">Not found</div><div class="name">{custom_q}</div>'
                    f'<div class="meta">Nothing in OpenAlex matches this. Try the full name as OpenAlex spells it, or add the venue\'s DOI prefix under Options and fetch anyway.</div></div>', unsafe_allow_html=True)
        if doi_prefixes:
            with st.container(key="fetch_row"):
                if st.button("Fetch by DOI prefix", key="fetch_prefix_btn"):
                    run_fetch(query, doi_prefixes, slug)
    elif slug:
        if custom_q and resolved:
            meta = f"About {resolved['n_papers']:,} papers since 2016" + (f" · DOI prefix {' '.join(resolved['doi_prefixes'])}" if resolved.get("doi_prefixes") else "") + " · not on this machine yet"
            warn = ""
            if resolved.get("ambiguous"):
                warn = '<div class="warn"><b>Shared prefix.</b> This DOI prefix is used by several venues: ' + "; ".join(f"{n} ({sh:.0%})" for n, sh in resolved["candidates"]) + ". The fetch will include all of them.</div>"
            card = f'<div class="pt-found"><div class="kicker">Found in OpenAlex</div><div class="name">{resolved["name"]}</div><div class="meta">{meta}</div>{warn}</div>'
        else:
            card = f'<div class="pt-found"><div class="kicker">Not fetched yet</div><div class="name">{query}</div><div class="meta">Not on this machine yet.</div></div>'
        st.markdown(card, unsafe_allow_html=True)
        with st.container(key="fetch_row"):
            b1, b2 = st.columns([1, 4])
            if b1.button("Fetch from OpenAlex", key="fetch_btn"):
                run_fetch(query, doi_prefixes, slug)
            b2.markdown('<div style="font-family: IBM Plex Sans, system-ui, sans-serif; color: #8A877F; font-size: 13px; padding-top: 8px">One to fifteen minutes depending on the venue\'s size; the data is then cached on this machine.</div>', unsafe_allow_html=True)
    st.markdown(home_page(available), unsafe_allow_html=True)
    st.stop()

# ---- controls row: period and view as links, not widgets ---------------------------
all_years = sorted({r["publication_year"] for r in records if r.get("publication_year")})
cov = frames.coverage_frame(records)
good = cov[cov["coverage"] >= 0.5]["year"].tolist() or all_years
last_good = good[-1]
periods = {
    "10": (f"Last 10 years", (max(good[0], last_good - 9), last_good)),
    "5": ("Last 5 years", (max(good[0], last_good - 4), last_good)),
    "all": (f"All {all_years[0]}–{all_years[-1]}", (all_years[0], all_years[-1])),
    "custom": ("Custom", None),
}
if period_key not in periods:
    period_key = "10"
mode = "Explore" if view_key == "explore" else "Report"
row = (
    '<div class="pt-controls"><span class="lbl">Period</span>'
    + links_row([(lbl, link(period=k), k == period_key) for k, (lbl, _) in periods.items()])
    + '<span class="lbl gap">View</span>'
    + links_row([("Report", link(view=None), mode == "Report"), ("Explore", link(view="explore"), mode == "Explore")])
    + '<span class="lbl gap"></span>' + links_row([("Options", link(options="1"), show_options)])
    + "</div>"
)
st.markdown(row, unsafe_allow_html=True)
if period_key == "custom":
    with st.container(key="custom_period"):
        years = st.slider("Years", all_years[0], all_years[-1], (all_years[0], all_years[-1]), label_visibility="collapsed")
else:
    years = periods[period_key][1]
low = cov[(cov["year"] >= years[0]) & (cov["year"] <= years[1]) & (cov["coverage"] < 0.5)]["year"].tolist()
if low:
    st.markdown(f'<div class="pt-note">Abstracts are mostly missing for {", ".join(map(str, low))}; text analyses under-count those years.</div>', unsafe_allow_html=True)

path, mtime = str(corpus_path(slug)), corpus_path(slug).stat().st_mtime
recs = filter_years(records, years)
cov_y = frames.coverage_frame(recs)

if mode == "Report":
    st.iframe(cached_report_html(path, mtime, years, query, slug, extra_stop), height="content")
    st.stop()

section = st.query_params.get("section", "overview")
SECTIONS = [("overview", "Overview"), ("keywords", "Keywords"), ("topics", "Topics"), ("rankings", "Rankings"), ("compare", "Compare"), ("data", "Data")]
if section not in dict(SECTIONS):
    section = "overview"
n_inst = len(cached_ranking(path, mtime, years, "institution").by_year)
st.markdown(
    f'<div class="pt-head"><div class="kicker">Explore · {years[0]}–{years[1]}</div><h1>{query}</h1>'
    f'<div class="meta"><span><b>{len(recs):,}</b> papers</span><span><b>{years[1] - years[0] + 1}</b> editions</span>'
    f'<span><b>{cov_y["abstracts"].sum() / max(len(recs), 1):.0%}</b> with abstracts</span><span><b>{n_inst:,}</b> institutions</span></div></div>'
    + '<div class="pt-controls pt-sections">' + links_row([(lbl, link(section=None if k == "overview" else k), k == section) for k, lbl in SECTIONS]) + "</div>",
    unsafe_allow_html=True,
)


def h2(text: str, lede: str | None = None) -> None:
    st.markdown(f'<h2 class="pt-h2">{text}</h2>' + (f'<p class="pt-lede">{lede}</p>' if lede else ""), unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<p class="pt-lede">{text}</p>', unsafe_allow_html=True)


if section == "overview":
    a, b = st.columns(2)
    rows_y = cov_y.to_dict("records")
    with a:
        figure_head("Papers per year")
        vl(charts.papers_bars(rows_y, "papers", "d", 120), key="ov-papers")
    with b:
        figure_head("Abstract coverage", "Share of each year's papers with an abstract in OpenAlex")
        vl(charts.papers_bars(rows_y, "coverage", ".0%", 120), key="ov-cov")
    rk_c = cached_ranking(path, mtime, years, "country")
    top_c = rk_c.top(12)
    a2, b2 = st.columns(2)
    with a2:
        figure_head("Papers by country", "A paper counts once per country; the arrow is the change in share between the two halves of the period")
        vl(charts.ranked_bars([{**r, "name": country_name(r["name"])} for r in ranking_rows(rk_c, top_c)]), key="ov-country")
        source_line()
    with b2:
        figure_head("By year")
        st.dataframe(frames.ranking_table(rk_c, top_c), hide_index=True, width="stretch")

if section == "keywords":
    o1, o2, o3 = st.columns([1, 1, 2])
    ngram = o1.selectbox("N-grams", ["1–3", "2–3", "1"], index=1)
    text_mode = o2.selectbox("Text", ["title+abstract", "title"])
    ng = {"1–3": (1, 3), "2–3": (2, 3), "1": (1, 1)}[ngram]
    kt = cached_keywords(path, mtime, years, text_mode, ng, extra_stop)
    rising = kt.rising(15, min_total=10)
    falling = kt.falling(15, min_total=10)
    default_terms = [t for t, *_ in rising[:5]]
    terms = o3.multiselect("Plot terms", kt.top_terms(300), default=default_terms)
    if terms:
        figure_head("Share of papers mentioning the phrase", f"{years[0]}–{years[1]}; the number at the end of each line is the latest year")
        small_multiples([{"term": t, "early": kt.momentum(t)[0], "late": kt.momentum(t)[1], "series": [{"year": y, "share": kt.share(t, y), "papers": kt.doc_freq[t].get(y, 0)} for y in kt.years]} for t in terms], kt.years, charts.RED)
        source_line()
    r, f = st.columns(2)
    r.markdown('<h2 class=\"pt-h2\">' + "Rising" + '</h2>', unsafe_allow_html=True)
    r.dataframe(as_pct(frames.movers_table(rising), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    f.markdown('<h2 class=\"pt-h2\">' + "Falling" + '</h2>', unsafe_allow_html=True)
    f.dataframe(as_pct(frames.movers_table(falling), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    h2("Emerging")
    emerging = kt.emerging(15, min_total=10)
    st.dataframe(
        as_pct(pd.DataFrame(emerging, columns=["term", "first seen", "early", "late"]), ["early", "late"]),
        hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late"]),
    )
    note("Near-absent in the first half of the range, at least 1 % of papers in the second half — the new vocabulary, ranked by current share.")
    h2("Papers mentioning a term")
    pick_options = list(dict.fromkeys([*terms, *[t for t, *_ in emerging[:5]]]))
    pick = st.selectbox("Term", pick_options, key="kw_pick") if pick_options else None
    if pick:
        hits = cached_papers_with(path, mtime, years, pick, text_mode)
        note(f"{len(hits)} papers, newest and most cited first.")
        st.dataframe(
            pd.DataFrame([{"year": r.get("publication_year"), "title": r.get("title"), "citations": r.get("cited_by_count", 0), "doi": r.get("doi")} for r in hits[:300]]),
            hide_index=True, width="stretch", height=320, column_config={"doi": st.column_config.LinkColumn("doi")},
        )
    h2("Top terms by year")
    top = kt.top_terms(40)
    st.dataframe(as_pct(frames.keyword_table(kt, top), [str(y) for y in kt.years]), hide_index=True, width="stretch", column_config=pct_cols(None, [str(y) for y in kt.years]))
    note("Early/late compare the pooled share of papers in the first vs. second half of the year range. Terms that almost always occur inside a longer phrase are folded into it.")

if section == "topics":
    o1, o2 = st.columns([1, 1])
    method = o1.selectbox("Method", ["nmf", "openalex", "openalex-subfield"], format_func=lambda m: {"nmf": "NMF on titles + abstracts", "openalex": "OpenAlex topic labels", "openalex-subfield": "OpenAlex subfields"}[m])
    n_topics = o2.slider("Topics (NMF)", 6, 20, 10, disabled=method != "nmf")
    tt = cached_topics(path, mtime, years, method, n_topics, extra_stop)
    ordered = tt.ordered()
    topic_rows = [{"topic": t.label, "year": y, "share": tt.share(t.id, y)} for t in ordered for y in tt.years]
    figure_head("Share of papers by dominant topic", "Each paper assigned to its strongest topic; smaller topics folded into “Other”")
    vl(charts.streamgraph(topic_rows, [t.label for t in ordered], tt.years), key="topics-stream")
    source_line()
    ttab = frames.topic_table(tt)
    st.dataframe(as_pct(ttab, ["early", "late", "delta"]), hide_index=True, width="stretch",
                 column_config={**pct_cols(None, ["early", "late", "delta"]), "terms": st.column_config.TextColumn(width="large"), "example": st.column_config.TextColumn(width="large")})
    if method == "nmf":
        note("Topics are fitted with NMF on TF-IDF (fixed seed, reproducible). Labels are the top terms; each paper is assigned to its strongest topic.")

if section == "rankings":
    o1, o2, o3, o4 = st.columns([1, 1, 1, 1])
    entity = o1.selectbox("Rank", ENTITIES, format_func=str.title)
    sort_by = o2.selectbox("Sort by", ["papers", "citations"])
    top_n = o3.slider("Show top", 10, 50, 20)
    roll_up = o4.toggle("Roll up to parent institutions", value=True, disabled=entity != "institution",
                        help="Credit the top-level parent from OpenAlex's lineage: A*STAR instead of IME, Chinese Academy of Sciences instead of its institutes.")
    rk = cached_ranking(path, mtime, years, entity, roll_up and entity == "institution")
    keys = rk.top(top_n, by=sort_by)
    table = frames.ranking_table(rk, keys)
    figure_head(f"Top {entity}s by {sort_by}", "Top three in red; the arrow is the change in share of papers between the two halves of the period")
    rows_r = ranking_rows(rk, keys)
    if entity == "country":
        rows_r = [{**r, "name": country_name(r["name"])} for r in rows_r]
    vl(charts.ranked_bars(rows_r, value=sort_by), key=f"rank-{entity}-{sort_by}")
    source_line()
    st.dataframe(table, hide_index=True, width="stretch")
    r, f = st.columns(2)
    r.markdown('<h2 class=\"pt-h2\">' + "Gaining share" + '</h2>', unsafe_allow_html=True)
    r.dataframe(as_pct(frames.ranking_movers(rk, rk.movers(10, 10, rising=True)), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    f.markdown('<h2 class=\"pt-h2\">' + "Losing share" + '</h2>', unsafe_allow_html=True)
    f.dataframe(as_pct(frames.ranking_movers(rk, rk.movers(10, 10, rising=False)), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    note("A paper counts once per entity (full counting). Institution ids come from OpenAlex affiliation matching, which is imperfect: treat close ranks as ties.")

if section == "compare":
    note("Same terms, other conferences. Only conferences already fetched on this server are listed.")
    local = {k: v for k, v in PRESETS.items() if v["slug"] != slug and corpus_path(v["slug"]).exists()}
    others = st.multiselect("Compare with", list(local), default=list(local)[:2], format_func=lambda k: k.split(" — ")[0])
    kt_here = cached_keywords(path, mtime, years, "title+abstract", (2, 3), extra_stop)
    default_terms = [t for t, *_ in kt_here.rising(4, min_total=10)]
    cmp_terms = st.multiselect("Terms", kt_here.top_terms(300), default=default_terms, key="cmp_terms")
    if others and cmp_terms:
        trends = {SHORT.get(slug, query): kt_here}
        for k in others:
            cp = corpus_path(local[k]["slug"])
            trends[k.split(" — ")[0].split("· ")[-1]] = cached_keywords(str(cp), cp.stat().st_mtime, years, "title+abstract", (2, 3), extra_stop)
        df = pd.DataFrame(compare.term_shares(trends, cmp_terms))
        names = list(trends)
        yrs = sorted(df["year"].unique().tolist())
        cols = st.columns(2)
        for i, term in enumerate(cmp_terms):
            rows_t = [{"name": r["conference"], "year": r["year"], "share": r["share"], "papers": r["papers"]} for r in df[df["term"] == term].to_dict("records")]
            with cols[i % 2]:
                vl(charts.multi_line(rows_t, names, yrs, title=term), key=f"cmp-{term}")
        source_line()
        wide = df.pivot_table(index=["term", "conference"], columns="year", values="share").reset_index()
        wide.columns = [str(c) for c in wide.columns]
        ycols = [c for c in wide.columns if c.isdigit()]
        st.dataframe(as_pct(wide, ycols), hide_index=True, width="stretch", column_config=pct_cols(None, ycols))
        common = compare.shared_risers(trends, k=12)
        if common:
            h2("Rising everywhere")
            st.dataframe(as_pct(pd.DataFrame([{"term": t, **{n: d for n, d in ds.items()}} for t, ds in common]), names), hide_index=True, width="stretch", column_config=pct_cols(None, names))
            note("Terms whose share rose in every selected conference, ranked by their smallest gain.")
    elif not others:
        st.info("Fetch another preset conference to enable comparison.")

if section == "data":
    size_mb = corpus_path(slug).stat().st_size / 1e6
    st.markdown(f"Corpus: `{corpus_path(slug)}` ({size_mb:.0f} MB) — one JSON record per paper (title, abstract, authorships, citations, OpenAlex topics).")
    # Downloads are generated on click (callables), so large corpora are never pushed to the browser on every rerun.
    st.download_button("Download corpus (JSONL)", lambda: corpus_path(slug).read_bytes(), file_name=f"{slug}.jsonl", mime="application/jsonl")
    st.download_button(
        "Download keyword table (CSV)",
        lambda: (lambda kt: frames.keyword_table(kt, kt.top_terms(200)).to_csv(index=False))(cached_keywords(path, mtime, years, "title+abstract", (1, 3), extra_stop)),
        file_name=f"{slug}_keywords.csv", mime="text/csv",
    )
    st.download_button(
        "Download institution ranking (CSV)",
        lambda: (lambda rk: frames.ranking_table(rk, rk.top(200)).to_csv(index=False))(cached_ranking(path, mtime, years, "institution")),
        file_name=f"{slug}_institutions.csv", mime="text/csv",
    )
    listing = pd.DataFrame(
        [{"year": r.get("publication_year"), "title": r.get("title"), "citations": r.get("cited_by_count", 0), "doi": r.get("doi")} for r in recs]
    ).sort_values(["year", "citations"], ascending=[False, False])
    st.dataframe(listing, hide_index=True, width="stretch", height=400, column_config={"doi": st.column_config.LinkColumn("doi")})
