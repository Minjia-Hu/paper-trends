import csv
import io
import json
from pathlib import Path

import pandas as pd
import pytest

from paper_trends import compare, frames, keywords, rank, topics
from paper_trends.csv_export import safe_cell
from paper_trends.store import write_jsonl


CASES = json.loads(Path(__file__).with_name("csv-export-cases.json").read_text())


@pytest.mark.parametrize("value, expected", CASES)
def test_text_formula_protection_preserves_other_values(value, expected):
    assert safe_cell(value) == expected


def test_app_csv_round_trips_quotes_newlines_unicode_and_missing_values():
    frame = pd.DataFrame({"title": [case[0] for case in CASES], "papers": [2] * len(CASES)})
    before = frame.copy(deep=True)
    rows = list(csv.DictReader(io.StringIO(frames.csv_text(frame))))
    assert [r["title"] for r in rows] == ["" if expected is None else str(expected) for _, expected in CASES]
    assert all(row["papers"] == "2" for row in rows)
    pd.testing.assert_frame_equal(frame, before)


def test_keyword_csv_protects_term_without_changing_counts(tmp_path):
    term = '=HYPERLINK("https://example.com", "paper")'
    kt = keywords.KeywordTrends([2025], {2025: 2}, {term: {2025: 1}})
    path = tmp_path / "keywords.csv"
    keywords.write_csv(kt, [term], path)
    with path.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["term"] == "'" + term
    assert row["total"] == "1" and row["share_2025"] == "0.5000"


def test_ranking_csv_protects_external_names_and_ids(tmp_path):
    rk = rank.Ranking("institution", [2025], {2025: 1}, {"@id": "+Lab"}, {"@id": {2025: 1}}, {"@id": 7})
    path = tmp_path / "rank.csv"
    rank.write_csv(rk, ["@id"], path)
    with path.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["institution"] == "'+Lab" and row["id"] == "'@id"
    assert row["papers"] == "1" and row["citations"] == "7"


def test_topic_csv_protects_labels_and_terms(tmp_path):
    topic = topics.Topic(0, " =topic", ["-term", "normal"])
    tt = topics.TopicTrends([2025], {2025: 1}, [topic], {0: {2025: 1}}, "openalex")
    path = tmp_path / "topics.csv"
    topics.write_csv(tt, [topic], path)
    with path.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["label"] == "' =topic" and row["terms"] == "'-term; normal"
    assert row["topic_id"] == "0" and row["papers"] == "1"


def test_compare_cli_protects_user_term_and_corpus_name(tmp_path, capsys):
    corpus = tmp_path / "@venue.jsonl"
    write_jsonl([{"title": "Chiplet design", "publication_year": 2025}] * 2, corpus)
    path = tmp_path / "compare.csv"
    assert compare.main([str(corpus), "--term", "=chiplet", "--csv", str(path)]) == 0
    with path.open(newline="") as fh:
        row = next(csv.DictReader(fh))
    assert row["conference"] == "'@venue" and row["term"] == "'=chiplet"
    assert row["papers"] == "2" and row["share"] == "1.0"
    capsys.readouterr()
