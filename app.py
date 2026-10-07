"""paper-trends — Streamlit UI. Run with:  uv run streamlit run app.py"""

from __future__ import annotations

import os
import threading
from datetime import date, datetime, timezone
from html import escape
from urllib.parse import urlencode
from pathlib import Path

import pandas as pd
import streamlit as st

from paper_trends import compare, frames
from paper_trends.branding import FAVICON, logo_svg
from paper_trends.i18n import language, tr, chart_labels, field_label
from paper_trends.report import charts
from paper_trends.background import field_of
from paper_trends.coverage import coverage_details, default_period
from paper_trends.fetch import coverage_table, fetch_conference, resolve_venue
from paper_trends.keywords import compute_trends
from paper_trends.openalex import OpenAlex, OpenAlexError
from paper_trends.rank import ENTITIES, compute_ranking
from paper_trends.report.build import build_report, country_name, inst_rank_rows, inst_topic_rows
from paper_trends.report.render import FULL, SHORT, TAGLINE, asset_version as report_asset_version, nav_for, render_explorer_page, render_page
from paper_trends.store import filter_years, metadata_path, provenance_label, read_jsonl, read_provenance, write_jsonl
from paper_trends.text import load_stopwords
from paper_trends.topics import InsufficientTopicData, compute_nmf, compute_openalex

DATA_DIR = Path("data")
PRESETS = {
    # ---- semiconductor & microelectronics ---------------------------------------------
    "Packaging & integration · ECTC — Electronic Components and Technology Conference": {
        "query": "Electronic Components and Technology Conference", "doi_prefixes": ["10.1109/ectc"], "slug": "ectc",
    },
    "Packaging & integration · EPTC — Electronics Packaging Technology Conference": {
        "query": "Electronics Packaging Technology Conference", "doi_prefixes": ["10.1109/eptc"], "slug": "eptc",
    },
    "Packaging & integration · ICEPT — International Conference on Electronic Packaging Technology": {
        "query": "International Conference on Electronic Packaging Technology", "doi_prefixes": ["10.1109/icept"], "slug": "icept",
    },
    "Thermal management & multiphysics · ITherm — Thermal and Thermomechanical Phenomena in Electronic Systems": {
        "query": "Thermal and Thermomechanical Phenomena in Electronic Systems", "doi_prefixes": ["10.1109/itherm"], "slug": "itherm",
    },
    "Reliability · IRPS — International Reliability Physics Symposium": {
        "query": "International Reliability Physics Symposium", "doi_prefixes": ["10.1109/irps"], "slug": "irps",
    },
    "Thermal management & multiphysics · EuroSimE — Thermal, Mechanical and Multi-Physics Simulation in Microelectronics": {
        "query": "Thermal, Mechanical and Multi-Physics Simulation and Experiments in Microelectronics and Microsystems",
        "doi_prefixes": ["10.1109/eurosime"], "slug": "eurosime",
    },
    # ---- devices and circuits ----------------------------------------------------------
    "Devices & circuits · IEDM — International Electron Devices Meeting": {
        "query": "International Electron Devices Meeting", "doi_prefixes": ["10.1109/iedm"], "slug": "iedm",
    },
    "Devices & circuits · ISSCC — International Solid-State Circuits Conference": {
        "query": "International Solid-State Circuits Conference", "doi_prefixes": ["10.1109/isscc"], "slug": "isscc",
    },
    "Devices & circuits · VLSI Symposium — Symposium on VLSI Technology and Circuits": {
        "query": "Symposium on VLSI Technology and Circuits",
        # the DOI prefix changed almost every year (IEEE / JSAP alternate as publisher)
        "doi_prefixes": [f"{reg}/{acr}" for reg in ("10.1109", "10.23919")
                         for acr in ("vlsit", "vlsic", "vlsitechnology", "vlsicircuits", "vlsitechnologyandcir")],
        "slug": "vlsi",
    },
    "Devices & circuits · IMW — International Memory Workshop": {
        "query": "International Memory Workshop", "doi_prefixes": ["10.1109/imw"], "slug": "imw",
    },
    # ---- broader research communities: curated examples, not an exhaustive directory ---
    "Computer vision · CVPR — Conference on Computer Vision and Pattern Recognition": {
        "query": "Conference on Computer Vision and Pattern Recognition", "doi_prefixes": ["10.1109/cvpr"], "slug": "cvpr",
    },
    "Speech technology · Interspeech — Conference of the International Speech Communication Association": {
        "query": "Interspeech", "doi_prefixes": ["10.21437/interspeech"], "slug": "interspeech",
    },
    "Robotics · ICRA — International Conference on Robotics and Automation": {
        "query": "International Conference on Robotics and Automation", "doi_prefixes": ["10.1109/icra"], "slug": "icra",
    },
    "Signal processing · ICASSP — International Conference on Acoustics, Speech and Signal Processing": {
        "query": "International Conference on Acoustics Speech and Signal Processing", "doi_prefixes": ["10.1109/icassp"], "slug": "icassp",
    },
    "Biomedical engineering · EMBC — Engineering in Medicine and Biology Society": {
        "query": "Annual International Conference of the IEEE Engineering in Medicine and Biology Society", "doi_prefixes": ["10.1109/embc"], "slug": "embc",
    },
    "Information security · IEEE S&P — Symposium on Security and Privacy": {
        "query": "Symposium on Security and Privacy", "doi_prefixes": ["10.1109/sp"], "slug": "sp", "aliases": ["S&P", "IEEE SP"],
    },
    "Communications & networking · GLOBECOM — Global Communications Conference": {
        "query": "Global Communications Conference", "doi_prefixes": ["10.1109/glocom", "10.1109/globecom"], "slug": "globecom",
    },
    "Communications & networking · INFOCOM — Conference on Computer Communications": {
        "query": "Conference on Computer Communications", "doi_prefixes": ["10.1109/infocom"], "slug": "infocom",
    },
}
FETCH_YEARS = (2016, 2026)

st.set_page_config(page_title="paper-trends", page_icon=str(FAVICON), layout="wide", initial_sidebar_state="collapsed")
LANG = language(st.query_params.get("lang"), st.context.headers.get("Accept-Language", ""))


def t(text: str, **values) -> str:
    return tr(text, LANG, **values)


st.markdown(
    """<style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
    #MainMenu, [data-testid="stToolbarActions"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
    header[data-testid="stHeader"] { background: transparent; height: 2.6rem; pointer-events: none; }
    [data-testid="stToolbar"] { pointer-events: none; }
    .block-container { padding-top: 0.2rem; padding-bottom: 0; max-width: 1240px; }
    iframe[title="st.iframe"] { display: block; }
    /* masthead rendered by Streamlit (outside the iframe, so links can change the query string) */
    .pt-masthead { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; padding: 10px 24px 12px; margin: 0; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-masthead .brand { display: inline-flex; align-items: center; gap: 9px; flex-shrink: 0; font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 20px; font-weight: 500; line-height: 1; color: #1B1B1B; text-decoration: none; letter-spacing: -0.01em; white-space: nowrap; }
    .pt-masthead .brand-mark { display: block; width: 28px; height: 28px; flex-shrink: 0; }
    .pt-masthead .tagline { font-size: 13.5px; color: #5C5C5C; }
    .pt-masthead .all { margin-left: auto; font-size: 13.5px; color: #5C5C5C; text-decoration: none; border-bottom: 1px solid #E6E3DC; }
    .pt-masthead .all:hover { color: #E3120B; border-color: #E3120B; }
    [data-testid="stExpandSidebarButton"] { display: none !important; }
    .st-key-controls_search { padding: 10px 24px 0; }
    .st-key-controls_row { padding: 6px 24px 0; }
    /* search box: white, hairline border, red underline on focus */
    .st-key-controls_search div[data-baseweb="input"], .st-key-controls_search div[data-baseweb="input"] > div, .st-key-controls_search div[data-baseweb="base-input"] { background-color: #FFFFFF !important; border-color: #E6E3DC !important; border-radius: 2px !important; }
    .st-key-controls_search div[data-baseweb="input"]:focus-within { border-color: #1B1B1B !important; box-shadow: none !important; }
    .st-key-controls_search input { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 14.5px !important; color: #1B1B1B !important; background: #FFFFFF !important; }
    /* buttons: ink, square corners, quiet */
    .st-key-fetch_btn button, .st-key-fetch_prefix_btn button { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 13.5px !important; border-radius: 2px !important; border: 1px solid #E6E3DC !important; background: #FFFFFF !important; color: #1B1B1B !important; box-shadow: none !important; }
    .st-key-fetch_btn button, .st-key-fetch_prefix_btn button { background: #1B1B1B !important; color: #FFFFFF !important; border-color: #1B1B1B !important; padding: 6px 18px !important; letter-spacing: 0.02em; }
    .st-key-fetch_btn button:hover, .st-key-fetch_prefix_btn button:hover { background: #E3120B !important; border-color: #E3120B !important; }
    /* compact editorial toolbar: each label owns one clearly separated group */
    .pt-controls { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 13.5px; color: #5C5C5C; margin: 14px 24px 0; padding: 0 0 13px; display: grid; grid-template-columns: max-content max-content 1fr; align-items: end; gap: 28px; border-bottom: 1px solid #E6E3DC; }
    .pt-control-group { display: grid; gap: 6px; }
    .pt-controls .lbl { font-size: 10px; line-height: 1; letter-spacing: 0.14em; text-transform: uppercase; color: #8A877F; }
    .pt-control-links { display: flex; align-items: baseline; flex-wrap: wrap; gap: 14px; }
    .pt-control-actions { justify-self: end; }
    .pt-controls a { color: #5C5C5C; text-decoration: none; padding-bottom: 3px; border-bottom: 2px solid transparent; white-space: nowrap; }
    .pt-controls a:hover { color: #E3120B; }
    .pt-controls a.current { color: #E3120B; border-bottom-color: #E3120B; }
    .st-key-custom_period { padding: 4px 24px 0; max-width: 520px; }
    .st-key-options_form { margin: 10px 24px 0; padding: 12px 18px 6px; border: 1px solid #E6E3DC; border-radius: 2px; background: #FFFFFF; }
    .pt-options-head { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: #8A877F; margin-bottom: 4px; }
    .pt-options-head a { color: #E3120B; text-decoration: none; margin-left: 12px; text-transform: none; letter-spacing: 0; font-size: 13px; }
    .st-key-options_form label p, .st-key-options_form label { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 13px !important; color: #5C5C5C !important; }
    .st-key-options_form div[data-baseweb="input"], .st-key-options_form div[data-baseweb="input"] > div, .st-key-options_form div[data-baseweb="base-input"], .st-key-options_form div[data-baseweb="textarea"], .st-key-options_form textarea { background-color: #FCFBF8 !important; border-color: #E6E3DC !important; border-radius: 2px !important; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 14px !important; }
    .st-key-refresh_btn button { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 13px !important; border-radius: 2px !important; border: 1px solid #E6E3DC !important; background: #FFFFFF !important; color: #1B1B1B !important; }
    .st-key-refresh_btn button:hover { border-color: #1B1B1B !important; }
    /* Reserve the report surface while its first analysis is being built. */
    .st-key-report_loading { margin: 0 24px; padding: 30px 0 0; }
    .pt-report-loading { padding: 0 0 18px; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-report-loading .kicker { margin: 0 0 9px; color: #E3120B; font-size: 11px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; }
    .pt-report-loading h2 { margin: 0 0 8px !important; padding: 0 !important; color: #1B1B1B; font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif !important; font-size: 30px !important; font-weight: 500 !important; line-height: 1.1; }
    .pt-report-loading p { max-width: 68ch; margin: 0; color: #5C5C5C; font-size: 14px; line-height: 1.6; }
    /* Keep the explorer responsive while its embedded analysis is assembled. */
    .st-key-explore_loading { margin: 8px 24px 0; }
    .pt-explore-loading { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 14px; padding: 12px 0 14px; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-explore-loading .kicker { color: #E3120B; font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; }
    .pt-explore-loading p { margin: 0; color: #5C5C5C; font-size: 13.5px; line-height: 1.5; }
    /* explore view header: the report's hierarchy, with an interactive workbench below */
    .pt-head { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; margin: 0 24px; padding: 30px 0 18px; border-bottom: 1px solid #1B1B1B; }
    .pt-head-grid { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 36px; }
    .pt-head-identity { min-width: 0; }
    .pt-head .kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin-bottom: 10px; }
    .pt-head h1 { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-weight: 500; font-size: clamp(34px, 4.6vw, 54px); line-height: 1.05; letter-spacing: -0.015em; margin: 0 0 12px; max-width: 18ch; color: #1B1B1B; padding: 0; overflow-wrap: anywhere; }
    .pt-head .full-name { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; color: #5C5C5C; font-size: 21px; line-height: 1.25; margin: -3px 0 0; max-width: 40ch; }
    .pt-head-stats { display: grid; grid-template-columns: repeat(3, minmax(92px, auto)); border-top: 1px solid #E6E3DC; }
    .pt-head-stats > span { display: grid; align-content: start; gap: 2px; padding: 11px 18px 2px; border-left: 1px solid #E6E3DC; }
    .pt-head-stats > span:first-child { padding-left: 0; border-left: 0; }
    .pt-head-stats b { color: #1B1B1B; font: 500 22px/1 Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; }
    .pt-head-stats small { color: #5C5C5C; font: 12px/1.35 "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; white-space: nowrap; }
    .pt-head-provenance { display: flex; gap: 8px 24px; flex-wrap: wrap; margin-top: 20px; padding-top: 10px; border-top: 1px solid #E6E3DC; color: #8A877F; font-size: 12px; }
    .pt-head-provenance a { color: #5C5C5C; text-decoration: none; border-bottom: 1px solid #C9C6BE; }
    .pt-head-provenance a:hover { color: #E3120B; border-bottom-color: #E3120B; }
    .st-key-explore_context { box-sizing: border-box; padding: 0 24px; }
    .pt-coverage-notice { margin: 10px 0 0; color: #5C5C5C; font: 12.5px/1.55 "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-coverage-panel { padding: 18px 0 20px; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-coverage-panel h2 { margin: 0 0 6px !important; padding: 0 !important; color: #1B1B1B; font: 500 20px/1.25 Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif !important; }
    .pt-coverage-panel .caveat { margin: 0 0 14px; color: #5C5C5C; font-size: 13px; line-height: 1.55; }
    .pt-coverage-panel .exclusion { margin: 0 0 8px; color: #5C5C5C; font-size: 12.5px; line-height: 1.5; }
    .pt-coverage-table { width: 100%; border-collapse: collapse; margin-top: 14px; font-size: 12.5px; font-variant-numeric: tabular-nums; }
    .pt-coverage-table th { padding: 8px 10px; border-top: 1px solid #1B1B1B; border-bottom: 1px solid #E6E3DC; color: #8A877F; font-weight: 500; text-align: right; }
    .pt-coverage-table td { padding: 8px 10px; border-bottom: 1px solid #EEECE6; color: #3D3D3D; text-align: right; }
    .pt-coverage-table th:first-child, .pt-coverage-table td:first-child { padding-left: 0; text-align: left; }
    /* Phrase search is an editorial tool row rather than a boxed Streamlit form. */
    .st-key-phrase_tool { margin: 0; padding: 0 0 18px !important; border-bottom: 1px solid #E6E3DC; }
    .st-key-phrase_tool [data-testid="stForm"] { padding: 0 !important; border: 0 !important; border-radius: 0 !important; background: transparent !important; }
    .pt-phrase-label { margin: 0 0 8px; color: #E3120B; font: 600 11px/1 "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; letter-spacing: 0.12em; text-transform: uppercase; }
    .st-key-phrase_tool div[data-baseweb="input"], .st-key-phrase_tool div[data-baseweb="input"] > div, .st-key-phrase_tool div[data-baseweb="base-input"] { min-height: 40px; background: #FFFFFF !important; border-color: #D8D5CE !important; border-radius: 2px !important; box-shadow: none !important; }
    .st-key-phrase_tool div[data-baseweb="input"]:focus-within { border-color: #1B1B1B !important; }
    .st-key-phrase_tool input { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 13.5px !important; color: #1B1B1B !important; background: #FFFFFF !important; }
    .st-key-phrase_submit button { min-height: 40px; border: 1px solid #1B1B1B !important; border-radius: 2px !important; background: #1B1B1B !important; color: #FFFFFF !important; box-shadow: none !important; font: 500 13px/1 "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; }
    .st-key-phrase_submit button:hover { border-color: #E3120B !important; background: #E3120B !important; color: #FFFFFF !important; }
    /* Explore tasks are page navigation, not another copy of the global toolbar. */
    .pt-sections { display: flex; align-items: baseline; flex-wrap: wrap; gap: 7px 24px; margin: 12px 24px 0; padding: 10px 0; border-top: 1px solid #E6E3DC; border-bottom: 1px solid #E6E3DC; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 13.5px; }
    .pt-sections a { color: #5C5C5C; text-decoration: none; padding-bottom: 3px; border-bottom: 2px solid transparent; white-space: nowrap; }
    .pt-sections a:hover { color: #E3120B; }
    .pt-sections a.current { color: #E3120B; border-bottom-color: #E3120B; }
    .pt-h2 { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif !important; font-weight: 500 !important; font-size: 26px !important; letter-spacing: -0.01em; margin: 26px 0 4px !important; padding: 0 !important; color: #1B1B1B; }
    .pt-subhead { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif !important; font-size: 21px !important; font-weight: 500 !important; margin: 14px 0 5px !important; }
    .block-container [data-testid="stMarkdownContainer"] p.pt-lede { font-family: var(--pt-sans); color: #5C5C5C; font-size: 14px; line-height: 1.65; max-width: 72ch; margin: 0 0 12px; }
    /* One content measure for every Explore task, including native controls. */
    :root { --pt-sans: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; --pt-serif: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; }
    .st-key-explore_body { box-sizing: border-box; padding: 0 24px 24px; min-width: 0; font-family: var(--pt-sans); }
    .pt-section-head { margin: 22px 0 8px; }
    .pt-section-head .pt-h2 { margin: 0 0 6px !important; font-family: var(--pt-serif) !important; line-height: 1.3; }
    .pt-section-head p.pt-lede { margin-bottom: 0 !important; }
    .st-key-explore_controls { padding: 0 0 16px; border-bottom: 1px solid #E6E3DC; }
    .st-key-explore_controls [data-testid="stToggle"] { min-height: 40px; display: flex; align-items: center; }
    .pt-control-label { margin: 0 0 8px; font: 400 12.5px/20px var(--pt-sans); color: #5C5C5C; }
    .st-key-explore_body [data-testid="stSelectbox"], .st-key-explore_body [data-testid="stMultiSelect"], .st-key-explore_body input, .st-key-explore_body button, .st-key-explore_body [data-testid="stMultiSelectTagsContainer"] { font-family: var(--pt-sans) !important; }
    .st-key-explore_body [data-testid="stMultiSelectTagsContainer"] span[data-tag] { font-size: 13px !important; line-height: 1.5; font-family: var(--pt-sans) !important; }
    .st-key-explore_body [data-testid="stWidgetLabel"] p { font-size: 12.5px !important; line-height: 20px; }
    .st-key-explore_body [data-testid="stMarkdownContainer"] p.pt-method-note { font: 400 12.5px/1.65 var(--pt-sans); color: #77746D; margin: 0 0 10px; max-width: 88ch; }
    .pt-method-note b { font-weight: 500; color: #5C5C5C; margin-right: 10px; }
    .st-key-explore_body .pt-h2, .st-key-explore_body .pt-fig .headline { font-family: var(--pt-serif) !important; }
    .st-key-explore_body .pt-fig { margin-top: 16px; }
    .st-key-explore_body .pt-fig .sub { font-size: 13px; line-height: 1.6; }
    .st-key-explore_body [data-testid="stExpander"] { border-radius: 2px; border-color: #E6E3DC; }
    .st-key-explore_body .st-key-explore_loading { margin: 0; }
    @media (max-width: 700px) {
        .st-key-explore_body { padding-left: 16px; padding-right: 16px; }
        .st-key-explore_body .st-key-phrase_tool, .st-key-explore_body .st-key-explore_loading { margin-left: 0; margin-right: 0; }
        .pt-section-head { margin-top: 18px; }
    }
    .block-container [data-testid="stMarkdownContainer"] p { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    /* explore widgets: quiet */
    .block-container label p, .block-container label { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 12.5px !important; color: #5C5C5C !important; }
    .block-container div[data-baseweb="select"] > div, .block-container div[data-baseweb="input"] > div, .block-container div[data-baseweb="textarea"] { background-color: #FFFFFF !important; border-color: #E6E3DC !important; border-radius: 2px !important; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 14px !important; }
    .block-container [data-testid="stDataFrame"] { border: 1px solid #E6E3DC; border-radius: 2px; }
    .block-container [data-testid="stToggle"] label p { font-size: 13px !important; }
    .block-container [data-testid="stSlider"] { padding-top: 4px; }
    /* figures in Explore, same anatomy as the report */
    .pt-fig { display: flex; flex-direction: column; gap: 2px; margin: 8px 0 6px; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-fig .headline { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 19px; font-weight: 500; line-height: 1.25; color: #1B1B1B; }
    .pt-fig .sub { color: #5C5C5C; font-size: 13.5px; }
    .pt-source { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; color: #8A877F; font-size: 12.5px; margin: 2px 0 14px; }
    .pt-sm { border-top: 2px solid #1B1B1B; padding-top: 6px; margin-top: 10px; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; }
    .pt-sm .term { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 17px; font-weight: 500; line-height: 1.2; margin: 0 0 2px; color: #1B1B1B; }
    .pt-sm .move { font-size: 12.5px; color: #5C5C5C; margin: 0; }
    [data-testid="stVegaLiteChart"] { margin-top: -6px; }
    /* tables in the report's style */
    .pt-table-wrap { overflow-x: auto; margin: 4px 0 6px; }
    .pt-table { border-collapse: collapse; width: 100%; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 13.5px; font-variant-numeric: tabular-nums; color: #1B1B1B; }
    .pt-table th { text-align: left; font-weight: 500; color: #5C5C5C; font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.06em; padding: 6px 12px 6px 0; border-bottom: 1px solid #1B1B1B; white-space: nowrap; }
    .pt-table td { padding: 7px 12px 7px 0; border-bottom: 1px solid #E6E3DC; vertical-align: top; }
    .pt-table th.num, .pt-table td.num { text-align: right; }
    .pt-table td a { color: #1B1B1B; text-decoration: none; border-bottom: 1px solid #E6E3DC; }
    .pt-table td a:hover { border-bottom-color: #E3120B; }
    .mono { font-family: "IBM Plex Mono", ui-monospace, Menlo, monospace; font-size: 13px; background: #F3F1EC; padding: 1px 6px; border-radius: 2px; }
    /* selects, chips, sliders: quiet (Streamlit >= 1.6x uses react-aria widgets, hence data-rac) */
    .block-container [data-testid="stSelectbox"] > div[data-rac] > div, .block-container [data-testid="stMultiSelect"] > div[data-rac] > div,
    .block-container [data-testid="stSelectbox"] [role="combobox"], .block-container [data-testid="stMultiSelect"] [role="combobox"] { background-color: #FFFFFF !important; border-color: #E6E3DC !important; border-radius: 2px !important; box-shadow: none !important; }
    .block-container [data-testid="stMultiSelectTagsContainer"] span[data-tag] { background-color: #F3F1EC !important; color: #1B1B1B !important; border-radius: 2px !important; border: 1px solid #E6E3DC; }
    .block-container [data-testid="stMultiSelectTagsContainer"] span[data-tag] span, .block-container [data-testid="stMultiSelectTagsContainer"] span[data-tag] button { color: #1B1B1B !important; }
    .block-container [data-testid="stSliderThumbValue"] p { color: #1B1B1B !important; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 12px !important; }
    .block-container [data-testid="stSliderTickBar"] p { color: #8A877F !important; font-size: 11px !important; }
    .st-key-dl_results button, .st-key-dl_corpus button, .st-key-dl_keywords button, .st-key-dl_institutions button { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif !important; font-size: 13px !important; border-radius: 2px !important; border: 1px solid #E6E3DC !important; background: #FFFFFF !important; color: #1B1B1B !important; width: 100%; }
    .st-key-dl_results button:hover, .st-key-dl_corpus button:hover, .st-key-dl_keywords button:hover, .st-key-dl_institutions button:hover { border-color: #1B1B1B !important; }
    .block-container [data-testid="stDataFrame"] { border: 1px solid #E6E3DC; border-radius: 2px; }
    /* resolution card */
    .pt-found { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; margin: 14px 24px 0; padding: 4px 0 4px 18px; border-left: 3px solid #E3120B; max-width: 820px; }
    .pt-found .kicker { font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin-bottom: 4px; }
    .pt-found .name { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 26px; font-weight: 500; line-height: 1.15; color: #1B1B1B; letter-spacing: -0.01em; }
    .pt-found .meta { color: #5C5C5C; font-size: 14px; margin-top: 6px; }
    .pt-found .warn { color: #1B1B1B; font-size: 14px; margin-top: 8px; }
    .pt-found .warn b { color: #E3120B; }
    .st-key-fetch_row { padding: 10px 24px 4px 45px; }
    .pt-note { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; color: #5C5C5C; font-size: 14px; padding: 4px 24px 0; }
    /* home page, rendered by Streamlit so its links can change the query string */
    .pt-home { font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; color: #1B1B1B; padding: 8px 24px 40px; max-width: 1120px; }
    .pt-home .kicker { font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: #E3120B; font-weight: 600; margin: 12px 0 14px; }
    .pt-home h1 { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-weight: 500; font-size: clamp(34px, 4.6vw, 54px); line-height: 1.05; letter-spacing: -0.015em; margin: 0 0 18px; max-width: 18ch; color: #1B1B1B; }
    .pt-home .lede { color: #5C5C5C; font-size: 16px; max-width: 66ch; margin: 0 0 16px; }
    .pt-home h2 { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-weight: 500; font-size: 30px; letter-spacing: -0.01em; margin: 44px 0 8px; color: #1B1B1B; }
    .pt-home .collection-note { max-width: 78ch; margin: 0 0 2px; color: #8A877F; font-size: 13px; }
    .pt-home .domain-jump { display: flex; flex-wrap: wrap; gap: 6px 20px; margin: 18px 0 4px; font-size: 13px; }
    .pt-home .domain-jump a { color: #5C5C5C; text-decoration: none; border-bottom: 1px solid #E6E3DC; }
    .pt-home .domain-jump a:hover { color: #E3120B; border-bottom-color: #E3120B; }
    .pt-home .domains { max-width: 1120px; }
    .pt-home .domain-section { padding: 28px 0 12px; border-top: 1px solid #E6E3DC; }
    .pt-home .domain-section h2 { font-size: 31px; margin: 0 0 18px; padding: 0; }
    .pt-home .directions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 48px; }
    .pt-home .direction h3 { font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 22px; font-weight: 500; line-height: 1.2; margin: 0 0 8px; color: #1B1B1B; }
    .pt-language { display: inline-flex; gap: 12px; white-space: nowrap; font-size: 13px; margin-left: auto; }
    .pt-language a { color: #5C5C5C; text-decoration: none; padding: 5px 0; }
    .pt-language a.current { color: #E3120B; border-bottom: 2px solid #E3120B; }
    .pt-home:lang(zh) h1 { font-family: "Songti SC", "Noto Serif CJK SC", serif; line-height: 1.35; max-width: 18em; }
    @media (max-width: 900px) { .pt-head-grid { grid-template-columns: 1fr; gap: 22px; } .pt-head-stats { width: min(100%, 430px); } }
    @media (max-width: 700px) { .pt-masthead { gap: 12px; flex-wrap: wrap; } .pt-masthead .tagline { display: none; } .pt-controls { grid-template-columns: 1fr auto; gap: 16px 22px; } .pt-control-group:first-child { grid-column: 1 / -1; } .pt-control-actions { align-self: end; } .st-key-report_loading { margin-left: 16px; margin-right: 16px; padding-top: 22px; } .st-key-explore_loading { margin-left: 16px; margin-right: 16px; } .pt-head { margin: 0 16px; padding-top: 22px; } .pt-head-stats { grid-template-columns: repeat(3, 1fr); width: 100%; } .pt-head-stats > span { min-width: 0; padding: 10px 9px 0; } .pt-head-stats b { font-size: 19px; } .pt-head-stats small { white-space: normal; } .pt-head-provenance { display: grid; gap: 4px; } .st-key-explore_context { padding-left: 16px; padding-right: 16px; } .pt-sections { margin-left: 16px; margin-right: 16px; gap: 7px 18px; } .pt-home .directions { grid-template-columns: 1fr; gap: 28px; } .pt-home .domain-section { padding-top: 30px; } .pt-home .domain-section > h2 { font-size: 27px; } }
    .pt-home ul { list-style: none; margin: 0; padding: 0; font-family: Newsreader, Georgia, "Songti SC", "Noto Serif CJK SC", serif; font-size: 20px; line-height: 1.4; }
    @media (max-width: 700px) {
      .pt-masthead { column-gap: 10px; padding-left: 16px; padding-right: 16px; }
      .pt-masthead .brand { gap: 7px; font-size: 18px; }
      .pt-masthead .brand-mark { width: 24px; height: 24px; }
      .pt-masthead .all { font-size: 12px; }
      .pt-home .domain-section h2 { font-size: 27px; }
    }
    .pt-home li { padding: 14px 0; border-bottom: 1px solid #E6E3DC; }
    .pt-home li:first-child { border-top: 1px solid #E6E3DC; }
    .pt-home li a { color: #1B1B1B; text-decoration: none; border-bottom: 1px solid #E6E3DC; }
    .pt-home li a:hover { border-bottom-color: #E3120B; }
    .pt-home li a em { font-style: normal; color: #E3120B; font-weight: 600; }
    .pt-home li .n { color: #8A877F; font-family: "IBM Plex Sans", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif; font-size: 14px; margin-left: 8px; }
    .pt-home p { font-size: 16px; color: #5C5C5C; max-width: 66ch; }
    .pt-home .collection-footer { margin-top: 28px; padding-top: 14px; border-top: 1px solid #E6E3DC; }
    .pt-home .collection-footer p { margin: 0 0 8px; font-size: 12.5px; line-height: 1.65; color: #8A877F; max-width: 78ch; }
    .pt-home .collection-footer a { color: #5C5C5C; border-bottom: 1px solid #E6E3DC; }
    .pt-home .collection-footer summary { cursor: pointer; color: #5C5C5C; font-size: 12.5px; }
    .pt-home .collection-footer details[open] p { margin-top: 10px; }
    </style>""",
    unsafe_allow_html=True,
)


def home_page(available: dict[str, dict]) -> str:
    parts = [
        f'<div class="pt-home" lang="{LANG}"><div class="kicker">{t(TAGLINE)}</div>',
        f'<h1>{t("What a field talks about, year by year")}</h1>',
        f'<p class="lede">{escape(t("Follow keyword and topic trends, and see who publishes."))}</p>',
        f'<p class="collection-note">{escape(t("Curated conferences, growing over time."))}</p>',
        '<nav class="domain-jump" aria-label="' + ("研究领域" if LANG == "zh" else "Research domains") + '">',
    ]
    navigation = nav_for(available)
    for index, (domain, _) in enumerate(navigation):
        parts.append(f'<a href="#domain-{index}">{escape(t(domain))}</a>')
    parts.append('</nav><div class="domains">')
    for index, (domain, directions) in enumerate(navigation):
        parts.append(f'<section class="domain-section" id="domain-{index}"><h2>{escape(t(domain))}</h2><div class="directions">')
        for direction, items in directions:
            parts.append('<section class="direction">' + (f'<h3>{escape(t(direction))}</h3>' if direction else '') + '<ul>')
            for slug_, short, name, n in items:
                tail = f"{n:,} {t('papers')}" if n else ("尚未获取数据，点击获取" if LANG == 'zh' else "not fetched yet — open to fetch")
                parts.append(f'<li><a href="?conference={escape(slug_)}&amp;lang={LANG}" target="_self"><em>{escape(short)}</em> — {escape(name)}</a><span class="n">{tail}</span></li>')
            parts.append("</ul></section>")
        parts.append("</div></section>")
    parts.append("</div>")
    parts.append('<h2>探索其他会议</h2><p>输入 OpenAlex 使用的会议英文名并按回车；若无法匹配，可在“选项”中添加 DOI 前缀。获取的数据会缓存，供后续使用。在会议页面切换到“探索”，可查看数据表、关键词对应论文，以及跨会议比较。</p>' if LANG == 'zh' else (
        "<h2>Your own conference</h2><p>Type any conference name in the search box above, as OpenAlex spells it, and press Enter; if the name "
        "does not match an OpenAlex source, add its DOI prefix under Options. Fetching takes a minute or two for most venues, and the data stays "
        "cached on this machine. On a conference page, switch the view to <b>Explore</b> for tables, the papers behind any term, and cross-conference comparison.</p>"
    ))
    parts.append(
        f'<footer class="collection-footer"><p>{escape(t("Data source"))}{"：" if LANG == "zh" else ": "}'
        '<a href="https://openalex.org" target="_blank" rel="noopener">OpenAlex</a></p>'
        f'<details><summary>{escape(t("About this collection"))}</summary>'
        f'<p>{escape(t("This directory features selected conferences, not a complete list. Paper counts reflect available OpenAlex records and may differ from official proceedings; the number of listed conferences does not indicate the size of a field."))}</p>'
        '</details></footer></div>'
    )
    return "".join(parts)


def masthead(on_conference: bool) -> str:
    """Brand and tagline; on a conference page, a way back to the list. The conferences
    themselves live on the home page (the tool is for any venue, the presets are examples)."""
    # the home page says the tagline in its kicker, so the masthead carries it only elsewhere
    rest = f'<span class="tagline">{t(TAGLINE)}</span><a class="all" href="?lang={LANG}" target="_self">{t("All conferences →")}</a>' if on_conference else ""
    languages = '<span class="pt-language" aria-label="Language / 语言">' + links_row([('中文', link(lang='zh'), LANG == 'zh'), ('English', link(lang='en'), LANG == 'en')]) + '</span>'
    return f'<nav class="pt-masthead"><a class="brand" href="?lang={LANG}" target="_self">{logo_svg()}<span>paper-trends</span></a>{rest}{languages}</nav>'

# OpenAlex credentials: environment first, then Streamlit secrets (hosted demo).
for _var in ("OPENALEX_MAILTO", "OPENALEX_API_KEY"):
    if not os.environ.get(_var):
        try:
            os.environ[_var] = st.secrets[_var]
        except Exception:
            pass


# ---- data access -------------------------------------------------------------------


@st.cache_resource
def fetch_lock() -> threading.Lock:
    return threading.Lock()


def corpus_path(slug: str) -> Path:
    return DATA_DIR / f"{slug}.jsonl"


@st.cache_data(show_spinner=False)
def load_records(path: str, mtime: float) -> list[dict]:
    return read_jsonl(Path(path))


@st.cache_data(show_spinner=False)
def corpus_size(path: str, mtime: float) -> int:
    with open(path, "rb") as fh:
        return sum(1 for line in fh if line.strip())


def available_corpora() -> dict[str, dict]:
    """Every preset conference, for the masthead and the home page; `n_papers` is 0 until
    its data has been fetched on this machine (the page then offers the fetch)."""
    out = {}
    for label, cfg in PRESETS.items():
        cp = corpus_path(cfg["slug"])
        n = corpus_size(str(cp), cp.stat().st_mtime) if cp.exists() else 0
        out[cfg["slug"]] = {"name": cfg["query"] if cfg["slug"] not in FULL else FULL[cfg["slug"]], "n_papers": n}
    return out


def records_for(slug: str) -> list[dict] | None:
    p = corpus_path(slug)
    if not p.exists():
        return None
    return load_records(str(p), p.stat().st_mtime)


def run_fetch(query: str, doi_prefixes: list[str], slug: str) -> None:
    lock = fetch_lock()
    if not lock.acquire(blocking=False):
        st.warning(t("Another fetch is running on this server. Please retry in a minute."))
        return
    try:
        with st.status(t("Fetching “{query}” from OpenAlex…", query=query), expanded=True) as status:
            lines: list[str] = []
            box = st.empty()

            def log(msg: str) -> None:
                lines.append(msg)
                box.code("\n".join(lines[-12:]))

            client = OpenAlex()
            records = fetch_conference(client, query, doi_prefix=doi_prefixes, years=FETCH_YEARS, log=log)
            write_jsonl(records, corpus_path(slug), fetched_at=datetime.now(timezone.utc))
            status.update(label=t("Fetched {count:,} papers → {path}", count=len(records), path=corpus_path(slug)), state="complete", expanded=False)
        st.code(coverage_table(records))
        load_records.clear()
        st.rerun()
    except OpenAlexError as e:
        st.error(t("Unable to fetch data from OpenAlex. Details: {error}", error=str(e)))
    except Exception as e:  # never dump a traceback (it would include request URLs) into the UI
        st.error(t("Fetch failed: {error}. Check your network and try again in a minute.", error=type(e).__name__))
    finally:
        lock.release()


# ---- cached analyses ---------------------------------------------------------------


@st.cache_data(show_spinner=t("Counting keywords…"))
def cached_keywords(path: str, mtime: float, years: tuple[int, int], text: str, ngram: tuple[int, int], extra_stop: str,
                    basis: str = "topical", keep_common: bool = False):
    """Count phrases with reviewed boilerplate and case-aware plurals (revision 5)."""
    recs = filter_years(load_records(path, mtime), years)
    stop = load_stopwords(extra_stop.split())
    return compute_trends(recs, text=text, n_min=ngram[0], n_max=ngram[1], stopwords=stop, basis=basis,
                          field=field_of(Path(path).stem), keep_common=keep_common)


@st.cache_data(show_spinner=t("Fitting topic model…"))
def cached_topics(path: str, mtime: float, years: tuple[int, int], method: str, n_topics: int, extra_stop: str):
    recs = filter_years(load_records(path, mtime), years)
    if method == "nmf":
        return compute_nmf(recs, n_topics=n_topics, stopwords=load_stopwords(extra_stop.split()))
    return compute_openalex(recs, level="subfield" if method.endswith("subfield") else "topic")


@st.cache_data(show_spinner=t("Looking the conference up in OpenAlex…"), ttl=3600)
def cached_resolve(text: str) -> dict | None:
    """Use conservative short-name and DOI-prefix matching (resolver revision 2)."""
    try:
        return resolve_venue(OpenAlex(), text)
    except OpenAlexError as e:
        return {"error": str(e)}


@st.cache_data(show_spinner=t("Writing the report…"))
def cached_report_data(path: str, mtime: float, years: tuple[int, int], name: str, slug: str, extra_stop: str,
                       provenance: dict | None = None, default_span: int | None = None,
                       calendar_year: int | None = None, explore_term: str = "", explorer_full: bool = False) -> dict:
    """Share the same analysis between languages (report data revision 1)."""
    recs = load_records(path, mtime)
    return build_report(recs, name=name, slug=slug, years=years, stopwords=load_stopwords(extra_stop.split()),
                     provenance=provenance, default_span=default_span, explore_term=explore_term, explorer_full=explorer_full)


@st.cache_data(show_spinner=False)
def cached_report_html(path: str, mtime: float, years: tuple[int, int], name: str, slug: str, extra_stop: str,
                       provenance: dict | None = None, default_span: int | None = None,
                       calendar_year: int | None = None, lang: str = "en", explore_href: str = "",
                       asset_version: tuple[tuple[str, int], ...] = ()) -> str:
    """Render a language-specific report without changing analysis (revision 13)."""
    r = cached_report_data(path, mtime, years, name, slug, extra_stop, provenance, default_span, calendar_year)
    return render_page(r, None, embedded=True, app_links=True, lang=lang, explore_href=explore_href)


@st.cache_data(show_spinner=False)
def cached_explorer_html(path: str, mtime: float, years: tuple[int, int], name: str, slug: str, extra_stop: str,
                         provenance: dict | None = None, default_span: int | None = None,
                         calendar_year: int | None = None, lang: str = "en", initial_term: str = "",
                         asset_version: tuple[tuple[str, int], ...] = ()) -> str:
    """Focused time-window workspace, sharing exactly the report's analysis data."""
    r = cached_report_data(path, mtime, years, name, slug, extra_stop, provenance, default_span, calendar_year,
                           initial_term, True)
    return render_explorer_page(r, lang=lang, initial_term=r["explore_term"])


@st.cache_data(show_spinner=t("Ranking…"))
def cached_ranking(path: str, mtime: float, years: tuple[int, int], entity: str, roll_up: bool = False):
    return compute_ranking(filter_years(load_records(path, mtime), years), entity, roll_up=roll_up)


# ---- charts: the report's Vega-Lite specs, rendered by Streamlit -------------------------


def vl(spec: dict, key: str | None = None) -> None:
    st.vega_lite_chart(chart_labels(spec, LANG), width="stretch", theme=None, key=key)


def source_line() -> None:
    st.markdown('<p class="pt-source">' + ('来源：' if LANG == 'zh' else 'Source: ') + 'OpenAlex · paper-trends</p>', unsafe_allow_html=True)


def figure_head(title: str, sub: str | None = None) -> None:
    st.markdown(f'<div class="pt-fig"><span class="headline">{escape(t(title))}</span>' + (f'<span class="sub">{escape(t(sub))}</span>' if sub else "") + "</div>", unsafe_allow_html=True)


def ranking_rows(rk, keys: list[str], value: str = "papers") -> list[dict]:
    rows = []
    for k in keys:
        e, l, d = rk.momentum(k)
        rows.append({"name": rk.names[k], "papers": rk.total(k), "citations": rk.citations.get(k, 0), "early": e, "late": l, "delta": d})
    return rows


def html_table(df: pd.DataFrame, pct: list[str] | None = None, links: list[str] | None = None, max_rows: int | None = None, signed: list[str] | None = None) -> None:
    """A table in the report's style (hairline rows, small-caps header, tabular figures).
    `pct` columns hold fractions; signed changes print as percentage points;
    `links` columns hold URLs; numeric columns right-align."""
    import html as _html

    pct, links, signed = set(pct or []), set(links or []), set(signed or [])
    plain = {c for c in df.columns if any(w in str(c).lower() for w in ("year", "seen"))} | {c for c in df.columns if str(c).isdigit()}  # years: no thousands separator
    shown = df if max_rows is None else df.head(max_rows)
    numeric = {c for c in df.columns if c in pct or pd.api.types.is_numeric_dtype(df[c])}
    head = "".join(f'<th class="{"num" if c in numeric else ""}">{_html.escape(field_label(str(c), LANG))}</th>' for c in df.columns)
    rows = []
    for _, r in shown.iterrows():
        cells = []
        for c in df.columns:
            v = r[c]
            if c in pct:
                if pd.isna(v):
                    txt = ""
                elif c in signed:
                    txt = f"{v * 100:+.1f}" + (" 个百分点" if LANG == "zh" else " pp")
                else:
                    txt = f"{v:.1%}"
            elif c in links and isinstance(v, str) and v:
                txt = f'<a href="{_html.escape(v)}" target="_blank" rel="noopener">{_html.escape(v.replace("https://doi.org/", ""))}</a>'
            elif isinstance(v, float):
                txt = "" if pd.isna(v) else (f"{v:.0f}" if c in plain else f"{v:,.0f}")
            elif isinstance(v, (int,)) or (hasattr(v, "item") and not isinstance(v, str)):
                try:
                    txt = f"{int(v)}" if c in plain else f"{int(v):,}"
                except (TypeError, ValueError):
                    txt = _html.escape(str(v))
            else:
                txt = _html.escape("" if v is None else str(v))
            cells.append(f'<td class="{"num" if c in numeric else ""}">{txt}</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    more_text = f'显示 {len(shown):,} / {len(df):,} 行。' if LANG == 'zh' else f'Showing {len(shown):,} of {len(df):,} rows.'
    more = f'<p class="pt-source">{more_text}</p>' if max_rows is not None and len(df) > max_rows else ""
    st.markdown(f'<div class="pt-table-wrap"><table class="pt-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{more}', unsafe_allow_html=True)


def pct_cols(df: pd.DataFrame, cols) -> dict:
    return {c: st.column_config.NumberColumn(format="%.1f%%") for c in cols}


def as_pct(df: pd.DataFrame, cols) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = out[c] * 100
    return out


# ---- sidebar -----------------------------------------------------------------------

# ---- selection: ?conference=<preset slug> | ?q=<custom name>[&prefix=...] | nothing = home ---------
wanted = st.query_params.get("conference", "")
custom_q = st.query_params.get("q", "")
custom_prefix = st.query_params.get("prefix", "")
available = available_corpora()

masthead_slot = st.empty()  # filled after the search row is resolved, so a new search un-highlights the old venue

# search row: any conference in OpenAlex (the only Streamlit widget on the page)
with st.container(key="controls_search"):
    typed = st.text_input(t("Search"), value=custom_q, placeholder=t("Any conference in OpenAlex — an acronym like DAC or ISCAS, or the name as OpenAlex spells it"),
                          label_visibility="collapsed", key="search")
    if typed.strip() and typed.strip() != custom_q:
        # a new search replaces whatever was selected; update the URL in this run (no st.rerun —
        # a rerun issued right after changing query params can drop the URL update)
        st.query_params.clear()
        st.query_params["lang"] = LANG
        shortcut = next((v["slug"] for k, v in PRESETS.items() if typed.strip().lower() in {
            v["slug"], k.split(" — ")[0].split("· ")[-1].lower(), v["query"].lower(),
            *(alias.lower() for alias in v.get("aliases", [])),
        }), None)
        if shortcut:
            st.query_params["conference"] = shortcut
            wanted, custom_q, custom_prefix = shortcut, "", ""
        else:
            st.query_params["q"] = typed.strip()
            custom_q, wanted, custom_prefix = typed.strip(), "", ""

# URL state beyond the selection
period_key = st.query_params.get("period", "10")
view_key = st.query_params.get("view", "report")
show_options = st.query_params.get("options") == "1"


def link(**changes: str | None) -> str:
    """Current URL with some query parameters changed; None removes one."""
    params = {k: st.query_params.get_all(k) for k in st.query_params}
    params["lang"] = LANG
    for k, v in changes.items():
        if v is None:
            params.pop(k, None)
        else:
            params[k] = v
    # Bound widgets update browser history independently of Python query params.
    # Links rendered in this run must use the actual slider value immediately.
    if params.get("period") in ("custom", ["custom"]) and "years" in st.session_state:
        params["years"] = list(st.session_state["years"])
    return "?" + urlencode(params, doseq=True) if params else "?"


def links_row(items: list[tuple[str, str, bool]]) -> str:
    """items: (label, href, is_current)."""
    return "".join(f'<a href="{escape(h)}" target="_self" class="{"current" if c else ""}">{escape(t(l))}</a>' for l, h, c in items)


# options form (DOI prefix, stopwords, refresh) — shown only when asked for
extra_stop = st.session_state.get("extra_stop_saved", "")
doi_prefix_in = custom_prefix
opt_refresh = False
if show_options:
    with st.container(key="options_form"):
        st.markdown('<div class="pt-options-head">' + t('Options') + ' <a href="' + escape(link(options=None)) + '" target="_self">' + t('close') + '</a></div>', unsafe_allow_html=True)
        o1, o2 = st.columns([1, 1])
        doi_prefix_in = o1.text_input(t("DOI prefix(es) for a custom conference, space-separated"), value=custom_prefix, placeholder="10.1109/dac")
        if doi_prefix_in.strip() != custom_prefix:
            st.query_params["prefix"] = doi_prefix_in.strip()
        stop_in = o2.text_area(t("Extra stopwords, one per line"), value=extra_stop, height=68, help=t("Words to ignore in keyword and topic analyses, e.g. your field's boilerplate."))
        if stop_in != extra_stop:
            st.session_state["extra_stop_saved"] = stop_in
            extra_stop = stop_in
        opt_refresh = st.button(t("Refresh data from OpenAlex"), key="refresh_btn")

masthead_slot.markdown(masthead(bool(wanted or custom_q)), unsafe_allow_html=True)
preset = next((v for v in PRESETS.values() if v["slug"] == wanted), None)
if preset:
    query, doi_prefixes, slug = preset["query"], preset["doi_prefixes"], preset["slug"]
elif custom_q:
    resolved = cached_resolve(custom_q) or {}
    if "error" in resolved:
        st.markdown(f'<div class="pt-note">{escape(t("Unable to look up this conference. Details: {error}", error=resolved["error"]))}</div>', unsafe_allow_html=True)
        resolved = {}
    query = resolved.get("name") or custom_q
    doi_prefixes = (doi_prefix_in or custom_prefix).split() or resolved.get("doi_prefixes", [])
    slug = resolved.get("slug") or "".join(ch for ch in custom_q.lower().replace(" ", "-") if ch.isalnum() or ch == "-")[:40]
else:
    query = slug = ""
    doi_prefixes = []

records = records_for(slug) if slug else None

if opt_refresh and slug:
    run_fetch(query, doi_prefixes, slug)

if not records:
    if slug and custom_q and not resolved:
        st.markdown(f'<div class="pt-found"><div class="kicker">{t("Not found")}</div><div class="name">{escape(custom_q)}</div>'
                    f'<div class="meta">{t("We could not identify this conference reliably. Try its full name, or add a known DOI prefix under Options.")}</div></div>', unsafe_allow_html=True)
        if doi_prefixes:
            with st.container(key="fetch_row"):
                if st.button(t("Fetch by DOI prefix"), key="fetch_prefix_btn"):
                    run_fetch(query, doi_prefixes, slug)
    elif slug:
        if custom_q and resolved:
            meta = t("About {count:,} papers since 2016", count=resolved['n_papers']) + ((" · DOI 前缀 " if LANG == 'zh' else " · DOI prefix ") + ' '.join(resolved['doi_prefixes']) if resolved.get("doi_prefixes") else "") + t(" · not on this machine yet")
            warn = ""
            if resolved.get("ambiguous"):
                warn = '<div class="warn"><b>' + t("Shared prefix.") + '</b> ' + t("This DOI prefix is used by several venues: ") + "; ".join(f"{escape(n)} ({sh:.0%})" for n, sh in resolved["candidates"]) + t(". The fetch will include all of them.") + '</div>'
            card = f'<div class="pt-found"><div class="kicker">{t("Found in OpenAlex")}</div><div class="name">{escape(resolved["name"])}</div><div class="meta">{escape(meta)}</div>{warn}</div>'
        else:
            card = f'<div class="pt-found"><div class="kicker">{t("Not fetched yet")}</div><div class="name">{escape(query)}</div><div class="meta">{t("Not on this machine yet.")}</div></div>'
        st.markdown(card, unsafe_allow_html=True)
        with st.container(key="fetch_row"):
            b1, b2 = st.columns([1, 4])
            if b1.button(t("Fetch from OpenAlex"), key="fetch_btn"):
                run_fetch(query, doi_prefixes, slug)
            b2.markdown('<div style="font-family: IBM Plex Sans, system-ui, sans-serif; color: #8A877F; font-size: 13px; padding-top: 8px">' + t("One to fifteen minutes depending on the venue's size; the data is then cached on this machine.") + '</div>', unsafe_allow_html=True)
    st.markdown(home_page(available), unsafe_allow_html=True)
    st.stop()

@st.cache_data(show_spinner=False)
def cached_provenance(path: str, mtime: float, metadata_mtime: int | None) -> dict:
    return read_provenance(Path(path))


# ---- controls row: period and view as links, not widgets ---------------------------
all_years = sorted({r["publication_year"] for r in records if r.get("publication_year")})
if not all_years:
    st.info(t("No papers with a publication year are available in this corpus."))
    st.stop()
recommended = default_period(records)
fallback = (all_years[0], all_years[-1])
periods = {
    "10": ("Last 10 years", recommended or fallback),
    "5": ("Last 5 years", default_period(records, 5) or fallback),
    "all": (f"{'全部' if LANG == 'zh' else 'All'} {all_years[0]}–{all_years[-1]}", (all_years[0], all_years[-1])),
    "custom": ("Custom", None),
}
if period_key not in periods:
    period_key = "10"
mode = "Explore" if view_key == "explore" else "Report"
controls_slot = st.empty()
if period_key == "custom" and len(all_years) > 1:
    with st.container(key="custom_period"):
        years = st.slider(t("Years"), all_years[0], all_years[-1], fallback,
                          label_visibility="collapsed", key="years", bind="query-params")
elif period_key == "custom":
    years = fallback
else:
    years = periods[period_key][1]
# Render links after bound widgets have synchronized the URL, including both range endpoints.
masthead_slot.markdown(masthead(True), unsafe_allow_html=True)
row = (
    f'<nav class="pt-controls" aria-label="{escape(t("Report controls"))}">'
    + f'<div class="pt-control-group"><span class="lbl">{t("Period")}</span><span class="pt-control-links">'
    + links_row([(lbl, link(period=k), k == period_key) for k, (lbl, _) in periods.items()]) + '</span></div>'
    + f'<div class="pt-control-group"><span class="lbl">{t("View")}</span><span class="pt-control-links">'
    + links_row([("Report", link(view=None), mode == "Report"), ("Explore", link(view="explore"), mode == "Explore")]) + '</span></div>'
    + '<div class="pt-control-actions">' + links_row([("Options", link(options="1"), show_options)]) + '</div>'
    + "</nav>"
)
controls_slot.markdown(row, unsafe_allow_html=True)
path, mtime = str(corpus_path(slug)), corpus_path(slug).stat().st_mtime
meta_path = metadata_path(Path(path))
provenance = cached_provenance(path, mtime, meta_path.stat().st_mtime_ns if meta_path.exists() else None)
default_span = int(period_key) if period_key in {"10", "5"} else None
recs = filter_years(records, years)
if not recs:
    st.info(t("No papers in the selected period. Choose another range."))
    st.stop()
cov_y = frames.coverage_frame(recs)

if mode == "Report":
    loading_slot = st.empty()
    with loading_slot.container(key="report_loading"):
        st.markdown(
            f'<div class="pt-report-loading"><div class="kicker">{escape(t("Generating report"))}</div>'
            f'<h2>{escape(SHORT.get(slug) or query)}</h2><p>{escape(t("Analyzing keywords, topics and publishing institutions. Large conferences may take tens of seconds."))}</p></div>',
            unsafe_allow_html=True,
        )
        with st.skeleton(height=360):
            report_html = cached_report_html(path, mtime, years, query, slug, extra_stop, provenance, default_span,
                                             date.today().year, LANG, link(view="explore", section=None, term=None),
                                             report_asset_version())
    loading_slot.empty()
    st.iframe(report_html, height="content")
    st.stop()

data_coverage = coverage_details(records, years, default_span=default_span)
coverage_open = st.query_params.get("coverage") == "1"
section = st.query_params.get("section", "trends")
section = {"overview": "trends", "keywords": "trends", "rankings": "institutions", "data": "papers"}.get(section, section)
SECTIONS = [("trends", "Trends & evidence"), ("topics", "Topic analysis"), ("institutions", "Institution analysis"),
            ("compare", "Compare conferences"), ("papers", "Papers & export")]
if section not in dict(SECTIONS):
    section = "trends"
short_name = SHORT.get(slug)
display_name = short_name or query
full_name = f'<div class="full-name">{escape(query)}</div>' if short_name and short_name != query else ""
coverage_href = link(coverage=None if coverage_open else "1")
coverage_label = t("Hide data details" if coverage_open else "Data definition and annual coverage")
coverage_marker = "↑" if coverage_open else "›"
st.markdown(
    f'<header class="pt-head"><div class="pt-head-grid"><div class="pt-head-identity">'
    f'<div class="kicker">{escape(t("Explore"))} · {years[0]}–{years[1]}</div>'
    f'<h1>{escape(display_name)}</h1>{full_name}</div>'
    f'<div class="pt-head-stats" aria-label="{escape(t("Conference summary"))}">'
    f'<span><b>{len(recs):,}</b><small>{escape(t("papers"))}</small></span>'
    f'<span><b>{years[1] - years[0] + 1}</b><small>{escape(t("editions"))}</small></span>'
    f'<span><b>{cov_y["abstracts"].sum() / max(len(recs), 1):.0%}</b><small>{escape(t("with abstracts"))}</small></span>'
    f'</div></div><div class="pt-head-provenance"><span>{escape(t(provenance_label(provenance)))}</span>'
    f'<span>{escape(t(data_coverage["selection"]))}</span>'
    f'<a href="{escape(coverage_href, quote=True)}" target="_self" aria-expanded="{str(coverage_open).lower()}">{escape(coverage_label)} {coverage_marker}</a>'
    f'</div></header>',
    unsafe_allow_html=True,
)
if data_coverage["notices"] or coverage_open:
    with st.container(key="explore_context"):
        for message in data_coverage["notices"]:
            st.markdown(f'<p class="pt-coverage-notice">{escape(t(message))}</p>', unsafe_allow_html=True)
        if coverage_open:
            table_rows = "".join(
                f'<tr><td>{row["year"]}</td><td>{row["papers"]:,}</td><td>{row["abstracts"]:,}</td>'
                f'<td>{row["coverage"]:.0%}</td></tr>' if row["coverage"] is not None else
                f'<tr><td>{row["year"]}</td><td>{row["papers"]:,}</td><td>{row["abstracts"]:,}</td><td>—</td></tr>'
                for row in data_coverage["rows"]
            )
            exclusions = "".join(
                f'<p class="exclusion">{escape(t(item["message"]))}</p>'
                for item in data_coverage["exclusions"]
            )
            st.markdown(
                f'<section class="pt-coverage-panel"><h2>{escape(t("Data definition and annual coverage"))}</h2>'
                f'<p class="caveat">{escape(t(data_coverage["caveat"]))}</p>{exclusions}'
                f'<table class="pt-coverage-table"><thead><tr>'
                f'<th>{escape(field_label("year", LANG))}</th><th>{escape(field_label("papers", LANG))}</th>'
                f'<th>{escape(field_label("abstracts", LANG))}</th><th>{escape(field_label("coverage", LANG))}</th>'
                f'</tr></thead><tbody>{table_rows}</tbody></table></section>',
                unsafe_allow_html=True,
            )
st.markdown(
    f'<nav class="pt-sections" aria-label="{escape(t("Explore sections"))}">'
    + links_row([(lbl, link(section=None if k == "trends" else k), k == section) for k, lbl in SECTIONS])
    + "</nav>",
    unsafe_allow_html=True,
)


def h2(text: str, lede: str | None = None) -> None:
    st.markdown(f'<h2 class="pt-h2">{t(text)}</h2>' + (f'<p class="pt-lede">{t(lede)}</p>' if lede else ""), unsafe_allow_html=True)


def note(text: str) -> None:
    st.markdown(f'<p class="pt-lede">{t(text)}</p>', unsafe_allow_html=True)


def section_head(title: str, description: str) -> None:
    st.markdown(
        f'<header class="pt-section-head"><h2 class="pt-h2">{escape(t(title))}</h2>'
        f'<p class="pt-lede">{escape(t(description))}</p></header>', unsafe_allow_html=True,
    )


with st.container(key="explore_body"):
    if len(cov_y) < 2 and section == "compare":
        st.info(t("Comparisons over time need at least two years. Open Papers & export to see the papers in this period."))
        st.stop()

    if section == "trends":
        section_head("Trends & evidence", "Follow keywords over time and read the papers behind their trends.")
        # This search adds a phrase to the observatory; the observatory owns the one
        # active term/window/rule used by its chart, complete evidence and CSV export.
        def find_phrase():
            phrase = st.session_state.get("phrase_search_input", "").strip()
            if phrase:
                st.query_params["term"] = phrase

        with st.container(key="phrase_tool"):
            with st.form("phrase_search", clear_on_submit=True):
                st.markdown(f'<div class="pt-phrase-label">{escape(t("Custom phrase"))}</div>', unsafe_allow_html=True)
                phrase_input, phrase_action = st.columns([6, 1.15], gap="small", vertical_alignment="bottom")
                with phrase_input:
                    phrase = st.text_input(
                        t("Custom phrase"), placeholder=t("Type a two- or three-word phrase"),
                        key="phrase_search_input", label_visibility="collapsed",
                    )
                with phrase_action:
                    st.form_submit_button(t("Analyze phrase"), on_click=find_phrase, width="stretch", key="phrase_submit")
        initial_term = st.query_params.get("term", "")
        loading_slot = st.empty()
        with loading_slot.container(key="explore_loading"):
            st.markdown(
                f'<div class="pt-explore-loading"><span class="kicker">{escape(t("Preparing exploration"))}</span>'
                f'<p>{escape(t("Building trends, paper evidence and interactive charts…"))}</p></div>',
                unsafe_allow_html=True,
            )
            with st.skeleton(height=360):
                explorer_html = cached_explorer_html(
                    path, mtime, years, query, slug, extra_stop, provenance, default_span,
                    date.today().year, LANG, initial_term, report_asset_version(),
                )
        loading_slot.empty()
        st.iframe(explorer_html, height="content")

    if section == "topics":
        section_head("Topic analysis", "Choose a topic method and follow how the research mix changes over time.")
        with st.container(key="explore_controls"):
            o1, o2 = st.columns([1, 1], vertical_alignment="bottom")
            method = o1.selectbox(t("Method"), ["nmf", "openalex", "openalex-subfield"], format_func=lambda m: t({"nmf": "NMF on titles + abstracts", "openalex": "OpenAlex topic labels", "openalex-subfield": "OpenAlex subfields"}[m]))
            n_topics = o2.slider(t("Topics (NMF)"), 6, 20, 8, disabled=method != "nmf")
        try:
            tt = cached_topics(path, mtime, years, method, n_topics, extra_stop)
        except InsufficientTopicData as exc:
            st.info(t(str(exc)))
            st.stop()
        ordered = tt.ordered()
        if not ordered:
            st.info(t("No topic data is available for the selected papers."))
            st.stop()
        topic_rows = [{"topic": t.label, "year": y, "share": tt.share(t.id, y)} for t in ordered for y in tt.years]
        figure_head("Share of papers by dominant topic", "Each paper assigned to its strongest topic; smaller topics folded into “Other”")
        if len(tt.years) > 1:
            vl(charts.streamgraph(topic_rows, [t.label for t in ordered], tt.years), key="topics-stream")
        source_line()
        ttab = frames.topic_table(tt)
        if len(tt.years) < 2:
            ttab = ttab.drop(columns=["early", "late", "delta"], errors="ignore")
        html_table(ttab, pct=["early", "late", "delta"], signed=["delta"])
        if method == "nmf":
            note("Topics are fitted with NMF on TF-IDF (fixed seed, reproducible). Labels are the top terms; each paper is assigned to its strongest topic.")

    if section == "institutions":
        section_head("Institution analysis", "Compare publication rankings and changes in research participation.")
        with st.container(key="explore_controls"):
            o1, o2 = st.columns(2, vertical_alignment="bottom")
            entity = o1.selectbox(t("Rank"), ENTITIES, format_func=lambda value: t(value) if LANG == 'zh' else value.title())
            sort_by = o2.selectbox(t("Sort by"), ["papers", "citations"], format_func=lambda value: field_label(value, LANG))
            o3, o4 = st.columns(2, vertical_alignment="bottom")
            top_n = o3.slider(t("Show top"), 10, 50, 20)
            with o4:
                st.markdown(f'<div class="pt-control-label">{escape(t("Affiliation grouping"))}</div>', unsafe_allow_html=True)
                roll_up = st.toggle(t("Roll up to parent institutions"), value=True, disabled=entity != "institution",
                                    help=t("Credit the top-level parent from OpenAlex's lineage: A*STAR instead of IME, Chinese Academy of Sciences instead of its institutes."))
        rk = cached_ranking(path, mtime, years, entity, roll_up and entity == "institution")
        keys = rk.top(top_n, by=sort_by)
        table = frames.ranking_table(rk, keys)
        figure_head(f"{t(entity)}排名 · 按{field_label(sort_by, LANG)}" if LANG == 'zh' else f"Top {entity}s by {sort_by}", "前三名标红；箭头表示前后半时段的论文占比变化" if LANG == 'zh' else "Top three in red; the arrow is the change in share of papers between the two halves of the period")
        rows_r = ranking_rows(rk, keys)
        if entity == "country":
            rows_r = [{**r, "name": country_name(r["name"])} for r in rows_r]
        vl(charts.ranked_bars(rows_r, value=sort_by, show_change=len(cov_y) > 1), key=f"rank-{entity}-{sort_by}")
        source_line()
        html_table(table.assign(**({entity: table[entity].map(country_name)} if entity == "country" else {})))
        if entity == "institution" and st.toggle(t("More institution analysis"), key="institution_details"):
            detail_keys = keys[:8]
            st.caption("以下分析展示当前排名的前 8 家机构。" if LANG == "zh" else "The analyses below show up to eight institutions from the current ranking.")
            if len(rk.years) > 1 and detail_keys:
                figure_head("Institution rank over time", "Ranks use a centered three-year paper count among the displayed institutions, regardless of the table sort order.")
                rank_rows = inst_rank_rows(rk, detail_keys, rk.years)
                vl(charts.bump_chart(rank_rows, rk.years, len(detail_keys)), key="institution-rank-history")
                with st.expander(t("Institution rank over time")):
                    html_table(pd.DataFrame(rank_rows)[["name", "year", "rank", "papers"]], max_rows=None)
            figure_head("Institution research profiles", "Each row shows the topic mix among an institution's papers with topic assignments. Parent roll-up follows the switch above.")
            try:
                institution_topics = cached_topics(path, mtime, years, "nmf", 8, extra_stop)
            except InsufficientTopicData as exc:
                st.info(t(str(exc)))
            else:
                ordered = institution_topics.ordered()
                if ordered and detail_keys:
                    mix = inst_topic_rows(recs, institution_topics, rk, detail_keys, ordered, roll_up=roll_up)
                    labels = [topic.label for topic in ordered[:len(charts.TOPIC_COLORS)]]
                    if len(ordered) > len(charts.TOPIC_COLORS):
                        labels.append("Other")
                    vl(charts.inst_topic_heatmap(mix, [rk.names[k] for k in detail_keys], labels), key="institution-topic-mix")
                    with st.expander(t("Institution research profiles")):
                        html_table(pd.DataFrame(mix), pct=["share"], max_rows=None)
                else:
                    st.info(t("No topic data is available for the selected papers."))
        if len(cov_y) < 2:
            st.info(t("Changes in share need at least two years."))
            st.stop()
        r, f = st.columns(2)
        r.markdown('<h2 class=\"pt-h2\">' + t("Gaining share") + '</h2>', unsafe_allow_html=True)
        with r:
            html_table(frames.ranking_movers(rk, rk.movers(10, 10, rising=True)), pct=["early", "late", "delta"], signed=["delta"])
        f.markdown('<h2 class=\"pt-h2\">' + t("Losing share") + '</h2>', unsafe_allow_html=True)
        with f:
            html_table(frames.ranking_movers(rk, rk.movers(10, 10, rising=False)), pct=["early", "late", "delta"], signed=["delta"])
        note("A paper counts once per entity (full counting). Institution ids come from OpenAlex affiliation matching, which is imperfect: treat close ranks as ties.")

    if section == "compare":
        section_head("Compare conferences", "Compare the share of the same phrase across conferences.")
        local = {k: v for k, v in PRESETS.items() if v["slug"] != slug and corpus_path(v["slug"]).exists()}
        text_mode = "title+abstract" if cov_y["abstracts"].sum() / max(len(recs), 1) >= 0.6 else "title"
        with st.container(key="explore_controls"):
            others = st.multiselect(t("Compare with"), list(local), default=list(local)[:2], format_func=lambda k: " · ".join(t(part) for part in k.split(" — ")[0].split(" · ")))
            kt_here = cached_keywords(path, mtime, years, text_mode, (2, 3), extra_stop, "topical", True)   # comparisons keep cross-field phrases
            default_terms = [t for t, *_ in kt_here.rising(4, min_total=10)]
            cmp_terms = st.multiselect(t("Terms"), kt_here.top_terms(300), default=default_terms, key="cmp_terms")
        st.markdown(
            f'<p class="pt-method-note"><b>{escape(t("Comparison basis"))}</b>'
            f'{escape(t("Same years, text range and counting rule; missing editions remain missing."))} '
            f'{escape(t("Only conferences with cached data are available."))}</p>', unsafe_allow_html=True,
        )
        if others and cmp_terms:
            trends = {SHORT.get(slug, query): kt_here}
            for k in others:
                cp = corpus_path(local[k]["slug"])
                trends[k.split(" — ")[0].split("· ")[-1]] = cached_keywords(str(cp), cp.stat().st_mtime, years, text_mode, (2, 3), extra_stop, "topical", True)
            df = pd.DataFrame(compare.term_shares(trends, cmp_terms))
            names = list(trends)
            yrs = sorted(df["year"].unique().tolist())
            cols = st.columns(2)
            for i, term in enumerate(cmp_terms):
                rows_t = [{"name": r["conference"], "year": r["year"], "share": r["share"], "papers": r["papers"]} for r in df[df["term"] == term].to_dict("records")]
                with cols[i % 2]:
                    vl(charts.multi_line(rows_t, names, yrs, title=term), key=f"cmp-{term}")
            source_line()
            wide = df.pivot_table(index=["term", "conference"], columns="year", values="share").reset_index()
            wide.columns = [str(c) for c in wide.columns]
            ycols = [c for c in wide.columns if c.isdigit()]
            html_table(wide, pct=ycols)
            common = compare.shared_risers(trends, k=12)
            if common:
                h2("Rising everywhere")
                html_table(pd.DataFrame([{"term": t, **{n: d for n, d in ds.items()}} for t, ds in common]), pct=names, signed=names)
                note("Terms whose share rose in every selected conference, ranked by their smallest gain.")
        elif not others:
            st.info(t("Fetch another preset conference to enable comparison."))

    if section == "papers":
        size_mb = corpus_path(slug).stat().st_size / 1e6
        section_head("Papers & export", "Search titles and abstracts within the selected period, then sort or export the current results.")
        with st.container(key="explore_controls"):
            paper_search, paper_order = st.columns([3, 1.5], vertical_alignment="bottom")
            paper_query = paper_search.text_input(t("Search paper titles and abstracts"), type="search", placeholder=t("Type a phrase, method or application"), key="paper_filter")
            sort_papers = paper_order.segmented_control(t("Sort papers"), ["newest", "cited"], default="newest", format_func=t, key="paper_sort") or "newest"
        needle = paper_query.strip().lower()
        matching = [rec for rec in recs if not needle or needle in f"{rec.get('title') or ''} {rec.get('abstract') or ''}".lower()]
        listing = pd.DataFrame(
            [{"year": rec.get("publication_year"), "title": rec.get("title"), "citations": rec.get("cited_by_count", 0), "doi": rec.get("doi")} for rec in matching],
            columns=["year", "title", "citations", "doi"],
        )
        listing = listing.sort_values(["citations", "year"], ascending=[False, False]) if sort_papers == "cited" else listing.sort_values(["year", "citations"], ascending=[False, False])
        figure_head("Papers in the current result", t("{count:,} papers; sortable and scrollable", count=len(listing)))
        st.dataframe(listing, hide_index=True, width="stretch", height=480,
                     column_config={**{c: field_label(c, LANG) for c in ("year", "title", "citations")}, "doi": st.column_config.LinkColumn(t("doi"))})
        h2("Export")
        note(t('Full corpus: {path} ({size:.0f} MB). Current-result export follows the selected period and paper search.', path=f'<span class="mono">{escape(str(corpus_path(slug)))}</span>', size=size_mb))
        # Downloads are generated on click (callables), so large corpora are never pushed to the browser on every rerun.
        d0, d1, d2, d3 = st.columns(4)
        d0.download_button(t("Current results (CSV)"), listing.to_csv(index=False), file_name=f"{slug}_{years[0]}-{years[1]}_papers.csv", mime="text/csv", key="dl_results")
        d1.download_button(t("Full corpus (JSONL)"), lambda: corpus_path(slug).read_bytes(), file_name=f"{slug}.jsonl", mime="application/jsonl", key="dl_corpus")
        d2.download_button(
            t("Keyword table (CSV)"),
            lambda: (lambda kt: frames.keyword_table(kt, kt.top_terms(200)).to_csv(index=False))(cached_keywords(path, mtime, years, "title+abstract" if cov_y["abstracts"].sum() / max(len(recs), 1) >= 0.6 else "title", (2, 3), extra_stop)),
            file_name=f"{slug}_keywords.csv", mime="text/csv", key="dl_keywords",
        )
        d3.download_button(
            t("Institution ranking (CSV)"),
            lambda: (lambda rk: frames.ranking_table(rk, rk.top(200)).to_csv(index=False))(cached_ranking(path, mtime, years, "institution", True)),
            file_name=f"{slug}_institutions.csv", mime="text/csv", key="dl_institutions",
        )
