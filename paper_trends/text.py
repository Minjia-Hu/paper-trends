"""Tokenization and n-gram extraction for titles/abstracts."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

# Generic English + academic-boilerplate stopwords. Domain-specific terms are NOT listed
# here; users can add their own with --stopwords.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but nor so yet of in on at to for from by with without within into onto
    over under between among through during before after above below up down out off than
    as is are was were be been being am do does did done have has had having can could may
    might must shall should will would this that these those it its itself they them their
    there here where when which who whom whose what why how all any both each few more most
    other some such no not only own same too very s t just also than then once about against
    because while if via per i we you he she our your his her us me my
    paper papers study studies work works result results approach approaches method methods
    proposed propose present presents presented presenting show shows shown showed
    demonstrate demonstrates demonstrated investigate investigated investigation
    based using use used uses utilizing utilized novel new different various several
    however therefore thus moreover furthermore respectively well due able
    achieve achieved achieves obtained obtain compared comparison order
    developed discussed measured fabricated applied enabling
    um mm nm cm ghz mhz khz hz db mw kw ma mv wt vol sec min hr
    first two three one
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9\.]*[a-z0-9]|[a-z0-9]")

# IEEE abstracts in OpenAlex often contain inline LaTeX, e.g. "5$\mu \mathrm{m}$".
_LATEX_UM = re.compile(r"\\mu\s*\\mathrm\{m\}|\\mu\s*m\b")
_LATEX_WRAPPER = re.compile(r"\\(?:mathrm|mathbf|mathit|text|textbf|boldsymbol|left|right)\b")
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+")
# Hyphens become spaces so "high-performance" and "high performance" count as one phrase.
_DASHES = str.maketrans({c: " " for c in "-\u2010\u2011\u2012\u2013\u2014"})


def clean_latex(text: str) -> str:
    text = _LATEX_UM.sub(" um ", text)
    text = _LATEX_WRAPPER.sub(" ", text)  # keep the wrapped content
    text = _LATEX_CMD.sub(" ", text)  # drop symbols such as \times, \circ, \Omega
    for ch in "${}^_":
        text = text.replace(ch, " ")
    return text


# Figure/table references and panel positions ("Fig. 17.9.1 (top left)") are caption noise.
_FIG_REF_RE = re.compile(
    r"\b(?:fig|figs|figure|figures|table|tables|eq|eqs|equation|equations|ref|refs)\.?\s*[\d\.\-]*[a-z]?\b|"
    r"\(?\b(?:top|bottom|upper|lower|middle)[- ](?:left|right|center|centre|middle|row|panel)\b\)?",
    re.I,
)


def tokenize(text: str | None) -> list[str]:
    """Lower-case word tokens; hyphens split, internal dots kept (e.g. '2.5d')."""
    if not text:
        return []
    if "\\" in text or "$" in text:
        text = clean_latex(text)
    text = _FIG_REF_RE.sub(" ", text)
    return _TOKEN_RE.findall(text.lower().translate(_DASHES))


def ngrams(tokens: list[str], n_min: int, n_max: int, stopwords: frozenset[str] = STOPWORDS) -> Iterator[str]:
    """Yield n-grams (n_min..n_max). Stopwords are dropped as unigrams and cannot start
    or end a longer n-gram; purely numeric terms are dropped."""
    for n in range(n_min, n_max + 1):
        for i in range(len(tokens) - n + 1):
            gram = tokens[i : i + n]
            if gram[0] in stopwords or gram[-1] in stopwords:
                continue
            if any(len(t) < 2 for t in gram):
                continue
            if all(_is_number(t) for t in gram):
                continue
            yield " ".join(gram)


def _is_number(tok: str) -> bool:
    return bool(re.fullmatch(r"[0-9][0-9\.\-]*", tok))


def doc_terms(text: str | None, n_min: int = 1, n_max: int = 3, stopwords: frozenset[str] = STOPWORDS) -> set[str]:
    """Distinct n-grams of one document (for document-frequency counting)."""
    return set(ngrams(tokenize(text), n_min, n_max, stopwords))


def load_stopwords(extra: Iterable[str] | None = None) -> frozenset[str]:
    words = set(STOPWORDS)
    for w in extra or []:
        w = w.strip().lower()
        if w and not w.startswith("#"):
            words.add(w)
    return frozenset(words)
