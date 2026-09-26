from paper_trends.keywords import compute_trends


def _rec(year, title, abstract=None):
    return {"publication_year": year, "title": title, "abstract": abstract}


def test_doc_frequency_and_share():
    recs = [
        _rec(2016, "Hybrid bonding study"),
        _rec(2016, "Wire bonding reliability"),
        _rec(2017, "Hybrid bonding hybrid bonding"),
        _rec(2017, "Thermal management"),
    ]
    kt = compute_trends(recs, text="title", n_min=1, n_max=2, min_total=1)
    assert kt.years == [2016, 2017]
    assert kt.doc_freq["bonding"] == {2016: 2, 2017: 1}
    assert kt.doc_freq["hybrid bonding"] == {2016: 1, 2017: 1}  # counted once per paper
    assert kt.share("bonding", 2016) == 1.0
    assert kt.share("bonding", 2017) == 0.5


def test_rising_and_falling():
    recs = [_rec(2016, "wire bonding")] * 3 + [_rec(2016, "solder")] + [_rec(2019, "hybrid bonding")] * 3 + [_rec(2019, "solder")]
    kt = compute_trends(recs, text="title", n_min=1, n_max=2, min_total=1)
    rising = [t for t, *_ in kt.rising(5, min_total=1)]
    falling = [t for t, *_ in kt.falling(5, min_total=1)]
    assert rising[0] in {"hybrid", "hybrid bonding"}
    assert falling[0] in {"wire", "wire bonding"}
    assert kt.momentum("solder")[2] == 0.0


def test_abstract_coverage_reported():
    recs = [_rec(2016, "a", "abstract"), _rec(2016, "b"), _rec(2017, "c")]
    kt = compute_trends(recs, min_total=1)
    assert kt.abstract_coverage == {2016: 0.5, 2017: 0.0}


def test_subphrases_collapse_into_longer_terms():
    from paper_trends.keywords import collapse_subphrases

    totals = {"hybrid bonding": 100, "hybrid": 110, "bonding": 400, "intelligence ai": 30,
              "artificial intelligence ai": 28, "ai": 50}
    kept = collapse_subphrases(list(totals), totals.__getitem__, 0.8)
    assert "hybrid" not in kept            # 100/110 >= 0.8 -> absorbed by 'hybrid bonding'
    assert "bonding" in kept               # 100/400 < 0.8 -> stands on its own
    assert "intelligence ai" not in kept   # 28/30 >= 0.8 -> absorbed by the 3-gram
    assert "artificial intelligence ai" in kept and "ai" in kept


def test_emerging_and_papers_with():
    from paper_trends.keywords import papers_with

    recs = [_rec(2016, "solder joints")] * 5 + [_rec(2017, "solder joints")] * 5
    recs += [_rec(2020, "chiplet integration")] * 3 + [_rec(2021, "chiplet integration"), _rec(2021, "solder joints")]
    kt = compute_trends(recs, text="title", n_min=1, n_max=2, min_total=1)
    em = kt.emerging(5, min_total=1)
    assert [t for t, *_ in em][:1] == ["chiplet integration"] or [t for t, *_ in em][:1] == ["chiplet"]
    assert all(first == 2020 for _, first, _, _ in em)
    assert "solder joints" not in [t for t, *_ in em]  # common early -> not emerging
    hits = papers_with(recs, "Chiplet Integration", text="title")
    assert len(hits) == 4 and hits[0]["publication_year"] == 2021
    assert papers_with(recs, "integration chiplet", text="title") == []  # phrase order matters
