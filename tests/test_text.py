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


def test_urls_are_dropped():
    toks = tokenize("Code is available at https://github.com/foo/bar and project page www.foo.io/page. Diffusion models.")
    assert "github" not in toks and "https" not in toks and "foo" not in toks and "io" not in toks
    assert "diffusion" in toks and "models" in toks


def test_mention_roles():
    from paper_trends.text import mention_role, term_mentions

    title = "Hybrid bonding at fine pitch"
    abstract = ("With the growth of artificial intelligence, packaging density must rise. "
                "We present a copper process. Finite element analysis predicts warpage. "
                "The copper process reaches a fine pitch. Yield is reported for the copper process.")
    roles = term_mentions(title, abstract, 1, 2)
    assert roles["hybrid bonding"] == "title"
    assert roles["artificial intelligence"] == "opening"      # once, in the first sentence
    assert roles["finite element"] == "body"                  # once, beyond the opening
    assert roles["copper process"] == "repeated"
    assert mention_role(title, abstract, "Artificial Intelligence") == "opening"
    assert mention_role(title, abstract, "fine pitch") == "title"   # the title wins over the abstract
    assert mention_role(title, abstract, "solder") is None


def test_one_sentence_abstract_is_not_all_opening():
    from paper_trends.text import term_mentions

    roles = term_mentions("A study", "thermal resistance heat sink cooling junction temperature heat flux variant three for packages", 1, 2)
    assert roles["thermal resistance"] == "opening"     # first fifth of the text
    assert roles["junction temperature"] == "body"      # the single sentence does not swallow everything
