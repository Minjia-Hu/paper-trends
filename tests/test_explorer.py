from collections import Counter

from paper_trends.keywords import compute_trends
from paper_trends.rank import compute_ranking
from paper_trends.report.explorer import ExplorerBuilder
from paper_trends.text import term_mentions
from paper_trends.topics import Topic, TopicTrends


def make_explorer(text="title+abstract", full_results=False):
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
    builder = ExplorerBuilder(records, kt, tt, inst, str, ["hybrid bonding"], full_results=full_results)
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


def test_full_evidence_covers_every_counted_paper_beyond_sample_cap():
    data, _ = make_explorer(full_results=True)
    term = data["terms"][0]
    assert len(data["papers"]) == 9
    assert len(data["results"]) == len(term["matches"]) == 15
    assert len({data["results"][i]["id"] for _, _, i in term["matches"]}) == 15
    for year, counts in enumerate(term["counts"]):
        for role, count in enumerate(counts):
            assert sum(y == year and r == role for y, r, _ in term["matches"]) == count


def test_institution_topic_mix_respects_parent_roll_up():
    from paper_trends.report.build import inst_topic_rows
    records = [{"publication_year": 2020, "authorships": [{"institutions": [
        {"id": "child", "name": "Lab", "root_id": "parent", "root_name": "University"}]}]}]
    tt = TopicTrends([2020], {2020: 1}, [Topic(0, "Packaging", [])], {0: {2020: 1}}, "nmf", assignments={0: 0})
    for roll_up, expected in [(True, "University"), (False, "Lab")]:
        rk = compute_ranking(records, "institution", roll_up=roll_up)
        rows = inst_topic_rows(records, tt, rk, rk.top(10), tt.ordered(), roll_up=roll_up)
        assert rows == [{"name": expected, "topic": "Packaging", "papers": 1, "share": 1.0}]
