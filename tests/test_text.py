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
    assert "5um" in toks and "bumps" in toks   # the number and its unit are one token


def test_number_and_unit_are_one_token():
    assert tokenize("a 28-nm CMOS, a 28 nm CMOS and a 28nm CMOS") .count("28nm") == 3
    assert tokenize("10-bit ADC at 1.2 GHz") == ["10bit", "adc", "at", "1.2ghz"]


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
    assert roles["artificial intelligence"] == "once"         # motivation, named once
    assert roles["finite element"] == "once"                  # a method used once
    assert roles["copper process"] == "repeated"
    assert mention_role(title, abstract, "Artificial Intelligence") == "once"
    assert mention_role(title, abstract, "fine pitch") == "title"   # the title wins over the abstract
    assert mention_role(title, abstract, "solder") is None


def test_acronym_definitions_follow_schwartz_hearst():
    from paper_trends.text import acronym_definitions

    d = acronym_definitions("A redistribution layer (RDL) on a through-silicon via (TSV); coefficient of thermal expansion (CTE); see Fig. 2 (a); 85 °C (RH).")
    assert d["rdl"] == ("RDL", ["redistribution", "layer"])
    assert d["tsv"] == ("TSV", ["through", "silicon", "via"])
    assert d["cte"] == ("CTE", ["coefficient", "of", "thermal", "expansion"])
    assert "a" not in d and "rh" not in d
    assert acronym_definitions("chip on wafer on substrate (CoWoS)")["cowos"][0] == "CoWoS"


def test_acronyms_expand_or_contract_consistently():
    from paper_trends.text import Acronyms, acronym_definitions, mention_role, term_mentions, tokenize

    abstract = ("We study through-silicon via (TSV) reliability. The TSVs crack. TSV depth matters. "
                "A redistribution layer (RDL) is added; the RDL is thin. Fan-out (FO) packages use it.")
    am = Acronyms(acronym_definitions(abstract), n_max=3)
    assert am.expand["rdl"] == ["redistribution", "layer"]       # a usable phrase: the acronym expands
    assert am.expand["fo"] == ["fan", "out"]                      # short: kept although "out" is a stopword
    assert "tsv" in am.short                                      # "through … via" cannot be a phrase: the long form contracts
    toks = am.apply(tokenize(abstract))
    assert toks.count("tsv") == 3 and "silicon" not in toks       # defining "(TSV)" dropped, plural folded
    assert toks.count("redistribution") == 2 and "rdl" not in toks
    roles = term_mentions("TSV interposer", abstract, 1, 2)
    assert roles["tsv"] == "title" and roles["redistribution layer"] == "repeated"
    assert mention_role("x", abstract, "through silicon via") == "repeated"   # queries are normalised the same way
    assert mention_role("x", abstract, "RDL") == "repeated"


def test_loss_is_not_a_plural_of_los():
    from paper_trends.text import Acronyms, paper_tokens

    definitions = {"los": ("LoS", ["line", "of", "sight"]),
                   "rdl": ("RDL", ["redistribution", "layer"])}
    for n_max in (1, 3):  # protect both contracted and expanded acronym paths
        am = Acronyms(definitions, n_max=n_max)
        title, abstract = paper_tokens("A loss function", "LoS links. RDLs connect chips.", am, n_max=n_max)
        assert title == ["a", "loss", "function"]
        assert "los" in abstract if n_max == 1 else abstract[:3] == ["line", "of", "sight"]
        assert "rdl" in abstract if n_max == 1 else "redistribution" in abstract
        assert am.apply(tokenize("line of sight loss"))[-1] == "loss"
        assert am.apply(tokenize("line of sight (LoS)")) == (
            ["los"] if n_max == 1 else ["line", "of", "sight"])
        title, _ = paper_tokens("LoSs incur loss. Loss and LOSS functions.", None, am, n_max=n_max)
        assert title.count("loss") == 3
        assert title[0] == ("los" if n_max == 1 else "line")

    from paper_trends.text import term_mentions
    roles = term_mentions("Emergency infrastructure",
                          "Movable base stations (MBS) connect devices. Multiple MBSs process data.", 2, 3)
    assert roles["base stations"] == "repeated"


def test_extension_pairs_tell_fragments_from_phrases():
    from paper_trends.text import extension_pairs, tokenize

    toks = tokenize("wafer level packaging and panel level packaging. hybrid bonding is used, with hybrid bonding process too")
    pairs = list(extension_pairs(toks, {"level packaging", "hybrid bonding"}, 2, 2))
    lp = [(l, r) for t, l, r in pairs if t == "level packaging"]
    assert lp == [("wafer level packaging", None), ("panel level packaging", "level packaging hybrid")]   # "and" cannot extend; punctuation is invisible
    hb = [(l, r) for t, l, r in pairs if t == "hybrid bonding"]
    assert hb == [("packaging hybrid bonding", None), (None, "hybrid bonding process")]
