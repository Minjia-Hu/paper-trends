"""Keyword / n-gram trends: how often each term appears in a conference's papers, by year."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .store import Record, filter_years, parse_years, read_jsonl
from . import background as bg
from .text import STOPWORDS, TOPICAL_ROLES, Acronyms, acronym_definitions, extension_pairs, load_stopwords, mention_role, paper_tokens, phrase_roles


@dataclass
class KeywordTrends:
    years: list[int]
    papers_per_year: dict[int, int]
    # term -> year -> number of papers counted for the term. With basis "topical" (default)
    # that is papers *about* the term; with "any", every paper that mentions it.
    doc_freq: dict[str, dict[int, int]]
    abstract_coverage: dict[int, float] = field(default_factory=dict)
    # if set, a term is hidden from rankings when at least this share of its occurrences sit
    # inside established longer phrases ("level packaging" inside "wafer level packaging")
    collapse_ratio: float | None = 0.8
    # term -> share of its occurrences inside established longer phrases (see `fragment_share`)
    inside: dict[str, float] = field(default_factory=dict)
    # corpus-wide acronym map (RDL -> redistribution layer, through silicon via -> TSV)
    acronyms: Acronyms | None = None
    basis: str = "topical"
    # term -> year -> papers mentioning the term in any role (>= doc_freq)
    mention_freq: dict[str, dict[int, int]] = field(default_factory=dict)
    # Reviewed boilerplate -> other fields supporting its exclusion from rankings.
    common: dict[str, list[str]] = field(default_factory=dict)
    keep_common: bool = False
    # Preserve the counting inputs for report drill-downs.
    text_mode: str = "title+abstract"
    n_min: int = 1
    n_max: int = 3
    stopwords: frozenset[str] = STOPWORDS

    def mentions(self, term: str) -> int:
        return sum(self.mention_freq.get(term, self.doc_freq[term]).values())

    def topical_share(self, term: str) -> float:
        """Share of mentioning papers with a title mention or repeated abstract mentions."""
        m = self.mentions(term)
        return self.total(term) / m if m else 0.0

    def total(self, term: str) -> int:
        return sum(self.doc_freq[term].values())

    def share(self, term: str, year: int) -> float:
        n = self.papers_per_year.get(year, 0)
        return self.doc_freq[term].get(year, 0) / n if n else 0.0

    def candidates(self) -> list[str]:
        terms = [t for t in self.doc_freq if self.keep_common or t not in self.common]
        if self.collapse_ratio is None:
            return terms
        return [t for t in terms if not self.is_fragment(t)]

    def is_fragment(self, term: str) -> bool:
        """True when the term is (almost) always part of established longer phrases."""
        return self.inside.get(term, 0.0) >= (self.collapse_ratio or 0.8)

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


FAMILY_HEAD_SHARE = 0.6  # a longer member heads its family when it has this share of the shortest member's papers


def group_families(rows: list[tuple], k: int | None = None, total=None) -> list[tuple[tuple, list[str]]]:
    """Fold rows whose terms contain one another ("hybrid bonding", "wafer hybrid bonding",
    "hybrid bonding process"), or are singular/plural twins, into one row that carries the
    others as variants: [(row, [variant terms])]. Rows are (term, ...) in rank order; the
    highest-ranked member heads the family, except that a longer member takes over when it
    accounts for most of the papers (`total`): "high-bandwidth memory" over "high-bandwidth"."""
    families: list[list[tuple]] = []
    for row in rows:
        words = singular(row[0]).split()
        for fam in families:
            head = singular(fam[0][0]).split()
            if _contains(head, words) or _contains(words, head):
                fam.append(row)
                break
        else:
            families.append([row])
    out = []
    for fam in families:
        head = fam[0]
        if total is not None:
            shortest = min(fam, key=lambda r: len(r[0].split()))
            longer = [r for r in fam if len(r[0].split()) > len(shortest[0].split()) and total(r[0]) >= FAMILY_HEAD_SHARE * total(shortest[0])]
            if longer and head is shortest:
                head = longer[0]
        out.append((head, [r[0] for r in fam if r is not head]))
        if k is not None and len(out) >= k:
            break
    return out


def singular(term: str) -> str:
    """Crude singular form for twin detection: "solder joints" -> "solder joint"."""
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in term.split())


def _contains(outer: list[str], inner: list[str]) -> bool:
    n = len(inner)
    return any(outer[i : i + n] == inner for i in range(len(outer) - n + 1))


def corpus_acronyms(records: list[Record], n_max: int = 3, stopwords: frozenset[str] = STOPWORDS,
                    min_defs: int = 3, agreement: float = 0.8) -> Acronyms:
    """Acronyms the corpus defines consistently: at least `min_defs` definitions, of which
    `agreement` share give the same long form. Papers that use the acronym without
    defining it are then read with it."""
    seen: dict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
    raw: dict[str, Counter[str]] = defaultdict(Counter)
    for r in records:
        for acr, (written, long_form) in {**acronym_definitions(r.get("title"), stopwords),
                                          **acronym_definitions(r.get("abstract"), stopwords)}.items():
            seen[acr][tuple(long_form)] += 1
            raw[acr][written] += 1
    defs = {}
    for acr, forms in seen.items():
        n = sum(forms.values())
        (best, m), = forms.most_common(1)
        if n >= min_defs and m >= agreement * n:
            defs[acr] = (raw[acr].most_common(1)[0][0], list(best))
    return Acronyms(defs, n_max, stopwords)


FRAGMENT_MIN = 10        # mentions a term needs before the fragment check is worth running
FRAGMENT_EXT_SHARE = 0.1  # a longer phrase is "established" for a term when it carries this share of its occurrences


def fragment_share(token_lists: list[list[str]], terms: set[str], n_min: int, n_max: int,
                   stopwords: frozenset[str] = STOPWORDS) -> dict[str, float]:
    """term -> share of its occurrences that sit inside an established longer phrase, i.e.
    one that carries at least FRAGMENT_EXT_SHARE of the term's occurrences on its own.
    "level packaging" scores ~1 (wafer-/panel-level packaging), "fine pitch" low (followed
    by many different nouns, none of them often)."""
    ext: dict[str, Counter[tuple[str | None, str | None]]] = defaultdict(Counter)
    for tokens in token_lists:
        for term, left, right in extension_pairs(tokens, terms, n_min, n_max, stopwords):
            ext[term][(left, right)] += 1
    out: dict[str, float] = {}
    for term, pairs in ext.items():
        occ = sum(pairs.values())
        by_ext: Counter[str] = Counter()
        for (left, right), n in pairs.items():
            for e in (left, right):
                if e:
                    by_ext[e] += n
        established = {e for e, n in by_ext.items() if n >= FRAGMENT_EXT_SHARE * occ}
        covered = sum(n for (left, right), n in pairs.items() if left in established or right in established)
        out[term] = covered / occ if occ else 0.0
    return out


def _pooled_share(kt: KeywordTrends, term: str, years: list[int]) -> float:
    n = sum(kt.papers_per_year.get(y, 0) for y in years)
    hits = sum(kt.doc_freq[term].get(y, 0) for y in years)
    return hits / n if n else 0.0


def papers_with(records: list[Record], term: str, text: str = "title+abstract", topical_only: bool = True,
                acronyms: Acronyms | None = None, n_max: int = 3,
                stopwords: frozenset[str] = STOPWORDS) -> list[Record]:
    """Papers counted for `term`, newest and most cited first. With `topical_only` (the
    default, matching the counts) a paper that mentions the phrase just once is left out.
    `acronyms` should be the map the counts were made with (`KeywordTrends.acronyms`); it
    is rebuilt from the records when not given."""
    if acronyms is None:
        acronyms = corpus_acronyms(records, n_max, stopwords)
    hits = []
    for r in records:
        role = mention_role(r.get("title"), r.get("abstract") if text != "title" else None, term, acronyms,
                            n_max=n_max, stopwords=stopwords)
        if role and (role in TOPICAL_ROLES or not topical_only):
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


def restore_case(term: str, surface: dict[str, str]) -> str:
    """Write contracted acronyms the way the corpus does: "cowos interposer" -> "CoWoS
    interposer" (`surface` is KeywordTrends.acronyms.surface)."""
    return " ".join("-".join(surface.get(p, p) for p in w.split("-")) for w in term.split())


def display_form(term: str, forms: Counter[str], surface: dict[str, str] | None = None) -> str:
    """Hyphens and acronym casing restored for display; counts stay keyed by the plain form."""
    return restore_case(restore_hyphens(term, forms), surface or {})


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
    basis: str = "topical",
    field: str | None = None,
    background: dict | None | str = "default",
    keep_common: bool = False,
) -> KeywordTrends:
    """Per-year paper counts for every n-gram.

    basis       "topical" counts a paper when the phrase is in its title or repeated in
                its abstract; this is a relevance heuristic. "any" counts every mention.
    field       the corpus' own field (see background.FIELD_OF), left out when judging
                whether a phrase is common across fields.
    background  the cross-field table; "default" loads the one shipped with the package,
                None switches the filter off.
    """
    if basis not in ("topical", "any"):
        raise ValueError("basis must be 'topical' or 'any'")
    papers: Counter[int] = Counter()
    with_abs: Counter[int] = Counter()
    topical: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    anyrole: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    acronyms = corpus_acronyms(records, n_max, stopwords)
    token_lists: list[list[str]] = []  # kept for the second pass (fragments)
    for r in records:
        y = r.get("publication_year")
        if not y:
            continue
        papers[y] += 1
        if r.get("abstract"):
            with_abs[y] += 1
        t_toks, a_toks = paper_tokens(r.get("title"), r.get("abstract") if text != "title" else None, acronyms, stopwords, n_max)
        token_lists.append(t_toks)
        token_lists.append(a_toks)
        for term, role in phrase_roles(t_toks, a_toks, n_min, n_max, stopwords).items():
            anyrole[term][y] += 1
            if role in TOPICAL_ROLES:
                topical[term][y] += 1
    # prune rare terms to keep memory/output sane
    keep = [t for t, ys in anyrole.items() if sum(ys.values()) >= min_total]
    inside = fragment_share(token_lists, {t for t in keep if sum(anyrole[t].values()) >= FRAGMENT_MIN}, n_min, n_max, stopwords)
    mention_freq = {t: dict(anyrole[t]) for t in keep}
    counted = mention_freq if basis == "any" else {t: dict(topical[t]) for t in keep if t in topical}
    table = bg.load() if background == "default" else background
    common = {}
    if table:
        for t in counted:
            if t not in bg.BOILERPLATE:
                continue
            fields = bg.common_fields(t, field, table)
            if len(fields) >= table.get("min_fields", bg.MIN_FIELDS):
                common[t] = fields
    years = sorted(papers)
    return KeywordTrends(
        years=years,
        papers_per_year=dict(papers),
        doc_freq=counted,
        abstract_coverage={y: with_abs[y] / papers[y] for y in years},
        basis=basis,
        mention_freq=mention_freq,
        common=common,
        keep_common=keep_common,
        inside=inside,
        acronyms=acronyms,
        text_mode=text,
        n_min=n_min,
        n_max=n_max,
        stopwords=stopwords,
    )


# ---- rendering -----------------------------------------------------------------


def render_top_table(kt: KeywordTrends, terms: list[str], as_share: bool = True, show=str) -> str:
    names = [show(t) for t in terms]
    w = max((len(n) for n in names), default=10)
    head = f"{'term':<{w}} {'total':>6} " + " ".join(f"{y:>6}" for y in kt.years)
    lines = [head, "-" * len(head)]
    for t, name in zip(terms, names):
        cells = []
        for y in kt.years:
            cells.append(f"{kt.share(t, y):>6.1%}" if as_share else f"{kt.doc_freq[t].get(y, 0):>6}")
        lines.append(f"{name:<{w}} {kt.total(t):>6} " + " ".join(cells))
    return "\n".join(lines)


def render_emerging(rows: list[tuple[str, int, float, float]], title: str, show=str) -> str:
    w = max((len(show(r[0])) for r in rows), default=10)
    lines = [title, f"{'term':<{w}} {'first':>6} {'early':>7} {'late':>7}", "-" * (w + 23)]
    for t, first, e, l in rows:
        lines.append(f"{show(t):<{w}} {first:>6} {e:>7.1%} {l:>7.1%}")
    return "\n".join(lines)


def render_momentum(rows: list[tuple[str, float, float, float]], title: str, variants: dict[str, list[str]] | None = None, show=str) -> str:
    w = max((len(show(r[0])) for r in rows), default=10)
    lines = [title, f"{'term':<{w}} {'early':>7} {'late':>7} {'delta':>7}", "-" * (w + 24)]
    for t, e, l, d in rows:
        also = (variants or {}).get(t)
        lines.append(f"{show(t):<{w}} {e:>7.1%} {l:>7.1%} {d:>+7.1%}" + (f"   also: {', '.join(show(v) for v in also)}" if also else ""))
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
    p.add_argument("--count", choices=["topical", "any"], default="topical",
                   help="topical (default): title mention or repeated abstract mentions; any: count every mention")
    p.add_argument("--keep-common", action="store_true", help="include reviewed boilerplate phrases otherwise hidden using cross-field evidence")
    p.add_argument("--field", help="the conference's field, excluded from the cross-field check (default: from the file name)")
    p.add_argument("--csv", type=Path, help="also write the top terms table to CSV")
    args = p.parse_args(argv)

    records = filter_years(read_jsonl(args.jsonl), parse_years(args.years))
    n_min, n_max = parse_years(args.ngram) or (1, 3)
    extra = args.stopwords.read_text().splitlines() if args.stopwords else None
    kt = compute_trends(records, text=args.text, n_min=n_min, n_max=n_max, stopwords=load_stopwords(extra),
                        basis=args.count, field=args.field or bg.field_of(args.jsonl.stem), keep_common=args.keep_common)
    if args.keep_subphrases:
        kt.collapse_ratio = None

    low = [y for y, c in kt.abstract_coverage.items() if c < 0.5]
    if low and args.text != "title":
        print(
            f"[warn] abstract coverage < 50% for {low}; those years under-count terms. "
            "Consider --years to exclude them or --text title.",
            file=sys.stderr,
        )

    forms = hyphen_forms(records, text=args.text)
    show = lambda t: display_form(t, forms, kt.acronyms.surface if kt.acronyms else None)  # noqa: E731
    top = [h[0] for h, _ in group_families([(t,) for t in kt.top_terms(args.top * 2)], args.top, kt.total)]
    print(f"{len(records)} papers, {kt.years[0]}-{kt.years[-1]}, text={args.text}, ngram={n_min}-{n_max}, count={kt.basis}")
    hidden = 0 if kt.keep_common else len(kt.common)
    print(f"{hidden} boilerplate phrases used in {bg.MIN_FIELDS}+ other fields hidden (--keep-common shows them)" if hidden else "")
    if kt.acronyms:
        print(f"{len(kt.acronyms.defs)} acronyms read as their long form (or the long form as the acronym: {', '.join(sorted(kt.acronyms.surface[a] for a in list(kt.acronyms.short)[:5]))}…)\n")
    print(render_top_table(kt, top, as_share=not args.counts, show=show))
    print()
    for name, rows in (("RISING", kt.rising(args.movers * 4, args.min_total)), ("FALLING", kt.falling(args.movers * 4, args.min_total))):
        fams = group_families(rows, args.movers, kt.total)
        print(render_momentum([h for h, _ in fams], f"{name} (share of papers, early vs late half; one phrase per family)", {h[0]: v for h, v in fams if v}, show))
        print()
    if args.emerging:
        fams = group_families(kt.emerging(args.emerging * 3, args.min_total), args.emerging, kt.total)
        print(render_emerging([h for h, _ in fams], "EMERGING (near-absent in the early half, >= 1% of papers in the late half)", show))
    if args.csv:
        write_csv(kt, top, args.csv)
        print(f"\n[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
