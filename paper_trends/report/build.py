"""Turn a corpus into the numbers, series and sentences one report page needs."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from ..background import field_of
from ..keywords import KeywordTrends, compute_trends, hyphen_forms, restore_hyphens
from ..rank import compute_ranking, entities_of
from ..store import Record, filter_years
from ..text import STOPWORDS
from ..topics import compute_nmf
from .charts import TOPIC_COLORS
from .entities import build_entities


COUNTRY = {
    "US": "United States", "CN": "China", "JP": "Japan", "KR": "South Korea", "TW": "Taiwan", "DE": "Germany", "GB": "United Kingdom",
    "FR": "France", "SG": "Singapore", "NL": "Netherlands", "BE": "Belgium", "CA": "Canada", "CH": "Switzerland", "IT": "Italy",
    "IN": "India", "HK": "Hong Kong", "SE": "Sweden", "AT": "Austria", "ES": "Spain", "IL": "Israel", "AU": "Australia", "FI": "Finland",
    "DK": "Denmark", "PL": "Poland", "IE": "Ireland", "NO": "Norway", "CZ": "Czechia", "BR": "Brazil", "RU": "Russia", "MY": "Malaysia",
    "TH": "Thailand", "PT": "Portugal", "GR": "Greece", "TR": "Türkiye", "SA": "Saudi Arabia", "AE": "United Arab Emirates", "MX": "Mexico",
    "VN": "Vietnam", "ID": "Indonesia", "PH": "Philippines", "EG": "Egypt", "ZA": "South Africa", "AR": "Argentina", "HU": "Hungary",
    "PK": "Pakistan", "IR": "Iran", "BD": "Bangladesh", "LK": "Sri Lanka", "NG": "Nigeria", "KE": "Kenya", "CL": "Chile", "CO": "Colombia",
    "PE": "Peru", "RO": "Romania", "UA": "Ukraine", "BG": "Bulgaria", "SK": "Slovakia", "SI": "Slovenia", "HR": "Croatia", "RS": "Serbia",
    "LT": "Lithuania", "LV": "Latvia", "EE": "Estonia", "LU": "Luxembourg", "IS": "Iceland", "NZ": "New Zealand", "QA": "Qatar",
    "KW": "Kuwait", "JO": "Jordan", "MA": "Morocco", "TN": "Tunisia", "DZ": "Algeria", "ET": "Ethiopia", "GH": "Ghana", "MO": "Macao",
    "KZ": "Kazakhstan", "UZ": "Uzbekistan", "NP": "Nepal", "CY": "Cyprus", "MT": "Malta", "IQ": "Iraq", "LB": "Lebanon", "OM": "Oman",
}


_ISO = json.loads((Path(__file__).parent / "static" / "iso3166.json").read_text(encoding="utf-8"))


def country_name(code: str) -> str:
    return COUNTRY.get(code) or _ISO.get(code, {}).get("name", code)


def country_id(code: str) -> int | None:
    """ISO 3166-1 numeric id, the key used by the world-110m topojson."""
    return _ISO.get(code, {}).get("id")


def country_map_rows(country_ranking, n_papers: int) -> list[dict[str, Any]]:
    rows = []
    for code in country_ranking.by_year:
        cid = country_id(code)
        if cid is None:
            continue
        n = country_ranking.total(code)
        rows.append({"id": cid, "name": country_name(code), "papers": n, "share": n / n_papers if n_papers else 0.0})
    return rows


def inst_topic_rows(records: list[Record], tt, inst, inst_keys: list[str], topics: list) -> list[dict[str, Any]]:
    """Share of each institution's papers whose dominant topic is each topic (rows sum to
    one). Topics beyond the coloured ones are folded into "Other", as in the streamgraph."""
    n_colored = len(TOPIC_COLORS)
    label_of = {t.id: (t.label if i < n_colored else "Other") for i, t in enumerate(topics)}
    pos = {k: i for i, k in enumerate(inst_keys)}
    counts: dict[int, Counter] = {i: Counter() for i in pos.values()}
    for i, r in enumerate(records):
        topic = tt.assignments.get(i)
        if topic is None:
            continue
        for k in entities_of(r, "institution", roll_up=True):
            if k in pos:
                counts[pos[k]][label_of[topic]] += 1
    columns = [t.label for t in topics[:n_colored]] + (["Other"] if len(topics) > n_colored else [])
    rows = []
    for k, i in pos.items():
        total = sum(counts[i].values()) or 1
        for col in columns:
            rows.append({"name": inst.names[k], "topic": col, "papers": counts[i][col], "share": counts[i][col] / total})
    return rows


def inst_rank_rows(inst, inst_keys: list[str], years: list[int], window: int = 3) -> list[dict[str, Any]]:
    """Yearly rank of each institution among `inst_keys`, on a rolling `window`-year count
    (a single year is too noisy for 10–30 papers). Ties go to the larger total."""
    half = window // 2
    rolling = {k: {y: sum(inst.by_year[k].get(yy, 0) for yy in years if abs(yy - y) <= half) for y in years} for k in inst_keys}
    rank: dict[str, dict[int, int]] = {k: {} for k in inst_keys}
    for y in years:
        order = sorted(inst_keys, key=lambda k: (-rolling[k][y], -inst.total(k)))
        for r, k in enumerate(order, 1):
            rank[k][y] = r
    rows = []
    for k in inst_keys:
        climb = rank[k][years[0]] - rank[k][years[-1]]
        tone = "up" if climb >= 3 else ("down" if climb <= -3 else "flat")
        name = inst.names[k]
        label = name if not climb else f"{name}  {'▲' if climb > 0 else '▼'}{abs(climb)}"
        for y in years:
            rows.append({"name": name, "year": y, "rank": rank[k][y], "papers": rolling[k][y], "tone": tone, "climb": climb, "label": label})
    return rows


def _pct(x: float) -> str:
    return f"{x:.0%}" if x >= 0.1 else f"{x:.1%}"


def _series(kt: KeywordTrends, term: str) -> list[dict[str, Any]]:
    return [{"year": y, "share": kt.share(term, y), "papers": kt.doc_freq[term].get(y, 0)} for y in kt.years]


def _singular(term: str) -> str:
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in term.split())


def _dedupe(rows: list[tuple]) -> list[tuple]:
    """Drop singular/plural twins ("diffusion model" next to "diffusion models"), keeping the
    higher-ranked one."""
    seen: set[str] = set()
    out = []
    for row in rows:
        key = _singular(row[0])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def coverage_note(papers: dict[int, int], with_abs: dict[int, int]) -> str:
    """", lowest 97% in 2020" when a year dips below the rest; empty when it is even."""
    shares = {y: with_abs.get(y, 0) / papers[y] for y in papers if papers[y]}
    if not shares:
        return ""
    y, low = min(shares.items(), key=lambda kv: kv[1])
    return f", lowest {low:.0%} in {y}" if low < 0.97 else ""


def growth_sentence(papers: dict[int, int]) -> str:
    ys = sorted(papers)
    if len(ys) < 3:
        return ""
    first = sum(papers[y] for y in ys[:2]) / 2
    last = sum(papers[y] for y in ys[-2:]) / 2
    n = ys[-1] - ys[0] - 1
    rate = (last / first) ** (1 / n) - 1 if first and n > 0 else 0.0
    lo, hi = min(papers.values()), max(papers.values())
    if abs(rate) < 0.01:
        return f"output has been flat, between {lo:,} and {hi:,} papers a year"
    verb = "growing" if rate > 0 else "shrinking"
    return f"output {verb} about {abs(rate):.0%} a year, from {papers[ys[0]]:,} to {papers[ys[-1]]:,} papers"


def build_report(records: list[Record], *, name: str, slug: str, years: tuple[int, int] | None = None,
                 n_topics: int = 8, n_multiples: int = 8, stopwords: frozenset[str] = STOPWORDS) -> dict[str, Any]:
    recs = filter_years(records, years)
    per_year: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    for r in recs:
        y = r.get("publication_year")
        if y:
            per_year[y] += 1
            if r.get("abstract"):
                with_abs[y] += 1
    ys = sorted(per_year)
    y0, y1 = ys[0], ys[-1]

    coverage = sum(with_abs.values()) / max(len(recs), 1)
    # Venues whose abstracts OpenAlex mostly lacks (Interspeech) are analysed on titles only,
    # otherwise the years with abstracts would dominate every share.
    text_mode = "title+abstract" if coverage >= 0.6 else "title"
    kt = compute_trends(recs, text=text_mode, n_min=2, n_max=3, stopwords=stopwords, field=field_of(slug))
    rising = _dedupe(kt.rising(n_multiples * 2, min_total=10))[:n_multiples]
    falling = _dedupe(kt.falling(n_multiples * 2, min_total=10))[:n_multiples]
    emerging = _dedupe(kt.emerging(20, min_total=10))[:10]
    forms = hyphen_forms(recs, text=text_mode)
    show = lambda t: restore_hyphens(t, forms)  # noqa: E731  display form only; counts stay keyed by the split form

    tt = compute_nmf(recs, n_topics=n_topics, stopwords=stopwords)
    topics = tt.ordered()
    for t in topics:  # display forms for labels and term lists (counts are keyed by topic id)
        t.label = " / ".join(show(x) for x in t.label.split(" / "))
        t.terms = [show(x) for x in t.terms]
    topic_rows = []
    for rank, t in enumerate(topics):
        for y in tt.years:
            topic_rows.append({"topic": t.label, "rank": rank, "year": y, "share": tt.share(t.id, y), "papers": tt.by_year[t.id].get(y, 0)})
    topic_moves = sorted(((t.label, *tt.momentum(t.id)) for t in topics), key=lambda x: x[3])
    loser, gainer = topic_moves[0], topic_moves[-1]

    inst = compute_ranking(recs, "institution", roll_up=True)
    country = compute_ranking(recs, "country")
    inst_top = inst.top(15)
    country_top = country.top(12)
    inst_mov = {k: inst.momentum(k) for k in inst_top}
    country_mov = {k: country.momentum(k) for k in country_top}
    inst_gainer = max(inst.movers(1, 10, rising=True), default=None)
    country_gainer = max(country.movers(1, 10, rising=True), default=None)

    top_rise = rising[0] if rising else None
    glance = [
        f"{name} published {len(recs):,} papers between {y0} and {y1}, {growth_sentence(per_year)}.",
    ]
    if top_rise:
        t, e, l, _ = top_rise
        glance.append(f"The fastest-growing phrase is “{show(t)}”, up from {_pct(e)} to {_pct(l)} of papers.")
    if inst_gainer or country_gainer:
        bits = []
        if inst_gainer:
            k, e, l, _ = inst_gainer
            bits.append(f"{inst.names[k]} gained the most share among institutions ({_pct(e)} → {_pct(l)})")
        if country_gainer:
            k, e, l, _ = country_gainer
            bits.append(f"{country_name(country.names[k])} among countries ({_pct(e)} → {_pct(l)})")
        glance.append("; ".join(bits) + ".")
    if emerging:
        glance.append("New vocabulary: " + ", ".join(show(t) for t, *_ in emerging[:4]) + ".")

    topic_sentence = (
        f"“{gainer[0]}” grew from {_pct(gainer[1])} to {_pct(gainer[2])} of papers, "
        f"while “{loser[0]}” fell from {_pct(loser[1])} to {_pct(loser[2])}."
    )

    # institution × topic: who specialises, measured against the conference as a whole
    heat_keys = inst_top[:12]
    heat_rows = inst_topic_rows(recs, tt, inst, heat_keys, topics)
    heat_sentence = ""
    if heat_rows:
        focus = max((r for r in heat_rows if r["topic"] != "Other"), key=lambda r: r["share"], default=None)
        if focus:
            conf_share = tt.total(next(t.id for t in topics if t.label == focus["topic"])) / len(recs)
            detail = f"{_pct(focus['share'])} of its papers are about “{focus['topic']}”, against {_pct(conf_share)} of the conference"
            if conf_share and focus["share"] / conf_share >= 1.8:
                heat_sentence = f"{focus['name']} is the most focused: {detail}."
            else:  # everyone works on everything (CVPR): say so instead of inventing a speciality
                heat_sentence = f"No leading institution specialises much; the most focused is {focus['name']}, {detail}."
    # ranks over time among the leading institutions
    rank_keys = inst_top[:10]
    rank_rows = inst_rank_rows(inst, rank_keys, ys)
    rank_sentence = ""
    if rank_rows:
        ends = {r["name"]: r for r in rank_rows if r["year"] == y1}
        climb = sorted(ends.values(), key=lambda r: -r["climb"])
        up, down = climb[0], climb[-1]
        bits = []
        if up["climb"] > 0:
            bits.append(f"{up['name']} climbed from rank {up['rank'] + up['climb']} to {up['rank']}")
        if down["climb"] < 0:
            bits.append(f"{down['name']} slipped from {down['rank'] + down['climb']} to {down['rank']}")
        rank_sentence = ("; ".join(bits) + ".") if bits else "The order of the leading institutions barely changed."

    return {
        "entities": build_entities(recs, kt, tt, inst, show),
        "name": name,
        "slug": slug,
        "years": ys,
        "year_range": [y0, y1],
        "n_papers": len(recs),
        "abstract_coverage": coverage,
        "text_mode": text_mode,
        "n_common_hidden": len(kt.common),
        "common_examples": [show(t) for t in sorted(kt.common, key=lambda t: -kt.mentions(t))[:6]],
        "generated": date.today().isoformat(),
        "papers_per_year": [{"year": y, "papers": per_year[y], "abstracts": with_abs[y]} for y in ys],
        "growth_sentence": growth_sentence(per_year),
        "coverage_note": coverage_note(per_year, with_abs),
        "glance": glance,
        "rising": [{"term": show(t), "early": e, "late": l, "delta": d, "series": _series(kt, t)} for t, e, l, d in rising],
        "falling": [{"term": show(t), "early": e, "late": l, "delta": d, "series": _series(kt, t)} for t, e, l, d in falling],
        "emerging": [{"term": show(t), "first": f, "early": e, "late": l, "series": _series(kt, t)} for t, f, e, l in emerging],
        "topics": [{"label": t.label, "terms": t.terms, "examples": t.examples, "papers": tt.total(t.id)} for t in topics],
        "topic_rows": topic_rows,
        "topic_sentence": topic_sentence,
        "institutions": [
            {"name": inst.names[k], "papers": inst.total(k), "citations": inst.citations.get(k, 0),
             "early": inst_mov[k][0], "late": inst_mov[k][1], "delta": inst_mov[k][2]}
            for k in inst_top
        ],
        "inst_topic": heat_rows,
        "inst_topic_insts": [inst.names[k] for k in heat_keys],
        "inst_topic_topics": [t.label for t in topics[: len(TOPIC_COLORS)]] + (["Other"] if len(topics) > len(TOPIC_COLORS) else []),
        "inst_topic_sentence": heat_sentence,
        "inst_ranks": rank_rows,
        "inst_rank_sentence": rank_sentence,
        "country_map": country_map_rows(country, len(recs)),
        "countries": [
            {"name": country_name(country.names[k]), "papers": country.total(k), "early": country_mov[k][0], "late": country_mov[k][1], "delta": country_mov[k][2]}
            for k in country_top
        ],
        "split_year": ys[len(ys) // 2],
    }
