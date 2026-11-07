"""Opt-in live check: ECTC 2019–2020 → cache → reports → CSV → Streamlit.

Run from the repository root with `uv run python -m scripts.smoke_openalex`.
Requires OPENALEX_MAILTO and an activated OPENALEX_API_KEY. Outputs live only in
a temporary directory; this never refreshes the user's existing data/ directory.
"""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv

from paper_trends.openalex import _redact
from paper_trends.store import read_jsonl, read_provenance

ROOT = Path(__file__).resolve().parents[1]
CREDENTIALS = ("OPENALEX_MAILTO", "OPENALEX_API_KEY")


def require_credentials() -> tuple[str, ...]:
    missing = [name for name in CREDENTIALS if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Live smoke check requires: " + ", ".join(missing))
    return tuple(os.environ[name].strip() for name in CREDENTIALS)


def run_cli(args: list[str], workdir: Path, secrets: tuple[str, ...]) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    print(f"Running CLI: {args[0]}", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "paper_trends", *args], cwd=workdir, env=env,
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode:
        output = _redact(result.stdout + "\n" + result.stderr, secrets)
        raise RuntimeError(f"{args[0]} failed (exit {result.returncode}):\n{output[-6000:]}")


def check_outputs(workdir: Path) -> int:
    corpus = workdir / "data/ectc.jsonl"
    records = read_jsonl(corpus)
    if len(records) <= 100:
        raise RuntimeError("Expected more than one API page of ECTC records")
    if {record["publication_year"] for record in records} != {2019, 2020}:
        raise RuntimeError("Fetched corpus does not cover exactly 2019 and 2020")
    if read_provenance(corpus)["status"] != "verified":
        raise RuntimeError("Corpus provenance did not verify")
    for filename in ("ectc.html", "ectc.zh.html"):
        html = (workdir / "site" / filename).read_text(encoding="utf-8")
        if "window.ENTITIES" not in html or "fig-topics" not in html:
            raise RuntimeError(f"Missing report content: {filename}")
    for command in ("keywords", "rank", "topics", "compare"):
        with (workdir / "data" / f"{command}.csv").open(encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        if len(rows) < 2:
            raise RuntimeError(f"Empty CSV export: {command}")
    return len(records)


def check_app(workdir: Path) -> None:
    from streamlit.testing.v1 import AppTest

    previous = Path.cwd()
    try:
        os.chdir(workdir)
        for lang in ("en", "zh"):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
            app.query_params.update(conference="ectc", period="all", lang=lang)
            app.run()
            if app.exception or not any(element.type == "iframe" for element in app):
                raise RuntimeError(f"Streamlit report failed: {lang}")
            app.query_params.update(view="explore", section="trends")
            app.run()
            if app.exception or not any(
                element.type == "iframe" and "obs-chart" in element.proto.srcdoc for element in app
            ):
                raise RuntimeError(f"Streamlit Explore failed: {lang}")
    finally:
        os.chdir(previous)


def main() -> int:
    load_dotenv(ROOT / ".env")
    secrets = tuple(os.environ.get(name, "").strip() for name in CREDENTIALS)
    try:
        require_credentials()
        with TemporaryDirectory(prefix="paper-trends-live-") as directory:
            workdir = Path(directory)
            run_cli(["--help"], workdir, secrets)
            run_cli([
                "fetch", "Electronic Components and Technology Conference",
                "--doi-prefix", "10.1109/ectc", "--years", "2019-2020", "--name", "ectc",
            ], workdir, secrets)
            run_cli([
                "report", "data/ectc.jsonl", "--years", "2019-2020", "--out", "site",
            ], workdir, secrets)
            for command, extra in (
                ("keywords", []), ("rank", ["--by", "institution"]),
                ("topics", ["--n-topics", "4"]), ("compare", ["--term", "hybrid bonding"]),
            ):
                run_cli([
                    command, "data/ectc.jsonl", "--years", "2019-2020",
                    "--csv", f"data/{command}.csv", *extra,
                ], workdir, secrets)
            count = check_outputs(workdir)
            check_app(workdir)
            print(
                f"PASS: {count} live records; pagination, verified provenance, four CSV exports, "
                "bilingual reports and Streamlit Report/Explore.", flush=True,
            )
        return 0
    except Exception as exc:
        print(_redact(f"FAIL: {exc}", secrets), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
