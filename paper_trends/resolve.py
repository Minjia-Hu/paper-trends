"""`paper-trends resolve "DAC"`: what would this acronym or name fetch?"""

from __future__ import annotations

import sys

from .fetch import resolve_venue
from .openalex import OpenAlex


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="paper-trends resolve", description="Resolve an acronym or name to a fetchable conference.")
    p.add_argument("text", nargs="+")
    args = p.parse_args(argv)
    r = resolve_venue(OpenAlex(), " ".join(args.text))
    if not r:
        print("nothing found; try the full name as OpenAlex spells it, or pass --doi-prefix to fetch", file=sys.stderr)
        return 1
    print(f"name:         {r['name']}")
    print(f"doi prefixes: {' '.join(r['doi_prefixes']) or '(none inferred)'}")
    print(f"sources:      {len(r['source_ids'])}")
    print(f"papers:       ~{r['n_papers']:,} (2016-2025)")
    if r["ambiguous"]:
        print("ambiguous:    the prefix is shared by several venues: " + "; ".join(f"{n} ({s:.0%})" for n, s in r["candidates"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
