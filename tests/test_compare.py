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
