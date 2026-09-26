"""Institution / author / country rankings for a conference corpus."""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from .store import Record, filter_years, parse_years, read_jsonl

ENTITIES = ("institution", "author", "country")


@dataclass
class Ranking:
    entity: str
    years: list[int]
    papers_per_year: dict[int, int]
    names: dict[str, str]  # key -> display name
    by_year: dict[str, dict[int, int]]  # key -> year -> papers
    citations: dict[str, int]  # key -> summed cited_by_count

    def total(self, key: str) -> int:
        return sum(self.by_year[key].values())

    def share(self, key: str, year: int) -> float:
        n = self.papers_per_year.get(year, 0)
        return self.by_year[key].get(year, 0) / n if n else 0.0

    def top(self, k: int, by: str = "papers") -> list[str]:
        score = self.citations if by == "citations" else {key: self.total(key) for key in self.by_year}
        return sorted(self.by_year, key=lambda key: (-score.get(key, 0), self.names[key]))[:k]

    def momentum(self, key: str) -> tuple[float, float, float]:
        ys = self.years
        if len(ys) < 2:
            return 0.0, 0.0, 0.0
        split = ys[len(ys) // 2]
        early = [y for y in ys if y < split]
        late = [y for y in ys if y >= split]
        e = _pooled(self, key, early)
        l = _pooled(self, key, late)
        return e, l, l - e

    def movers(self, k: int, min_total: int, rising: bool) -> list[tuple[str, float, float, float]]:
        rows = [(key, *self.momentum(key)) for key in self.by_year if self.total(key) >= min_total]
        rows.sort(key=lambda r: r[3], reverse=rising)
        return rows[:k]


def _pooled(rk: Ranking, key: str, years: list[int]) -> float:
    n = sum(rk.papers_per_year.get(y, 0) for y in years)
    hits = sum(rk.by_year[key].get(y, 0) for y in years)
    return hits / n if n else 0.0


def entities_of(rec: Record, entity: str) -> dict[str, str]:
    """Distinct entities (key -> name) credited on one paper. A paper counts once per entity
    even if several co-authors share it (full counting)."""
    found: dict[str, str] = {}
    for a in rec.get("authorships") or []:
        if entity == "author":
            key = a.get("author_id") or a.get("author_name")
            if key:
                found[key] = a.get("author_name") or key
            continue
        insts = a.get("institutions") or []
        if entity == "institution":
            if insts:
                for inst in insts:
                    key = inst.get("id") or inst.get("name")
                    if key:
                        found[key] = inst.get("name") or key
            else:
                # no resolved institution: fall back to the raw affiliation string
                for raw in a.get("raw_affiliations") or []:
                    found[f"raw:{raw}"] = raw
        elif entity == "country":
            for inst in insts:
                if inst.get("country"):
                    found[inst["country"]] = inst["country"]
    return found


def compute_ranking(records: list[Record], entity: str) -> Ranking:
    if entity not in ENTITIES:
        raise ValueError(f"entity must be one of {ENTITIES}")
    papers: Counter[int] = Counter()
    names: dict[str, str] = {}
    by_year: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    cites: Counter[str] = Counter()
    for r in records:
        y = r.get("publication_year")
        if not y:
            continue
        papers[y] += 1
        for key, name in entities_of(r, entity).items():
            names[key] = name
            by_year[key][y] += 1
            cites[key] += r.get("cited_by_count") or 0
    return Ranking(
        entity=entity,
        years=sorted(papers),
        papers_per_year=dict(papers),
        names=names,
        by_year={k: dict(v) for k, v in by_year.items()},
        citations=dict(cites),
    )


# ---- rendering -----------------------------------------------------------------


def _short(name: str, width: int) -> str:
    return name if len(name) <= width else name[: width - 1] + "…"


def render_table(rk: Ranking, keys: list[str], width: int = 40) -> str:
    head = f"{'#':>3} {rk.entity:<{width}} {'papers':>6} {'cites':>6} " + " ".join(f"{y % 100:>4}" for y in rk.years)
    lines = [head, "-" * len(head)]
    for i, k in enumerate(keys, 1):
        cells = " ".join(f"{rk.by_year[k].get(y, 0):>4}" for y in rk.years)
        lines.append(f"{i:>3} {_short(rk.names[k], width):<{width}} {rk.total(k):>6} {rk.citations.get(k, 0):>6} {cells}")
    return "\n".join(lines)


def render_movers(rk: Ranking, rows, title: str, width: int = 40) -> str:
    lines = [title, f"{rk.entity:<{width}} {'early':>7} {'late':>7} {'delta':>7}", "-" * (width + 24)]
    for k, e, l, d in rows:
        lines.append(f"{_short(rk.names[k], width):<{width}} {e:>7.1%} {l:>7.1%} {d:>+7.1%}")
    return "\n".join(lines)


def write_csv(rk: Ranking, keys: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow([rk.entity, "id", "papers", "citations", *[str(y) for y in rk.years]])
        for k in keys:
            wr.writerow([rk.names[k], k, rk.total(k), rk.citations.get(k, 0), *[rk.by_year[k].get(y, 0) for y in rk.years]])


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends rank", description="Rank institutions, authors or countries.")
    p.add_argument("jsonl", type=Path)
    p.add_argument("--by", choices=ENTITIES, default="institution")
    p.add_argument("--years")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--sort", choices=["papers", "citations"], default="papers")
    p.add_argument("--movers", type=int, default=10, help="rising/falling entities to show (0 to hide)")
    p.add_argument("--min-total", type=int, default=10, help="min papers for an entity to be a mover")
    p.add_argument("--csv", type=Path)
    args = p.parse_args(argv)

    records = filter_years(read_jsonl(args.jsonl), parse_years(args.years))
    rk = compute_ranking(records, args.by)
    keys = rk.top(args.top, by=args.sort)
    n_credited = sum(1 for r in records if entities_of(r, args.by))
    print(f"{len(records)} papers, {rk.years[0]}-{rk.years[-1]}; {n_credited} have {args.by} data; full counting\n")
    print(render_table(rk, keys))
    if args.movers:
        print()
        print(render_movers(rk, rk.movers(args.movers, args.min_total, rising=True), "RISING (share of papers, early vs late half)"))
        print()
        print(render_movers(rk, rk.movers(args.movers, args.min_total, rising=False), "FALLING (share of papers, early vs late half)"))
    if args.csv:
        write_csv(rk, keys, args.csv)
        print(f"\n[csv] wrote {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
