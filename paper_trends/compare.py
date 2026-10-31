"""Compare how the same terms trend across several conferences."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from .csv_export import safe_cell
from .keywords import KeywordTrends, compute_trends
from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS, paper_tokens


def trends_for(corpora: dict[str, list[Record]], **kwargs) -> dict[str, KeywordTrends]:
    """Trends per corpus. Boilerplate phrases are kept here (unlike in a single
    conference's rankings): what venues share is exactly what a comparison is after."""
    from .background import field_of

    kwargs.setdefault("keep_common", True)
    return {name: compute_trends(recs, field=field_of(name), **kwargs) for name, recs in corpora.items()}


def term_shares(trends: dict[str, KeywordTrends], terms: list[str], *, years: list[int] | None = None) -> list[dict]:
    """Long rows over a shared calendar range.

    A venue without papers for a year has unknown counts/shares (None), whereas a
    year containing papers but no matching term has a measured zero. An explicit
    range also preserves empty leading/trailing years selected by the caller.
    """
    if years is None:
        known_years = sorted({y for kt in trends.values() for y in kt.years})
        years = list(range(known_years[0], known_years[-1] + 1)) if known_years else []
    rows = []
    for name, kt in trends.items():
        for term in terms:
            normalized = " ".join(paper_tokens(term, None, kt.acronyms, kt.stopwords, kt.n_max)[0])
            for y in years:
                tot = kt.papers_per_year.get(y, 0)
                n = kt.doc_freq.get(normalized, {}).get(y, 0) if tot else None
                rows.append({"conference": name, "term": term, "year": y, "papers": n, "share": n / tot if tot else None})
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
    by_term: dict[str, dict[tuple[str, int], float | None]] = {}
    for r in rows:
        by_term.setdefault(r["term"], {})[(r["conference"], r["year"])] = r["share"]
    w = max(len(c) for c in conferences) + 2
    for term, cells in by_term.items():
        out.append(f"{term}")
        out.append(f"{'':<{w}}" + " ".join(f"{y:>6}" for y in years))
        for c in conferences:
            shares = [cells.get((c, y)) for y in years]
            out.append(f"{c:<{w}}" + " ".join(f"{'—':>6}" if share is None else f"{share:>6.1%}" for share in shares))
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
    if not years:
        print("[error] No papers with a publication year in the selected range.", file=sys.stderr)
        return 1
    years = list(range(yrs[0], yrs[1] + 1)) if yrs else list(range(years[0], years[-1] + 1))
    names = list(corpora)

    terms = [t.strip() for t in args.term]
    if not terms:
        common = shared_risers(trends, k=args.top)
        print(f"Terms rising in all of {', '.join(names)} (delta = late-half share minus early-half share)\n")
        w = max((len(t) for t, _ in common), default=10)
        print(f"{'term':<{w}} " + " ".join(f"{n:>10}" for n in names))
        for t, ds in common:
            print(f"{t:<{w}} " + " ".join(f"{ds[n]:>+10.1%}" for n in names))
        terms = [t for t, _ in common[:3]]
        print()
    rows = term_shares(trends, terms, years=years)
    print(render(rows, names, years))
    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=["conference", "term", "year", "papers", "share"])
            wr.writeheader()
            wr.writerows({key: safe_cell(value) for key, value in row.items()} for row in rows)
        print(f"[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
