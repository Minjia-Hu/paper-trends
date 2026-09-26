from paper_trends.fetch import is_front_matter


def test_front_matter_detection():
    assert is_front_matter({"title": "Title Page iii"})
    assert is_front_matter({"title": "ECTC 2023 Program Committee"})
    assert is_front_matter({"title": "2020 IEEE 70th Electronic Components and Technology Conference (ECTC)"})
    assert is_front_matter({"title": "Real paper", "is_paratext": True})
    assert not is_front_matter({"title": "Index Matching Materials for Photonic Packaging"})
    assert not is_front_matter({"title": "Committee-less Consensus for Chiplet Test Scheduling"})


def test_session_overviews_and_forums_are_front_matter():
    for t in ["Session 26 overview: Wireless for IoE", "ISSCC 2024 Timetable", "ISSCC 2019 Panel Discussion",
              "F6: Advances in energy efficient analog design", "EE3: Industry showcase [multiple abstracts]",
              "Tutorials [10 abstracts]", "ISSCC 2018 Index to Authors"]:
        assert is_front_matter({"title": t}), t
    assert is_front_matter({"title": "Quantum engineering", "abstract_inverted_index": {"The": [0], "talk": [1], "was": [2], "not": [3], "made": [4], "available": [5], "for": [6], "publication": [7]}})
    assert not is_front_matter({"title": "A 5G Transceiver in 28nm CMOS", "abstract_inverted_index": {"We": [0], "present": [1]}})
    assert not is_front_matter({"title": "Session-Based Recommendation Hardware"})


def test_doi_prefix_boundary():
    from paper_trends.fetch import build_filters, doi_has_prefix

    assert doi_has_prefix("https://doi.org/10.1109/ECTC.2016.10", "10.1109/ectc")
    assert doi_has_prefix("https://doi.org/10.1109/ECTC51906.2022.00010", "10.1109/ectc")
    assert doi_has_prefix("https://doi.org/10.1109/ISCA45697.2020.00012", "10.1109/isca")
    assert not doi_has_prefix("https://doi.org/10.1109/ISCAS45731.2020.9180400", "10.1109/isca")
    assert not doi_has_prefix("https://doi.org/10.1109/IMWS-AMP.2016.7588326", "10.1109/imw")
    assert not doi_has_prefix("https://doi.org/10.1109/VLSITechnologyandCir46769.2022.9830245", "10.1109/vlsit")
    assert doi_has_prefix("https://doi.org/10.1109/VLSITechnologyandCir46769.2022.9830245", "10.1109/vlsitechnologyandcir")
    assert not doi_has_prefix(None, "10.1109/ectc")
    filters = build_filters([], ["10.1109/vlsit", "10.23919/vlsic"], (2016, 2025))
    assert [pfx for _, pfx in filters] == ["10.1109/vlsit", "10.23919/vlsic"]
