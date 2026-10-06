"""Smoke-test the Streamlit app with a tiny synthetic corpus via streamlit.testing."""

import json
import re
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

THERMAL = "thermal resistance heat sink cooling junction temperature heat flux"
BONDING = "hybrid bonding copper pad pitch dielectric bond interface void"


def _iframe(at):
    return next(e.proto.srcdoc for e in at if e.type == "iframe")


def _explorer(at):
    return json.loads(re.search(r"window.ENTITIES = (.*);", _iframe(at))[1])["explorer"]


def test_custom_period_survives_report_explore_and_new_session(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_corpus(tmp_path / "data" / "ectc.jsonl")
    app = str(Path(__file__).resolve().parents[1] / "app.py")
    at = AppTest.from_file(app, default_timeout=120)
    at.query_params.update(conference="ectc", period="custom")
    at.run()
    at.slider(key="years").set_value((2017, 2020)).run()
    assert not at.exception
    target = json.loads(re.search(r"window.EXPLORE_URL = (.*);", _iframe(at))[1])
    params = parse_qs(urlparse(target).query)
    assert params["years"] == ["2017", "2020"]
    fresh = AppTest.from_file(app, default_timeout=120)
    fresh.query_params.update(params)
    fresh.run()
    assert not fresh.exception
    assert fresh.slider(key="years").value == (2017, 2020)
    assert _explorer(fresh)["years"] == [2017, 2018, 2019, 2020]


def test_deep_link_normalizes_hyphenated_phrase_and_keeps_full_evidence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = tmp_path / "data" / "ectc.jsonl"
    _write_corpus(path)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    for rec in records[:5]:
        rec["title"] = "Co-packaged optics"
    path.write_text("\n".join(json.dumps(r) for r in records))
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=120)
    at.query_params.update(conference="ectc", view="explore", term="CO-PACKAGED optics")
    at.run()
    assert not at.exception
    data = _explorer(at)
    assert json.loads(re.search(r"window.EXPLORER_TERM = (.*);", _iframe(at))[1]) == "co packaged optics"
    term = data["terms"][0]
    assert term["key"] == "co packaged optics"
    assert sum(sum(row) for row in term["counts"]) == len(term["matches"]) == 5
    assert {data["results"][i]["id"] for _, _, i in term["matches"]} == {r["id"] for r in records[:5]}
    # An unfound phrase stays selected as an empty result, never an unrelated fallback.
    at.query_params["term"] = "nonexistent phrase"
    at.run()
    assert not at.exception
    assert _explorer(at)["terms"][0]["key"] == "nonexistent phrase"
    assert _explorer(at)["terms"][0]["matches"] == []
    at.text_input(key="phrase_search_input").set_value("hybrid bonding")
    next(b for b in at.button if b.label == "Explore phrase").click().run()
    assert not at.exception
    assert _explorer(at)["terms"][0]["key"] == "hybrid bonding"
    assert any("term=hybrid+bonding" in m.value and "section=institutions" in m.value for m in at.markdown)


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
    assert any('class="report-jump"' in e.proto.srcdoc and 'id="observatory"' not in e.proto.srcdoc for e in at if e.type == "iframe")
    at.query_params["view"] = "explore"
    at.query_params["section"] = "trends"
    at.run()
    assert not at.exception, at.exception
    assert len(at.tabs) == 0 and not at.title  # sections are links, header is HTML
    assert any('id="observatory"' in e.proto.srcdoc for e in at if e.type == "iframe")
    explorer = next(e.proto.srcdoc for e in at if e.type == "iframe")
    assert 'id="obs-results"' in explorer
    assert not at.multiselect  # One active phrase/rule/window, all inside the observatory.
    if lang == "zh":
        assert "全部匹配论文与导出" in explorer and "当前结果（CSV）" in explorer
    for section in ("trends", "topics", "institutions", "compare", "papers"):  # every section must render
        at.query_params["section"] = section
        at.run()
        assert not at.exception, (section, at.exception)
        if section == "compare":
            assert any(("共同上升的关键词" if lang == "zh" else "Rising everywhere") in m.value for m in at.markdown)
        if section == "institutions" and lang == "zh":
            assert any("机构排名 · 按论文数" in m.value for m in at.markdown)
        if section == "institutions":
            at.toggle(key="institution_details").set_value(True).run()
            assert not at.exception, at.exception
            assert any(("机构研究方向" if lang == "zh" else "Institution research profiles") in m.value for m in at.markdown)
        if section == "papers" and lang == "zh":
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
    for section in ("trends", "topics", "institutions", "compare", "papers"):
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
