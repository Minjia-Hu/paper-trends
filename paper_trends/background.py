"""Cross-field frequency evidence for a conservative boilerplate filter.

A small table of document frequencies per *field* (several venues pooled) ships with the
package. A phrase is "common" for a conference when at least `MIN_FIELDS` other fields use
it in >= `MIN_SHARE` of their papers: "high performance" reaches 1 % in devices, circuits,
thermal and reliability; "hybrid bonding" in none. Same-field venues are pooled so that ECTC,
EPTC and ICEPT do not vouch for each other's vocabulary being generic.
Frequency alone does not imply boilerplate: technical phrases such as "deep learning"
remain eligible. Only exact phrases in BOILERPLATE may be hidden by this evidence.

    paper-trends background data/*.jsonl        # rebuild paper_trends/resources/background.json
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from .store import Record, filter_years, parse_years, read_jsonl
from .text import STOPWORDS, term_mentions

RESOURCE = Path(__file__).parent / "resources" / "background.json"
MIN_SHARE = 0.01     # a field "uses" a phrase when this share of its papers mention it
MIN_FIELDS = 3       # ... and the phrase is common when this many other fields use it
STORE_SHARE = 0.005  # shares below this are not stored
VENUE_CAP = 2500     # papers sampled per venue, so one large venue does not define its field

# Explicit, reviewable phrases with little topical content on their own. This is a
# conservative editorial heuristic, not a learned semantic classifier. Match the whole
# phrase: "high performance computing" must not inherit "high performance"'s exclusion.
# Technical properties (energy consumption, real time, high voltage, etc.) stay eligible.
BOILERPLATE = frozenset({
    "high performance", "better performance", "superior performance",
    "excellent performance", "good performance", "improved performance",
    "low cost", "cost effective", "high quality", "next generation",
    "wide range", "wide variety", "large number", "great potential",
    "promising candidate", "promising candidates", "recent years",
    "significant improvement", "significant improvements",
    "significantly improve", "significantly improves", "address this issue",
})

FIELD_OF = {
    "ectc": "packaging", "eptc": "packaging", "icept": "packaging",
    "itherm": "thermal", "eurosime": "thermal",
    "irps": "reliability",
    "iedm": "devices", "vlsi": "devices", "imw": "devices",
    "isscc": "circuits",
    "cvpr": "vision",
    "interspeech": "speech",
    "icra": "robotics",
    "icassp": "signal_processing",
    "embc": "biomedical_engineering",
    "sp": "security",
    "globecom": "communications",
}


def field_of(slug: str | None) -> str | None:
    return FIELD_OF.get((slug or "").lower())


def build(corpora: dict[str, list[Record]], fields: dict[str, str] | None = None) -> dict[str, Any]:
    """corpora: slug -> records. Venues without a field form their own field."""
    fields = fields or FIELD_OF
    df: dict[str, Counter[str]] = {}
    n: Counter[str] = Counter()
    venues: dict[str, list[str]] = {}
    for slug, recs in sorted(corpora.items()):
        f = fields.get(slug, slug)
        venues.setdefault(f, []).append(slug)
        step = max(1, math.ceil(len(recs) / VENUE_CAP))
        counts = df.setdefault(f, Counter())
        for r in recs[::step]:
            n[f] += 1
            counts.update(term_mentions(r.get("title"), r.get("abstract"), 1, 3, STOPWORDS).keys())
    terms: dict[str, dict[str, float]] = {}
    for f, counts in df.items():
        for t, c in counts.items():
            share = c / n[f]
            if share >= STORE_SHARE:
                terms.setdefault(t, {})[f] = round(share, 4)
    return {"built": date.today().isoformat(), "min_share": MIN_SHARE, "min_fields": MIN_FIELDS,
            "fields": {f: {"papers": n[f], "venues": venues[f]} for f in sorted(n)}, "terms": terms}


@lru_cache(maxsize=1)
def load() -> dict[str, Any] | None:
    try:
        return json.loads(RESOURCE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def common_fields(term: str, own_field: str | None = None, table: dict[str, Any] | None = None) -> list[str]:
    """Other fields in which `term` is used by at least MIN_SHARE of the papers."""
    table = table if table is not None else load()
    if not table:
        return []
    shares = table["terms"].get(term)
    if not shares:
        return []
    return sorted(f for f, s in shares.items() if f != own_field and s >= MIN_SHARE)


def is_common(term: str, own_field: str | None = None, table: dict[str, Any] | None = None) -> bool:
    return len(common_fields(term, own_field, table)) >= MIN_FIELDS


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends background", description="Rebuild the cross-field background table from fetched corpora.")
    p.add_argument("jsonl", type=Path, nargs="+")
    p.add_argument("--years", default="2016-2025")
    p.add_argument("--out", type=Path, default=RESOURCE)
    args = p.parse_args(argv)
    corpora = {path.stem: filter_years(read_jsonl(path), parse_years(args.years)) for path in args.jsonl}
    table = build(corpora)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    load.cache_clear()
    for f, meta in table["fields"].items():
        print(f"  {f:<12} {meta['papers']:>6} papers  {', '.join(meta['venues'])}", file=sys.stderr)
    n_common = sum(1 for t in table["terms"] if len([1 for s in table["terms"][t].values() if s >= MIN_SHARE]) >= MIN_FIELDS)
    print(f"[background] {len(table['terms'])} phrases stored, {n_common} used by >= {MIN_FIELDS} fields -> {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
