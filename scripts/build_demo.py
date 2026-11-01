"""Build the public ECTC/CVPR report snapshot from existing, git-ignored corpora.

Run `uv run python -m scripts.build_demo`. No network or OpenAlex key is needed.
See docs/demo-deployment.md for preview and publication instructions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from paper_trends.presets import FULL
from paper_trends.report.build import build_report
from paper_trends.report.render import render_site
from paper_trends.store import read_jsonl, read_provenance

VENUES = ("ectc", "cvpr")
YEARS = (2016, 2025)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("site/demo"))
    args = parser.parse_args()
    paths = [args.data_dir / f"{slug}.jsonl" for slug in VENUES]
    for path in paths:
        if not path.is_file():
            parser.error(f"Missing {path}; fetch this corpus before building the demo")
    reports, sources = [], []
    for slug, path in zip(VENUES, paths):
        print(f"Building {slug}: {YEARS[0]}–{YEARS[1]}", flush=True)
        provenance = read_provenance(path)
        report = build_report(read_jsonl(path), name=FULL[slug], slug=slug,
                              years=YEARS, n_topics=8, provenance=provenance)
        if report["n_papers"] == 0:
            parser.error(f"No {slug} papers in the demo period")
        reports.append(report)
        sources.append({"slug": slug, "corpus_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "papers_in_period": report["n_papers"], "provenance": provenance})
    render_site(reports, args.out, demo=True)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "source_revision": revision, "years": list(YEARS), "n_topics": 8, "sources": sources}
    (args.out / "demo-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.out / ".nojekyll").touch()
    print(f"Built bilingual reports in {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
