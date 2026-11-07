import json
from pathlib import Path
import re

import pytest

from paper_trends.report.build import build_report, growth_sentence
from paper_trends.report.render import figure_specs, render_explorer_page, render_site

THERMAL = "thermal resistance heat sink cooling junction temperature heat flux"
BONDING = "hybrid bonding copper pad pitch dielectric bond interface void"


def _corpus():
    recs = []
    for i in range(80):
        y = 2016 + i % 8
        topic = BONDING if (i % 3 == 0 or y >= 2021) else THERMAL
        recs.append({
            "id": f"W{i}", "doi": f"10.1109/x.{y}.{i}", "title": f"{' '.join(topic.split()[:2])} study {i}", "publication_year": y,
            "abstract": f"{topic} variant {i % 5}", "cited_by_count": i,
            "authorships": [{"author_id": f"A{i % 7}", "author_name": f"Author {i % 7}",
                             "institutions": [{"id": f"I{i % 4}", "name": f"Inst {i % 4}", "country": ["US", "KR", "JP", "TW"][i % 4],
                                               "root_id": f"I{i % 4}", "root_name": f"Inst {i % 4}", "root_country": ["US", "KR", "JP", "TW"][i % 4]}]}],
            "topics": [], "oa_keywords": [], "type": "conference-paper", "source_id": None, "source_name": "X",
        })
    return recs


def test_growth_sentence():
    assert growth_sentence({2016: 100, 2017: 100, 2018: 100, 2019: 100}) == "output has been flat, between 100 and 100 papers a year"
    assert "growing" in growth_sentence({2016: 100, 2017: 110, 2018: 130, 2019: 150})


def test_build_and_render(tmp_path):
    r = build_report(_corpus(), name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    assert r["n_papers"] == 80 and r["year_range"] == [2016, 2023]
    assert r["glance"] and "Test Conf" in r["glance"][0]
    assert r["countries"][0]["name"] in {"United States", "South Korea", "Japan", "Taiwan"}
    specs = figure_specs(r)
    assert {"fig-papers", "fig-topics", "fig-inst", "fig-country"} <= set(specs)
    assert "fig-heat" not in specs and "fig-bump" not in specs
    assert len([key for key in specs if key.startswith("fig-rise-")]) <= 4
    assert len([key for key in specs if key.startswith("fig-fall-")]) <= 4
    json.dumps(specs)  # must be JSON-serialisable
    render_site([r], tmp_path)
    html = (tmp_path / "test.html").read_text()
    assert "Test Conf" in html and "fig-topics" in html and "report.css" in html
    assert (tmp_path / "index.html").exists() and (tmp_path / "report.css").exists()


@pytest.mark.parametrize("lang", ["en", "zh"])
def test_standalone_report_has_embedded_assets_and_no_local_navigation(lang):
    from html.parser import HTMLParser
    from paper_trends.report.render import render_page

    report = build_report(_corpus(), name="Test Conf", slug="test", years=(2017, 2020), n_topics=2)
    html = render_page(report, nav=[("test", "Test")], embedded=True, app_links=True,
                       explore_href="?conference=test&view=explore", lang=lang, standalone=True,
                       generated_on="2026-11-07")

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key in {"href", "src"}:
                    assert value.startswith(("https://", "data:", "#")), value

    Links().feed(html)
    assert '<style>' in html and 'window.openEntity' in html
    assert 'class="page embedded"' not in html
    assert 'hreflang=' not in html and 'class="page language-switch"' not in html
    assert 'window.EXPLORE_URL = null;' in html
    assert '2026-11-07' in html and '2017–2020' in html
    assert f'<html lang="{"zh-CN" if lang == "zh" else "en"}">' in html
    entities = json.loads(re.search(r"window.ENTITIES = (.*);", html)[1])
    assert entities == {k: v for k, v in report['entities'].items() if k != 'explorer'}
    assert ('报告快照' if lang == 'zh' else 'Saved report snapshot') in html


def test_report_and_explorer_are_separate_surfaces():
    from paper_trends.report.render import render_page

    report = build_report(_corpus(), name="Legacy Conf", slug="legacy", years=(2016, 2023), n_topics=2,
                          include_explorer=True)
    html = render_page(report, embedded=True, explore_href="?view=explore")
    assert 'id="observatory"' not in html
    assert 'class="report-jump"' in html
    assert 'class="title-grid"' in html
    assert 'class="title-stats"' in html
    assert 'class="title-provenance"' in html
    assert "Explore trends and supporting papers" in html
    assert "window.navigateHost" in html
    assert "window.scrollReportHostTo" in html
    assert "querySelectorAll('.report-jump a[href^=\"#\"]')" in html
    assert 'data-open-details="method-details">Data &amp; methods</a>' in html
    assert '<details class="method-details" id="method-details">' in html
    assert "details.open = true" in html
    assert "window.setTimeout(() => window.scrollReportHostTo" in html
    assert 'id="observatory"' in render_explorer_page(report)
    data = json.loads(re.search(r"window.ENTITIES = (.*);", html)[1])
    assert "explorer" not in data  # legacy input must not inflate the report payload
    del report["entities"]["explorer"]
    explorer_html = render_explorer_page(report)
    assert "Legacy Conf" in explorer_html and 'id="observatory"' not in explorer_html


def test_report_does_not_build_unused_explorer(monkeypatch):
    from paper_trends.report import entities

    def unused(*args, **kwargs):
        raise AssertionError("A report must not construct exploration data")

    monkeypatch.setattr(entities, "ExplorerBuilder", unused)
    report = build_report(_corpus(), name="Test", slug="test", n_topics=2)
    assert "explorer" not in report["entities"]
    assert report["entities"]["terms"]  # report detail panels still have their data


def test_modifying_report_output_does_not_mutate_shared_analysis():
    from paper_trends.report.analysis import analyze_corpus

    records = _corpus()
    analysis = analyze_corpus(records, slug="test", n_topics=2)
    original = [(list(topic.terms), list(topic.examples)) for topic in analysis.topics.ordered()]
    report = build_report(records, name="Test", slug="test", years=(2016, 2023), analysis=analysis)
    report["topics"][0]["terms"].clear()
    report["topics"][0]["examples"].append("unrelated paper")
    report["entities"]["years"].clear()
    assert [(topic.terms, topic.examples) for topic in analysis.topics.ordered()] == original
    assert analysis.keywords.years == list(range(2016, 2024))
    again = build_report(records, name="Test", slug="test", years=(2016, 2023), analysis=analysis)
    assert again["topics"][0]["terms"] == original[0][0]
    assert again["topics"][0]["examples"] == original[0][1]


@pytest.mark.parametrize("query", ["hybrid bonding", "thermal resistance", "Rare scientific phrase"])
def test_light_explorer_matches_full_role_counts_and_evidence(query):
    from paper_trends.report.analysis import analyze_corpus
    from paper_trends.report.build import build_explorer_data

    records = _corpus()
    records[0]["title"] += " Rare scientific phrase"
    analysis = analyze_corpus(records, slug="test", n_topics=2)
    full = build_report(records, name="Test", slug="test", years=(2016, 2023),
                        analysis=analysis, explorer_full=True, explore_term=query)
    light = build_explorer_data(analysis, name="Test", slug="test", initial_term=query)
    assert light["entities"]["explorer"] == full["entities"]["explorer"]
    assert set(light["entities"]) == {"explorer"}


def test_generation_date_can_refresh_without_rebuilding_analysis():
    from paper_trends.report.render import render_page

    report = build_report(_corpus(), name="Test", slug="test", n_topics=2)
    report["generated"] = "2020-01-01"
    html = render_page(report, generated_on="2026-10-07")
    assert "report generated 2026-10-07" in html
    assert report["generated"] == "2020-01-01"  # cached data was not mutated


def test_coverage_note():
    from paper_trends.report.build import coverage_note

    assert coverage_note({2016: 100, 2017: 100}, {2016: 99, 2017: 100}) == ""
    assert coverage_note({2016: 100, 2020: 100}, {2016: 99, 2020: 91}) == ", lowest 91% in 2020"


def test_country_map_rows_and_spec():
    import json
    from paper_trends.rank import compute_ranking
    from paper_trends.report.build import country_id, country_map_rows
    from paper_trends.report.charts import world_map

    assert country_id("US") == 840 and country_id("TW") == 158 and country_id("XX") is None
    rk = compute_ranking(_corpus(), "country")
    rows = country_map_rows(rk, 80)
    assert {r["name"] for r in rows} == {"United States", "South Korea", "Japan", "Taiwan"}
    assert abs(sum(r["share"] for r in rows) - 1.0) < 1e-9
    json.dumps(world_map(rows))
    # per-year rolling fields for the map's year control; each year's shares sum to one too
    years = list(range(2016, 2024))
    rows = country_map_rows(rk, 80, years)
    for y in years:
        assert abs(sum(r[f"s{y}"] for r in rows) - 1.0) < 1e-9 and sum(r[f"n{y}"] for r in rows) > 0
    from paper_trends.report.build import map_lines
    lines = map_lines(rows, years)
    assert set(lines) == {"0", *map(str, years)} and "United States" in lines["0"]
    spec = world_map(rows, years=years)
    assert spec["params"] == [{"name": "year", "value": 0}] and "s2019" in spec["layer"][1]["transform"][1]["from"]["fields"]


def test_institution_topic_matrix_and_ranks():
    from collections import defaultdict

    r = build_report(_corpus(), name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    # every institution row of the heatmap sums to one, over the listed columns
    sums = defaultdict(float)
    for row in r["inst_topic"]:
        assert row["topic"] in r["inst_topic_topics"] and row["name"] in r["inst_topic_insts"]
        sums[row["name"]] += row["share"]
    assert set(sums) == set(r["inst_topic_insts"]) and all(abs(s - 1) < 1e-9 for s in sums.values())
    assert r["inst_topic_sentence"].endswith("of the conference.")
    # ranks: each year is a permutation of 1..n, and the label carries the climb
    by_year = defaultdict(list)
    for row in r["inst_ranks"]:
        by_year[row["year"]].append(row["rank"])
    n = len({row["name"] for row in r["inst_ranks"]})
    assert all(sorted(v) == list(range(1, n + 1)) for v in by_year.values()) and set(by_year) == set(r["years"])
    for row in r["inst_ranks"]:
        assert ("▲" in row["label"]) == (row["climb"] > 0) and ("▼" in row["label"]) == (row["climb"] < 0)
    assert r["inst_rank_sentence"]


def test_entities_are_consistent_with_the_page():
    import json
    from paper_trends.report.build import build_report

    r = build_report(_corpus(), name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    e = r["entities"]
    json.dumps(e)
    assert e["n_papers"] == 80 and len(e["topics"]) == 2
    # only the papers some panel lists are shipped, and every reference points inside that list
    assert 0 < len(e["papers"]) <= 80
    refs = [p for group in ("terms", "insts", "topics") for ent in e[group] for p in ent["papers"]]
    assert refs and set(refs) == set(range(len(e["papers"])))
    assert all(p["tp"] in (0, 1, None) for p in e["papers"])
    assert e["inst_index"] and e["term_index"]
    term = e["terms"][0]
    assert term["insts"] and all(isinstance(i, int) for i, _ in term["insts"])
    # a rising phrase on the page can be looked up in the panel data
    assert all(t["term"] in e["term_index"] for t in r["rising"][:3])
    inst = e["insts"][0]
    assert inst["total"] == sum(s["n"] for s in inst["series"])


def test_rendered_page_carries_the_panel(tmp_path):
    r = build_report(_corpus(), name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    render_site([r], tmp_path)
    html = (tmp_path / "test.html").read_text()
    assert "window.ENTITIES = {" in html and "ent-drawer" in html
    assert 'data-ent="term"' in html and 'data-ent="topic"' in html
    assert "openEntity" in html and "<\\/" not in html[:200]


def test_report_escapes_markup_and_roundtrips_inline_json():
    from html.parser import HTMLParser
    from paper_trends.report.render import render_index, render_page

    payload = '</script><script id="review-probe">alert(1)</script><img src=x onerror="alert(1)"> & "'
    recs = _corpus()
    recs[0]["title"] = payload
    for rec in recs:
        rec["authorships"][0]["institutions"][0]["root_name"] = payload
    r = build_report(recs, name=payload, slug="test", n_topics=2)
    html = render_page(r, embedded=True, app_links=True)

    class Tags(HTMLParser):
        def __init__(self):
            super().__init__()
            self.tags = []
        def handle_starttag(self, tag, attrs):
            self.tags.append((tag, dict(attrs)))

    parser = Tags()
    parser.feed(html)
    # Trusted rendering may add scripts (e.g. print handling); injected markup must
    # never create an executable element or event handler.
    assert not any(tag == "img" or "onerror" in attrs or attrs.get("id") == "review-probe" for tag, attrs in parser.tags)
    assert '&lt;/script&gt;' in html
    specs = json.loads(re.search(r"const specs = (.*?);\n", html).group(1))
    assert specs["fig-inst"]["data"]["values"][0]["name"] == payload
    entities = json.loads(re.search(r"window.ENTITIES = (.*?);\n", html).group(1))
    assert entities["insts"][0]["name"] == payload
    assert '.ent-drawer' in html and 'if (!E) return;' in html  # trusted CSS / JS remain executable
    index = render_index([("More", [(None, [("test", "TEST", payload, 80)])])], embedded=True)
    assert payload not in index and '&lt;/script&gt;' in index
    assert 'Data fetched: unknown' in html and 'report generated ' in html


def test_home_navigation_uses_domains_and_research_directions():
    from paper_trends.report.render import nav_for, render_index

    available = {
        "ectc": {"name": "ECTC", "n_papers": 10},
        "irps": {"name": "IRPS", "n_papers": 20},
        "iedm": {"name": "IEDM", "n_papers": 30},
        "infocom": {"name": "INFOCOM", "n_papers": 40},
    }
    nav = nav_for(available)
    assert [domain for domain, _ in nav] == ["Semiconductor & microelectronics", "Communications & signal processing"]
    semiconductor = nav[0][1]
    assert [direction for direction, _ in semiconductor] == ["Packaging & integration", "Reliability", "Devices & circuits"]
    assert nav[1][1][0][0] == "Communications & networking"
    zh = render_index(nav, embedded=True, lang="zh")
    assert "半导体与微电子" in zh and "封装与集成" in zh and "可靠性" in zh and "通信与信号处理" in zh
    assert 'href="#domain-0"' in zh and 'id="domain-0"' in zh
    assert "所列会议数量不代表各领域的会议规模" in zh


def test_panel_uses_the_same_title_only_counts_as_the_report():
    records = [{
        "id": f"W{i}", "publication_year": 2020 + i % 2,
        "title": "hybrid bonding" if i < 5 else "acoustic sensing",
        "abstract": "hybrid bonding improves hybrid bonding" if i in (5, 6, 7) else None,
        "authorships": [{"institutions": [{"id": "I1", "name": "Lab", "country": "US"}]}],
    } for i in range(10)]
    r = build_report(records, name="Sparse abstracts", slug="test", n_topics=2)
    assert r["text_mode"] == "title"
    e = r["entities"]
    term = next(t for t in e["terms"] if t["term"] == "hybrid bonding")
    assert term["total"] == 5
    assert term["insts"] == [[0, 5]]
    assert all(e["papers"][i]["t"] == "hybrid bonding" for i in term["papers"])


def test_report_distinguishes_fetch_time_generation_and_missing_years():
    from paper_trends.report.render import render_page
    provenance = {"fetched_at": "2020-01-02T03:04:00+00:00", "status": "verified"}
    r = build_report(_corpus(), name="Test", slug="test", years=(2015, 2023), n_topics=2,
                     provenance=provenance)
    html = render_page(r)
    assert "Data fetched: 2020-01-02 03:04 UTC" in html
    assert f"report generated {r['generated']}" in html
    assert "No cached records for 2015" in html and "No cached records</td>" in html
    assert "Reporting period: 2015–2023" in html
    assert "share of indexed papers with abstracts, not the completeness of conference proceedings" in html


def test_all_displayed_phrases_get_panels_even_outside_top_terms(monkeypatch):
    from paper_trends.report import build
    from paper_trends.report.entities import build_entities

    # Simulate a page whose selected risers/fallers fall below the panel's frequency cap.
    def without_popular_terms(*args, **kwargs):
        return build_entities(*args, n_terms=0, **kwargs)
    monkeypatch.setattr(build, "build_entities", without_popular_terms)
    r = build_report(_corpus(), name="Test", slug="test", n_topics=2)
    displayed = {t for section in ("rising", "falling", "emerging") for row in r[section]
                 for t in [row["term"], *row["variants"]]}
    assert displayed and displayed <= set(r["entities"]["term_index"])


@pytest.mark.parametrize("records", [[], [{"title": "Undated"}]])
def test_empty_reports_explain_missing_data(records):
    with pytest.raises(ValueError, match="No papers with a publication year"):
        build_report(records, name="Empty", slug="empty")


def test_empty_period_cli_returns_a_clear_error(tmp_path, capsys):
    from paper_trends.report.render import main
    from paper_trends.store import write_jsonl
    corpus = tmp_path / "test.jsonl"
    write_jsonl(_corpus(), corpus)
    assert main([str(corpus), "--years", "2000-2001", "--out", str(tmp_path / "site")]) == 2
    assert "No papers" in capsys.readouterr().err
    assert not (tmp_path / "site").exists()


@pytest.mark.parametrize("records", [
    [{"publication_year": 2020, "title": "hybrid bonding"}],
    [{"publication_year": 2020, "title": "the and of"}] * 3,
    [{"publication_year": 2020, "title": "hybrid bonding"}] * 20,
])
def test_single_year_and_small_corpora_render_without_false_trends(records):
    from paper_trends.report.render import render_page
    r = build_report(records, name="Small", slug="small")
    html = render_page(r)
    assert not r["has_trends"] and not r["rising"] and not r["falling"] and not r["inst_ranks"]
    assert "Only one year" in html and 'id="rising"' not in html
    assert "2020–2019" not in html and "up from 0.0% to 0.0%" not in html
    assert "fig-topics" not in figure_specs(r)
