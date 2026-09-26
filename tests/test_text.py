from paper_trends.text import doc_terms, ngrams, tokenize


def test_tokenize_splits_hyphens_keeps_dots():
    assert tokenize("Cu-Cu Hybrid Bonding for 2.5D/3D Integration") == [
        "cu", "cu", "hybrid", "bonding", "for", "2.5d", "3d", "integration",
    ]
    assert tokenize("high-performance") == tokenize("high performance")


def test_ngrams_skip_stopword_edges_and_numbers():
    toks = tokenize("thermal analysis of the chiplet 2024")
    grams = set(ngrams(toks, 1, 2))
    assert "thermal analysis" in grams
    assert "chiplet" in grams
    assert "of the" not in grams
    assert "analysis of" not in grams  # ends with stopword
    assert "2024" not in grams


def test_doc_terms_are_distinct():
    terms = doc_terms("bonding bonding bonding", 1, 1)
    assert terms == {"bonding"}


def test_latex_is_stripped():
    toks = tokenize(r"pitch of 5$\mu \mathrm{m}$ and $\boldsymbol{\mu}-\mathbf{bumps}$ at 250$^{\circ}$C")
    assert "mathrm" not in toks and "mu" not in toks and "boldsymbol" not in toks
    assert "um" in toks and "bumps" in toks


def test_figure_references_are_dropped():
    toks = tokenize("as shown in Fig. 17.9.1 (top left), the latency drops; see Table 2 and bottom-right panel")
    assert "fig" not in toks and "top" not in toks and "left" not in toks and "table" not in toks
    assert "latency" in toks
