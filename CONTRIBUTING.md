# Contributing

Thanks for your interest. Bug reports, venue coverage notes and pull requests are welcome.

## Setup and checks

```bash
uv sync --frozen             # Python 3.12+, dependencies into .venv
npm ci --ignore-scripts      # jsdom for the DOM tests (Node 24.15+ recommended)
uv run ruff check .          # minimal correctness checks
uv run pytest -q             # offline Python suite
npm test                     # Node core + jsdom interaction tests
```

Run the tool in place with `uv run python -m paper_trends ...`; the project is not
installed into the virtual environment (see the note on `package = false` in
`pyproject.toml`). Copy `.env.example` to a git-ignored `.env` and fill in
`OPENALEX_MAILTO` and an activated `OPENALEX_API_KEY`. Complete fetches require the key
because OpenAlex cursor paging beyond the first page is authenticated.

Ruff checks syntax and selected correctness errors; formatting is not enforced.
Dependabot checks Python, npm and GitHub Actions dependencies weekly and opens
update pull requests for review.

## Optional live API check

`uv run --frozen python -m scripts.smoke_openalex` fetches ECTC 2019–2020 into a
temporary directory, checks pagination and provenance, generates both report languages
and four CLI CSV exports, and exercises Streamlit Report/Explore in both languages.
It requires the two OpenAlex settings above and spends API quota. Existing `data/`
files are left intact; temporary outputs are removed after the run.

Maintainers can run the same check under **Actions → Live OpenAlex smoke check →
Run workflow** after configuring repository Actions secrets named `OPENALEX_MAILTO`
and `OPENALEX_API_KEY`. Run it on the trusted `main` branch. It never runs on a push,
pull request or schedule, and does not upload fetched data as an artifact.
The regular test suite remains offline; live failures can also reflect upstream
availability or exhausted quota rather than a code regression.

## Ground rules

- **Public data only.** OpenAlex is the sole data source. Do not add other sources,
  and never commit fetched corpora (`data/` is git-ignored) or credentials.
- **Library first.** Analyses are plain functions over the records from
  `store.read_jsonl`; CLI, Streamlit app and static reports all call the same functions.
  Keep printing and argparse out of analysis code.
- **Generic stopwords only.** `text.STOPWORDS` holds generic English, academic
  boilerplate and unit tokens. Domain words belong in a user-supplied `--stopwords` file.
- **Adding a conference preset.** Read `docs/venue-audit-2026-10-05.md` first, verify
  the DOI prefix boundary (`scripts/audit_venues.py`), add the entry to
  `presets.py:CONFERENCES`, then rebuild `resources/background.json`.
- **Both languages.** Interface copy lives in `i18n.py`; keep English and Chinese in step.
- Add or adjust a test for behaviour changes. Design notes and audits under `docs/` are
  written in Chinese; English summaries in pull requests are fine.
