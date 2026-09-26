from paper_trends.rank import compute_ranking, entities_of


def _paper(year, cites, *affils):
    """affils: list of (author, institution, country) per author."""
    return {
        "publication_year": year,
        "cited_by_count": cites,
        "authorships": [
            {
                "author_id": f"A/{a}",
                "author_name": a,
                "institutions": [{"id": f"I/{i}", "name": i, "country": c}] if i else [],
                "raw_affiliations": [] if i else ["Unknown Lab"],
            }
            for a, i, c in affils
        ],
    }


def test_full_counting_once_per_paper():
    rec = _paper(2020, 5, ("alice", "TSMC", "TW"), ("bob", "TSMC", "TW"), ("carol", "Intel", "US"))
    assert set(entities_of(rec, "institution").values()) == {"TSMC", "Intel"}
    assert set(entities_of(rec, "country")) == {"TW", "US"}
    assert len(entities_of(rec, "author")) == 3


def test_ranking_totals_and_citations():
    recs = [
        _paper(2020, 5, ("alice", "TSMC", "TW"), ("bob", "TSMC", "TW")),
        _paper(2021, 1, ("carol", "Intel", "US")),
        _paper(2021, 2, ("alice", "TSMC", "TW"), ("dan", "Intel", "US")),
    ]
    rk = compute_ranking(recs, "institution")
    tsmc, intel = "I/TSMC", "I/Intel"
    assert rk.total(tsmc) == 2 and rk.total(intel) == 2
    assert rk.citations[tsmc] == 7 and rk.citations[intel] == 3
    assert rk.top(1, by="citations") == [tsmc]
    assert rk.share(tsmc, 2021) == 0.5


def test_raw_affiliation_fallback():
    rec = _paper(2020, 0, ("eve", None, None))
    assert list(entities_of(rec, "institution").values()) == ["Unknown Lab"]
