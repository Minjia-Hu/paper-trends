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
    developed discussed measured fabricated applied enabling extensive extensively
    insight insights leverage leverages leveraging leveraged
    available publicly code codes github https http www url urls com org page pages
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


_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b\S+\.(?:com|org|io|net|edu)(?:/\S*)?", re.I)


# A number and its unit become one token, so "28 nm", "28-nm" and "28nm" are the same word.
_UNITS = frozenset("nm um mm cm m ghz mhz khz hz db dbm mw kw w ma mv v ms ns ps fs gb mb kb gbps mbps bit bits".split())


def tokenize(text: str | None) -> list[str]:
    """Lower-case word tokens; hyphens split, internal dots kept (e.g. '2.5d'), a number
    joined to the unit that follows it ('28nm')."""
    if not text:
        return []
    if "\\" in text or "$" in text:
        text = clean_latex(text)
    text = _URL_RE.sub(" ", text)
    text = _FIG_REF_RE.sub(" ", text)
    toks = _TOKEN_RE.findall(text.lower().translate(_DASHES))
    out: list[str] = []
    for tok in toks:
        if out and tok in _UNITS and _is_number(out[-1]):
            out[-1] += tok
        else:
            out.append(tok)
    return out


def _gram_ok(gram: list[str], stopwords: frozenset[str]) -> bool:
    """Stopwords cannot start or end an n-gram; one-character and all-numeric grams are out."""
    if gram[0] in stopwords or gram[-1] in stopwords:
        return False
    if any(len(t) < 2 for t in gram) or all(_is_number(t) for t in gram):
        return False
    return True


def ngrams(tokens: list[str], n_min: int, n_max: int, stopwords: frozenset[str] = STOPWORDS) -> Iterator[str]:
    """Yield n-grams (n_min..n_max). Stopwords are dropped as unigrams and cannot start
    or end a longer n-gram; purely numeric terms are dropped."""
    for n in range(n_min, n_max + 1):
        for i in range(len(tokens) - n + 1):
            gram = tokens[i : i + n]
            if _gram_ok(gram, stopwords):
                yield " ".join(gram)


# ---- acronyms --------------------------------------------------------------------------
# "redistribution layer (RDL)" defines RDL; later "RDL"/"RDLs" are the same phrase. Without
# this the tokens "layer rdl" form a phrase of their own and the acronym mentions do not
# count as repeats. The long form is found with the Schwartz-Hearst rule (2003): match the
# acronym's letters right-to-left in the words before the bracket, the first letter at the
# start of a word. Each acronym is then normalised one way for the whole paper (or corpus):
#   - expand   "rdl" -> "redistribution layer" when the long form is itself a usable phrase
#   - contract "through silicon via" -> "tsv" when it is not (starts or ends with a stopword:
#     "through", "via"; or longer than the n-gram limit: "fan out wafer level packaging")
_ACRONYM_RE = re.compile(r"\(([A-Za-z][A-Za-z0-9\-]{1,7})\)")
_ACRONYM_MAX_WORDS = 2  # the long form may have this many words beyond the acronym's letters


def acronym_definitions(text: str | None, stopwords: frozenset[str] = STOPWORDS) -> dict[str, tuple[str, list[str]]]:
    """Acronyms defined in `text` as "long form (ACR)": lower-cased acronym ->
    (acronym as written, long-form tokens)."""
    defs: dict[str, tuple[str, list[str]]] = {}
    if not text or "(" not in text:
        return defs
    for m in _ACRONYM_RE.finditer(text):
        raw = m.group(1).replace("-", "")
        acr = raw.lower()
        if len(acr) < 2 or not any(c.isalpha() for c in acr) or acr in stopwords or _is_number(acr):
            continue
        before = tokenize(text[: m.start()])
        words = before[-(len(acr) + _ACRONYM_MAX_WORDS):]
        long_form = _match_long_form(acr, words)
        if long_form and long_form != [acr] and sum(len(w) for w in long_form) > len(acr):
            defs[acr] = (raw, long_form)
    return defs


class Acronyms:
    """How to normalise acronyms in a token stream (see the note above)."""

    def __init__(self, defs: dict[str, tuple[str, list[str]]], n_max: int = 3, stopwords: frozenset[str] = STOPWORDS):
        self.defs = defs
        self.expand: dict[str, list[str]] = {}
        self.contract: dict[str, list[tuple[list[str], str]]] = {}  # first token -> [(long form, acronym)]
        self.surface: dict[str, str] = {}  # lower-cased acronym -> as written ("CoWoS")
        self.short: set[str] = set()  # acronyms the long form is contracted to
        for acr, (raw, long_form) in defs.items():
            self.surface[acr] = raw
            # a short long form is kept even when a stopword sits at its edge ("fan out"): it
            # still forms phrases with a neighbour ("fan out packaging"); "through silicon via"
            # (3 tokens, both edges stopwords) cannot and becomes "tsv"
            if len(long_form) < n_max or (len(long_form) == n_max and _gram_ok(long_form, stopwords)):
                self.expand[acr] = long_form
            else:
                self.contract.setdefault(long_form[0], []).append((long_form, acr))
                self.short.add(acr)
        for runs in self.contract.values():
            runs.sort(key=lambda r: -len(r[0]))  # longest long form first

    def __bool__(self) -> bool:
        return bool(self.expand or self.contract)

    def apply(self, tokens: list[str]) -> list[str]:
        """Expand or contract acronyms; the defining occurrence right after the long form is
        dropped (it would otherwise double the phrase). Plurals ("TSVs") count."""
        if not self or not tokens:
            return tokens
        out: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            for long_form, acr in self.contract.get(tok, ()):
                if tokens[i : i + len(long_form)] == long_form:
                    out.append(acr)
                    i += len(long_form)
                    if i < len(tokens) and tokens[i].rstrip("s") == acr:
                        i += 1  # the "(TSV)" right after the long form
                    break
            else:
                key = tok if tok in self.expand else (tok[:-1] if tok.endswith("s") and tok[:-1] in self.expand else None)
                if key is not None:
                    if out[-len(self.expand[key]):] != self.expand[key]:  # "redistribution layer (rdl)" -> keep once
                        out.extend(self.expand[key])
                elif tok.endswith("s") and tok[:-1] in self.short:
                    out.append(tok[:-1])  # "tsvs" -> "tsv"
                else:
                    out.append(tok)
                i += 1
        return out


def _match_long_form(acr: str, words: list[str]) -> list[str] | None:
    """Schwartz-Hearst: walk the acronym backwards through the words, each letter matched to
    an earlier character; the first letter must open a word. Returns the words used."""
    text = " ".join(words)
    a, t = len(acr) - 1, len(text) - 1
    while a >= 0:
        c = acr[a]
        if a == 0:  # the first letter must start a word
            while t >= 0 and not (text[t] == c and (t == 0 or text[t - 1] == " ")):
                t -= 1
        else:
            while t >= 0 and text[t] != c:
                t -= 1
        if t < 0:
            return None
        a -= 1
        t -= 1
    start = text[: t + 1].count(" ")  # word index where the match begins
    return words[start:]


# ---- what role does a phrase play in a paper? ------------------------------------------
# A phrase in the title, or used more than once, is what the paper is *about*; a single
# mention is not. Checked against titles on ECTC 2016-2025 (roles from the abstract alone,
# then "is it also in the title?"): repeated 32 %, once in the opening 21 %, once later
# 7 % — single mentions late in the abstract are mostly methods and test conditions
# ("finite element", "thermal cycling"), single mentions early are mostly motivation
# ("with the rise of artificial intelligence").
TOPICAL_ROLES = frozenset({"title", "repeated"})


def _gram_positions(tokens: list[str], n_min: int, n_max: int, stopwords: frozenset[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for n in range(n_min, n_max + 1):
        for i in range(len(tokens) - n + 1):
            if _gram_ok(tokens[i : i + n], stopwords):
                out.setdefault(" ".join(tokens[i : i + n]), []).append(i)
    return out


def extension_pairs(tokens: list[str], terms: set[str], n_min: int, n_max: int,
                    stopwords: frozenset[str] = STOPWORDS) -> Iterator[tuple[str, str | None, str | None]]:
    """For every occurrence of a term in `terms`: (term, phrase one token longer to the
    left or None, one token longer to the right or None). Which longer phrases a term lives
    inside tells fragments ("level packaging", always inside "wafer level packaging") from
    phrases in their own right ("fine pitch", followed by anything)."""
    for n in range(n_min, n_max + 1):
        for i in range(len(tokens) - n + 1):
            gram = tokens[i : i + n]
            key = " ".join(gram)
            if key not in terms:
                continue
            left = " ".join(tokens[i - 1 : i + n]) if i > 0 and _gram_ok(tokens[i - 1 : i + n], stopwords) else None
            right = " ".join(tokens[i : i + n + 1]) if i + n < len(tokens) and _gram_ok(tokens[i : i + n + 1], stopwords) else None
            yield key, left, right


def paper_acronyms(title: str | None, abstract: str | None, acronyms: Acronyms | None = None,
                   stopwords: frozenset[str] = STOPWORDS, n_max: int = 3) -> Acronyms | None:
    """The corpus-wide `acronyms` (see keywords.corpus_acronyms) plus, overriding them, the
    ones this paper defines itself."""
    own = {**acronym_definitions(title, stopwords), **acronym_definitions(abstract, stopwords)}
    if not own:
        return acronyms
    return Acronyms({**(acronyms.defs if acronyms else {}), **own}, n_max, stopwords)


def paper_tokens(title: str | None, abstract: str | None, acronyms: Acronyms | None = None,
                 stopwords: frozenset[str] = STOPWORDS, n_max: int = 3) -> tuple[list[str], list[str]]:
    """Title and abstract tokens with acronyms normalised."""
    am = paper_acronyms(title, abstract, acronyms, stopwords, n_max)
    if not am:
        return tokenize(title), tokenize(abstract)
    return am.apply(tokenize(title)), am.apply(tokenize(abstract))


def phrase_roles(t_toks: list[str], a_toks: list[str], n_min: int = 1, n_max: int = 3,
                 stopwords: frozenset[str] = STOPWORDS) -> dict[str, str]:
    """Every n-gram of a paper (tokens from `paper_tokens`) with its role: "title",
    "repeated" or "once"."""
    roles = {g: "title" for g in _gram_positions(t_toks, n_min, n_max, stopwords)}
    for g, pos in _gram_positions(a_toks, n_min, n_max, stopwords).items():
        if g not in roles:
            roles[g] = "repeated" if len(pos) >= 2 else "once"
    return roles


def term_mentions(title: str | None, abstract: str | None, n_min: int = 1, n_max: int = 3,
                  stopwords: frozenset[str] = STOPWORDS, acronyms: Acronyms | None = None) -> dict[str, str]:
    """Every n-gram of a paper with its role: "title", "repeated" or "once"."""
    return phrase_roles(*paper_tokens(title, abstract, acronyms, stopwords, n_max), n_min, n_max, stopwords)


def mention_role(title: str | None, abstract: str | None, term: str, acronyms: Acronyms | None = None) -> str | None:
    """Role of one phrase in one paper, or None when it does not occur."""
    am = paper_acronyms(title, abstract, acronyms)
    t_toks, a_toks = (am.apply(tokenize(title)), am.apply(tokenize(abstract))) if am else (tokenize(title), tokenize(abstract))
    want = am.apply(tokenize(term)) if am else tokenize(term)
    n = len(want)
    if not n:
        return None

    def positions(tokens: list[str]) -> list[int]:
        return [i for i in range(len(tokens) - n + 1) if tokens[i : i + n] == want]

    if positions(t_toks):
        return "title"
    pos = positions(a_toks)
    if not pos:
        return None
    return "repeated" if len(pos) >= 2 else "once"


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
