"""Read/write the JSONL corpus produced by `fetch`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Record = dict[str, Any]


def write_jsonl(records: list[Record], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Record]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def filter_years(records: list[Record], years: tuple[int, int] | None) -> list[Record]:
    if not years:
        return records
    lo, hi = years
    return [r for r in records if r.get("publication_year") and lo <= r["publication_year"] <= hi]


def parse_years(text: str | None) -> tuple[int, int] | None:
    if not text:
        return None
    if "-" in text:
        lo, hi = text.split("-", 1)
        return int(lo), int(hi)
    return int(text), int(text)
