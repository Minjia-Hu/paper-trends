"""Keep untrusted text cells literal when CSV exports are opened in spreadsheets."""

from collections.abc import Iterable
from typing import Any


def safe_cell(value: Any) -> Any:
    """Prefix formula-like text; preserve numbers, missing values and ordinary text.

    Strip leading spaces/BOM only for detection, retaining the original text in
    the exported cell. Keep this rule in sync with report/static/explorer.js.
    """
    if isinstance(value, str) and value.lstrip(" \ufeff").startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return "'" + value
    return value


def safe_row(values: Iterable[Any]) -> list[Any]:
    return [safe_cell(value) for value in values]
