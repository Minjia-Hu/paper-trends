from paper_trends.compare import shared_risers, term_shares, trends_for


def _rec(year, title):
    return {"publication_year": year, "title": title, "abstract": None}


def test_term_shares_and_shared_risers():
    a = [_rec(2016, "solder"), _rec(2016, "solder"), _rec(2019, "chiplet ai"), _rec(2019, "chiplet")]
    b = [_rec(2016, "cmos"), _rec(2016, "cmos"), _rec(2019, "ai accelerator"), _rec(2019, "ai")]
    trends = trends_for({"A": a, "B": b}, text="title", n_min=1, n_max=1, min_total=1, background=None)
    rows = term_shares(trends, ["ai"])
    share = {(r["conference"], r["year"]): r["share"] for r in rows}
    assert share[("A", 2019)] == 0.5 and share[("B", 2019)] == 1.0 and share[("A", 2016)] == 0.0
    common = shared_risers(trends, k=5, min_total=1)
    assert [t for t, _ in common] == ["ai"]  # chiplet rises only in A, cmos falls only in B


def test_comparison_normalizes_hyphens_and_corpus_acronyms():
    a = [_rec(2020, "High-bandwidth memory (HBM) through-silicon via (TSV)")] * 3
    b = [_rec(2020, "High bandwidth memory through silicon via")] * 3
    trends = trends_for({"A": a, "B": b}, text="title", n_min=1, n_max=3, min_total=1, background=None)
    terms = ["High-Bandwidth Memory", "through silicon via"]
    rows = term_shares(trends, terms)
    by_key = {(r["conference"], r["term"]): r["papers"] for r in rows}
    assert by_key[("A", terms[0])] == by_key[("B", terms[0])] == 3
    # A contracts the long form to TSV; B's literal phrase has stopword edges and
    # is not counted by the keyword rules. Normalize against each corpus map.
    assert by_key[("A", terms[1])] == 3
    assert by_key[("B", terms[1])] == 0
    assert term_shares(trends, ["HBM"])[0]["papers"] == 3


def test_compare_cli_normalization_and_empty_range(tmp_path, capsys):
    from paper_trends.compare import main
    from paper_trends.store import write_jsonl

    path = tmp_path / "papers.jsonl"
    write_jsonl([_rec(2020, "High-bandwidth memory")] * 2, path)
    assert main([str(path), "--term", "High-Bandwidth Memory"]) == 0
    assert "100.0%" in capsys.readouterr().out
    assert main([str(path), "--years", "1900-1901"]) == 1
    assert "No papers" in capsys.readouterr().err


def test_comparison_distinguishes_missing_editions_from_measured_zero():
    a = [_rec(2020, "solder"), _rec(2022, "chiplet")]
    b = [_rec(2021, "solder")]
    trends = trends_for({"A": a, "B": b}, text="title", min_total=1, background=None)
    rows = term_shares(trends, ["chiplet"])
    by_key = {(r["conference"], r["year"]): r for r in rows}
    assert len(rows) == 6
    assert by_key[("A", 2020)]["papers"] == 0 and by_key[("A", 2020)]["share"] == 0.0
    assert by_key[("A", 2021)]["papers"] is None and by_key[("A", 2021)]["share"] is None
    assert by_key[("A", 2022)]["papers"] == 1 and by_key[("A", 2022)]["share"] == 1.0
    assert by_key[("B", 2020)]["share"] is None and by_key[("B", 2022)]["share"] is None
    assert by_key[("B", 2021)]["share"] == 0.0
    explicit = term_shares(trends, ["chiplet"], years=[2019, 2020, 2021, 2022, 2023])
    assert len(explicit) == 10
    assert all(r["share"] is None for r in explicit if r["year"] in (2019, 2023))


def test_compare_cli_and_csv_preserve_missing_calendar_years(tmp_path, capsys):
    import csv
    from paper_trends.compare import main
    from paper_trends.store import write_jsonl

    path = tmp_path / "papers.jsonl"
    write_jsonl([_rec(2020, "solder"), _rec(2022, "chiplet")] * 2, path)
    export = tmp_path / "comparison.csv"
    assert main([str(path), "--term", "chiplet", "--years", "2019-2023", "--csv", str(export)]) == 0
    output = capsys.readouterr().out
    assert "2019" in output and "2023" in output
    assert "—" in output and "0.0%" in output and "100.0%" in output
    with export.open() as fh:
        rows = {int(r["year"]): r for r in csv.DictReader(fh)}
    assert rows[2020]["papers"] == "0" and rows[2020]["share"] == "0.0"
    for missing in (2019, 2021, 2023):
        assert rows[missing]["papers"] == rows[missing]["share"] == ""
