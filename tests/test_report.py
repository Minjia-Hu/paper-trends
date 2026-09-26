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
            "id": f"W{i}", "doi": f"10.1109/x.{y}.{i}", "title": f"{topic.split()[0]} study {i}", "publication_year": y,
            "abstract": f"{topic} variant {i % 5}", "cited_by_count": i,
            "authorships": [{"author_id": f"A{i % 7}", "author_name": f"Author {i % 7}",
                             "institutions": [{"id": f"I{i % 4}", "name": f"Inst {i % 4}", "country": ["US", "KR", "JP", "TW"][i % 4],
                                               "root_id": f"I{i % 4}", "root_name": f"Inst {i % 4}", "root_country": ["US", "KR", "JP", "TW"][i % 4]}]}],
            "topics": [], "oa_keywords": [], "type": "conference-paper", "source_id": None, "source_name": "X",
        })
    return recs


def test_growth_sentence():
    assert growth_sentence({2016: 100, 2017: 100, 2018: 100, 2019: 100}) == "output has been flat"
    assert "growing" in growth_sentence({2016: 100, 2017: 110, 2018: 130, 2019: 150})


def test_build_and_render(tmp_path):
    r = build_report(_corpus(), name="Test Conf", slug="test", years=(2016, 2023), n_topics=2)
    assert r["n_papers"] == 80 and r["year_range"] == [2016, 2023]
    assert r["glance"] and "Test Conf" in r["glance"][0]
    assert r["countries"][0]["name"] in {"United States", "South Korea", "Japan", "Taiwan"}
    specs = figure_specs(r)
    assert {"fig-papers", "fig-topics", "fig-inst", "fig-country"} <= set(specs)
    json.dumps(specs)  # must be JSON-serialisable
    render_site([r], tmp_path)
    html = (tmp_path / "test.html").read_text()
    assert "Test Conf" in html and "fig-topics" in html and "report.css" in html
    assert (tmp_path / "index.html").exists() and (tmp_path / "report.css").exists()


def test_dedupe_singular_plural():
    from paper_trends.report.build import _dedupe

    rows = [("diffusion models", 1), ("diffusion model", 2), ("vision language", 3), ("solder joint", 4), ("solder joints", 5), ("stress", 6)]
    assert [r[0] for r in _dedupe(rows)] == ["diffusion models", "vision language", "solder joint", "stress"]
