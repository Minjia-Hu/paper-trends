"""paper-trends — Streamlit UI. Run with:  uv run streamlit run app.py"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from paper_trends import compare, frames, viz
from paper_trends.fetch import coverage_table, fetch_conference
from paper_trends.keywords import compute_trends, papers_with
from paper_trends.openalex import OpenAlex, OpenAlexError
from paper_trends.rank import ENTITIES, compute_ranking
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

st.set_page_config(page_title="paper-trends", page_icon="📈", layout="wide")
alt.theme.register("paper_trends", enable=True)(viz.altair_theme)

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


@st.cache_data(show_spinner="Ranking…")
def cached_ranking(path: str, mtime: float, years: tuple[int, int], entity: str, roll_up: bool = False):
    return compute_ranking(filter_years(load_records(path, mtime), years), entity, roll_up=roll_up)


# ---- charts ------------------------------------------------------------------------


def share_line_chart(df: pd.DataFrame, series: str, title: str) -> alt.Chart:
    names = list(dict.fromkeys(df[series]))
    domain, rng = viz.series_colors(names)
    base = alt.Chart(df).encode(
        x=alt.X("year:O", title=None),
        y=alt.Y("share:Q", title="share of papers", axis=alt.Axis(format="%")),
        color=alt.Color(f"{series}:N", scale=alt.Scale(domain=domain, range=rng), legend=alt.Legend(title=None, orient="bottom", columns=4)),
        tooltip=[alt.Tooltip(f"{series}:N"), alt.Tooltip("year:O"), alt.Tooltip("papers:Q"), alt.Tooltip("share:Q", format=".1%")],
    )
    return (base.mark_line() + base.mark_point()).properties(height=340, title=title)


def stacked_area_chart(df: pd.DataFrame, title: str) -> alt.Chart:
    names = list(dict.fromkeys(df["topic"]))
    df = df.assign(rank=df["topic"].map({n: i for i, n in enumerate(names)}))
    domain, rng = viz.series_colors(names)
    return (
        alt.Chart(df)
        .mark_area(stroke="#ffffff", strokeWidth=1.5, interpolate="monotone")
        .encode(
            x=alt.X("year:Q", title=None, axis=alt.Axis(format="d", tickMinStep=1), scale=alt.Scale(nice=False, padding=0)),
            y=alt.Y("share:Q", stack="normalize", title="share of papers", axis=alt.Axis(format="%")),
            color=alt.Color("topic:N", scale=alt.Scale(domain=domain, range=rng), legend=alt.Legend(title=None, orient="bottom", columns=2)),
            order=alt.Order("rank:Q"),  # fixed stacking order across years (largest topic at the bottom)
            tooltip=[alt.Tooltip("topic:N"), alt.Tooltip("year:Q", format="d"), alt.Tooltip("papers:Q"), alt.Tooltip("share:Q", format=".1%")],
        )
        .properties(height=380, title=title)
    )


def bar_chart(df: pd.DataFrame, x: str, y: str, title: str, fmt: str | None = None) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(color=viz.PRIMARY)
        .encode(
            x=alt.X(f"{x}:O", title=None),
            y=alt.Y(f"{y}:Q", title=y, axis=alt.Axis(format=fmt) if fmt else alt.Axis()),
            tooltip=[alt.Tooltip(f"{x}:O"), alt.Tooltip(f"{y}:Q", format=fmt or "")],
        )
        .properties(height=260, title=title)
    )


def hbar_chart(df: pd.DataFrame, label: str, value: str, title: str) -> alt.Chart:
    return (
        alt.Chart(df)
        .mark_bar(color=viz.PRIMARY)
        .encode(
            y=alt.Y(f"{label}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=280, labelOverlap=False)),
            x=alt.X(f"{value}:Q", title=value),
            tooltip=[alt.Tooltip(f"{label}:N"), alt.Tooltip(f"{value}:Q")],
        )
        .properties(height=max(200, 26 * len(df) + 20), title=title)
    )


def pct_cols(df: pd.DataFrame, cols) -> dict:
    return {c: st.column_config.NumberColumn(format="%.1f%%") for c in cols}


def as_pct(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = out[c] * 100
    return out


# ---- sidebar -----------------------------------------------------------------------

with st.sidebar:
    st.title("paper-trends")
    st.caption("Publication trends for any conference, from OpenAlex.")
    # ?conference=<slug> pre-selects a preset, so links to a specific conference can be shared
    wanted = st.query_params.get("conference", "")
    options = [*PRESETS, "Custom…"]
    default_idx = next((i for i, k in enumerate(PRESETS) if PRESETS[k]["slug"] == wanted), 0)
    choice = st.selectbox("Conference", options, index=default_idx)
    if choice != "Custom…" and PRESETS[choice]["slug"] != wanted:
        st.query_params["conference"] = PRESETS[choice]["slug"]
    if choice == "Custom…":
        query = st.text_input("Conference name (as OpenAlex spells it)", placeholder="Custom Integrated Circuits Conference")
        doi_prefix = st.text_input("DOI prefix(es), optional, space-separated", placeholder="10.1109/cicc")
        doi_prefixes = doi_prefix.split()
        slug = "".join(ch for ch in query.lower().replace(" ", "-") if ch.isalnum() or ch == "-")[:40]
    else:
        preset = PRESETS[choice]
        query, doi_prefixes, slug = preset["query"], preset["doi_prefixes"], preset["slug"]

    records = records_for(slug) if slug else None
    if records is None:
        st.info("No local data for this conference yet.")
        if st.button("Fetch from OpenAlex", type="primary", disabled=not query):
            run_fetch(query, doi_prefixes, slug)
    else:
        all_years = sorted({r["publication_year"] for r in records if r.get("publication_year")})
        st.success(f"{len(records)} papers · {all_years[0]}–{all_years[-1]}")
        if st.button("Refresh from OpenAlex"):
            run_fetch(query, doi_prefixes, slug)

    if records:
        cov = frames.coverage_frame(records)
        good = cov[cov["coverage"] >= 0.5]["year"].tolist()
        default = (max(good[0], good[-1] - 9), good[-1]) if good else (all_years[0], all_years[-1])
        years = st.slider("Years", all_years[0], all_years[-1], default)
        low = cov[(cov["year"] >= years[0]) & (cov["year"] <= years[1]) & (cov["coverage"] < 0.5)]["year"].tolist()
        if low:
            st.warning(f"Abstracts mostly missing for {low}; text analyses under-count those years.")
        extra_stop = st.text_area("Extra stopwords", placeholder="one per line", height=68)
        st.caption("Words to ignore in keyword and topic analyses, e.g. your field's boilerplate.")

# ---- main ---------------------------------------------------------------------------

if not records:
    st.title("paper-trends")
    st.markdown(
        "Pick a conference in the sidebar and fetch its papers from [OpenAlex](https://openalex.org). "
        "Then explore keyword trends, topic evolution and who publishes where."
    )
    st.stop()

path, mtime = str(corpus_path(slug)), corpus_path(slug).stat().st_mtime
recs = filter_years(records, years)
cov_y = frames.coverage_frame(recs)

st.title(query)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Papers", f"{len(recs):,}")
c2.metric("Years", f"{years[0]}–{years[1]}")
c3.metric("With abstract", f"{cov_y['abstracts'].sum() / max(len(recs), 1):.0%}")
c4.metric("Institutions", f"{len(cached_ranking(path, mtime, years, 'institution').by_year):,}")

tab_overview, tab_kw, tab_topics, tab_rank, tab_compare, tab_data = st.tabs(["Overview", "Keywords", "Topics", "Rankings", "Compare", "Data"])

with tab_overview:
    a, b = st.columns(2)
    a.altair_chart(bar_chart(cov_y, "year", "papers", "Papers per year"), width="stretch")
    b.altair_chart(bar_chart(cov_y, "year", "coverage", "Abstract coverage", fmt="%"), width="stretch")
    rk_c = cached_ranking(path, mtime, years, "country")
    top_c = rk_c.top(12)
    a.altair_chart(hbar_chart(frames.ranking_table(rk_c, top_c)[["country", "papers"]], "country", "papers", "Papers by country (full counting)"), width="stretch")
    b.dataframe(frames.ranking_table(rk_c, top_c), hide_index=True, width="stretch")

with tab_kw:
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
        st.altair_chart(share_line_chart(frames.keyword_series(kt, terms), "term", "Share of papers mentioning the term"), width="stretch")
    r, f = st.columns(2)
    r.subheader("Rising")
    r.dataframe(as_pct(frames.movers_table(rising), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    f.subheader("Falling")
    f.dataframe(as_pct(frames.movers_table(falling), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    st.subheader("Emerging")
    emerging = kt.emerging(15, min_total=10)
    st.dataframe(
        as_pct(pd.DataFrame(emerging, columns=["term", "first seen", "early", "late"]), ["early", "late"]),
        hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late"]),
    )
    st.caption("Near-absent in the first half of the range, at least 1 % of papers in the second half — the new vocabulary, ranked by current share.")
    st.subheader("Papers mentioning a term")
    pick_options = list(dict.fromkeys([*terms, *[t for t, *_ in emerging[:5]]]))
    pick = st.selectbox("Term", pick_options, key="kw_pick") if pick_options else None
    if pick:
        hits = cached_papers_with(path, mtime, years, pick, text_mode)
        st.caption(f"{len(hits)} papers, newest and most cited first.")
        st.dataframe(
            pd.DataFrame([{"year": r.get("publication_year"), "title": r.get("title"), "citations": r.get("cited_by_count", 0), "doi": r.get("doi")} for r in hits[:300]]),
            hide_index=True, width="stretch", height=320, column_config={"doi": st.column_config.LinkColumn("doi")},
        )
    st.subheader("Top terms by year")
    top = kt.top_terms(40)
    st.dataframe(as_pct(frames.keyword_table(kt, top), [str(y) for y in kt.years]), hide_index=True, width="stretch", column_config=pct_cols(None, [str(y) for y in kt.years]))
    st.caption("Early/late compare the pooled share of papers in the first vs. second half of the year range. Terms that almost always occur inside a longer phrase are folded into it.")

with tab_topics:
    o1, o2 = st.columns([1, 1])
    method = o1.selectbox("Method", ["nmf", "openalex", "openalex-subfield"], format_func=lambda m: {"nmf": "NMF on titles + abstracts", "openalex": "OpenAlex topic labels", "openalex-subfield": "OpenAlex subfields"}[m])
    n_topics = o2.slider("Topics (NMF)", 6, 20, 10, disabled=method != "nmf")
    tt = cached_topics(path, mtime, years, method, n_topics, extra_stop)
    st.altair_chart(stacked_area_chart(frames.topic_series(tt), "Topic mix per year (dominant topic per paper)"), width="stretch")
    ttab = frames.topic_table(tt)
    st.dataframe(as_pct(ttab, ["early", "late", "delta"]), hide_index=True, width="stretch",
                 column_config={**pct_cols(None, ["early", "late", "delta"]), "terms": st.column_config.TextColumn(width="large"), "example": st.column_config.TextColumn(width="large")})
    if method == "nmf":
        st.caption("Topics are fitted with NMF on TF-IDF (fixed seed, reproducible). Labels are the top terms; each paper is assigned to its strongest topic.")

with tab_rank:
    o1, o2, o3, o4 = st.columns([1, 1, 1, 1])
    entity = o1.selectbox("Rank", ENTITIES, format_func=str.title)
    sort_by = o2.selectbox("Sort by", ["papers", "citations"])
    top_n = o3.slider("Show top", 10, 50, 20)
    roll_up = o4.toggle("Roll up to parent institutions", value=True, disabled=entity != "institution",
                        help="Credit the top-level parent from OpenAlex's lineage: A*STAR instead of IME, Chinese Academy of Sciences instead of its institutes.")
    rk = cached_ranking(path, mtime, years, entity, roll_up and entity == "institution")
    keys = rk.top(top_n, by=sort_by)
    table = frames.ranking_table(rk, keys)
    st.altair_chart(hbar_chart(table[[entity, sort_by]], entity, sort_by, f"Top {entity}s by {sort_by}"), width="stretch")
    st.dataframe(table, hide_index=True, width="stretch")
    r, f = st.columns(2)
    r.subheader("Gaining share")
    r.dataframe(as_pct(frames.ranking_movers(rk, rk.movers(10, 10, rising=True)), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    f.subheader("Losing share")
    f.dataframe(as_pct(frames.ranking_movers(rk, rk.movers(10, 10, rising=False)), ["early", "late", "delta"]), hide_index=True, width="stretch", column_config=pct_cols(None, ["early", "late", "delta"]))
    st.caption("A paper counts once per entity (full counting). Institution ids come from OpenAlex affiliation matching, which is imperfect: treat close ranks as ties.")

with tab_compare:
    st.caption("Same terms, other conferences. Only conferences already fetched on this server are listed.")
    local = {k: v for k, v in PRESETS.items() if v["slug"] != slug and corpus_path(v["slug"]).exists()}
    others = st.multiselect("Compare with", list(local), default=list(local)[:2], format_func=lambda k: k.split(" — ")[0])
    kt_here = cached_keywords(path, mtime, years, "title+abstract", (2, 3), extra_stop)
    default_terms = [t for t, *_ in kt_here.rising(4, min_total=10)]
    cmp_terms = st.multiselect("Terms", kt_here.top_terms(300), default=default_terms, key="cmp_terms")
    if others and cmp_terms:
        trends = {choice.split(" — ")[0].split("· ")[-1]: kt_here}
        for k in others:
            cp = corpus_path(local[k]["slug"])
            trends[k.split(" — ")[0].split("· ")[-1]] = cached_keywords(str(cp), cp.stat().st_mtime, years, "title+abstract", (2, 3), extra_stop)
        df = pd.DataFrame(compare.term_shares(trends, cmp_terms))
        names = list(trends)
        domain, rng = viz.series_colors(names)
        chart = (
            alt.Chart(df)
            .mark_line(point=True)
            .encode(
                x=alt.X("year:O", title=None),
                y=alt.Y("share:Q", title="share of papers", axis=alt.Axis(format="%")),
                color=alt.Color("conference:N", scale=alt.Scale(domain=domain, range=rng), legend=alt.Legend(title=None, orient="bottom")),
                tooltip=[alt.Tooltip("conference:N"), alt.Tooltip("term:N"), alt.Tooltip("year:O"), alt.Tooltip("papers:Q"), alt.Tooltip("share:Q", format=".1%")],
            )
            .properties(height=220, width=430)
            .facet(facet=alt.Facet("term:N", title=None, header=alt.Header(labelFontSize=13, labelFontWeight="bold")), columns=2)
            .resolve_scale(y="independent")
        )
        st.altair_chart(chart, width="stretch")
        wide = df.pivot_table(index=["term", "conference"], columns="year", values="share").reset_index()
        wide.columns = [str(c) for c in wide.columns]
        ycols = [c for c in wide.columns if c.isdigit()]
        st.dataframe(as_pct(wide, ycols), hide_index=True, width="stretch", column_config=pct_cols(None, ycols))
        common = compare.shared_risers(trends, k=12)
        if common:
            st.subheader("Rising everywhere")
            st.dataframe(as_pct(pd.DataFrame([{"term": t, **{n: d for n, d in ds.items()}} for t, ds in common]), names), hide_index=True, width="stretch", column_config=pct_cols(None, names))
            st.caption("Terms whose share rose in every selected conference, ranked by their smallest gain.")
    elif not others:
        st.info("Fetch another preset conference to enable comparison.")

with tab_data:
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
