"""Reproducible local review of phrase filtering, counts, and acronym definitions.

python -m scripts.audit_trends --label before
Uses the five cached 2016–2025 corpora; writes evidence to data/trend-audit/<label>/.
The "before" label reproduces the former frequency-only filter, using the current
tokenizer and corpus. "after" checks current rankings and any saved baseline counts.
This is a diagnostic review set, not an independently annotated accuracy benchmark.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from paper_trends import background as bg
from paper_trends.keywords import compute_trends, group_families
from paper_trends.store import filter_years, read_jsonl
from paper_trends.text import acronym_definitions, paper_tokens

REVIEW = {
    "ectc": ["hybrid bonding", "heterogeneous integration", "artificial intelligence", "deep learning", "high performance", "low cost"],
    "icassp": ["deep learning", "neural networks", "large language models", "line of sight", "high performance", "real time"],
    "embc": ["machine learning", "deep learning", "neural networks", "magnetic resonance imaging", "high performance", "real time"],
    "sp": ["machine learning", "neural networks", "large language models", "differential privacy", "end to end", "high performance"],
    "globecom": ["reinforcement learning", "federated learning", "reconfigurable intelligent surface", "neural networks", "energy consumption", "high performance", "low cost"],
}


def occurrence_count(tokens: list[str], wanted: list[str]) -> int:
    return sum(tokens[i:i + len(wanted)] == wanted for i in range(len(tokens) - len(wanted) + 1))


def audit(slug: str, baseline: dict | None = None, *, legacy_filter: bool = False,
          allow_count_changes: bool = False) -> dict:
    records = filter_years(read_jsonl(Path(f"data/{slug}.jsonl")), (2016, 2025))
    kt = compute_trends(records, n_min=2, n_max=3, field=bg.field_of(slug))
    if legacy_filter:
        table = bg.load() or {}
        kt.common = {term: fields for term in kt.doc_freq
                     if len(fields := bg.common_fields(term, bg.field_of(slug), table))
                     >= table.get("min_fields", bg.MIN_FIELDS)}
    candidates = set(kt.candidates())
    top = {
        name: [head[0] for head, _ in group_families(fn(32, min_total=10), 8, kt.total)]
        for name, fn in (("rising", kt.rising), ("falling", kt.falling))
    }
    selected = list(dict.fromkeys(REVIEW[slug] + top["rising"] + top["falling"]
                                 + ([r["term"] for r in baseline["rows"]] if baseline else [])))
    counts = {term: Counter() for term in selected}
    roles = {term: Counter() for term in selected}
    samples = {term: {} for term in selected}
    definitions = defaultdict(Counter)
    raw_abstracts = sum(bool(r.get("abstract")) for r in records)
    for r in records:
        # Independently aggregate selected phrases from normalized token windows,
        # without calling phrase_roles, term_mentions, momentum, or papers_with.
        title, abstract = paper_tokens(r.get("title"), r.get("abstract"), kt.acronyms)
        own = {**acronym_definitions(r.get("title")), **acronym_definitions(r.get("abstract"))}
        for key, (_, long) in own.items():
            definitions[key][" ".join(long)] += 1
        for term in selected:
            wanted = term.split()
            nt, na = occurrence_count(title, wanted), occurrence_count(abstract, wanted)
            if not nt and not na:
                continue
            role = "title" if nt else "repeated" if na >= 2 else "once"
            roles[term][role] += 1
            if role == "once":
                continue
            y = r["publication_year"]
            counts[term][y] += 1
            bucket = "early" if y <= 2020 else "late"
            # Deterministic first counted example per half, including unmodified text.
            if bucket not in samples[term]:
                samples[term][bucket] = {"id": r["id"], "doi": r.get("doi"), "year": y,
                    "title": r.get("title"), "abstract": r.get("abstract"), "role": role,
                    "local_definitions": {k: " ".join(v[1]) for k, v in own.items()}}
    rows = []
    for term in selected:
        expected = kt.doc_freq.get(term, {})
        assert dict(counts[term]) == expected, (slug, term, "year counts disagree")
        early = sum(n for y, n in counts[term].items() if y <= 2020) / sum(r["publication_year"] <= 2020 for r in records)
        late = sum(n for y, n in counts[term].items() if y >= 2021) / sum(r["publication_year"] >= 2021 for r in records)
        if term in kt.doc_freq:
            assert all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip((early, late, late-early), kt.momentum(term)))
        rows.append({"term": term, "review_anchor": term in REVIEW[slug], "total": sum(counts[term].values()),
            "by_year": dict(sorted(counts[term].items())), "early": early, "late": late, "delta": late-early,
            "hidden_common": term in kt.common, "fragment": kt.is_fragment(term), "candidate": term in candidates,
            "cross_fields": bg.common_fields(term, bg.field_of(slug)), "roles": dict(roles[term]),
            "examples": samples[term]})
    acronyms = [{"short": key, "chosen": " ".join(value[1]),
                 "definitions": definitions[key].most_common(), "surface": value[0]}
                for key,value in kt.acronyms.defs.items()]
    changes = []
    if baseline:
        previous = {r["term"]: r for r in baseline["rows"]}
        assert len(records) == baseline["papers"]
        for row in rows:
            if row["term"] in previous:
                for key in ("by_year", "early", "late", "delta", "total", "roles"):
                    old = previous[row["term"]][key]
                    current = {str(k): v for k,v in row[key].items()} if key == "by_year" else row[key]
                    if current != old:
                        changes.append({"term": row["term"], "metric": key, "before": old, "after": current})
                        assert allow_count_changes, (slug, row["term"], key, "changed")
    return {"slug":slug,"papers":len(records),"abstracts":raw_abstracts,"years":[2016,2025],
            "top":top,"rows":rows,"acronyms":acronyms,
            "hidden":sorted(kt.common),"checked_terms":len(rows), "baseline_changes": changes,
            "count_check":"passed; independent aggregation shares the production tokenizer and acronym map"}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, choices=("before","after"))
    parser.add_argument("--allow-count-changes", action="store_true",
                        help="record expected normalization corrections instead of requiring unchanged baseline counts")
    parser.add_argument("slugs", nargs="*", choices=tuple(REVIEW))
    args=parser.parse_args()
    out=Path("data/trend-audit")/args.label
    out.mkdir(parents=True,exist_ok=True)
    for slug in args.slugs or REVIEW:
        baseline_path = Path("data/trend-audit/before") / f"{slug}.json"
        baseline = json.loads(baseline_path.read_text()) if args.label == "after" and baseline_path.exists() else None
        result=audit(slug, baseline, legacy_filter=args.label == "before", allow_count_changes=args.allow_count_changes)
        (out/f"{slug}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
        hidden=[r["term"] for r in result["rows"] if r["review_anchor"] and r["hidden_common"]]
        print(f"{slug}: {result['papers']} records; {result['checked_terms']} phrase counts verified; hidden anchors={hidden}",flush=True)


if __name__=="__main__":
    main()
