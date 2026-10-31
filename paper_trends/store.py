"""Read/write the JSONL corpus produced by `fetch`."""

from __future__ import annotations

import json
import hashlib
import os
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, TextIO

Record = dict[str, Any]


@contextmanager
def _atomic_text(path: Path) -> Iterator[TextIO]:
    """Publish a complete UTF-8 file, leaving the old file intact on write failure."""
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                prefix=f".{path.name}.", suffix=".tmp", delete=False) as fh:
            temporary = Path(fh.name)
            yield fh
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_jsonl(records: list[Record], path: Path, *, fetched_at: datetime | None = None) -> None:
    """Save records; only an actual successful fetch supplies a timezone-aware timestamp.

    A sidecar binds provenance to the exact file bytes. Later edits invalidate it;
    file modification times are never interpreted as fetch times.
    """
    if fetched_at is not None and fetched_at.utcoffset() is None:
        raise ValueError("fetched_at must include a timezone")
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with _atomic_text(path) as fh:
        for r in records:
            line = json.dumps(r, ensure_ascii=False) + "\n"
            fh.write(line)
            digest.update(line.encode("utf-8"))
    if fetched_at is not None:
        # The two replacements are individually atomic. Between them (or if the
        # sidecar write fails), a digest mismatch safely reports unknown provenance.
        with _atomic_text(metadata_path(path)) as fh:
            fh.write(json.dumps({
                "version": 1, "source": "OpenAlex",
                "fetched_at": fetched_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
                "sha256": digest.hexdigest(),
                "records": len(records),
            }, indent=2) + "\n")


def metadata_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".meta.json")


def read_provenance(path: Path) -> dict:
    """Read verified provenance or return an explicit unknown state for legacy data."""
    unknown = {"fetched_at": None, "status": "unrecorded"}
    try:
        metadata = json.loads(metadata_path(path).read_text(encoding="utf-8"))
        if metadata.get("version") != 1 or metadata.get("source") != "OpenAlex":
            return {**unknown, "status": "invalid"}
        fetched = datetime.fromisoformat(metadata["fetched_at"])
        if fetched.utcoffset() is None:
            return {**unknown, "status": "invalid"}
        if metadata.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            return {**unknown, "status": "changed"}
        return {"fetched_at": fetched.astimezone(timezone.utc).isoformat(timespec="seconds"), "status": "verified"}
    except FileNotFoundError:
        return unknown
    except (ValueError, TypeError, KeyError, AttributeError):
        return {**unknown, "status": "invalid"}


def provenance_label(provenance: dict | None) -> str:
    if provenance and provenance.get("status") == "verified" and provenance.get("fetched_at"):
        return "Data fetched: " + datetime.fromisoformat(provenance["fetched_at"]).strftime("%Y-%m-%d %H:%M UTC")
    reason = {"changed": "corpus changed since the recorded fetch", "invalid": "fetch metadata is invalid"}.get(
        (provenance or {}).get("status"), "no recorded fetch timestamp")
    return f"Data fetched: unknown ({reason})"


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
