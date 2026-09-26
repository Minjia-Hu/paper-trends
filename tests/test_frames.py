from paper_trends import frames
from paper_trends.keywords import compute_trends
from paper_trends.rank import compute_ranking
from paper_trends.viz import CATEGORICAL, OTHER, series_colors


def _rec(year, title, abstract=None):
    return {"publication_year": year, "title": title, "abstract": abstract, "cited_by_count": 1,
            "authorships": [{"author_id": "A1", "author_name": "A", "institutions": [{"id": "I1", "name": "Lab", "country": "US"}]}]}


def test_coverage_and_keyword_frames():
    recs = [_rec(2016, "hybrid bonding", "x"), _rec(2016, "solder"), _rec(2017, "hybrid bonding")]
    cov = frames.coverage_frame(recs)
    assert cov["papers"].tolist() == [2, 1] and cov["coverage"].tolist() == [0.5, 0.0]
    kt = compute_trends(recs, text="title", min_total=1)
    long = frames.keyword_series(kt, ["hybrid bonding"])
    assert long["share"].tolist() == [0.5, 1.0]
    wide = frames.keyword_table(kt, ["hybrid bonding"])
    assert list(wide.columns) == ["term", "papers", "2016", "2017"]


def test_ranking_frame():
    rk = compute_ranking([_rec(2016, "a"), _rec(2017, "b")], "institution")
    df = frames.ranking_table(rk, rk.top(5))
    assert df.iloc[0]["institution"] == "Lab" and df.iloc[0]["papers"] == 2


def test_series_colors_fixed_order_and_other():
    domain, rng = series_colors(["b", "a", "Other"])
    assert rng == [CATEGORICAL[0], CATEGORICAL[1], OTHER]
