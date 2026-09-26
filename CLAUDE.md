# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**paper-trends** — give it any academic conference name and it pulls the conference's
historical paper metadata from OpenAlex, then produces keyword trends, topic evolution,
and institution/author rankings. Target users are researchers in any field, not only
semiconductor packaging.

- First showcase: **ECTC (Electronic Components and Technology Conference) 2016–2026**.
- The README must also demonstrate at least one other venue (ISSCC or IEDM) to prove the
  tool is general-purpose, not ECTC-specific.
- Goal of the repo: a useful open-source tool that people star. Keep the CLI and README
  polished; prefer features that generalize across conferences.

## Hard rules

- **Only public data and public methods.** OpenAlex is the sole data source (free, CC0).
  Never pull from or cite non-public sources.
- Every OpenAlex request carries `mailto=`; the value comes from the `OPENALEX_MAILTO`
  env var (loaded from `.env` via python-dotenv). Never hard-code an address.
- `OPENALEX_API_KEY` (optional, sent as `Authorization: Bearer`) is effectively required:
  since 2026 OpenAlex meters anonymous requests against a small daily budget shared by
  every user behind the same IP address (`HTTP 429`, `Retry-After` in hours, "Insufficient
  budget"). The client fails fast on that instead of retrying; get a free key at
  https://help.openalex.org/api/authentication/. Never log or display the key or mailto
  (`openalex._redact` strips mailto from error text).
- `.env` and `data/` are git-ignored and must stay that way.
- **No personal information of the author** (email, employer, etc.) in `CLAUDE.md`,
  `README.md`, or code. Use placeholders like `you@example.com` in docs.

## Commands

Dependencies are managed with `uv` (Python ≥ 3.12; `.python-version` pins 3.12).

```bash
uv sync                                   # create .venv and install deps

# Fetch a conference (writes data/<name>.jsonl and prints a per-year coverage table)
uv run python -m paper_trends fetch "Electronic Components and Technology Conference" \
    --doi-prefix 10.1109/ectc --years 2016-2026 --name ectc

# Analyses over a fetched corpus (exclude years with missing abstracts)
uv run python -m paper_trends keywords data/ectc.jsonl --years 2016-2025 --ngram 2-3 --csv data/ectc_keywords.csv
uv run python -m paper_trends topics   data/ectc.jsonl --years 2016-2025 --n-topics 10 --csv data/ectc_topics.csv
uv run python -m paper_trends rank     data/ectc.jsonl --years 2016-2025 --by institution   # or author / country
uv run python -m paper_trends compare  data/ectc.jsonl data/iedm.jsonl --years 2016-2025 --term chiplet

uv run streamlit run app.py               # interactive UI (same analysis functions)
uv run python -m paper_trends report data/ectc.jsonl --name "..." --years 2016-2025 --out site   # static report pages
uv run python -m paper_trends fetch --help
uv run pytest -q                          # tests live in tests/, pythonpath="." set in pyproject
uv run pytest -q tests/test_keywords.py::test_rising_and_falling   # single test
```

The project deliberately sets `[tool.uv] package = false` and uses a flat layout
(`paper_trends/` at repo root), so it is run in place with `python -m` rather than
installed into the venv. Reason: on this machine `.pth` files in `.venv` get the macOS
"hidden" flag, and Python ≥ 3.12.12 silently skips hidden `.pth` files, which breaks
editable installs (`ModuleNotFoundError: paper_trends`). Do not switch back to a
`src/` layout with an editable install without solving that.

No linter is configured yet.

## Architecture

The package is a **library first, CLI second**: every analysis is a plain function over
the list of records returned by `store.read_jsonl`, and each module's `main()` is a thin
argparse wrapper. A Streamlit front end is planned on top of the same functions, so keep
analysis code free of printing/argparse.

```
paper_trends/
  cli.py       # `paper-trends <command>` dispatcher; add new subcommands to COMMANDS
  openalex.py  # API client: polite pool, cursor paging, retries, abstract reconstruction
  fetch.py     # conference -> works resolution, coverage table
  store.py     # JSONL read/write, year filtering (shared by all commands)
  text.py      # tokenizer (strips inline LaTeX from IEEE abstracts), n-grams, stopwords
  keywords.py  # KeywordTrends: per-year document frequency, rising/falling terms
  topics.py    # TopicTrends: NMF on TF-IDF (default) or OpenAlex topic labels, per-year share
  rank.py      # Ranking: institutions / authors / countries, papers + citations per year
  compare.py   # same terms across several corpora; "shared risers"
  frames.py    # analysis results -> tidy pandas DataFrames (charts/tables)
  viz.py       # chart palette (CVD-validated, fixed slot order) + Altair theme
  report/      # static report site: build.py (numbers + sentences), charts.py (Vega-Lite specs),
               #   render.py (Jinja2 -> site/), templates/, static/report.css
app.py         # Streamlit UI: sidebar presets/fetch, tabs Overview/Keywords/Topics/Rankings/Compare/Data
.github/workflows/ci.yml  # pytest on push/PR (tests are fully offline: OpenAlex is mocked)
.streamlit/config.toml  # theme; secrets.toml (git-ignored) may hold OPENALEX_MAILTO when hosted
data/<name>.jsonl   # one work per line (git-ignored)
docs/               # README screenshots
tests/              # pytest, incl. a streamlit.testing AppTest smoke test of app.py
```

**Streamlit app = shell around the report, no sidebar.** Layout top to bottom: masthead
(brand = home, grouped conference links; Streamlit-rendered HTML because the report iframe
is sandboxed without top navigation), a search row (`st.text_input` for any OpenAlex
conference + an **Options** popover holding DOI prefix, extra stopwords and refresh), then
for a selected conference a controls row of plain text links (period, Report/Explore,
Options — all `?param=` links, no widgets: Streamlit widgets cannot be restyled enough to
match the page) and either
the embedded report (`st.iframe(render_page(..., embedded=True), height="content")`) or the
Explore view — the interactive side (papers behind a term, comparisons, tables) restyled to
the report's voice: HTML header (`.pt-head`), sections as `?section=` links instead of tabs
(only the chosen section is computed), `h2()`/`note()` helpers for headings and captions,
and the Altair theme in `viz.py` built from the report tokens (grey bars with the top three
in red, dashed grid, IBM Plex Sans). Selection lives in the URL: `?conference=<preset slug>` or
`?q=<custom name>&prefix=...`, plus `period=10|5|all|custom`, `view=explore`, `options=1`;
nothing selected = the native home page (`home_page()`). The only widgets are the search
box, the custom-period slider and the Options form (stopwords persist in
`st.session_state["extra_stop_saved"]` because the form is not always rendered).
Do not call `st.rerun()` right after changing `st.query_params` — the URL update is lost;
set the params and continue the run. Hide Streamlit chrome via `stToolbarActions`,
`stMainMenu`, `stAppDeployButton` and make the header `pointer-events: none`, otherwise
the transparent toolbar swallows clicks on the masthead. `components.v1.html` is
deprecated and did not auto-size; `st.iframe` measures srcdoc content itself.

**Streamlit app conventions**: all heavy work goes through `st.cache_data` keyed on
(corpus path, mtime, params); fetches are serialized with a `threading.Lock` held in
`st.cache_resource`. Charts follow the dataviz rules: categorical colours from
`viz.CATEGORICAL` in fixed order, at most 8 series then fold into "Other", one axis per
chart, a table next to every chart. Stacked areas need a fixed `order` across years
(sorting by value per year breaks the areas). To eyeball the UI, run the app headless on
a spare port and screenshot tabs with Playwright (system `python3` has it with Chromium).

**Resolution strategy in `fetch.py`** — this is the non-obvious part:

1. Search OpenAlex `sources` by display name. Prefer sources whose *core name* equals
   the query — `_core_name` strips year/ordinal/publisher prefixes ("2022 IEEE/CVF",
   "Proceedings of the 38th") and trailing "(CVPR)"/"Digest of Technical Papers" — so
   CVPR does not absorb "CVPR Workshops" and ICML does not absorb "Machine Learning and
   Applications". Only if nothing matches exactly fall back to substring containment.
2. Optionally add `doi_starts_with:<prefix>` filters (`--doi-prefix`, repeatable). OpenAlex
   matches these against lower-cased DOIs, so prefixes are lower-cased (`10.1109/ectc`).
   Each hit must then pass `doi_has_prefix`: prefix + optional conference number + "."
   — otherwise `10.1109/isca` returns 5k ISCAS papers and `10.1109/imw` returns IMWS-AMP.
3. Union the results, de-duplicated by work id.

`resolve_venue` (CLI `resolve`, app search box) turns an acronym or name into
{name, doi_prefixes, source_ids, slug, n_papers, ambiguous}: acronyms are probed as
`10.1109/<acr>` and `10.23919/<acr>` (≥ 50 papers 2016–2025) and the name is the most
common decoration-stripped source name in a 60-paper sample; names go through
`resolve_sources` with a prefix inferred from sampled DOIs (≥ 60 % agreement). Non-IEEE
acronyms (NeurIPS) resolve to nothing — say so instead of guessing. The app maps typed
preset acronyms/slugs straight to `?conference=`.

Commas cannot appear in an OpenAlex filter value (they separate filters), so
`search_sources` replaces them with spaces (EuroSimE's full name has one).

**Presets** live in `app.py:PRESETS` (packaging: ECTC, EPTC, ICEPT, ITherm, IRPS, EuroSimE;
devices/circuits: IEDM, ISSCC, VLSI Symposium, IMW; other fields: CVPR, Interspeech —
the generality showcase), each with its DOI prefix list. VLSI
Symposium needs ten prefixes because IEEE (10.1109) and JSAP (10.23919) alternate as
publisher and the acronym changed (vlsit/vlsic → vlsitechnology/vlsicircuits →
vlsitechnologyandcir). Venues that alternate IEEE/ACM DOIs by year (DAC, ICCAD) or whose
prefix is a substring of a bigger venue's (ISCA/ISCAS) were deliberately left out.

The DOI fallback exists because **most ECTC years have no OpenAlex source at all** —
only 2022 has a source record (S4363608088); other years carry just a
`raw_source_name` on the work, which OpenAlex cannot filter on. Other IEEE conferences
(ISSCC, IEDM) do have sources, so the name search alone may suffice for them. Always
check the printed `[sources]` list and per-year counts to confirm nothing irrelevant
leaked in.

**Record schema** (`to_record`): `id, doi, title, publication_year, abstract` (plain text
rebuilt from `abstract_inverted_index`), `authorships` (slimmed: author id/name/position,
institutions id/name/country plus `root_id`/`root_name`/`root_country` = the top of
OpenAlex's lineage, resolved after the fetch by `resolve_roots`; raw affiliation
strings), `cited_by_count`, `type`,
`source_id`, `source_name` (falls back to `raw_source_name`), `topics` (OpenAlex topic
labels with subfield/field), `oa_keywords`.

`fetch` drops proceedings front matter via `is_front_matter`: OpenAlex's `is_paratext`
flag catches only a fraction; the rest is a title regex (title pages, committees, indexes,
"Session N overview", timetables, tutorials, ISSCC-style "F6:"/"EE3:" forum codes) plus
an abstract rule for invited talks "not made available for publication". ISSCC loses
~800 such items (a quarter of its DOIs), ECTC ~100. Extend the regex if junk topics like
"title page / copyright" or "session overview" reappear in `topics`.

**Shared analysis conventions** (keywords, topics, rank all follow them):
- Everything is a *share of that year's papers*, so years of different size compare.
- "Rising/falling" = pooled share in the late half of the year range minus the early half.
- Full counting: a paper counts once for each distinct entity/term it has.

**Topics (`topics.py`)**: default is NMF on TF-IDF (unigrams+bigrams, `min_df=5`,
`max_df=0.4`, `nndsvda` init, fixed seed) with each paper assigned to its dominant topic;
labels come from `make_label`, which prefers phrases over their constituent words.
`--method openalex` uses OpenAlex's own labels instead — too coarse for ECTC (half the
papers land in "3D IC and TSV technologies") but fine for broad venues.

**Keyword analysis (`keywords.py`)** counts *document frequency* (papers mentioning a term
at least once per year) and reports it as a share of that year's papers, so years of
different size are comparable. Rising/falling terms compare pooled share in the early vs.
late half of the year range. Two filters shape the output and are easy to misread as bugs:

- `STOPWORDS` in `text.py` is generic English + academic boilerplate + unit tokens only.
  Do not add domain words there; users pass `--stopwords file` for that.
- `collapse_subphrases` hides a term when a longer term containing it accounts for ≥ 80 %
  of its occurrences (`performance computing` → `high-performance computing`). Disable
  with `--keep-subphrases`.

Unigram rankings are dominated by generic words (process, performance, thermal); phrase
level views (`--ngram 2-3`) and the rising/falling lists are where the signal is.

**Coverage differs a lot by venue.** IEEE venues with acronym DOIs (ECTC, ISSCC, CVPR,
ICRA…) are complete. Interspeech (ISCA, `10.21437/interspeech`) has every paper but
abstracts for only ~40 % (2023+ ~20 %): use `--text title` there. Venues without DOIs
(NeurIPS, ICML, CHI) are patchy in OpenAlex — NeurIPS' source covers 2016–2021 only —
so they are not good showcases; say so rather than fetching them.

**Report design (the public face; Streamlit is the local tool).** Editorial data-journalism
style after Our World in Data / The Economist, agreed with Minjia on 2026-09-26: warm
paper background `#FCFBF8`, ink `#1B1B1B`, one accent red `#E3120B` for the focus series
and key numbers, blue `#1F4E79` for "fading", grey `#B8B5AE` for context; Newsreader for
headings, IBM Plex Sans (tabular numerals) for everything else. Rules: every chart gets a
conclusion sentence, direct end labels instead of legends, one focus series, gridlines
faint and dashed, a "Source:" line, tables only inside `<details>`. Vega-Lite specs are
built in `charts.py` with a shared `CONFIG`; the streamgraph stacks by `rank` ascending
so the right-edge labels (computed in Python) line up with the bands. Preview with
`python3 -m http.server --directory site` + Playwright screenshots; the CDN scripts need
network. `site/` is git-ignored. `build_report` switches to title-only phrase counting when
abstract coverage is under 60 % (Interspeech), restores corpus hyphenation for display
(`restore_hyphens`: "co-packaged optics"), and drops singular/plural twins from the lists.
`render.FULL`/`SHORT`/`GROUPS` hold the preset names and the masthead grouping.

## Known data caveats (ECTC run, 2026-09)

- ~4.1k works for 2016–2026, ~97–98 % abstract coverage per year, **except 2026 (~3 %)**:
  OpenAlex has not yet indexed most 2026 abstracts. Analyses that depend on abstracts
  should treat the latest year as incomplete or exclude it.
- OpenAlex occasionally returns truncated/non-JSON bodies or drops TLS connections
  (`SSL: UNEXPECTED_EOF_WHILE_READING`, more often through the local proxy on this
  machine, 127.0.0.1:1082, which `requests` picks up from macOS system settings); the
  client retries both with backoff.
- OpenAlex institution disambiguation is imperfect: the same lab can appear under two ids
  ("Institute of Microelectronics" is both A*STAR IME and CAS IME) and a few affiliations
  are mis-resolved. `rank --roll-up` (the app's default for institutions) credits the
  lineage root instead, which merges parents and children (A*STAR + IME, CAS + its
  institutes, Samsung's subsidiaries); corpora fetched before lineage was stored fall back
  to the affiliated institution. Roll-up can over-merge where OpenAlex's root is an
  umbrella body: ETH Zurich and EPFL both roll into "Board of the Swiss Federal Institutes
  of Technology". Leave that as is (it is what the data says) and let users toggle. `rank.py` uses raw affiliation strings only when OpenAlex
  resolved nothing.
- CS venues put "Code is available at https://github.com/..." in abstracts; `tokenize`
  strips URLs and the stopword list has that boilerplate (available, code, github, page).
- OpenAlex mis-resolves some affiliations to look-alike entities (CVPR: "Shanghai AI
  Laboratory" also shows up as "ShangHai JiAi Genetics & IVF Institute"). Rankings are
  indicative; do not "fix" individual names in code.
- Scale: CVPR (17k papers, 76 MB JSONL) takes ~8 s and ~0.8 GB for keywords or topics
  on the CLI; the app caches each analysis per (corpus, years, params).
- ~5 % of ECTC abstracts contain inline LaTeX (`5$\mu \mathrm{m}$`); `text.clean_latex`
  strips it. If new junk tokens (`mathrm`, `boldsymbol`, ...) show up in rankings, extend it.
