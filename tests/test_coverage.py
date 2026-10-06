from paper_trends.coverage import coverage_details, default_period, period_decision


def corpus(counts, coverage=1.0):
    return [{"publication_year": y, "title": "hybrid bonding", "abstract": "text" if i < n * coverage else None}
            for y, n in counts.items() for i in range(n)]


def test_defaults_exclude_current_year_and_sparse_trailing_editions():
    records = corpus({2022: 100, 2023: 110, 2024: 105, 2025: 2, 2026: 1})
    assert default_period(records, current_year=2026) == (2022, 2024)
    # The sparse cached edition remains excluded after the calendar moves on.
    assert default_period(records, current_year=2027) == (2022, 2024)
    assert default_period(records, 2, current_year=2026) == (2023, 2024)


def test_title_only_venues_keep_early_years_with_sparse_abstracts():
    records = corpus({y: 100 for y in range(2016, 2026)}, coverage=0.2)
    records += corpus({2026: 1})
    assert default_period(records, current_year=2026) == (2016, 2025)


def test_delayed_abstracts_are_skipped_for_normally_high_coverage_venues():
    records = corpus({2022: 100, 2023: 100, 2024: 100}) + corpus({2025: 100}, coverage=0.03)
    assert default_period(records, current_year=2026) == (2022, 2024)


def test_small_venues_and_no_past_data():
    assert default_period(corpus({2024: 2, 2025: 2}), current_year=2026) == (2024, 2025)
    assert default_period(corpus({2026: 100}), current_year=2026) is None
    assert default_period([{"title": "undated"}], current_year=2026) is None


def test_exclusion_reasons_follow_the_same_decision_as_the_default_period():
    records = corpus({2022: 100, 2023: 110, 2024: 105, 2025: 2, 2026: 1})
    decision = period_decision(records, current_year=2026)
    assert decision["period"] == (2022, 2024)
    assert [(r["year"], r["reason"]) for r in decision["excluded"]] == [
        (2025, "sparse_records"), (2026, "current_or_future")]
    assert "2 records" in decision["excluded"][0]["message"]
    assert "median (105)" in decision["excluded"][0]["message"]
    delayed = period_decision(corpus({2022: 100, 2023: 100}) + corpus({2024: 100}, .03), current_year=2026)
    assert delayed["excluded"][0]["reason"] == "delayed_abstracts"
    assert "3.0%" in delayed["excluded"][0]["message"]


def test_coverage_explains_abstract_gaps_without_treating_them_as_empty_editions():
    records = corpus({2023: 100}) + corpus({2025: 1000}, .852)
    details = coverage_details(records, (2023, 2025))
    assert details["rows"][1] == {"year": 2024, "papers": 0, "abstracts": 0, "coverage": None}
    assert any("2025 (85.2%)" in note for note in details["notices"])
    assert any("not evidence of zero research output" in note for note in details["notices"])
    sparse = coverage_details(corpus({2020: 100, 2021: 100}, .2), (2020, 2021))
    assert any("titles only" in note and "topic analysis" in note for note in sparse["notices"])
