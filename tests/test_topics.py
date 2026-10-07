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


def test_topic_vocabulary_keeps_scientific_terms_and_numeric_boundaries():
    from paper_trends.text import STOPWORDS
    from paper_trends.topics import _topic_terms

    terms = set(_topic_terms("3D integration 2.5D packaging 5G radio 28nm CMOS copper 2024 bonding", STOPWORDS))
    assert {"3d", "3d integration", "2.5d", "2.5d packaging", "5g", "5g radio", "28nm", "28nm cmos"} <= terms
    assert "2024" not in terms
    assert "copper bonding" not in terms
    assert "copper 2024" not in terms and "2024 bonding" not in terms
    assert "müller model" in _topic_terms("Müller model", STOPWORDS)


def test_nmf_retains_numeric_prefixes_in_fitted_topics():
    records = [_rec(2020, "3D integration", f"2.5D packaging 5G radio 28nm CMOS {ending}", "Devices")
               for ending in ("copper bonds", "silicon devices", "radio channels", "thermal interfaces")]
    tt = compute_nmf(records, n_topics=2, n_terms=100, min_df=1, max_df=1.0)
    terms = {term for topic in tt.topics for term in topic.terms}
    assert {"3d integration", "2.5d packaging", "5g radio", "28nm cmos"} <= terms
    assert sum(tt.total(t.id) for t in tt.topics) == len(records)


def test_topics_cli_explains_empty_range_and_insufficient_text(tmp_path, capsys):
    from paper_trends.store import write_jsonl
    from paper_trends.topics import main

    path = tmp_path / "papers.jsonl"
    write_jsonl(_corpus(), path)
    for method in ("nmf", "openalex", "openalex-subfield"):
        assert main([str(path), "--years", "1900-1901", "--method", method]) == 1
        assert "[error]" in capsys.readouterr().err
    write_jsonl([_rec(2020, "and the", "of the", "Empty")] * 2, path)
    assert main([str(path)]) == 1
    assert "No usable vocabulary" in capsys.readouterr().err
    write_jsonl([_rec(2020, "thermal", "cooling", "Thermal")], path)
    assert main([str(path)]) == 1
    assert "at least two papers" in capsys.readouterr().err
