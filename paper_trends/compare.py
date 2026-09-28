"""Compare how the same terms trend across several conferences."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from .keywords import KeywordTrends, compute_trends
from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS


def trends_for(corpora: dict[str, list[Record]], **kwargs) -> dict[str, KeywordTrends]:
    """Trends per corpus. Phrases common to many fields are kept here (unlike in a single
    conference's rankings): what venues share is exactly what a comparison is after."""
    from .background import field_of

    kwargs.setdefault("keep_common", True)
    return {name: compute_trends(recs, field=field_of(name), **kwargs) for name, recs in corpora.items()}


def term_shares(trends: dict[str, KeywordTrends], terms: list[str]) -> list[dict]:
    """Long rows: conference, term, year, papers, share (0 when the term never occurs)."""
    rows = []
    for name, kt in trends.items():
        for term in terms:
            for y in kt.years:
                n = kt.doc_freq.get(term, {}).get(y, 0)
                tot = kt.papers_per_year.get(y, 0)
                rows.append({"conference": name, "term": term, "year": y, "papers": n, "share": n / tot if tot else 0.0})
    return rows


def shared_risers(trends: dict[str, KeywordTrends], k: int = 15, min_total: int = 10) -> list[tuple[str, dict[str, float]]]:
    """Terms rising in every conference, ranked by their smallest delta across venues."""
    deltas: dict[str, dict[str, float]] = {}
    for name, kt in trends.items():
        for term, _e, _l, d in kt.rising(10_000, min_total=min_total):
            deltas.setdefault(term, {})[name] = d
    common = [(t, ds) for t, ds in deltas.items() if len(ds) == len(trends) and all(v > 0 for v in ds.values())]
    common.sort(key=lambda x: -min(x[1].values()))
    return common[:k]


def render(rows: list[dict], conferences: list[str], years: list[int]) -> str:
    out = []
    by_term: dict[str, dict[tuple[str, int], float]] = {}
    for r in rows:
        by_term.setdefault(r["term"], {})[(r["conference"], r["year"])] = r["share"]
    w = max(len(c) for c in conferences) + 2
    for term, cells in by_term.items():
        out.append(f"{term}")
        out.append(f"{'':<{w}}" + " ".join(f"{y:>6}" for y in years))
        for c in conferences:
            out.append(f"{c:<{w}}" + " ".join(f"{cells.get((c, y), 0.0):>6.1%}" for y in years))
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends compare", description="Compare term trends across conferences.")
    p.add_argument("jsonl", type=Path, nargs="+", help="two or more corpora, e.g. data/ectc.jsonl data/iedm.jsonl")
    p.add_argument("--term", action="append", default=[], help="term to compare (repeatable); default: shared risers")
    p.add_argument("--years", help="year range, e.g. 2016-2025")
    p.add_argument("--text", choices=["title", "title+abstract"], default="title+abstract")
    p.add_argument("--ngram", default="1-3")
    p.add_argument("--top", type=int, default=12, help="how many shared risers to show when no --term is given")
    p.add_argument("--csv", type=Path)
    args = p.parse_args(argv)

    yrs = parse_years(args.years)
    n_min, n_max = parse_years(args.ngram) or (1, 3)
    corpora = {path.stem: filter_years(read_jsonl(path), yrs) for path in args.jsonl}
    trends = trends_for(corpora, text=args.text, n_min=n_min, n_max=n_max, stopwords=STOPWORDS)
    years = sorted({y for kt in trends.values() for y in kt.years})
    names = list(corpora)

    terms = [t.lower() for t in args.term]
    if not terms:
        common = shared_risers(trends, k=args.top)
        print(f"Terms rising in all of {', '.join(names)} (delta = late-half share minus early-half share)\n")
        w = max((len(t) for t, _ in common), default=10)
        print(f"{'term':<{w}} " + " ".join(f"{n:>10}" for n in names))
        for t, ds in common:
            print(f"{t:<{w}} " + " ".join(f"{ds[n]:>+10.1%}" for n in names))
        terms = [t for t, _ in common[:3]]
        print()
    rows = term_shares(trends, terms)
    print(render(rows, names, years))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=["conference", "term", "year", "papers", "share"])
            wr.writeheader()
            wr.writerows(rows)
        print(f"[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
