"""Shared editorial pt mark for the app and portable HTML reports."""

from base64 import b64encode
from pathlib import Path

ASSETS = Path(__file__).parent / "report" / "static"
FAVICON = ASSETS / "favicon.svg"


def logo_svg() -> str:
    """Trusted project-owned markup, independent of installed fonts."""
    return (ASSETS / "logo.svg").read_text(encoding="utf-8")


def favicon_uri() -> str:
    return "data:image/svg+xml;base64," + b64encode(FAVICON.read_bytes()).decode("ascii")
