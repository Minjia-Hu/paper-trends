"""Conservative defaults for cached corpora, not a guarantee of complete indexing."""

from collections import Counter
from datetime import date
from statistics import median

from .store import Record


def period_decision(records: list[Record], span: int = 10, *, current_year: int | None = None) -> dict:
    """Prefer past years; skip suspicious trailing counts and delayed abstracts.

    A trailing count below 20% of the preceding three observed editions is suspect.
    Sparse-abstract venues keep their early years: their reports use titles instead.
    All/Custom remain available to inspect excluded years. These are heuristics, not
    evidence that a selected edition has been fully indexed.
    """
    current_year = date.today().year if current_year is None else current_year
    papers = Counter(r["publication_year"] for r in records if r.get("publication_year"))
    abstracts = Counter(r["publication_year"] for r in records if r.get("publication_year") and r.get("abstract"))
    years = sorted(papers)
    excluded = []
    if not years:
        return {"period": None, "excluded": excluded}
    past = [y for y in years if y < current_year]
    for y in years:
        if y >= current_year:
            excluded.append({"year": y, "reason": "current_or_future",
                             "message": f"{y} is not used by default: current or future calendar year; indexing may be incomplete."})
    if not past:
        return {"period": None, "excluded": excluded}
    typical_coverage = median(abstracts[y] / papers[y] for y in past)
    candidates = list(past)
    while len(candidates) > 1:
        last = candidates[-1]
        previous = candidates[max(0, len(candidates) - 4):-1]
        sparse = papers[last] < 0.2 * median(papers[y] for y in previous)
        delayed = typical_coverage >= 0.6 and abstracts[last] / papers[last] < 0.5
        if not (sparse or delayed):
            break
        reasons = []
        if sparse:
            reasons.append(f"{papers[last]:,} records, below 20% of the median ({median(papers[y] for y in previous):g}) for the preceding {len(previous)} observed editions")
        if delayed:
            reasons.append(f"only {abstracts[last] / papers[last]:.1%} have abstracts, at a venue with typical coverage of {typical_coverage:.1%}")
        excluded.append({"year": last, "reason": "sparse_records" if sparse else "delayed_abstracts",
                         "message": f"{last} is not used by default: " + "; ".join(reasons) + ". This may reflect incomplete indexing."})
        candidates.pop()
    last = candidates[-1]
    return {"period": (max(years[0], last - span + 1), last), "excluded": sorted(excluded, key=lambda r: r["year"])}


def default_period(records: list[Record], span: int = 10, *, current_year: int | None = None) -> tuple[int, int] | None:
    return period_decision(records, span, current_year=current_year)["period"]


def coverage_details(records: list[Record], years: tuple[int, int], *, default_span: int | None = None) -> dict:
    """User-facing evidence for the selection and limitations; no completeness claim."""
    decision = period_decision(records, default_span or 10)
    recommended = decision["period"]
    if default_span and recommended:
        selection = f"Default period: {years[0]}–{years[1]} (up to {default_span} calendar years ending before the current year)."
    elif default_span:
        selection = f"Provisional period: {years[0]}–{years[1]}; no past editions are cached."
    else:
        selection = f"Selected period: {years[0]}–{years[1]}."
        if recommended and tuple(years) != recommended:
            selection += f" Recommended default: {recommended[0]}–{recommended[1]}."
    selected = [r for r in records if r.get("publication_year") and years[0] <= r["publication_year"] <= years[1]]
    papers = Counter(r["publication_year"] for r in selected)
    abstracts = Counter(r["publication_year"] for r in selected if r.get("abstract"))
    rows = [{"year": y, "papers": papers[y], "abstracts": abstracts[y],
             "coverage": abstracts[y] / papers[y] if papers[y] else None}
            for y in range(years[0], years[1] + 1)]
    coverage = sum(abstracts.values()) / max(len(selected), 1)
    notices = []
    gaps = [str(r["year"]) for r in rows if not r["papers"]]
    if gaps:
        notices.append("No cached records for " + ", ".join(gaps) + ". This may be a skipped edition or an indexing/query gap; it is not evidence of zero research output.")
    if coverage < 0.6:
        notices.append(f"Only {coverage:.1%} of selected records have abstracts. Report phrase trends use titles only and may miss subjects absent from titles; topic analysis still uses available titles and abstracts.")
    else:
        low = [f"{r['year']} ({r['coverage']:.1%})" for r in rows if r["coverage"] is not None and r["coverage"] < 0.9]
        if low:
            notices.append("Abstract coverage below 90%: " + ", ".join(low) + ". Changes in abstract availability can affect phrase trends.")
    return {"selection": selection, "exclusions": decision["excluded"], "notices": notices, "rows": rows,
            "caveat": "Coverage describes cached OpenAlex records, not completeness against the official proceedings."}
