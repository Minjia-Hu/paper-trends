from paper_trends.topics import compute_nmf, compute_openalex


def _rec(year, title, abstract, topic):
    return {"publication_year": year, "title": title, "abstract": abstract,
            "topics": [{"name": topic, "subfield": "EE"}], "cited_by_count": 0}


THERMAL = "thermal resistance heat sink cooling junction temperature heat flux"
BONDING = "hybrid bonding copper pad pitch dielectric bond interface void"


def _corpus():
    recs = []
    for i in range(12):
        recs.append(_rec(2016 + i % 2, f"thermal {i}", THERMAL + f" fin {i % 3}", "Thermal"))
        recs.append(_rec(2018 + i % 2, f"bonding {i}", BONDING + f" anneal {i % 3}", "Bonding"))
    return recs


def test_nmf_separates_two_topics_and_is_deterministic():
    recs = _corpus()
    a = compute_nmf(recs, n_topics=2, n_terms=4, min_df=1, max_df=1.0)
    b = compute_nmf(recs, n_topics=2, n_terms=4, min_df=1, max_df=1.0)
    assert [t.terms for t in a.topics] == [t.terms for t in b.topics]
    assert sorted(a.total(t.id) for t in a.topics) == [12, 12]
    thermal = next(t for t in a.topics if "thermal" in t.terms or "heat" in t.terms)
    assert set(a.by_year[thermal.id]) == {2016, 2017}
    assert a.momentum(thermal.id)[2] < 0  # thermal papers are all in the early half


def test_openalex_topics_by_year():
    tt = compute_openalex(_corpus())
    labels = {t.label for t in tt.topics}
    assert labels == {"Thermal", "Bonding"}
    assert sum(tt.papers_per_year.values()) == 24


def test_label_prefers_phrases():
    from paper_trends.topics import make_label

    assert make_label(["fan", "level", "wafer", "wafer level", "rdl", "package"]) == "fan / wafer level / rdl"
    assert make_label(["thermal", "heat", "power"]) == "thermal / heat / power"
