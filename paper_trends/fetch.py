"""Resolve a conference to OpenAlex works and dump them as JSONL."""

from __future__ import annotations

import html
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


# Decoration OpenAlex source names carry around the conference name proper:
# "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)"
# "ESSCIRC 2022- IEEE 48th European Solid State Circuits Conference": an acronym with a year
_ACR_YEAR = r"[a-z][a-z0-9/]{1,11}\s*['’]?\d{2,4}(?!\s*(?:st|nd|rd|th))\s*[-–:]?\s*"
_DECOR_LEAD = re.compile(
    r"^(?:proceedings of (?:the )?|proceedings\W+|" + _ACR_YEAR + r"|\d{4}\s*|\d+(?:st|nd|rd|th)\s*|"
    r"(?:ieee|acm|ieee/cvf|cvf|ieee/acm|acm/ieee|usenix|siam|international|annual)\W+)+",
    re.I,
)
_DECOR_TAIL = re.compile(
    r"(?:\s*[\(\[][^\)\]]*[\)\]]"  # "(CVPR)", "[Cat. No...]"
    r"|\s*[-–:.,]\s*(?:digest|technical digest|proceedings|conference proceedings|part\b|vol\b)[^\(\[]*"
    r"|\s*[-–:,]\s*\d{4}\b.*"  # " - 2019 ...", "(DATE), 2017"
    r"|\s+\d{4}"  # "... Conference 2019"
    r"|\s*[-–:]"  # a dangling dash once the bracket after it is gone
    r")+\s*$",
    re.I,
)


_DECOR_LEAD_LIGHT = re.compile(r"^(?:proceedings of (?:the )?|proceedings\W+|" + _ACR_YEAR + r"|\d{4}\s*|\d+(?:st|nd|rd|th)\s*|(?:ieee|acm|ieee/cvf|cvf|ieee/acm|acm/ieee|usenix|siam)\W+)+", re.I)


def strip_decoration(display_name: str, light: bool = False) -> str:
    """Conference name without year/ordinal/publisher prefixes and trailing "(ACR)". `light`
    keeps words like "International" (for display); the default also drops them (for matching)."""
    name = html.unescape(html.unescape(display_name.strip()))  # OpenAlex ships "&amp;amp;" in some names
    name = _DECOR_TAIL.sub("", name)
    out = (_DECOR_LEAD_LIGHT if light else _DECOR_LEAD).sub("", name).strip()
    if not out:  # the name *is* an acronym with a year ("Interspeech 2022"): keep the word
        out = re.sub(r"\s*['’]?\d{2,4}\s*[-–:]?\s*$", "", name).strip()
    return out


def _core_name(display_name: str) -> str:
    return _norm(strip_decoration(display_name))


def resolve_sources(client: OpenAlex, query: str) -> list[dict[str, Any]]:
    """Sources for a conference name.

    Prefer sources whose name, stripped of year/ordinal/publisher decoration and trailing
    parentheticals, *equals* the query — so "Conference on Computer Vision and Pattern
    Recognition" does not pull in "... Pattern Recognition Workshops (CVPRW)". If nothing
    matches exactly, fall back to sources whose name merely contains the query.
    """
    key = _norm(query)
    key_core = _core_name(query)
    candidates = client.search_sources(query)
    exact = [s for s in candidates if _core_name(s["display_name"]) == key_core]
    if exact:
        return sorted(exact, key=lambda s: s["display_name"])
    loose = [s for s in candidates if key in _norm(s["display_name"])]
    return sorted(loose, key=lambda s: s["display_name"])


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
                        # OpenAlex lineage: [top-level parent, ..., this institution]
                        "root_id": (inst.get("lineage") or [inst.get("id")])[0],
                    }
                    for inst in a.get("institutions") or []
                ],
                "raw_affiliations": a.get("raw_affiliation_strings") or [],
            }
        )
    return out


def _prefix_of(doi: str | None) -> str | None:
    m = re.match(r"https://doi\.org/(10\.\d+/[a-z][a-z\-]*)", (doi or "").lower())
    return m.group(1) if m else None


def resolve_venue(client: OpenAlex, text: str, years: tuple[int, int] = (2016, 2025)) -> dict[str, Any] | None:
    """Turn what a person typed — an acronym ("DAC") or a name — into something fetchable.

    Acronyms are tried as IEEE-style DOI prefixes (10.1109/dac, 10.23919/dac) and the
    conference name is read off a sample of the matching papers. Names are matched
    against OpenAlex sources, and a DOI prefix is inferred from a sample of their papers.
    Returns None when nothing plausible is found."""
    text = text.strip()
    if not text:
        return None
    yf = f",publication_year:{years[0]}-{years[1]}"
    is_acronym = " " not in text and len(text) <= 12

    if is_acronym:
        for reg in ("10.1109", "10.23919"):
            pfx = f"{reg}/{text.lower()}"
            total = sum(client.count_by_year(f"doi_starts_with:{pfx}{yf}").values())
            if total < 50:
                continue
            page = client.get("works", {"filter": f"doi_starts_with:{pfx}{yf}", "select": "doi,primary_location", "per-page": 60, "sample": 60, "seed": 7})
            names: Counter[str] = Counter()
            ok = 0
            for w in page.get("results", []):
                if not doi_has_prefix(w.get("doi"), pfx):
                    continue
                ok += 1
                loc = w.get("primary_location") or {}
                raw = (loc.get("source") or {}).get("display_name") or loc.get("raw_source_name") or ""
                if raw:
                    names[strip_decoration(raw, light=True)] += 1
            if not ok or not names:
                continue
            top, n_top = names.most_common(1)[0]
            share = n_top / sum(names.values())
            return {
                "name": top, "doi_prefixes": [pfx], "source_ids": [], "slug": text.lower(),
                "n_papers": round(total * ok / max(len(page.get("results", [])), 1)),
                "candidates": [(n, c / sum(names.values())) for n, c in names.most_common(3)],
                "ambiguous": share < 0.6, "how": "acronym",
            }
        # fall through: maybe it is a one-word name ("Interspeech")

    sources = resolve_sources(client, text)
    if not sources:
        return None
    ids = [s_["id"].rsplit("/", 1)[-1] for s_ in sources[:OR_LIMIT]]
    total = sum(client.count_by_year(f"primary_location.source.id:{'|'.join(ids)}{yf}").values())
    page = client.get("works", {"filter": f"primary_location.source.id:{'|'.join(ids)}{yf}", "select": "doi", "per-page": 60, "sample": 60, "seed": 7})
    prefixes: Counter[str] = Counter(p for p in (_prefix_of(w.get("doi")) for w in page.get("results", [])) if p)
    doi_prefixes: list[str] = []
    if prefixes:
        pfx, n = prefixes.most_common(1)[0]
        if n / max(len(page.get("results", [])), 1) >= 0.6:
            doi_prefixes = [pfx]
            total = max(total, sum(client.count_by_year(f"doi_starts_with:{pfx}{yf}").values()))
    name = strip_decoration(max(sources, key=lambda s_: s_.get("works_count", 0))["display_name"], light=True)
    slug = (doi_prefixes[0].split("/")[1] if doi_prefixes else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"))[:40]
    return {"name": name, "doi_prefixes": doi_prefixes, "source_ids": [s_["id"] for s_ in sources], "slug": slug,
            "n_papers": total, "candidates": [(name, 1.0)], "ambiguous": False, "how": "name"}


def resolve_roots(client: OpenAlex, records: list[dict[str, Any]], log=print) -> None:
    """Fill `root_name` / `root_country` on every institution entry. Names of parents that
    never appear as a direct affiliation are looked up in batches of 50."""
    known: dict[str, tuple[str, str | None]] = {}
    for r in records:
        for a in r.get("authorships") or []:
            for inst in a.get("institutions") or []:
                if inst.get("id") and inst.get("name"):
                    known[inst["id"]] = (inst["name"], inst.get("country"))
    missing = sorted({inst["root_id"] for r in records for a in r.get("authorships") or [] for inst in a.get("institutions") or [] if inst.get("root_id") and inst["root_id"] not in known})
    if missing:
        log(f"[institutions] resolving {len(missing)} parent institutions")
    for i in range(0, len(missing), OR_LIMIT):
        ids = "|".join(m.rsplit("/", 1)[-1] for m in missing[i : i + OR_LIMIT])
        page = client.get("institutions", {"filter": f"ids.openalex:{ids}", "select": "id,display_name,country_code", "per-page": OR_LIMIT})
        for inst in page.get("results", []):
            known[inst["id"]] = (inst["display_name"], inst.get("country_code"))
    for r in records:
        for a in r.get("authorships") or []:
            for inst in a.get("institutions") or []:
                root = inst.get("root_id") or inst.get("id")
                name, country = known.get(root, (inst.get("name"), inst.get("country")))
                inst["root_name"], inst["root_country"] = name, country


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
    resolve_roots(client, records, log=log)
    return records


def coverage_table(records: list[dict[str, Any]], years: tuple[int, int] | None = None) -> str:
    """Papers and abstract coverage per year. With `years`, a year inside the range that
    has no papers is printed as a gap rather than silently left out (ESSCIRC 2020, or a
    venue that changed its DOI prefix)."""
    total: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    for r in records:
        y = r.get("publication_year") or 0
        total[y] += 1
        if r.get("abstract"):
            with_abs[y] += 1
    shown = sorted(set(total) | (set(range(years[0], years[1] + 1)) if years else set()))
    lines = [f"{'year':>6} {'papers':>8} {'abstracts':>10} {'coverage':>9}", "-" * 37]
    gaps = []
    for y in shown:
        n, a = total[y], with_abs[y]
        if n:
            lines.append(f"{y:>6} {n:>8} {a:>10} {a / n:>8.1%}")
        else:
            lines.append(f"{y:>6} {0:>8} {'':>10} {'':>9}   <- no papers found")
            gaps.append(y)
    n, a = sum(total.values()), sum(with_abs.values())
    lines.append("-" * 37)
    lines.append(f"{'all':>6} {n:>8} {a:>10} {a / n if n else 0:>8.1%}")
    if gaps:
        lines.append(f"\nNo papers for {', '.join(map(str, gaps))}: the venue may have skipped the year, or used another DOI prefix "
                     "or source name then. Check OpenAlex (https://openalex.org) and pass extra --doi-prefix values if so.")
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
    print(coverage_table(records, parse_years(args.years)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
