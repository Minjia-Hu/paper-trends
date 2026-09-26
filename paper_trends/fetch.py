"""Resolve a conference to OpenAlex works and dump them as JSONL."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .openalex import OpenAlex, reconstruct_abstract, year_filter
from .store import parse_years, write_jsonl

OR_LIMIT = 50  # OpenAlex allows at most 50 values in one OR filter

# Proceedings front matter that OpenAlex indexes as "works". OpenAlex flags some of it
# (is_paratext / type=paratext); the rest is caught by title.
_FRONT_MATTER_RE = re.compile(
    r"^\s*(?:"
    r"\[?front cover|\[?back cover|title page|copyright|table of contents|foreword|preface|"
    r"(?:author|subject|keyword) index|index(?: to authors)?$|message from|welcome|"
    r"(?:program|executive|organizing|technical|steering) committee|committees?$|"
    r"(?:[a-z]+ )?\d{4} (?:program|executive|organizing|technical program) committee|"
    r"(?:[a-z]+ )?\d{4} (?:timetable|awards?|foreword|reflections|tutorials?|panel discussion|index to authors|"
    r"session \d+|committees?|sponsors?|short course|forums?|highlights?)\b|"
    r"conference (?:info|committees|sponsors|guide)|\d{4} ieee \d+\w* electronic components|"
    r"sponsors?$|timetable|list of (?:reviewers|contributors)|reviewers$|"
    r"session \d+ overview|panel discussion|panel session|tutorials?\b|short course|"
    r"[a-z]{1,3}\d{1,2}:\s"  # ISSCC-style forum / evening-event codes: "F6: ...", "EE3: ..."
    r")",
    re.I,
)
# Invited talks / panels whose "abstract" says there is no paper.
_NO_PAPER_RE = re.compile(r"not (?:been )?made available for publication|\[\d+ abstracts?\]", re.I)


def is_front_matter(work: dict[str, Any]) -> bool:
    if work.get("is_paratext") or work.get("type") in {"paratext", "editorial"}:
        return True
    title = work.get("title") or ""
    if _FRONT_MATTER_RE.match(title) or _NO_PAPER_RE.search(title):
        return True
    inv = work.get("abstract_inverted_index") or {}
    if inv and len(inv) < 60:  # short blurbs only; a real abstract is longer
        return bool(_NO_PAPER_RE.search(" ".join(inv)))
    return False


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve_sources(client: OpenAlex, query: str) -> list[dict[str, Any]]:
    """Sources whose name contains every word of `query` (punctuation/case-insensitive)."""
    key = _norm(query)
    hits = [s for s in client.search_sources(query) if key in _norm(s["display_name"])]
    return sorted(hits, key=lambda s: s["display_name"])


def build_filters(
    source_ids: list[str],
    doi_prefixes: list[str],
    years: tuple[int, int] | None,
) -> list[tuple[str, str | None]]:
    """(filter expression, doi prefix it came from or None) pairs."""
    yf = year_filter(years)
    filters: list[tuple[str, str | None]] = []
    ids = [s.rsplit("/", 1)[-1] for s in source_ids]
    for i in range(0, len(ids), OR_LIMIT):
        chunk = "|".join(ids[i : i + OR_LIMIT])
        filters.append((f"primary_location.source.id:{chunk}{yf}", None))
    for pfx in doi_prefixes:
        # OpenAlex matches DOI prefixes case-sensitively against lower-cased DOIs.
        filters.append((f"doi_starts_with:{pfx.lower()}{yf}", pfx.lower()))
    return filters


def doi_has_prefix(doi: str | None, prefix: str) -> bool:
    """True when `doi` is `prefix` followed by an optional IEEE conference number and a
    dot — i.e. the venue acronym ends there. `10.1109/isca` must not match ISCAS papers
    (10.1109/ISCAS45731.2020...), and `10.1109/imw` must not match IMWS-AMP."""
    d = (doi or "").lower().removeprefix("https://doi.org/")
    return bool(re.match(re.escape(prefix.lower()) + r"\d*\.", d))


def slim_authorships(authorships: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for a in authorships or []:
        author = a.get("author") or {}
        out.append(
            {
                "author_id": author.get("id"),
                "author_name": author.get("display_name"),
                "position": a.get("author_position"),
                "institutions": [
                    {
                        "id": inst.get("id"),
                        "name": inst.get("display_name"),
                        "country": inst.get("country_code"),
                    }
                    for inst in a.get("institutions") or []
                ],
                "raw_affiliations": a.get("raw_affiliation_strings") or [],
            }
        )
    return out


def to_record(work: dict[str, Any]) -> dict[str, Any]:
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    return {
        "id": work["id"],
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "authorships": slim_authorships(work.get("authorships")),
        "cited_by_count": work.get("cited_by_count", 0),
        "type": work.get("type"),
        "source_id": src.get("id"),
        "source_name": src.get("display_name") or loc.get("raw_source_name"),
        # OpenAlex's own classification (coarse but free): topics and tagged keywords
        "topics": [
            {
                "id": t.get("id"),
                "name": t.get("display_name"),
                "score": t.get("score"),
                "subfield": (t.get("subfield") or {}).get("display_name"),
                "field": (t.get("field") or {}).get("display_name"),
            }
            for t in work.get("topics") or []
        ],
        "oa_keywords": [
            {"name": k.get("display_name"), "score": k.get("score")} for k in work.get("keywords") or []
        ],
    }


def fetch_conference(
    client: OpenAlex,
    query: str,
    *,
    doi_prefix: str | list[str] | None = None,
    source_ids: list[str] | None = None,
    years: tuple[int, int] | None = None,
    log=print,
) -> list[dict[str, Any]]:
    if source_ids is None:
        sources = resolve_sources(client, query)
        source_ids = [s["id"] for s in sources]
        log(f"[sources] {len(sources)} matched '{query}'")
        for s in sources:
            log(f"  {s['id'].rsplit('/', 1)[-1]:>12}  {s.get('works_count', 0):>6} works  {s['display_name']}")
    prefixes = [doi_prefix] if isinstance(doi_prefix, str) else list(doi_prefix or [])
    if not source_ids and not prefixes:
        raise SystemExit(
            f"No OpenAlex source matched '{query}'. Try a different spelling, "
            "or pass --doi-prefix (e.g. 10.1109/ectc) / --source S123."
        )

    filters = build_filters(source_ids, prefixes, years)
    seen: dict[str, dict[str, Any]] = {}
    skipped = 0
    other_venue = 0
    for f, pfx in filters:
        n_before = len(seen)
        for work in client.works_by_filter(f):
            if work["id"] in seen:
                continue
            if pfx and not doi_has_prefix(work.get("doi"), pfx):
                other_venue += 1  # e.g. ISCAS caught by the ISCA prefix
                continue
            if is_front_matter(work):
                skipped += 1
                continue
            seen[work["id"]] = to_record(work)
        log(f"[works] +{len(seen) - n_before:>5} new  (filter: {f[:90]}{'...' if len(f) > 90 else ''})")
    records = sorted(seen.values(), key=lambda r: (r["publication_year"] or 0, r["id"]))
    log(f"[works] {len(records)} unique works total; {skipped} front-matter items skipped; {other_venue} other-venue DOIs ignored")
    return records


def coverage_table(records: list[dict[str, Any]]) -> str:
    total: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    for r in records:
        y = r.get("publication_year") or 0
        total[y] += 1
        if r.get("abstract"):
            with_abs[y] += 1
    lines = [f"{'year':>6} {'papers':>8} {'abstracts':>10} {'coverage':>9}", "-" * 37]
    for y in sorted(total):
        n, a = total[y], with_abs[y]
        lines.append(f"{y:>6} {n:>8} {a:>10} {a / n:>8.1%}")
    n, a = sum(total.values()), sum(with_abs.values())
    lines.append("-" * 37)
    lines.append(f"{'all':>6} {n:>8} {a:>10} {a / n if n else 0:>8.1%}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(
        prog="paper-trends fetch",
        description="Fetch all works of a conference from OpenAlex into a JSONL file.",
    )
    p.add_argument("query", help='conference name, e.g. "Electronic Components and Technology Conference"')
    p.add_argument("--years", help="year or range, e.g. 2016-2026")
    p.add_argument("--doi-prefix", action="append", default=[], help="also include works whose DOI starts with this, e.g. 10.1109/ectc (repeatable)")
    p.add_argument("--source", action="append", help="explicit OpenAlex source ID (repeatable); skips name search")
    p.add_argument("--out", type=Path, help="output path (default data/<slug>.jsonl)")
    p.add_argument("--name", help="short slug used for the default output file, e.g. ectc")
    args = p.parse_args(argv)

    slug = (args.name or re.sub(r"[^a-z0-9]+", "-", args.query.lower()).strip("-"))
    out = args.out or Path("data") / f"{slug}.jsonl"

    client = OpenAlex()
    records = fetch_conference(
        client,
        args.query,
        doi_prefix=args.doi_prefix,
        source_ids=args.source,
        years=parse_years(args.years),
        log=lambda m: print(m, file=sys.stderr),
    )
    write_jsonl(records, out)
    print(f"[done] wrote {len(records)} records -> {out}", file=sys.stderr)
    print()
    print(coverage_table(records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
