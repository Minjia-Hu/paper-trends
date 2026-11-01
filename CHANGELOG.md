# Changelog

## Unreleased

- Exclude workshop sources from main-conference searches even when OpenAlex source
  naming forces a fallback to substring matching. Also reject records with explicit
  workshop provenance in raw venue names or CVF/DBLP workshop URLs, even when their
  OpenAlex source ID points to the main conference.
- Public [bilingual demo](https://minjia-hu.github.io/paper-trends/) with linked
  detail panels for ECTC and CVPR, covering 2016–2025 without sign-in or an API key.
- Reproducible demo build script and deployment instructions, with corpus hashes,
  verified fetch timestamps for refreshed data, and the source revision in a manifest.
- Tighter spacing and fewer dividers on the report index, with conference groups
  distinguished by typography and whitespace.

## [0.1.0](https://github.com/Minjia-Hu/paper-trends/releases/tag/v0.1.0) — 2026-11-01

The first public release of paper-trends: fetch public conference metadata from
OpenAlex and explore how research topics, phrases and participating institutions
change over time.

**Included**

- CLI commands for fetching, coverage inspection, keyword trends, topics,
  institution/author/country rankings and cross-conference phrase comparisons.
- A bilingual Streamlit app with Report and Explore views, supporting-paper
  evidence, linked detail panels and CSV exports.
- Shareable static HTML reports in English and Chinese.
- Configuration examples, atomic corpus writes, CSV formula protection and
  automated tests.

**Getting started**

Follow the [English README](https://github.com/Minjia-Hu/paper-trends/blob/v0.1.0/README.md)
or [中文 README](https://github.com/Minjia-Hu/paper-trends/blob/v0.1.0/README.zh-CN.md).
Python 3.12+ and uv are required for the documented setup. Run the project in place
with `uv run python -m paper_trends`; launch the app with `uv run streamlit run app.py`.
Complete fetches require an activated OpenAlex API key and a contact email.

**Scope and limitations**

- This is an early release. OpenAlex coverage and abstract availability vary by
  venue and year; check the coverage summary before interpreting trends.
- Analyses use public metadata and available abstracts, not paywalled full text.
  Phrase and topic trends are analytical signals, not an exhaustive literature review.
- Static reports include linked detail panels; the complete Explore workspace runs
  in the Streamlit app. Report chart libraries and fonts load from CDNs on first use.
- No hosted public demo is included in this release.

Code: MIT. OpenAlex metadata: CC0.
