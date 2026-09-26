"""Keyword / n-gram trends: how often each term appears in a conference's papers, by year."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS, doc_terms, load_stopwords


@dataclass
class KeywordTrends:
    years: list[int]
    papers_per_year: dict[int, int]
    # term -> year -> number of papers mentioning the term
    doc_freq: dict[str, dict[int, int]]
    abstract_coverage: dict[int, float] = field(default_factory=dict)
    # if set, terms that are (almost) always part of a longer term are hidden from rankings
    collapse_ratio: float | None = 0.8

    def total(self, term: str) -> int:
        return sum(self.doc_freq[term].values())

    def share(self, term: str, year: int) -> float:
        n = self.papers_per_year.get(year, 0)
        return self.doc_freq[term].get(year, 0) / n if n else 0.0

    def candidates(self) -> list[str]:
        terms = list(self.doc_freq)
        if self.collapse_ratio is None:
            return terms
        return collapse_subphrases(terms, self.total, self.collapse_ratio)

    def top_terms(self, k: int, min_total: int = 1) -> list[str]:
        ranked = sorted(self.candidates(), key=lambda t: (-self.total(t), t))
        return [t for t in ranked if self.total(t) >= min_total][:k]

    def momentum(self, term: str, split: int | None = None) -> tuple[float, float, float]:
        """(early share, late share, delta). Years are split in half unless `split` given."""
        ys = self.years
        if len(ys) < 2:
            return 0.0, 0.0, 0.0
        split = split if split is not None else ys[len(ys) // 2]
        early = [y for y in ys if y < split]
        late = [y for y in ys if y >= split]
        e = _pooled_share(self, term, early)
        l = _pooled_share(self, term, late)
        return e, l, l - e

    def rising(self, k: int, min_total: int = 10) -> list[tuple[str, float, float, float]]:
        return self._by_momentum(k, min_total, reverse=True)

    def falling(self, k: int, min_total: int = 10) -> list[tuple[str, float, float, float]]:
        return self._by_momentum(k, min_total, reverse=False)

    def emerging(
        self, k: int, min_total: int = 10, max_early: float = 0.002, min_late: float = 0.01
    ) -> list[tuple[str, int, float, float]]:
        """Terms that were (almost) absent in the early half and are established now:
        (term, first year seen, early share, late share), ranked by late share.
        Unlike `rising`, this is not dominated by already-common words."""
        rows = []
        for t in self.candidates():
            if self.total(t) < min_total:
                continue
            e, l, _ = self.momentum(t)
            if e <= max_early and l >= min_late:
                first = min(y for y, n in self.doc_freq[t].items() if n)
                rows.append((t, first, e, l))
        rows.sort(key=lambda r: (-r[3], r[0]))
        return rows[:k]

    def _by_momentum(self, k: int, min_total: int, reverse: bool):
        rows = []
        for t in self.candidates():
            if self.total(t) < min_total:
                continue
            e, l, d = self.momentum(t)
            rows.append((t, e, l, d))
        rows.sort(key=lambda r: (r[3], r[0]), reverse=reverse)
        if reverse:
            rows.sort(key=lambda r: -r[3])
        return rows[:k]


def collapse_subphrases(terms: list[str], total, ratio: float) -> list[str]:
    """Drop a term when a longer term containing it (on word boundaries) accounts for at
    least `ratio` of its occurrences — e.g. 'performance computing' disappears into
    'high-performance computing', 'intelligence ai' into 'artificial intelligence ai'."""
    by_len: dict[int, list[str]] = defaultdict(list)
    for t in terms:
        by_len[len(t.split())].append(t)
    # index longer terms by each of their contained sub-phrases
    contained: dict[str, int] = defaultdict(int)  # sub-phrase -> max total of a containing term
    for n, group in by_len.items():
        for t in group:
            words = t.split()
            tot = total(t)
            for size in range(1, n):
                for i in range(n - size + 1):
                    sub = " ".join(words[i : i + size])
                    if tot > contained[sub]:
                        contained[sub] = tot
    return [t for t in terms if contained.get(t, 0) < ratio * total(t)]


def _pooled_share(kt: KeywordTrends, term: str, years: list[int]) -> float:
    n = sum(kt.papers_per_year.get(y, 0) for y in years)
    hits = sum(kt.doc_freq[term].get(y, 0) for y in years)
    return hits / n if n else 0.0


def papers_with(records: list[Record], term: str, text: str = "title+abstract") -> list[Record]:
    """Papers whose title/abstract contains `term` as a whole phrase (same tokenization as
    the counts, so the result matches the document frequency)."""
    from .text import tokenize

    needle = " " + " ".join(tokenize(term)) + " "
    hits = []
    for r in records:
        hay = " " + " ".join(tokenize(build_text(r, text))) + " "
        if needle in hay:
            hits.append(r)
    hits.sort(key=lambda r: (-(r.get("publication_year") or 0), -(r.get("cited_by_count") or 0)))
    return hits


def hyphen_forms(records: list[Record], text: str = "title+abstract") -> Counter[str]:
    """How often each hyphenated compound ("co-packaged", "wafer-level") occurs in the raw
    text. Tokenisation splits hyphens so that spellings merge for counting; this lets the
    display layer put them back."""
    pat = re.compile(r"\b[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\b")
    c: Counter[str] = Counter()
    for r in records:
        for m in pat.findall(build_text(r, text)):
            c[m.lower()] += 1
    return c


def restore_hyphens(term: str, forms: Counter[str], min_count: int = 3) -> str:
    """Re-join adjacent words of `term` when the corpus mostly writes them hyphenated:
    "co packaged optics" -> "co-packaged optics" if "co-packaged" is common."""
    words = term.split()
    out: list[str] = []
    i = 0
    while i < len(words):
        joined = None
        # longest hyphenated run first (e.g. "state-of-the-art")
        for j in range(len(words), i + 1, -1):
            cand = "-".join(words[i:j])
            if forms.get(cand, 0) >= min_count:
                joined, i = cand, j
                break
        if joined is None:
            out.append(words[i])
            i += 1
        else:
            out.append(joined)
    return " ".join(out)


def build_text(rec: Record, mode: str) -> str:
    title = rec.get("title") or ""
    if mode == "title":
        return title
    return f"{title}. {rec.get('abstract') or ''}"


def compute_trends(
    records: list[Record],
    *,
    text: str = "title+abstract",
    n_min: int = 1,
    n_max: int = 3,
    stopwords: frozenset[str] = STOPWORDS,
    min_total: int = 2,
) -> KeywordTrends:
    papers: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    df: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        y = r.get("publication_year")
        if not y:
            continue
        papers[y] += 1
        if r.get("abstract"):
            with_abs[y] += 1
        for term in doc_terms(build_text(r, text), n_min, n_max, stopwords):
            df[term][y] += 1
    # prune rare terms to keep memory/output sane
    pruned = {t: dict(ys) for t, ys in df.items() if sum(ys.values()) >= min_total}
    years = sorted(papers)
    return KeywordTrends(
        years=years,
        papers_per_year=dict(papers),
        doc_freq=pruned,
        abstract_coverage={y: with_abs[y] / papers[y] for y in years},
    )


# ---- rendering -----------------------------------------------------------------


def render_top_table(kt: KeywordTrends, terms: list[str], as_share: bool = True) -> str:
    w = max((len(t) for t in terms), default=10)
    head = f"{'term':<{w}} {'total':>6} " + " ".join(f"{y:>6}" for y in kt.years)
    lines = [head, "-" * len(head)]
    for t in terms:
        cells = []
        for y in kt.years:
            cells.append(f"{kt.share(t, y):>6.1%}" if as_share else f"{kt.doc_freq[t].get(y, 0):>6}")
        lines.append(f"{t:<{w}} {kt.total(t):>6} " + " ".join(cells))
    return "\n".join(lines)


def render_emerging(rows: list[tuple[str, int, float, float]], title: str) -> str:
    w = max((len(r[0]) for r in rows), default=10)
    lines = [title, f"{'term':<{w}} {'first':>6} {'early':>7} {'late':>7}", "-" * (w + 23)]
    for t, first, e, l in rows:
        lines.append(f"{t:<{w}} {first:>6} {e:>7.1%} {l:>7.1%}")
    return "\n".join(lines)


def render_momentum(rows: list[tuple[str, float, float, float]], title: str) -> str:
    w = max((len(r[0]) for r in rows), default=10)
    lines = [title, f"{'term':<{w}} {'early':>7} {'late':>7} {'delta':>7}", "-" * (w + 24)]
    for t, e, l, d in rows:
        lines.append(f"{t:<{w}} {e:>7.1%} {l:>7.1%} {d:>+7.1%}")
    return "\n".join(lines)


def write_csv(kt: KeywordTrends, terms: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["term", "total", *[f"count_{y}" for y in kt.years], *[f"share_{y}" for y in kt.years]])
        for t in terms:
            wr.writerow(
                [t, kt.total(t)]
                + [kt.doc_freq[t].get(y, 0) for y in kt.years]
                + [f"{kt.share(t, y):.4f}" for y in kt.years]
            )


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends keywords", description="Keyword / n-gram trends by year.")
    p.add_argument("jsonl", type=Path, help="corpus produced by `fetch`, e.g. data/ectc.jsonl")
    p.add_argument("--years", help="restrict to a year range, e.g. 2016-2025")
    p.add_argument("--text", choices=["title", "title+abstract"], default="title+abstract")
    p.add_argument("--ngram", default="1-3", help="n-gram range, default 1-3")
    p.add_argument("--top", type=int, default=30, help="how many top terms to show")
    p.add_argument("--movers", type=int, default=15, help="how many rising/falling terms to show")
    p.add_argument("--emerging", type=int, default=15, help="how many emerging terms (absent early, established late) to show")
    p.add_argument("--min-total", type=int, default=10, help="min papers a term must appear in to be a mover")
    p.add_argument("--stopwords", type=Path, help="extra stopwords file, one term per line")
    p.add_argument("--counts", action="store_true", help="show raw paper counts instead of share")
    p.add_argument("--keep-subphrases", action="store_true", help="do not hide terms that are mostly part of longer terms")
    p.add_argument("--csv", type=Path, help="also write the top terms table to CSV")
    args = p.parse_args(argv)

    records = filter_years(read_jsonl(args.jsonl), parse_years(args.years))
    n_min, n_max = parse_years(args.ngram) or (1, 3)
    extra = args.stopwords.read_text().splitlines() if args.stopwords else None
    kt = compute_trends(records, text=args.text, n_min=n_min, n_max=n_max, stopwords=load_stopwords(extra))
    if args.keep_subphrases:
        kt.collapse_ratio = None

    low = [y for y, c in kt.abstract_coverage.items() if c < 0.5]
    if low and args.text != "title":
        print(
            f"[warn] abstract coverage < 50% for {low}; those years under-count terms. "
            "Consider --years to exclude them or --text title.",
            file=sys.stderr,
        )

    top = kt.top_terms(args.top)
    print(f"{len(records)} papers, {kt.years[0]}-{kt.years[-1]}, text={args.text}, ngram={n_min}-{n_max}\n")
    print(render_top_table(kt, top, as_share=not args.counts))
    print()
    print(render_momentum(kt.rising(args.movers, args.min_total), f"RISING (share of papers, early vs late half)"))
    print()
    print(render_momentum(kt.falling(args.movers, args.min_total), f"FALLING (share of papers, early vs late half)"))
    if args.emerging:
        print()
        print(render_emerging(kt.emerging(args.emerging, args.min_total), "EMERGING (near-absent in the early half, >= 1% of papers in the late half)"))
    if args.csv:
        write_csv(kt, top, args.csv)
        print(f"\n[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
