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


def test_fragments_of_longer_phrases_are_hidden():
    # "level packaging" only ever sits inside wafer-/panel-level packaging; "fine pitch" is
    # followed by many different nouns and stands on its own
    nouns = ["interconnects", "bumps", "pillars", "applications", "copper", "assembly", "redistribution", "substrates", "probes", "flip", "test", "dies"]
    recs = [_rec(2016 + i % 4, f"Wafer level packaging with fine pitch {nouns[i]}") for i in range(12)]
    recs += [_rec(2016 + i % 4, f"Panel level packaging at fine pitch {nouns[i]}") for i in range(12)]
    kt = compute_trends(recs, text="title", n_min=2, n_max=3, min_total=1, background=None)
    assert kt.is_fragment("level packaging") and kt.inside["level packaging"] == 1.0
    assert not kt.is_fragment("fine pitch") and kt.inside["fine pitch"] < 0.5
    assert "level packaging" not in kt.top_terms(50) and "fine pitch" in kt.top_terms(50)
    kt.collapse_ratio = None
    assert "level packaging" in kt.top_terms(50)


def test_group_families_folds_variants_and_twins():
    from paper_trends.keywords import group_families

    rows = [("hybrid bonding", 0.1), ("heterogeneous integration", 0.05), ("wafer hybrid bonding", 0.04),
            ("solder joints", 0.03), ("hybrid bonding process", 0.02), ("solder joint", 0.01), ("high bandwidth", 0.01), ("high bandwidth memory", 0.005)]
    fams = group_families(rows)
    assert [h[0] for h, _ in fams] == ["hybrid bonding", "heterogeneous integration", "solder joints", "high bandwidth"]
    assert dict((h[0], v) for h, v in fams)["hybrid bonding"] == ["wafer hybrid bonding", "hybrid bonding process"]
    assert dict((h[0], v) for h, v in fams)["solder joints"] == ["solder joint"]
    # with totals, a longer member that carries most of the papers heads the family
    totals = {"high bandwidth": 90, "high bandwidth memory": 60, "hybrid bonding": 200, "wafer hybrid bonding": 40, "hybrid bonding process": 30,
              "heterogeneous integration": 1, "solder joints": 1, "solder joint": 1}
    fams = group_families(rows, k=4, total=totals.__getitem__)
    assert [h[0] for h, _ in fams] == ["hybrid bonding", "heterogeneous integration", "solder joints", "high bandwidth memory"]
    assert len(group_families(rows, k=2)) == 2


def test_corpus_acronyms_need_agreement():
    from paper_trends.keywords import corpus_acronyms

    recs = [_rec(2020, "x", "A thermal interface material (TIM) is used. TIM thickness matters.")] * 4
    recs += [_rec(2021, "x", "The time in minutes (TIM) is logged.")]
    recs += [_rec(2021, "x", "Power delivery (PD) and photodiode (PD) differ.")] * 2
    am = corpus_acronyms(recs)
    assert am.expand["tim"] == ["thermal", "interface", "material"]   # 4 of 5 definitions agree
    assert "pd" not in am.defs                                         # too few, and inconsistent
    kt = compute_trends(recs + [_rec(2022, "TIM reliability", "No definition here, TIM used twice. TIM again.")], n_min=2, n_max=3, min_total=1, background=None)
    assert kt.doc_freq["thermal interface material"] == {2020: 4, 2022: 1}   # the undefined use is read through the corpus map


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


def test_restore_hyphens_from_corpus_spelling():
    from collections import Counter
    from paper_trends.keywords import hyphen_forms, restore_hyphens

    recs = [_rec(2020, "Co-packaged optics and wafer-level packaging")] * 3 + [_rec(2021, "co packaged optics")]
    forms = hyphen_forms(recs, text="title")
    assert forms["co-packaged"] == 3 and forms["wafer-level"] == 3
    assert restore_hyphens("co packaged optics", forms) == "co-packaged optics"
    assert restore_hyphens("wafer level packaging", forms) == "wafer-level packaging"
    assert restore_hyphens("hybrid bonding", forms) == "hybrid bonding"
    assert restore_hyphens("state of the art", Counter({"state-of-the-art": 5})) == "state-of-the-art"


def test_topical_counts_ignore_single_mentions():
    abstract = ("Artificial intelligence drives demand for packaging. We study solder joints under load. "
                "Cracks grow in solder joints after cycling. Finite element analysis is used.")
    recs = [_rec(2020, "Reliability of interconnects", abstract)] * 3
    topical = compute_trends(recs, n_min=2, n_max=2, min_total=1, background=None)
    every = compute_trends(recs, n_min=2, n_max=2, min_total=1, basis="any", background=None)
    assert "artificial intelligence" not in topical.doc_freq            # name-dropped once
    assert "finite element" not in topical.doc_freq                     # a method, used once
    assert every.doc_freq["artificial intelligence"] == {2020: 3}
    assert topical.doc_freq["solder joints"] == {2020: 3}
    assert topical.mentions("solder joints") == 3 and topical.topical_share("solder joints") == 1.0


def test_common_phrases_are_hidden_from_rankings():
    table = {"min_fields": 3, "terms": {"high performance": {"devices": .08, "circuits": .06, "thermal": .09, "packaging": .11},
                                         "hybrid bonding": {"packaging": .06, "devices": .006}}}
    recs = [_rec(2016, "High performance hybrid bonding")] * 2 + [_rec(2019, "High performance hybrid bonding")] * 2
    kt = compute_trends(recs, text="title", n_min=2, n_max=2, min_total=1, field="packaging", background=table)
    assert kt.common == {"high performance": ["circuits", "devices", "thermal"]}   # own field is not counted
    assert "high performance" not in kt.top_terms(10) and "hybrid bonding" in kt.top_terms(10)
    kt.keep_common = True
    assert "high performance" in kt.top_terms(10)
    # only two other fields -> not common
    table["terms"]["high performance"].pop("thermal")
    assert not compute_trends(recs, text="title", n_min=2, n_max=2, min_total=1, field="packaging", background=table).common


def test_cross_field_technology_is_not_boilerplate():
    terms = ["deep learning", "neural networks", "reinforcement learning", "energy consumption",
             "real time", "end to end", "high performance computing", "high performance"]
    table = {"min_fields": 3, "terms": {
        term: {"devices": .08, "circuits": .06, "thermal": .09} for term in terms}}
    records = [_rec(2020, term) for term in terms] * 2
    kt = compute_trends(records, n_min=2, n_max=3, background=table)
    assert set(kt.common) == {"high performance"}
    assert set(terms[:-1]) <= set(kt.candidates())
    unfiltered = compute_trends(records, n_min=2, n_max=3, background=None)
    assert kt.doc_freq == unfiltered.doc_freq  # filtering changes eligibility, never counts
    assert kt.momentum("deep learning") == unfiltered.momentum("deep learning")
    kt.keep_common = True
    assert "high performance" in kt.candidates()


def test_local_acronym_meaning_overrides_corpus_majority():
    # Both meanings occur in the S&P audit. A minority definition must not be
    # silently turned into the majority meaning by the corpus-wide map.
    records = [_rec(2020, "x", "A man in the middle (MITM) attack. MITM attacks persist.")] * 5
    records += [_rec(2021, "x", "A meet in the middle (MITM) attack. MITM attacks persist.")]
    kt = compute_trends(records, n_min=1, n_max=4, min_total=1, background=None)
    assert kt.acronyms.defs["mitm"][1] == ["man", "in", "the", "middle"]
    assert kt.doc_freq["man in the middle"] == {2020: 5}
    assert kt.doc_freq["meet in the middle"] == {2021: 1}


def test_paper_lookup_uses_the_counting_normalization_options():
    from paper_trends.keywords import papers_with
    from paper_trends.text import load_stopwords

    definitions = [_rec(2020, "Interconnect fabrication",
                        "Redistribution layer (RDL) is added. RDL thickness matters.")] * 3
    literal = [_rec(2021, "Layer uniformity")] * 2
    records = definitions + literal
    kt = compute_trends(records, n_min=1, n_max=1, background=None)
    assert kt.total("layer") == 2
    assert papers_with(records, "layer", n_max=1) == literal

    records = definitions + [_rec(2021, "Redistribution layer uniformity")] * 2
    stop = load_stopwords(["rdl"])
    kt = compute_trends(records, n_min=2, n_max=3, stopwords=stop, background=None)
    assert kt.total("redistribution layer") == 2
    assert len(papers_with(records, "redistribution layer", stopwords=stop)) == 2


def test_keywords_cli_reports_empty_year_range(tmp_path, capsys):
    from paper_trends.keywords import main
    from paper_trends.store import write_jsonl

    path = tmp_path / "papers.jsonl"
    write_jsonl([_rec(2020, "Hybrid bonding")], path)
    assert main([str(path), "--years", "1900-1901"]) == 1
    assert "No papers" in capsys.readouterr().err


def test_retained_tokens_preserve_record_alignment_and_counting():
    from paper_trends.text import paper_tokens, phrase_roles, TOPICAL_ROLES

    records = [_rec(2020, "Hybrid bonding", "Müller models hybrid bonding"),
               _rec(None, "Undated paper"), _rec(2021, "3D integration")]
    plain = compute_trends(records, min_total=1, background=None)
    retained = compute_trends(records, min_total=1, background=None, retain_tokens=True)
    assert plain.tokenized_papers is None
    assert retained.doc_freq == plain.doc_freq
    assert len(retained.tokenized_papers) == len(records)
    assert retained.tokenized_papers[1] == ([], [])
    for i in (0, 2):
        record = records[i]
        tokens = retained.tokenized_papers[i]
        assert tokens == paper_tokens(record.get("title"), record.get("abstract"), retained.acronyms)
        for term, role in phrase_roles(*tokens).items():
            if role in TOPICAL_ROLES:
                assert retained.doc_freq[term][record["publication_year"]] >= 1

    titles = compute_trends(records, text="title", retain_tokens=True)
    assert titles.tokenized_papers[0][1] == []
