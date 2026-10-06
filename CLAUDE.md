# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**paper-trends** — give it any academic conference name and it pulls the conference's
historical paper metadata from OpenAlex, then produces keyword trends, topic evolution,
and institution/author rankings. Target users are researchers in any field, not only
semiconductor packaging.

**Positioning (decided with the maintainer on 2026-10-02): "any conference" is the
product; the presets are examples.** The semiconductor-heavy mix of presets reflects
where the maintainer works, not the tool's scope, and the UI must not suggest otherwise:
the masthead carries only the brand, the tagline (`render.TAGLINE`, "Publication trends
for any academic conference") and, on a conference page, "All conferences →"; the search
box is the primary entry; presets live on the home page grouped by domain and research
direction (never "Other fields"). Their group sizes represent verified data coverage,
not the real-world size of each research community. Keep the README's first sentence and the home page consistent
with this.

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
  validate.py  # title-agreement check of the mention roles (how the counting rule was chosen)
  openalex.py  # API client: polite pool, cursor paging, retries, abstract reconstruction
  fetch.py     # conference -> works resolution, coverage table
  store.py     # JSONL read/write, year filtering (shared by all commands)
  coverage.py  # conservative default report period; excludes current/incomplete trailing editions
  text.py      # tokenizer (strips inline LaTeX from IEEE abstracts), n-grams, stopwords
  keywords.py  # KeywordTrends: per-year counts of papers about a phrase, rising/falling/emerging
  background.py  # cross-field table of common phrases (resources/background.json) + builder
  topics.py    # TopicTrends: NMF on TF-IDF (default) or OpenAlex topic labels, per-year share
  rank.py      # Ranking: institutions / authors / countries, papers + citations per year
  compare.py   # same terms across several corpora; "shared risers"
  frames.py    # analysis results -> tidy pandas DataFrames (charts/tables)
  viz.py       # chart palette (CVD-validated, fixed slot order) + Altair theme
  report/      # static report site: build.py (numbers + sentences), charts.py (Vega-Lite specs),
               #   entities.py (linked-entity panel data), render.py (Jinja2 -> site/), templates/,
               #   static/report.css, static/entities.js (the panel, no library)
app.py         # Streamlit UI: masthead + search, Report (iframe) / Explore views, no sidebar
.github/workflows/ci.yml  # pytest on push/PR (tests are fully offline: OpenAlex is mocked)
.streamlit/config.toml  # theme; secrets.toml (git-ignored) may hold OPENALEX_MAILTO when hosted
data/<name>.jsonl   # one work per line (git-ignored)
docs/               # README screenshots
tests/              # pytest, incl. a streamlit.testing AppTest smoke test of app.py
```

**Streamlit app = shell around the report, no sidebar.** Layout top to bottom: masthead
(brand = home, tagline, "All conferences →" on a conference page; Streamlit-rendered HTML
because the report iframe is sandboxed without top navigation; the conference list is on
the home page in a grid of field groups, unfetched presets greyed with the fetch offered
when opened), a search row (`st.text_input` for any OpenAlex
conference + an **Options** popover holding DOI prefix, extra stopwords and refresh), then
for a selected conference a controls row of plain text links (period, Report/Explore,
Options — all `?param=` links, no widgets: Streamlit widgets cannot be restyled enough to
match the page) and either
the concise embedded report (`st.iframe(render_page(..., embedded=True), height="content")`)
or Explore — a task-oriented workspace with Trends & evidence, Topic analysis,
Institution analysis, Compare conferences, and Papers & export. Its field observatory is
rendered by `render_explorer_page`; the remaining tools use the report's voice: HTML header
(`.pt-head`), sections as `?section=` links instead of tabs (only the chosen section is
computed), `h2()`/`note()` helpers for headings and captions, and the Altair theme in
`viz.py` built from the report tokens (grey bars with the top three in red, dashed grid,
IBM Plex Sans). Selection lives in the URL: `?conference=<preset slug>` or
`?q=<custom name>&prefix=...`, plus `period=10|5|all|custom`, `view=explore`, `options=1`;
nothing selected = the native home page (`home_page()`). The only widgets are the search
box, the custom-period slider and the Options form (stopwords persist in
`st.session_state["extra_stop_saved"]` because the form is not always rendered).
Do not call `st.rerun()` right after changing `st.query_params` — the URL update is lost;
set the params and continue the run. Hide Streamlit chrome via `stToolbarActions`,
`stMainMenu`, `stAppDeployButton` and make the header `pointer-events: none`, otherwise
the transparent toolbar swallows clicks on the masthead. `components.v1.html` is
deprecated and did not auto-size; `st.iframe` measures srcdoc content itself.

**Widget styling**: small tables are rendered by `html_table()` (`.pt-table`, the report's
table anatomy); `st.dataframe` only for the long paper listing. Streamlit ≥ 1.6x builds
widgets with react-aria (`data-rac`, `data-tag`, `stMultiSelectTagsContainer`), not
baseweb, so CSS hooks are those attributes. `.streamlit/config.toml` sets
`primaryColor` to ink (#1B1B1B) so sliders, toggles and focus rings stay quiet; red is
reserved for our own HTML (current links, kicker, focus series). Verify styling changes
with a Playwright screenshot — many selectors silently fail to match.

**Streamlit app conventions**: all heavy work goes through `st.cache_data` keyed on
(corpus path, mtime, params); fetches are serialized with a `threading.Lock` held in
`st.cache_resource`. Charts follow the dataviz rules: categorical colours from
`viz.CATEGORICAL` in fixed order, at most 8 series then fold into "Other", one axis per
chart, a table next to every chart. Stacked areas need a fixed `order` across years
(sorting by value per year breaks the areas). To eyeball the UI, run the app headless on
a spare port and screenshot tabs with Playwright (system `python3` has it with Chromium).

**Report consistency**: app default periods and CLI reports without `--years` use
`coverage.default_period`; All/Custom or explicit CLI years override the heuristic.
Do not select years solely by abstract coverage: title-only venues still need their
historical years. Single-year reports omit time comparisons; empty periods and
`InsufficientTopicData` have explanatory UI states. Detail panels preserve the
`KeywordTrends` text mode, n-gram bounds, stopwords and counting basis, and include
every displayed trend phrase and variant even outside the frequent-term cap.
Jinja HTML templates use autoescaping and `tojson` for inline data; only local CSS/JS
assets are marked safe. `generated` is the report date, not a fetch timestamp.
`store.read_provenance` verifies `<corpus>.jsonl.meta.json` against the corpus SHA-256;
only successful fetch paths pass a timezone-aware `fetched_at` to `write_jsonl`.
Legacy/malformed/mismatched metadata must show an unknown fetch time, never infer one
from file mtime. App provenance cache keys include sidecar mtime; report cache keys
include the verified provenance and default-period span.
`coverage.period_decision` supplies both default years and exclusion reasons;
`coverage_details` supplies visible abstract limitations and a gap-inclusive coverage
table. Keep these descriptions shared between static reports and Explore. The 90%
abstract-notice threshold is descriptive, not a measure of proceedings completeness.

**Interactive exploration**: `report/explorer.py` accumulates exclusive title/repeated/once
roles during the existing `build_entities` pass; do not estimate counts from sampled
papers. It tracks up to 20 phrases over every calendar year, keeping gaps at zero
denominator (the frontend renders missing shares, not 0%). Institutional counts dedupe
co-authors and use all institutions, not just the legacy panel's top-60 set. Topic
assignments are fitted once for the full report. Only evidence examples are capped at
three per phrase/year/role. Explore opts into `explorer_full` to include every matching
paper's listing metadata and role-separated IDs; abstracts remain sampled. The full
evidence table (20 rows per page), counts and CSV use this same local selection, with no
second native keyword filter. The phrase-search form adds an explicit term to the
observatory, normalized with the corpus acronym map; rare and empty results stay explicit.
`static/explorer.js` owns the local time/rule state and stops
playback on manual edits, hidden pages and page exit. `explorer_page.html.j2` is the
standalone Streamlit iframe; the narrative report deliberately excludes the observatory.
Report links may open Explore with `term=` while preserving conference and period.
Custom ranges bind the `years` slider to query params; links must serialize both endpoints
with `get_all` and `urlencode(..., doseq=True)`, using the live slider value on reruns.
Institution rank history and topic mix are available behind a native toggle in Explore;
both respect the parent roll-up setting. No new
frontend runtime dependencies are required.

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
3. Union the results, de-duplicated by work ID and DOI. `deduplicate_dois` retains one
   record, preferring abstract/authorship availability then higher citations; never
   sum duplicate citation counts or merge DOI-less records on title alone.

`resolve_venue` (CLI `resolve`, app search box) turns an acronym or name into
{name, doi_prefixes, source_ids, slug, n_papers, ambiguous}: acronyms are probed as
`10.1109/<acr>` and `10.23919/<acr>` (≥ 50 papers 2016–2025) and the name is the most
common decoration-stripped source name in a 60-paper sample; names go through
`resolve_sources` with a prefix inferred from sampled DOIs (≥ 60 % agreement and
accepted by `doi_has_prefix`). A short query that failed prefix probing may only match
an exact source core name, such as Interspeech; do not fall back to substring matches
like CHI → TAP CHI SINH HOC or ACL → Findings. Failure means the venue could not be
identified reliably, not that OpenAlex has none of its papers. The app maps typed
preset acronyms/slugs straight to `?conference=`.

Before adding presets, consult `docs/venue-audit-2026-10-05.md` and its JSON snapshot.
`scripts/audit_venues.py` repeats the cached coverage probes. DOI boundary checks do
not disambiguate conferences sharing the same acronym (ICC, ICSE, ECCE); GLOBECOM
needs both `glocom` and `globecom`. Grouped API counts are not clean corpus totals.

Commas cannot appear in an OpenAlex filter value (they separate filters), so
`search_sources` replaces them with spaces (EuroSimE's full name has one).

**Presets** live in `app.py:PRESETS` (semiconductor & microelectronics: packaging and
integration — ECTC, EPTC, ICEPT; thermal management and multiphysics — ITherm,
EuroSimE; reliability — IRPS; devices and circuits — IEDM, ISSCC, VLSI Symposium,
IMW; artificial intelligence and perception: computer vision — CVPR, speech technology
— Interspeech; communications and signal processing: signal processing — ICASSP,
communications and networking — GLOBECOM, INFOCOM; information security — IEEE S&P;
robotics — ICRA; biomedical engineering — EMBC), each with
its DOI prefix list; `render.GROUPS` holds the same grouping for the home page and the
static index, `background.FIELD_OF` the field used by the common-phrase filter (rebuild
`resources/background.json` when a preset is added). VLSI
Symposium needs ten prefixes because IEEE (10.1109) and JSAP (10.23919) alternate as
publisher and the acronym changed (vlsit/vlsic → vlsitechnology/vlsicircuits →
vlsitechnologyandcir). Venues that alternate IEEE/ACM DOIs by year (DAC, ICCAD) or whose
prefix is a substring of a bigger venue's (ISCA/ISCAS) were deliberately left out.
GLOBECOM uses both `10.1109/glocom` and `10.1109/globecom`. INFOCOM's default report
ends in 2024 because the 2025 DOI-prefix corpus remains sparse. IEEE S&P's slug is `sp`;
the search also accepts `S&P`, `IEEE S&P` and `IEEE SP`. The cross-field presets have
cached corpora; GLOBECOM's 2025 abstract coverage is lower than preceding years.

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
an abstract rule for invited talks "not made available for publication", and J-GLOBAL's
machine-translated Japanese duplicates ("【Powered by NICT】", no DOI; 65 in ICRA). ISSCC
loses ~800 such items (a quarter of its DOIs), ECTC ~100. Extend the regex if junk topics like
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

**Keyword analysis (`keywords.py`)**: phrases are n-grams of titles and abstracts (no full
text in OpenAlex), reported as a share of that year's papers. Rising/falling compare pooled
share in the early vs. late half of the range. Five things shape the output and are easy
to misread as bugs:

- **Topical counting** (`basis="topical"`, default): a paper counts for a phrase when the
  phrase is in its title or mentioned more than once (`text.TOPICAL_ROLES` = title,
  repeated; a single mention is role `once`). Chosen with `paper-trends validate`, which
  judges roles from the abstract alone and asks how often the phrase is also in the title
  (ECTC: repeated 36 %, once in the opening 19 %, once later 10 %). An earlier rule that
  counted "once, beyond the opening" and excluded "once, in the opening" had it backwards:
  single late mentions are methods and test conditions (finite element, thermal cycling).
  `KeywordTrends.doc_freq` holds the counts for the chosen basis, `mention_freq` every
  mention, `topical_share(term)` their ratio.
- **Acronyms** (`text.acronym_definitions`, `text.Acronyms`, `keywords.corpus_acronyms`):
  "long form (ACR)" definitions are found with the Schwartz-Hearst rule; the corpus map
  keeps acronyms defined ≥ 3 times with ≥ 80 % agreement, a paper's own definitions
  override it. Each acronym is normalised one way: expanded to the long form when that is a
  usable phrase (fewer than `n_max` tokens, or `n_max` tokens without a stopword at either
  edge: RDL → redistribution layer, FO → fan out), otherwise the long form is contracted to
  the acronym (through silicon via → tsv, fan out wafer level packaging → fowlp; "via",
  "through", "out" are stopwords). The defining occurrence is dropped so it is not a
  repeat; plurals fold with case evidence for `ss` endings (MBSs folds; loss does not
  expand as plural LoS). Explicit definitions still match directly. `Acronyms.surface` keeps the corpus casing for display
  (`display_form` = `restore_hyphens` + `restore_case`). Consequence worth knowing: after
  "artificial intelligence (AI)" every later "AI" is a repeat, so AI now counts in ~2 % of
  ECTC papers (10 % in 2025). Repeated application/background mentions also pass this
  rule; counts alone do not prove that AI is the paper’s research subject.
- **Fragments** (`fragment_share`, `KeywordTrends.inside`, `is_fragment`): a second pass
  over the stored token lists records, for every occurrence of a term with ≥ 10 mentions,
  the one-token-longer phrases to its left and right. Extensions carrying ≥ 10 % of the
  term's occurrences are "established"; when they cover ≥ `collapse_ratio` (0.8) of the
  occurrences the term is hidden ("level packaging" 1.0, "scanning electron" 0.94, "fine
  pitch" 0.0, "hybrid bonding" 0.14). The earlier total-based `collapse_subphrases` missed
  terms split between several longer phrases; a "standalone occurrence" test hid every
  adjective-like bigram. `--keep-subphrases` sets `collapse_ratio=None`.
- **Families** (`group_families`): rising/falling/emerging lists show one row per family
  of terms that contain one another or are singular/plural twins, variants listed under
  the head; a longer member heads the family when it has ≥ 60 % of the shortest member's
  papers (high-bandwidth memory over high-bandwidth; not finite-element analysis over
  finite-element at 52 %). Callers ask for more rows than they show (`rising(k*4)`).
- **Boilerplate** (`background.BOILERPLATE`, `resources/background.json`). Hide an exact
  phrase only if it is in the reviewed boilerplate list AND is used by >= 1% of papers in
  3+ other fields. Cross-field frequency is not a semantic test: deep learning, neural
  networks, real time and energy consumption remain eligible. Exact matching preserves
  high performance computing even when high performance is hidden. `KeywordTrends.common`
  contains only exclusions; `--keep-common` restores them. Fields pool related venues;
  own-field evidence is excluded. Rebuild the frequency table after adding corpora.
  See `docs/trend-audit-2026-10-05.md` for the diagnostic review and limitations.
- `STOPWORDS` in `text.py` is generic English + academic boilerplate + unit tokens only.
  Do not add domain words there; users pass `--stopwords file` for that. Test corpora must
  avoid stopwords inside the phrases they expect ("study", "paper" are stopwords) and
  repeat a phrase or put it in the title, or nothing is topical.

These are data-driven heuristics without ground truth; `validate` is a sanity check, not a
gold standard. The five-conference audit adds targeted paper review and reproducible count checks, not
a representative independently annotated benchmark; do not present the rules as validated.

**Coverage differs a lot by venue.** IEEE venues with acronym DOIs (ECTC, ISSCC, CVPR,
ICRA…) are complete. Interspeech (ISCA, `10.21437/interspeech`) has every paper but
abstracts for only ~40 % (2023+ ~20 %): use `--text title` there. Venues without DOIs
(NeurIPS, ICML, CHI) are patchy in OpenAlex — NeurIPS' source covers 2016–2021 only —
so they are not good showcases; say so rather than fetching them.

**World map** (`charts.world_map`): choropleth of share of papers by country, joined to
the vega-datasets world-110m topojson (CDN) by ISO 3166-1 numeric id from
`report/static/iso3166.json` (generated once with pycountry; not a runtime dependency).
Antarctica (id 10) is dropped; city-states are too small to see — say so rather than hack.
On the report page the map has a year control (period link / slider / Play): the rows
carry three-year rolling fields `s<year>`/`n<year>` (`country_map_rows(..., years)`), a
Vega signal `year` (0 = pooled) picks the field via `calculate`, and the page's own HTML
controls set it with `view.signal("year", y).runAsync()` — no Vega `bind`, so the
controls follow `report.css`. `build.map_lines` precomputes the "leaders" line per year.

**Report design (the public face; Streamlit is the local tool).** Editorial data-journalism
style after Our World in Data / The Economist, agreed with the maintainer on 2026-09-26: warm
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
`render.FULL`/`SHORT`/`GROUPS`/`TAGLINE` hold the preset names, the home-page grouping and the tagline.

The report is intentionally selective: at most four rising and four fading phrase charts,
five visible topic labels, and no institution bump chart or institution × topic heatmap.
Those deeper ranking and composition questions belong in Explore. The underlying
`build.inst_rank_rows` and `build.inst_topic_rows` data remain available for analysis.

**Linked-entity panel** (`report/entities.py` + `static/entities.js`). Every phrase,
institution and topic on the page is clickable (`<span class="ent" data-ent="term|inst|topic"
data-name="…">`, plus Vega click listeners on the institution bars, topic bands and
emerging cells) and opens a drawer with the entity's trend, related institutions / topics /
co-occurring phrases (lift > 1.3, ≥ 8 shared papers) / signature phrases (lift > 1.4, ≥ 5
papers) and most cited papers; names inside the drawer are clickable too, with a history
stack and crumbs. The data (`build_entities`: 150 terms, 60 institutions, all topics)
is inlined as `window.ENTITIES`; only the papers some panel lists are shipped, renumbered,
which keeps CVPR at ~0.4 MB instead of 2.7 MB. Topic membership comes from
`TopicTrends.assignments` (record index → dominant NMF topic). Two things that are easy to
break: Vega embed promises resolve before the next `<script>` runs, so the click handlers
must look up `window.openEntity` lazily at click time, not when binding; and inside the
Streamlit iframe (`<body class="embedded">`) the drawer cannot be `position: fixed`
(the iframe is sized to its content, so fixed = the top of the document) — `place()`
positions it absolutely near the last click instead.

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
