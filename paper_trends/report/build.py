"""Turn a corpus into the numbers, series and sentences one report page needs."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from ..keywords import KeywordTrends, compute_trends, hyphen_forms, restore_hyphens
from ..rank import compute_ranking
from ..store import Record, filter_years
from ..text import STOPWORDS
from ..topics import compute_nmf


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


def country_name(code: str) -> str:
    return COUNTRY.get(code, code)


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


def growth_sentence(papers: dict[int, int]) -> str:
    ys = sorted(papers)
    if len(ys) < 3:
        return ""
    first = sum(papers[y] for y in ys[:2]) / 2
    last = sum(papers[y] for y in ys[-2:]) / 2
    n = ys[-1] - ys[0] - 1
    rate = (last / first) ** (1 / n) - 1 if first and n > 0 else 0.0
    if abs(rate) < 0.01:
        return "output has been flat"
    verb = "growing" if rate > 0 else "shrinking"
    return f"output {verb} about {abs(rate):.0%} a year"


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
    kt = compute_trends(recs, text=text_mode, n_min=2, n_max=3, stopwords=stopwords)
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

    return {
        "name": name,
        "slug": slug,
        "years": ys,
        "year_range": [y0, y1],
        "n_papers": len(recs),
        "abstract_coverage": coverage,
        "text_mode": text_mode,
        "generated": date.today().isoformat(),
        "papers_per_year": [{"year": y, "papers": per_year[y], "abstracts": with_abs[y]} for y in ys],
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
        "countries": [
            {"name": country_name(country.names[k]), "papers": country.total(k), "early": country_mov[k][0], "late": country_mov[k][1], "delta": country_mov[k][2]}
            for k in country_top
        ],
        "split_year": ys[len(ys) // 2],
    }
