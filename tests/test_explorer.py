from collections import Counter

from paper_trends.keywords import compute_trends
from paper_trends.rank import compute_ranking
from paper_trends.report.explorer import ExplorerBuilder
from paper_trends.text import term_mentions
from paper_trends.topics import Topic, TopicTrends


def make_explorer(text="title+abstract"):
    records = []
    for role in ("title", "repeated", "once"):
        for i in range(5):
            records.append({"id": f"{role}{i}", "publication_year": 2018 if role != "once" else 2020,
                            "title": "Hybrid bonding" if role == "title" else "Interconnect reliability",
                            "abstract": "Hybrid bonding improves hybrid bonding." if role == "repeated" else "Hybrid bonding is used.",
                            "cited_by_count": i, "authorships": [
                                {"institutions": [{"id": "I1", "name": "Lab"}]},
                                {"institutions": [{"id": "I1", "name": "Lab"}]}]})
    kt = compute_trends(records, text=text, n_min=2, n_max=3, background=None)
    tt = TopicTrends(kt.years, kt.papers_per_year, [Topic(0, "Packaging", [])], {}, "nmf",
                     assignments={i: 0 for i in range(len(records))})
    inst = compute_ranking(records, "institution", roll_up=True)
    builder = ExplorerBuilder(records, kt, tt, inst, str, ["hybrid bonding"])
    for i, r in enumerate(records):
        builder.add(i, term_mentions(r["title"], r["abstract"] if text != "title" else None, 2, 3, acronyms=kt.acronyms))
    return builder.finish(), kt


def test_explorer_roles_are_exclusive_and_full_counts_survive_sampling():
    data, kt = make_explorer()
    term = data["terms"][0]
    assert data["years"] == [2018, 2019, 2020]
    assert data["papers_per_year"] == [10, 0, 5]
    assert term["counts"] == [[5, 5, 0], [0, 0, 0], [0, 0, 5]]
    assert sum(row[0] + row[1] for row in term["counts"]) == kt.total("hybrid bonding") == 10
    assert term["institutions"] == [{"name": "Lab", "rows": [[0, 5, 5, 0], [2, 0, 0, 5]]}]
    assert term["topics"] == [{"name": "Packaging", "rows": [[0, 5, 5, 0], [2, 0, 0, 5]]}]
    assert Counter((y, role) for y, role, _ in term["examples"]) == {(0, 0): 3, (0, 1): 3, (2, 2): 3}
    assert len(data["papers"]) == 9  # 15 counted records, nine explicitly sampled examples
    assert {p["citations"] for p in data["papers"]} == {2, 3, 4}


def test_title_only_explorer_cannot_silently_use_abstract_evidence():
    data, kt = make_explorer("title")
    assert data["text_mode"] == "title"
    assert data["terms"][0]["counts"] == [[5, 0, 0], [0, 0, 0], [0, 0, 0]]
    assert len(data["papers"]) == 3
    assert sum(row[0] for row in data["terms"][0]["counts"]) == kt.total("hybrid bonding")
