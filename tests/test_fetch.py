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
    assert is_front_matter({"title": "心外膜パラレルワイヤロボットの並列力/位置制御【Powered by NICT】"})   # machine-translated duplicate


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


def test_source_matching_prefers_exact_core_name():
    from paper_trends.fetch import _core_name, resolve_sources

    assert _core_name("2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)") == _core_name("Conference on Computer Vision and Pattern Recognition")
    assert _core_name("Proceedings of the 38th International Conference on Machine Learning") == _core_name("International Conference on Machine Learning")
    assert _core_name("2002 IEEE International Solid-State Circuits Conference. Digest of Technical Papers (Cat. No.02CH37315)") == _core_name("International Solid-State Circuits Conference")
    assert _core_name("Conference on Computer Vision and Pattern Recognition Workshops") != _core_name("Conference on Computer Vision and Pattern Recognition")
    assert _core_name("2021 3rd International Conference on Machine Learning, Big Data and Business Intelligence (MLBDBI)") != _core_name("International Conference on Machine Learning")
    assert _core_name("Proceedings of the 2018 Conference on Foo, Proceedings") == _core_name("Conference on Foo")

    class FakeClient:
        def search_sources(self, q):
            return [
                {"id": "S1", "display_name": "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)"},
                {"id": "S2", "display_name": "2022 IEEE/CVF Conference on Computer Vision and Pattern Recognition Workshops (CVPRW)"},
                {"id": "S3", "display_name": "IEEE International Conference on Machine Learning and Applications"},
            ]

    hits = resolve_sources(FakeClient(), "Conference on Computer Vision and Pattern Recognition")
    assert [h["id"] for h in hits] == ["S1"]
    # no exact match -> fall back to substring matches
    hits = resolve_sources(FakeClient(), "Machine Learning and Applications")
    assert [h["id"] for h in hits] == ["S3"]


def test_resolve_roots_looks_up_missing_parents():
    from paper_trends.fetch import resolve_roots

    class FakeClient:
        calls = []
        def get(self, path, params):
            self.calls.append(params["filter"])
            return {"results": [{"id": "https://openalex.org/I19820366", "display_name": "Chinese Academy of Sciences", "country_code": "CN"}]}

    recs = [{"authorships": [{"institutions": [
        {"id": "https://openalex.org/I4210165038", "name": "University of Chinese Academy of Sciences", "country": "CN", "root_id": "https://openalex.org/I19820366"},
        {"id": "https://openalex.org/I1", "name": "Standalone Lab", "country": "US", "root_id": "https://openalex.org/I1"},
    ]}]}]
    client = FakeClient()
    resolve_roots(client, recs, log=lambda m: None)
    insts = recs[0]["authorships"][0]["institutions"]
    assert insts[0]["root_name"] == "Chinese Academy of Sciences" and insts[0]["root_country"] == "CN"
    assert insts[1]["root_name"] == "Standalone Lab"  # already known, no lookup needed
    assert client.calls == ["ids.openalex:I19820366"]


def test_resolve_venue_acronym_and_name():
    from paper_trends.fetch import resolve_venue, strip_decoration

    assert strip_decoration("2020 57th ACM/IEEE Design Automation Conference (DAC)", light=True) == "Design Automation Conference"
    assert strip_decoration("2021 IEEE International Symposium on Circuits and Systems (ISCAS)", light=True) == "International Symposium on Circuits and Systems"

    class Fake:
        def count_by_year(self, f):
            if "doi_starts_with:10.1109/dac" in f: return {2020: 300, 2021: 300}
            if "primary_location.source.id" in f: return {2020: 100}
            return {}
        def get(self, path, params):
            if "doi_starts_with:10.1109/dac" in params["filter"]:
                return {"results": [{"doi": f"https://doi.org/10.1109/DAC18072.2020.{i}", "primary_location": {"raw_source_name": "2020 57th ACM/IEEE Design Automation Conference (DAC)"}} for i in range(10)]}
            return {"results": [{"doi": f"https://doi.org/10.1109/CICC.2022.{i}"} for i in range(10)]}
        def search_sources(self, q):
            return [{"id": "https://openalex.org/S1", "display_name": "2022 IEEE Custom Integrated Circuits Conference (CICC)", "works_count": 104}]

    r = resolve_venue(Fake(), "DAC")
    assert r["how"] == "acronym" and r["name"] == "Design Automation Conference" and r["doi_prefixes"] == ["10.1109/dac"] and not r["ambiguous"]
    r = resolve_venue(Fake(), "Custom Integrated Circuits Conference")
    assert r["how"] == "name" and r["doi_prefixes"] == ["10.1109/cicc"] and r["slug"] == "cicc" and r["source_ids"] == ["https://openalex.org/S1"]
    assert resolve_venue(Fake(), "") is None
