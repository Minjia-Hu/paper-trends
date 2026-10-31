"""Turn analysis results into tidy pandas DataFrames for charts and tables."""

from __future__ import annotations

from collections import Counter

import pandas as pd

from .csv_export import safe_cell, safe_row
from .keywords import KeywordTrends
from .rank import Ranking
from .store import Record
from .topics import TopicTrends


def csv_text(frame: pd.DataFrame) -> str:
    """Export a copy with formula-like text escaped, leaving displayed data intact."""
    return frame.map(safe_cell).to_csv(index=False, header=safe_row(frame.columns))


def coverage_frame(records: list[Record]) -> pd.DataFrame:
    papers: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    for r in records:
        y = r.get("publication_year")
        if not y:
            continue
        papers[y] += 1
        if r.get("abstract"):
            with_abs[y] += 1
    rows = [{"year": y, "papers": papers[y], "abstracts": with_abs[y], "coverage": with_abs[y] / papers[y]} for y in sorted(papers)]
    return pd.DataFrame(rows)


def keyword_series(kt: KeywordTrends, terms: list[str]) -> pd.DataFrame:
    """Long frame: term, year, papers, share — one row per term/year."""
    rows = [
        {"term": t, "year": y, "papers": kt.doc_freq[t].get(y, 0), "share": kt.share(t, y)}
        for t in terms
        for y in kt.years
    ]
    return pd.DataFrame(rows)


def keyword_table(kt: KeywordTrends, terms: list[str]) -> pd.DataFrame:
    df = pd.DataFrame({"term": terms, "papers": [kt.total(t) for t in terms]})
    for y in kt.years:
        df[str(y)] = [kt.share(t, y) for t in terms]
    return df


def movers_table(rows: list[tuple[str, float, float, float]], label: str = "term") -> pd.DataFrame:
    return pd.DataFrame(rows, columns=[label, "early", "late", "delta"])


def topic_series(tt: TopicTrends, max_series: int = 8) -> pd.DataFrame:
    """Long frame of topic share per year; topics beyond `max_series` fold into 'Other'."""
    ordered = tt.ordered()
    keep = ordered[:max_series]
    rest = ordered[max_series:]
    rows = []
    for t in keep:
        for y in tt.years:
            rows.append({"topic": t.label, "year": y, "papers": tt.by_year[t.id].get(y, 0), "share": tt.share(t.id, y)})
    if rest:
        for y in tt.years:
            n = sum(tt.by_year[t.id].get(y, 0) for t in rest)
            tot = tt.papers_per_year.get(y, 0)
            rows.append({"topic": "Other", "year": y, "papers": n, "share": n / tot if tot else 0.0})
    return pd.DataFrame(rows)


def topic_table(tt: TopicTrends) -> pd.DataFrame:
    rows = []
    for t in tt.ordered():
        e, l, d = tt.momentum(t.id)
        rows.append(
            {
                "topic": t.label,
                "papers": tt.total(t.id),
                "early": e,
                "late": l,
                "delta": d,
                "terms": ", ".join(t.terms),
                "example": t.examples[0] if t.examples else "",
            }
        )
    return pd.DataFrame(rows)


def ranking_table(rk: Ranking, keys: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            rk.entity: [rk.names[k] for k in keys],
            "papers": [rk.total(k) for k in keys],
            "citations": [rk.citations.get(k, 0) for k in keys],
        }
    )
    for y in rk.years:
        df[str(y)] = [rk.by_year[k].get(y, 0) for k in keys]
    return df


def ranking_movers(rk: Ranking, rows) -> pd.DataFrame:
    return pd.DataFrame([(rk.names[k], e, l, d) for k, e, l, d in rows], columns=[rk.entity, "early", "late", "delta"])
