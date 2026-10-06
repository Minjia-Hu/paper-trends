import json
from datetime import datetime, timezone

import pytest

from paper_trends.store import metadata_path, provenance_label, read_provenance, write_jsonl


def test_fetch_timestamp_is_verified_and_not_inferred_from_file_time(tmp_path):
    path = tmp_path / "papers.jsonl"
    records = [{"title": "Hybrid bonding", "publication_year": 2025}]
    write_jsonl(records, path)
    assert read_provenance(path) == {"fetched_at": None, "status": "unrecorded"}
    assert "unknown" in provenance_label(read_provenance(path))

    when = datetime(2026, 10, 5, 8, 30, tzinfo=timezone.utc)
    write_jsonl(records, path, fetched_at=when)
    info = read_provenance(path)
    assert info == {"fetched_at": "2026-10-05T08:30:00+00:00", "status": "verified"}
    assert "2026-10-05 08:30 UTC" in provenance_label(info)
    assert json.loads(metadata_path(path).read_text())["records"] == 1

    write_jsonl(records + [{"title": "Additional record"}], path)
    assert read_provenance(path) == {"fetched_at": None, "status": "changed"}
    assert "unknown" in provenance_label(read_provenance(path))


@pytest.mark.parametrize("content", ['{', '[]', '{"version": 9}', '{"version":1,"source":"OpenAlex","fetched_at":"bad"}'])
def test_malformed_fetch_metadata_cannot_break_a_report(tmp_path, content):
    path = tmp_path / "papers.jsonl"
    write_jsonl([], path)
    metadata_path(path).write_text(content)
    assert read_provenance(path) == {"fetched_at": None, "status": "invalid"}


def test_timestamp_requires_timezone(tmp_path):
    with pytest.raises(ValueError, match="timezone"):
        write_jsonl([], tmp_path / "papers.jsonl", fetched_at=datetime(2026, 10, 5))
