"""Smoke-test the Streamlit app with a tiny synthetic corpus via streamlit.testing."""

import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

THERMAL = "thermal resistance heat sink cooling junction temperature heat flux"
BONDING = "hybrid bonding copper pad pitch dielectric bond interface void"


def _write_corpus(path: Path) -> None:
    recs = []
    for i in range(30):
        y = 2016 + i % 6
        topic = THERMAL if i % 2 else BONDING
        recs.append(
            {
                "id": f"W{i}", "doi": f"10.1109/ectc.{y}.{i}", "title": f"paper {i} {topic.split()[0]}",
                "publication_year": y, "abstract": f"{topic} variant {i % 4}", "cited_by_count": i,
                "authorships": [{"author_id": f"A{i % 5}", "author_name": f"Author {i % 5}", "position": "first",
                                 "institutions": [{"id": f"I{i % 3}", "name": f"Inst {i % 3}", "country": ["US", "TW", "JP"][i % 3]}],
                                 "raw_affiliations": []}],
                "type": "conference-paper", "source_id": None, "source_name": "ECTC",
                "topics": [{"name": "Packaging", "subfield": "EE"}], "oa_keywords": [],
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs))


def test_app_renders_all_tabs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / "ectc.jsonl")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value.startswith("Electronic Components")
    assert len(at.tabs) == 6
    assert any("Rising" in h.value for h in at.subheader)


def test_query_param_selects_preset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / "imw.jsonl")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params["conference"] = "imw"
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "International Memory Workshop"
