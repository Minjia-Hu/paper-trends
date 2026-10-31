import json
from datetime import datetime, timezone

import pytest

from paper_trends import store
from paper_trends.store import metadata_path, provenance_label, read_jsonl, read_provenance, write_jsonl


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


def test_interrupted_serialization_preserves_old_corpus_and_provenance(tmp_path):
    path = tmp_path / "papers.jsonl"
    write_jsonl([{"title": "Original"}], path, fetched_at=datetime.now(timezone.utc))
    before = path.read_bytes(), metadata_path(path).read_bytes()
    with pytest.raises(TypeError):
        write_jsonl([{"title": "Partial replacement"}, {"bad": object()}], path,
                    fetched_at=datetime.now(timezone.utc))
    assert (path.read_bytes(), metadata_path(path).read_bytes()) == before
    assert read_provenance(path)["status"] == "verified"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["papers.jsonl", "papers.jsonl.meta.json"]


def test_readers_see_complete_corpus_and_sidecar_during_replacement(tmp_path, monkeypatch):
    path = tmp_path / "papers.jsonl"
    old, new = [{"title": "Original"}], [{"title": "新论文\u2028with a separator"}, {"title": "Second"}]
    write_jsonl(old, path, fetched_at=datetime.now(timezone.utc))
    replace = store.os.replace
    destinations = []

    def inspect_replace(source, destination):
        assert source.parent == destination.parent
        if destination == path:
            assert read_jsonl(path) == old
            assert read_jsonl(source) == new
        else:
            assert destination == metadata_path(path)
            assert read_jsonl(path) == new
            assert read_provenance(path)["status"] == "changed"
            assert json.loads(source.read_text())["records"] == 2
        replace(source, destination)
        destinations.append(destination)

    monkeypatch.setattr(store.os, "replace", inspect_replace)
    write_jsonl(new, path, fetched_at=datetime.now(timezone.utc))
    assert destinations == [path, metadata_path(path)]
    assert read_provenance(path)["status"] == "verified"


def test_failed_sidecar_replacement_keeps_new_data_with_unknown_provenance(tmp_path, monkeypatch):
    path = tmp_path / "papers.jsonl"
    write_jsonl([{"title": "Old"}], path, fetched_at=datetime.now(timezone.utc))
    replace = store.os.replace

    def fail_sidecar(source, destination):
        if destination == metadata_path(path):
            raise OSError("simulated disk failure")
        replace(source, destination)

    monkeypatch.setattr(store.os, "replace", fail_sidecar)
    with pytest.raises(OSError, match="disk failure"):
        write_jsonl([{"title": "New"}], path, fetched_at=datetime.now(timezone.utc))
    assert read_jsonl(path) == [{"title": "New"}]
    assert read_provenance(path) == {"fetched_at": None, "status": "changed"}
    assert not list(tmp_path.glob(".*.tmp"))
