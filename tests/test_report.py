import json
from pathlib import Path

from paper_trends.report.build import build_report, growth_sentence
from paper_trends.report.render import figure_specs, render_site

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
    assert {"fig-papers", "fig-topics", "fig-inst", "fig-country", "fig-heat", "fig-bump"} <= set(specs)
    json.dumps(specs)  # must be JSON-serialisable
    render_site([r], tmp_path)
    html = (tmp_path / "test.html").read_text()
    assert "Test Conf" in html and "fig-topics" in html and "report.css" in html
    assert (tmp_path / "index.html").exists() and (tmp_path / "report.css").exists()


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
