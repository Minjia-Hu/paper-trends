"""Reusable corpus analysis shared by Report and individual Explore queries."""

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from ..background import field_of
from ..keywords import KeywordTrends, compute_trends, display_form, group_families, hyphen_forms
from ..rank import Ranking, compute_ranking
from ..store import Record
from ..text import STOPWORDS
from ..topics import InsufficientTopicData, TopicTrends, compute_nmf


@dataclass
class CorpusAnalysis:
    """Completed analysis; consumers treat its records and fitted results as read-only."""
    records: list[Record]
    keywords: KeywordTrends
    topics: TopicTrends
    institutions: Ranking
    countries: Ranking
    forms: dict[str, int]
    notes: list[str] = field(default_factory=list)

    def display(self, term: str) -> str:
        surface = self.keywords.acronyms.surface if self.keywords.acronyms else {}
        return display_form(term, self.forms, surface)

    @cached_property
    def exploration_terms(self) -> list[str]:
        kt = self.keywords
        if len(kt.years) > 1:
            rising = group_families(kt.rising(32, min_total=10), 8, kt.total)
            falling = group_families(kt.falling(32, min_total=10), 8, kt.total)
            emerging = group_families(kt.emerging(30, min_total=10), 10, kt.total)
        else:
            rising = falling = emerging = []
        return list(dict.fromkeys([
            *[row[0] for row, _ in rising[:6]],
            *[row[0] for row, _ in emerging[:4]],
            *[row[0] for row, _ in falling[:4]],
            *kt.top_terms(20),
        ]))[:20]


def analysis_version() -> tuple[tuple[str, int], ...]:
    """Invalidate imported analysis code without restarting the Streamlit server."""
    package = Path(__file__).resolve().parents[1]
    files = [package / name for name in ("text.py", "keywords.py", "topics.py", "rank.py",
                                         "background.py", "coverage.py")]
    files.extend(package / "report" / name for name in ("analysis.py", "build.py", "entities.py", "explorer.py"))
    return tuple((str(path.relative_to(package)), path.stat().st_mtime_ns) for path in files)


def analyze_corpus(records: list[Record], *, slug: str, n_topics: int = 8,
                   stopwords: frozenset[str] = STOPWORDS) -> CorpusAnalysis:
    """Analyse already-selected records once, retaining tokens for cheap phrase queries.

    Calendar dates and display languages do not affect these counts. Callers cache this
    result by corpus revision, selected years and analysis settings.
    """
    records = [r for r in records if r.get("publication_year")]
    if not records:
        raise ValueError("No papers with a publication year in the selected period.")
    coverage = sum(bool(r.get("abstract")) for r in records) / len(records)
    text_mode = "title+abstract" if coverage >= 0.6 else "title"
    kt = compute_trends(records, text=text_mode, n_min=2, n_max=3,
                        stopwords=stopwords, field=field_of(slug), retain_tokens=True)
    forms = hyphen_forms(records, text=text_mode)
    notes = []
    try:
        tt = compute_nmf(records, n_topics=n_topics, stopwords=stopwords)
    except InsufficientTopicData as exc:
        tt = TopicTrends(kt.years, kt.papers_per_year, [], {}, "nmf")
        notes.append(f"Topics are unavailable: {exc}")
    surface = kt.acronyms.surface if kt.acronyms else {}
    for topic in tt.topics:
        topic.label = " / ".join(display_form(t, forms, surface) for t in topic.label.split(" / "))
        topic.terms = [display_form(t, forms, surface) for t in topic.terms]
    analysis = CorpusAnalysis(records, kt, tt, compute_ranking(records, "institution", roll_up=True),
                              compute_ranking(records, "country"), forms, notes)
    # Populate the bounded default list before serialization; individual queries reuse it.
    analysis.exploration_terms
    return analysis
