"""`paper-trends` command-line entry point."""

from __future__ import annotations

import sys

COMMANDS = {
    "fetch": "paper_trends.fetch",
    "keywords": "paper_trends.keywords",
    "rank": "paper_trends.rank",
    "topics": "paper_trends.topics",
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help"}:
        print("usage: paper-trends <command> [args]\n\ncommands:")
        for name in COMMANDS:
            print(f"  {name}")
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return 2
    import importlib

    return importlib.import_module(COMMANDS[cmd]).main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
