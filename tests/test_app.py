"""Smoke-test the Streamlit app with a tiny synthetic corpus via streamlit.testing."""

import json
from html import escape
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
                "id": f"W{i}", "doi": f"10.1109/ectc.{y}.{i}", "title": f"{' '.join(topic.split()[:2])} paper {i}",
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


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_app_renders_all_tabs(tmp_path, monkeypatch, lang):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / "ectc.jsonl")
    _write_corpus(tmp_path / "data" / "imw.jsonl")  # a second corpus so Compare has something to compare with
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params["lang"] = lang
    at.run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 0 and not at.radio  # home page: no per-conference controls
    at.query_params["conference"] = "ectc"
    at.run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 0 and not at.radio  # Report view: an embedded page, controls are links
    assert any('id="observatory"' in e.proto.srcdoc for e in at if e.type == "iframe")
    at.query_params["view"] = "explore"
    at.query_params["section"] = "keywords"
    at.run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 0 and not at.title  # sections are links, header is HTML
    assert any(("上升" if lang == "zh" else "Rising") in m.value for m in at.markdown)
    copy = "\n".join(m.value for m in at.markdown)
    assert ("个百分点" if lang == "zh" else " pp") in copy
    if lang == "zh":
        assert "被引次数" in copy and ">论文数<" in copy
        assert "papers matching" not in copy and "the number at the end" not in copy
    for section in ("overview", "topics", "rankings", "compare", "data"):  # every section must render
        at.query_params["section"] = section
        at.run()
        assert not at.exception, (section, at.exception)
        if section == "compare":
            assert any(("共同上升的关键词" if lang == "zh" else "Rising everywhere") in m.value for m in at.markdown)
        if section == "overview" and lang == "zh":
            copy = "\n".join(m.value for m in at.markdown)
            assert "年发文量" in copy and "摘要覆盖率" in copy
            assert "Output has been" not in copy and "A paper counts" not in copy
        if section == "rankings" and lang == "zh":
            assert any("机构排名 · 按论文数" in m.value for m in at.markdown)
        if section == "data" and lang == "zh":
            assert json.loads(at.dataframe[-1].proto.columns)["citations"]["label"] == "被引次数"


def test_query_param_selects_preset(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / "imw.jsonl")
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params["conference"] = "imw"
    at.run()
    assert not at.exception, at.exception
    at.query_params["view"] = "explore"
    at.run()
    assert not at.exception, at.exception
    assert any("International Memory Workshop" in m.value for m in at.markdown)


def test_language_switch_and_search_preserve_locale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / 'data' / 'ectc.jsonl')
    _write_corpus(tmp_path / 'data' / 'imw.jsonl')
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=120)
    at.query_params.update({'conference': 'ectc', 'lang': 'zh', 'period': '5'})
    at.run()
    assert not at.exception
    assert any('趋势速览' in e.proto.srcdoc for e in at if e.type == 'iframe')
    assert any('lang=en' in m.value and 'period=5' in m.value for m in at.markdown)
    at.query_params['lang'] = 'en'
    at.run()
    assert not at.exception
    assert any('At a glance' in e.proto.srcdoc and '趋势速览' not in e.proto.srcdoc for e in at if e.type == 'iframe')
    at.query_params['lang'] = 'zh'
    at.run()
    at.text_input(key='search').set_value('IMW').run()
    assert not at.exception
    assert at.query_params['lang'] in ('zh', ['zh'])
    assert any('趋势速览' in e.proto.srcdoc for e in at if e.type == 'iframe')


def test_report_refreshes_when_only_fetch_metadata_changes(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from paper_trends.store import metadata_path, read_jsonl, write_jsonl
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "ectc.jsonl"
    _write_corpus(path)
    write_jsonl(read_jsonl(path), path, fetched_at=datetime(2020, 1, 2, tzinfo=timezone.utc))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params["conference"] = "ectc"
    at.run()
    assert not at.exception
    assert any("Data fetched: 2020-01-02" in str(e.proto) for e in at if e.type == "iframe")
    metadata = json.loads(metadata_path(path).read_text())
    metadata["fetched_at"] = "2020-02-03T00:00:00+00:00"
    metadata_path(path).write_text(json.dumps(metadata))
    at.run()
    assert not at.exception
    assert any("Data fetched: 2020-02-03" in str(e.proto) for e in at if e.type == "iframe")


def test_default_period_keeps_sparse_abstract_history_and_excludes_current_year(tmp_path, monkeypatch):
    from datetime import date
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "interspeech.jsonl"
    _write_corpus(path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    current = date.today().year
    for i, record in enumerate(records):
        record["publication_year"] = current - 6 + i % 6
        if i % 5:
            record["abstract"] = None
    records.append({**records[0], "id": "W-current", "publication_year": current, "abstract": "a complete abstract"})
    path.write_text("\n".join(json.dumps(r) for r in records))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params["conference"] = "interspeech"
    at.run()
    assert not at.exception, at.exception
    assert any(f"{current - 6}–{current - 1}" in str(e.proto) for e in at if e.type == "iframe")
    assert any("current or future calendar year" in str(e.proto) for e in at if e.type == "iframe")


def test_custom_empty_period_and_single_paper_are_safe_in_report_and_explore(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "ectc.jsonl"
    path.parent.mkdir()
    records = [{"id": "W1", "publication_year": 2016, "title": "hybrid bonding"},
               {"id": "W2", "publication_year": 2022, "title": "acoustic sensing"}]
    path.write_text("\n".join(json.dumps(r) for r in records))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params.update({"conference": "ectc", "period": "custom"})
    at.run()
    at.slider[0].set_value((2019, 2021)).run()
    assert not at.exception and any("No papers in the selected period" in e.value for e in at.info)
    at.slider[0].set_value((2022, 2022)).run()
    assert not at.exception, at.exception
    assert any("Only one year" in str(e.proto) for e in at if e.type == "iframe")
    at.query_params["view"] = "explore"
    for section in ("overview", "keywords", "topics", "rankings", "compare", "data"):
        at.query_params["section"] = section
        at.run()
        assert not at.exception, (section, at.exception)


def test_single_edition_custom_period_does_not_create_an_invalid_slider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "imw.jsonl"
    path.parent.mkdir()
    path.write_text(json.dumps({"id": "W1", "publication_year": 2020, "title": "hybrid bonding"}))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params.update({"conference": "imw", "period": "custom"})
    at.run()
    assert not at.exception and not at.slider


@pytest.mark.parametrize("slug, search, field, title", [
    ("icassp", "ICASSP", "Signal processing", "Acoustics Speech and Signal Processing"),
    ("embc", "EMBC", "Biomedical engineering", "Engineering in Medicine and Biology Society"),
    ("sp", "S&P", "Information security", "Symposium on Security and Privacy"),
    ("globecom", "GLOBECOM", "Communications & networking", "Global Communications Conference"),
    ("infocom", "INFOCOM", "Communications & networking", "Conference on Computer Communications"),
])
def test_new_presets_open_cached_reports_from_search(tmp_path, monkeypatch, slug, search, field, title):
    from unittest.mock import Mock
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / f"{slug}.jsonl")
    # A known preset must route to its cached corpus without a remote venue lookup.
    monkeypatch.setattr("paper_trends.openalex.OpenAlex", Mock(side_effect=AssertionError("Unexpected remote lookup")))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120).run()
    assert not at.exception
    assert any(escape(field) in m.value and f"?conference={slug}" in m.value for m in at.markdown)
    at.text_input(key="search").set_value(search).run()
    assert not at.exception, at.exception
    assert at.query_params["conference"] in (slug, [slug])
    assert any(title in str(e.proto) and "fig-papers" in str(e.proto) for e in at if e.type == "iframe")
