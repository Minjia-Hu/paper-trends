"""Check the phrase rules against the one signal the data carries for free: the title.

The title is the author's own one-line answer to "what is this paper about". So for every
phrase of a paper, take its role in the *abstract alone* (mentioned more than once, or just
once) and ask how often the same phrase is also in the title. A role whose phrases rarely
make it into titles is a weak sign of topicality. This is how the counting rule was chosen
(ECTC 2016–2025: repeated 32 %, once in the opening 21 %, once later 7 %) and how a change
to it can be judged without hand-labelled papers. It is a sanity check, not a gold standard:
titles are short, so even repeated phrases reach them only a third of the time.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .keywords import compute_trends, corpus_acronyms
from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS, _gram_positions, paper_tokens


def title_agreement(records: list[Record], n_min: int = 2, n_max: int = 3, top: int = 300,
                    stopwords: frozenset[str] = STOPWORDS) -> dict[str, tuple[int, float]]:
    """role -> (abstract mentions among the `top` phrases, share also found in the title).
    Roles are judged from the abstract only: "repeated", "once (opening)" for a single
    mention in the first fifth of the abstract, "once (later)" for one further on."""
    kt = compute_trends(records, n_min=n_min, n_max=n_max, stopwords=stopwords, background=None)
    phrases = set(kt.top_terms(top, min_total=5))
    acronyms = corpus_acronyms(records, n_max, stopwords)
    hit: Counter[str] = Counter()
    tot: Counter[str] = Counter()
    for r in records:
        if not r.get("abstract") or not r.get("title"):
            continue
        t_toks, a_toks = paper_tokens(r.get("title"), r.get("abstract"), acronyms, stopwords, n_max)
        in_title = set(_gram_positions(t_toks, n_min, n_max, stopwords))
        opening = max(1, len(a_toks) // 5)
        for g, pos in _gram_positions(a_toks, n_min, n_max, stopwords).items():
            if g not in phrases:
                continue
            role = "repeated" if len(pos) >= 2 else ("once (opening)" if pos[0] < opening else "once (later)")
            tot[role] += 1
            hit[role] += g in in_title
    return {role: (tot[role], hit[role] / tot[role] if tot[role] else 0.0) for role in ("repeated", "once (opening)", "once (later)")}


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends validate", description="How well each mention role predicts a phrase's presence in the title.")
    p.add_argument("jsonl", type=Path)
    p.add_argument("--years", help="restrict to a year range, e.g. 2016-2025")
    p.add_argument("--ngram", default="2-3")
    p.add_argument("--top", type=int, default=300, help="judge the N most frequent phrases")
    args = p.parse_args(argv)
    records = filter_years(read_jsonl(args.jsonl), parse_years(args.years))
    n_min, n_max = parse_years(args.ngram) or (2, 3)
    rows = title_agreement(records, n_min, n_max, args.top)
    print(f"{len(records)} papers; roles judged from the abstract alone, top {args.top} phrases\n")
    print(f"{'role in abstract':18} {'mentions':>9} {'also in title':>14}")
    for role, (n, share) in rows.items():
        print(f"{role:18} {n:>9,} {share:>14.1%}")
    print("\nThe counting rule treats 'repeated' (and the title itself) as topical, single mentions as not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
