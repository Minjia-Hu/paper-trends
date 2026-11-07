"""Small, cached OpenAlex probes for potential presets; does not fetch full corpora.

Run from the repository root: python -m scripts.audit_venues [slug ...]
Results and raw responses stay under the ignored data/venue-audit/ directory.
Delete that directory to run a fresh snapshot; otherwise responses are reused.
Counts describe each API filter separately, before local DOI/front-matter checks.
Overlapping source/prefix filters must never be added together as a venue total.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from paper_trends.fetch import doi_has_prefix, is_front_matter, resolve_sources, resolve_venue, strip_decoration
from paper_trends.openalex import PER_PAGE, OpenAlex, OpenAlexError

YEARS = (2016, 2025)
SAMPLE = PER_PAGE
CANDIDATES = {
    "icc": ("ICC", "International Conference on Communications", "Communications"),
    "globecom": ("GLOBECOM", "Global Communications Conference", "Communications"),
    "icassp": ("ICASSP", "International Conference on Acoustics Speech and Signal Processing", "Signal processing"),
    "infocom": ("INFOCOM", "Conference on Computer Communications", "Networking"),
    "sp": ("SP", "Symposium on Security and Privacy", "Security"),
    "icse": ("ICSE", "International Conference on Software Engineering", "Software engineering"),
    "embc": ("EMBC", "International Conference of the IEEE Engineering in Medicine and Biology Society", "Biomedical engineering"),
    "ecce": ("ECCE", "Energy Conversion Congress and Exposition", "Power electronics"),
    "chi": ("CHI", "CHI Conference on Human Factors in Computing Systems", "Human-computer interaction"),
    "acl": ("ACL", "Annual Meeting of the Association for Computational Linguistics", "Natural language processing"),
    "neurips": ("NeurIPS", "Advances in Neural Information Processing Systems", "Machine learning"),
    "icml": ("ICML", "International Conference on Machine Learning", "Machine learning"),
}
IEEE_CANDIDATES = {"icc", "globecom", "icassp", "infocom", "sp", "icse", "embc", "ecce"}


class CachedClient(OpenAlex):
    def __init__(self, cache: Path):
        super().__init__()
        self.cache = cache
        self.cache.mkdir(parents=True, exist_ok=True)
        self.requests = 0

    def get(self, path, params=None):
        # Credentials are added inside OpenAlex.get, never to the cache key or payload.
        request = {"path": path, "params": params or {}}
        digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        target = self.cache / f"{digest}.json"
        if target.exists():
            return json.loads(target.read_text())["response"]
        response = super().get(path, params)
        self.requests += 1
        target.write_text(json.dumps({"request": request, "response": response}, ensure_ascii=False))
        return response


def probe(client: OpenAlex, label: str, base_filter: str, prefix: str | None = None) -> dict:
    filt = f"{base_filter},publication_year:{YEARS[0]}-{YEARS[1]}"
    counts = client.count_by_year(filt)
    total = sum(counts.values())
    result = {"label": label, "filter": filt, "raw_works": total, "by_year": counts}
    if not total:
        return result
    abstracts = client.count_by_year(filt + ",has_abstract:true")
    size = min(SAMPLE, total)
    sample = client.get("works", {
        "filter": filt, "sample": size, "seed": 7, "per-page": size,
        "select": "id,doi,title,publication_year,primary_location,is_paratext,type",
    }).get("results", [])
    rejected = [w for w in sample if prefix and not doi_has_prefix(w.get("doi"), prefix)]
    accepted = [w for w in sample if (not prefix or doi_has_prefix(w.get("doi"), prefix)) and not is_front_matter(w)]
    names = Counter()
    evidence = []
    for w in sample:
        loc = w.get("primary_location") or {}
        raw_name = (loc.get("source") or {}).get("display_name") or loc.get("raw_source_name") or "(missing)"
        names[strip_decoration(raw_name, light=True)] += 1
        evidence.append({"id": w.get("id"), "doi": w.get("doi"), "year": w.get("publication_year"),
                         "title": w.get("title"), "source": raw_name,
                         "boundary_ok": not prefix or doi_has_prefix(w.get("doi"), prefix),
                         "front_matter": is_front_matter(w)})
    result.update({
        "abstracts_by_year": abstracts,
        "abstract_coverage": sum(abstracts.values()) / total,
        "sample_size": len(sample), "sample_boundary_rejected": len(rejected),
        "sample_after_local_filters": len(accepted),
        "sample_sources": names.most_common(), "sample": evidence,
    })
    return result


def probe_bounded(client: OpenAlex, prefix: str) -> dict:
    """Sum disjoint dot/digit partitions; do not OR doi_starts_with values.

    This API filter returned zero for pipe-joined values even with known matches.
    A digit followed by letters can still leak through, so retain the regex check.
    Samples are stratified by partition, not one uniform sample of the union.
    """
    parts = [probe(client, prefix + suffix, f"doi_starts_with:{prefix}{suffix}", prefix)
             for suffix in ".0123456789"]
    counts, abstracts, names = Counter(), Counter(), Counter()
    sample = []
    for part in parts:
        counts.update(part["by_year"])
        abstracts.update(part.get("abstracts_by_year", {}))
        names.update(dict(part.get("sample_sources", [])))
        sample.extend(part.get("sample", []))
    total = sum(counts.values())
    return {
        "label": "bounded " + prefix, "parts": parts, "raw_works": total,
        "by_year": dict(counts), "abstracts_by_year": dict(abstracts),
        "abstract_coverage": sum(abstracts.values()) / total if total else 0,
        "sample_size": len(sample), "sample_boundary_rejected": sum(not w["boundary_ok"] for w in sample),
        "sample_after_local_filters": sum(w["boundary_ok"] and not w["front_matter"] for w in sample),
        "sample_sources": names.most_common(), "sample": sample,
        "sampling": "up to 200 per nonempty disjoint prefix partition; not a uniform union sample",
    }


def audit(client: OpenAlex, slug: str) -> dict:
    query, name, field = CANDIDATES[slug]
    result = {"slug": slug, "query": query, "expected_name": name, "field": field,
              "years": YEARS, "checked_at": datetime.now(timezone.utc).isoformat(),
              "short_resolution": resolve_venue(client, query, YEARS), "probes": []}
    sources = resolve_sources(client, name)
    result["name_sources"] = sources
    # Each work has one primary source, so chunks of disjoint source IDs do not overlap.
    # Keep chunks separate here, just like prefix probes, to make every count auditable.
    for i in range(0, len(sources), 50):
        ids = "|".join(s["id"].rsplit("/", 1)[-1] for s in sources[i:i + 50])
        result["probes"].append(probe(client, f"name sources {i // 50 + 1}", f"primary_location.source.id:{ids}"))
    prefixes = [f"{registry}/{slug}" for registry in ("10.1109", "10.23919")]
    for prefix in prefixes:
        result["probes"].append(probe(client, prefix, f"doi_starts_with:{prefix}", prefix))
    if slug in IEEE_CANDIDATES:
        prefix = f"10.1109/{slug}"
        result["probes"].append(probe_bounded(client, prefix))
    if slug == "globecom":
        prefix = "10.1109/glocom"
        result["probes"].append(probe_bounded(client, prefix))
    return result


def main() -> int:
    selected = sys.argv[1:] or list(CANDIDATES)
    if any(s not in CANDIDATES for s in selected):
        print("Choose from: " + " ".join(CANDIDATES), file=sys.stderr)
        return 2
    out = Path("data/venue-audit")
    try:
        client = CachedClient(out / "responses")
        for slug in selected:
            print(f"[audit] {slug}: resolving and sampling…", flush=True)
            result = audit(client, slug)
            (out / f"{slug}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
            resolution = result["short_resolution"]
            print(f"[audit] {slug}: shortcut = {resolution['name'] if resolution else 'not found'}", flush=True)
            for p in result["probes"]:
                detail = f", abstracts {p['abstract_coverage']:.1%}, rejected {p['sample_boundary_rejected']}/{p['sample_size']}" if p["raw_works"] else ""
                print(f"  {p['label']}: {p['raw_works']:,} raw works{detail}", flush=True)
        print(f"[audit] completed {len(selected)} venues; {client.requests} uncached requests", flush=True)
    except OpenAlexError as exc:
        print(f"[audit] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
