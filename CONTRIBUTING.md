# Contributing

Thanks for your interest. Bug reports, venue coverage notes and pull requests are welcome.

## Setup and checks

```bash
uv sync                      # Python 3.12+, dependencies into .venv
npm ci --ignore-scripts      # jsdom for the DOM tests (Node 24 recommended)
uv run pytest -q             # offline Python suite
npm test                     # Node core + jsdom interaction tests
```

Run the tool in place with `uv run python -m paper_trends ...`; the project is not
installed into the virtual environment (see the note on `package = false` in
`pyproject.toml`). Copy `.env.example` to a git-ignored `.env` and fill in
`OPENALEX_MAILTO` and an activated `OPENALEX_API_KEY`. Complete fetches require the key
because OpenAlex cursor paging beyond the first page is authenticated.

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
