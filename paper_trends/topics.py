"""Topic evolution: how a conference's subject mix shifts over time.

Two methods:
- ``nmf`` (default): NMF on TF-IDF of title+abstract, topics labelled by their top terms.
  Fully reproducible (fixed seed), no external models.
- ``openalex``: OpenAlex's own per-work topic labels (coarse; fine for broad venues).
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .csv_export import safe_row
from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS, _is_number, load_stopwords, tokenize


@dataclass
class Topic:
    id: int
    label: str
    terms: list[str]
    examples: list[str] = field(default_factory=list)  # representative paper titles


@dataclass
class TopicTrends:
    years: list[int]
    papers_per_year: dict[int, int]
    topics: list[Topic]
    by_year: dict[int, dict[int, int]]  # topic id -> year -> papers (dominant topic)
    method: str
    # index of the record in the input list -> its dominant topic id (NMF only)
    assignments: dict[int, int] = field(default_factory=dict)

    def total(self, tid: int) -> int:
        return sum(self.by_year[tid].values())

    def share(self, tid: int, year: int) -> float:
        n = self.papers_per_year.get(year, 0)
        return self.by_year[tid].get(year, 0) / n if n else 0.0

    def momentum(self, tid: int) -> tuple[float, float, float]:
        ys = self.years
        if len(ys) < 2:
            return 0.0, 0.0, 0.0
        split = ys[len(ys) // 2]
        early = [y for y in ys if y < split]
        late = [y for y in ys if y >= split]
        e = _pooled(self, tid, early)
        l = _pooled(self, tid, late)
        return e, l, l - e

    def ordered(self) -> list[Topic]:
        return sorted(self.topics, key=lambda t: -self.total(t.id))


def _pooled(tt: TopicTrends, tid: int, years: list[int]) -> float:
    n = sum(tt.papers_per_year.get(y, 0) for y in years)
    hits = sum(tt.by_year[tid].get(y, 0) for y in years)
    return hits / n if n else 0.0


def _doc_text(rec: Record) -> str:
    return " ".join(tokenize(f"{rec.get('title') or ''}. {rec.get('abstract') or ''}"))


def _topic_terms(text: str, stopwords: frozenset[str]) -> list[str]:
    """Unigrams/bigrams with scientific tokens retained and numbers as boundaries.

    Removing "2024" from "copper 2024 bonding" must not invent "copper bonding".
    Stopword handling stays consistent with the previous vectorizer: stopwords are
    omitted before forming bigrams within each numeric-free run.
    """
    terms: list[str] = []
    previous: str | None = None
    for token in tokenize(text):
        if _is_number(token) or len(token) < 2:
            previous = None
            continue
        if token in stopwords:
            continue
        terms.append(token)
        if previous is not None:
            terms.append(f"{previous} {token}")
        previous = token
    return terms


# ---- NMF ----------------------------------------------------------------------


class InsufficientTopicData(ValueError):
    """The selected papers do not contain enough usable text to fit topics."""


def make_label(terms: list[str], n: int = 3) -> str:
    """Label from the top terms, preferring phrases: a single word is skipped when one of
    the top terms is a phrase containing it ('wafer', 'level' -> 'wafer level')."""
    phrases = [t for t in terms if " " in t]
    picked: list[str] = []
    for t in terms:
        if " " not in t and any(t in ph.split() for ph in phrases):
            continue
        picked.append(t)
        if len(picked) == n:
            break
    return " / ".join(picked or terms[:n])


def compute_nmf(
    records: list[Record],
    *,
    n_topics: int = 12,
    n_terms: int = 8,
    stopwords: frozenset[str] = STOPWORDS,
    min_df: int = 5,
    max_df: float = 0.4,
    seed: int = 0,
) -> TopicTrends:
    from sklearn.decomposition import NMF
    from sklearn.feature_extraction.text import TfidfVectorizer

    doc_idx = [i for i, r in enumerate(records) if r.get("publication_year") and (r.get("abstract") or r.get("title"))]
    docs = [records[i] for i in doc_idx]
    if len(docs) < 2:
        raise InsufficientTopicData("Need at least two papers with text to fit topics.")
    texts = [_doc_text(r) for r in docs]
    # scale the pruning thresholds down for small corpora so the vocabulary never empties
    min_df = max(1, min(min_df, len(docs) // 50))
    n_topics = max(1, min(n_topics, len(docs) - 1))

    def vectorize(min_df_: int, max_df_: float):
        vec_ = TfidfVectorizer(
            analyzer=lambda text: _topic_terms(text, stopwords),
            min_df=min_df_,
            max_df=max_df_,
            sublinear_tf=True,
        )
        return vec_, vec_.fit_transform(texts)

    try:
        vec, X = vectorize(min_df, max_df)
    except ValueError:  # "After pruning, no terms remain" on tiny/homogeneous corpora
        try:
            vec, X = vectorize(1, 1.0)
        except ValueError as exc:
            raise InsufficientTopicData("No usable vocabulary remains after text filtering.") from exc
    n_topics = min(n_topics, X.shape[1])
    model = NMF(n_components=n_topics, init="nndsvda" if n_topics <= min(X.shape) else "random", random_state=seed, max_iter=400)
    W = model.fit_transform(X)  # docs x topics
    H = model.components_  # topics x terms
    vocab = vec.get_feature_names_out()

    topics: list[Topic] = []
    for k in range(n_topics):
        top_idx = H[k].argsort()[::-1][:n_terms]
        terms = [vocab[i] for i in top_idx]
        topics.append(Topic(id=k, label=make_label(terms), terms=terms))

    dominant = W.argmax(axis=1)
    papers: Counter[int] = Counter()
    by_year: dict[int, dict[int, int]] = {k: defaultdict(int) for k in range(n_topics)}
    assignments: dict[int, int] = {}
    for i, r, k, w in zip(doc_idx, docs, dominant, W):
        y = r["publication_year"]
        papers[y] += 1
        if w[k] > 0:
            by_year[k][y] += 1
            assignments[i] = int(k)
    # representative papers: highest topic weight, tie-break by citations
    for k in range(n_topics):
        idx = W[:, k].argsort()[::-1][:20]
        best = sorted(idx, key=lambda i: (-W[i, k], -(docs[i].get("cited_by_count") or 0)))[:3]
        topics[k].examples = [docs[i].get("title") or "" for i in best]
    return TopicTrends(
        years=sorted(papers),
        papers_per_year=dict(papers),
        topics=topics,
        by_year={k: dict(v) for k, v in by_year.items()},
        method="nmf",
        assignments=assignments,
    )


# ---- OpenAlex topics ----------------------------------------------------------------


def compute_openalex(records: list[Record], level: str = "topic") -> TopicTrends:
    """Use each paper's primary OpenAlex topic (or its subfield)."""
    papers: Counter[int] = Counter()
    ids: dict[str, int] = {}
    labels: dict[int, str] = {}
    by_year: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in records:
        y = r.get("publication_year")
        tops = r.get("topics") or []
        if not y or not tops:
            continue
        t = tops[0]
        name = t.get("subfield") if level == "subfield" else t.get("name")
        if not name:
            continue
        papers[y] += 1
        tid = ids.setdefault(name, len(ids))
        labels[tid] = name
        by_year[tid][y] += 1
    topics = [Topic(id=i, label=labels[i], terms=[]) for i in range(len(ids))]
    return TopicTrends(
        years=sorted(papers),
        papers_per_year=dict(papers),
        topics=topics,
        by_year={k: dict(v) for k, v in by_year.items()},
        method=f"openalex-{level}",
    )


# ---- rendering -----------------------------------------------------------------


def render_table(tt: TopicTrends, topics: list[Topic], width: int = 44) -> str:
    head = f"{'topic':<{width}} {'papers':>6} " + " ".join(f"{y % 100:>5}" for y in tt.years) + "   delta"
    lines = [head, "-" * len(head)]
    for t in topics:
        label = t.label if len(t.label) <= width else t.label[: width - 1] + "…"
        cells = " ".join(f"{tt.share(t.id, y):>5.0%}" for y in tt.years)
        d = tt.momentum(t.id)[2]
        lines.append(f"{label:<{width}} {tt.total(t.id):>6} {cells}  {d:>+6.1%}")
    return "\n".join(lines)


def render_details(tt: TopicTrends, topics: list[Topic]) -> str:
    out = []
    for t in topics:
        e, l, d = tt.momentum(t.id)
        out.append(f"[{t.id:>2}] {t.label}   ({tt.total(t.id)} papers, {e:.1%} -> {l:.1%}, {d:+.1%})")
        if t.terms:
            out.append("     terms:    " + ", ".join(t.terms))
        for ex in t.examples:
            out.append(f"     e.g.      {ex}")
    return "\n".join(out)


def write_csv(tt: TopicTrends, topics: list[Topic], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["topic_id", "label", "terms", "papers", *[f"count_{y}" for y in tt.years], *[f"share_{y}" for y in tt.years]])
        for t in topics:
            wr.writerow(safe_row(
                [t.id, t.label, "; ".join(t.terms), tt.total(t.id)]
                + [tt.by_year[t.id].get(y, 0) for y in tt.years]
                + [f"{tt.share(t.id, y):.4f}" for y in tt.years]
            ))


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends topics", description="Topic evolution over time.")
    p.add_argument("jsonl", type=Path)
    p.add_argument("--years")
    p.add_argument("--method", choices=["nmf", "openalex", "openalex-subfield"], default="nmf")
    p.add_argument("--n-topics", type=int, default=12, help="number of NMF topics")
    p.add_argument("--n-terms", type=int, default=8, help="terms shown per NMF topic")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--stopwords", type=Path, help="extra stopwords file, one term per line")
    p.add_argument("--top", type=int, default=20, help="max topics to show (openalex method)")
    p.add_argument("--details", action="store_true", help="print terms and example papers per topic")
    p.add_argument("--csv", type=Path)
    args = p.parse_args(argv)

    records = filter_years(read_jsonl(args.jsonl), parse_years(args.years))
    if not any(r.get("publication_year") for r in records):
        print("[error] No papers with a publication year in the selected range.", file=sys.stderr)
        return 1
    try:
        if args.method == "nmf":
            extra = args.stopwords.read_text().splitlines() if args.stopwords else None
            tt = compute_nmf(records, n_topics=args.n_topics, n_terms=args.n_terms, stopwords=load_stopwords(extra), seed=args.seed)
        else:
            tt = compute_openalex(records, level="subfield" if args.method.endswith("subfield") else "topic")
    except InsufficientTopicData as exc:
        print(f"[error] Cannot fit topics: {exc}", file=sys.stderr)
        return 1
    if not tt.years:
        print("[error] No papers with usable topic data in the selected year range.", file=sys.stderr)
        return 1
    topics = tt.ordered()[: args.top if args.method != "nmf" else None]
    n_used = sum(tt.papers_per_year.values())
    print(f"{n_used} papers, {tt.years[0]}-{tt.years[-1]}, method={tt.method}; share of papers per year by dominant topic\n")
    print(render_table(tt, topics))
    if args.details or args.method == "nmf":
        print()
        print(render_details(tt, topics))
    if args.csv:
        write_csv(tt, topics, args.csv)
        print(f"\n[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
