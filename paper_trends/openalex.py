"""Thin OpenAlex API client: polite pool, cursor paging, retries, abstract reconstruction."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Iterator
from typing import Any

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.openalex.org"
PER_PAGE = 200
MAX_RETRIES = 8
MAX_BACKOFF = 60.0

WORK_FIELDS = [
    "id",
    "doi",
    "title",
    "publication_year",
    "abstract_inverted_index",
    "authorships",
    "cited_by_count",
    "type",
    "is_paratext",
    "primary_location",
    "primary_topic",
    "topics",
    "keywords",
]


class OpenAlexError(RuntimeError):
    pass


def get_api_key() -> str | None:
    """Optional OpenAlex API key (OPENALEX_API_KEY). Without one, requests draw on a free
    daily budget shared by every anonymous user behind the same IP address."""
    load_dotenv()
    return os.environ.get("OPENALEX_API_KEY", "").strip() or None


def get_mailto() -> str:
    """Read the polite-pool contact address from OPENALEX_MAILTO (.env or environment)."""
    load_dotenv()
    mailto = os.environ.get("OPENALEX_MAILTO", "").strip()
    if not mailto:
        raise OpenAlexError(
            "OPENALEX_MAILTO is not set. Put OPENALEX_MAILTO=you@example.com in .env "
            "or export it in your shell."
        )
    return mailto


class OpenAlex:
    def __init__(self, mailto: str | None = None, session: requests.Session | None = None, api_key: str | None = None):
        self.mailto = mailto or get_mailto()
        self.api_key = api_key or get_api_key()
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = f"paper-trends (mailto:{self.mailto})"
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET with retries on 429/5xx, truncated bodies and connection/TLS errors."""
        params = dict(params or {})
        params["mailto"] = self.mailto
        url = f"{BASE_URL}/{path.lstrip('/')}"
        delay = 1.0
        last = "no response"
        for attempt in range(MAX_RETRIES):
            wait = delay
            try:
                resp = self.session.get(url, params=params, timeout=60)
            except requests.RequestException as e:  # SSL EOF, connection reset, timeout ...
                last = f"{type(e).__name__}: {_redact(str(e))[:200]}"
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        last = "truncated/non-JSON body"
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last = f"HTTP {resp.status_code}"
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        wait = max(wait, float(retry_after))
                    if resp.status_code == 429 and wait > MAX_BACKOFF:
                        # Daily budget exhausted: retrying is pointless until it resets.
                        raise OpenAlexError(_budget_message(resp, self.api_key))
                else:
                    raise OpenAlexError(f"HTTP {resp.status_code} for {_redact(resp.url)}: {resp.text[:300]}")
            if attempt == MAX_RETRIES - 1:
                break
            time.sleep(min(wait, MAX_BACKOFF))
            delay = min(delay * 2, MAX_BACKOFF)
        raise OpenAlexError(
            f"OpenAlex request failed after {MAX_RETRIES} attempts ({last}) for {_redact(url)}. "
            "This is usually a flaky network or OpenAlex rate limiting (HTTP 429): wait a minute and retry."
        )

    def paginate(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Yield every result of a list endpoint using cursor paging."""
        params = dict(params)
        params.setdefault("per-page", PER_PAGE)
        cursor = "*"
        while cursor:
            params["cursor"] = cursor
            page = self.get(path, params)
            yield from page.get("results", [])
            cursor = (page.get("meta") or {}).get("next_cursor")

    # ---- sources -------------------------------------------------------------

    def search_sources(self, query: str) -> list[dict[str, Any]]:
        """All sources whose display name matches `query`."""
        # Commas separate OpenAlex filters, so they cannot appear inside a value; the
        # search is token-based anyway, so dropping them changes nothing.
        query = query.replace(",", " ")
        return list(
            self.paginate(
                "sources",
                {
                    "filter": f"display_name.search:{query}",
                    "select": "id,display_name,type,works_count,issn",
                },
            )
        )

    # ---- works ---------------------------------------------------------------

    def works_by_filter(self, filter_expr: str) -> Iterator[dict[str, Any]]:
        yield from self.paginate(
            "works",
            {"filter": filter_expr, "select": ",".join(WORK_FIELDS)},
        )

    def count_by_year(self, filter_expr: str) -> dict[int, int]:
        page = self.get("works", {"filter": filter_expr, "group_by": "publication_year"})
        return {int(g["key"]): g["count"] for g in page.get("group_by", []) if g["key"]}


def _budget_message(resp: Any, api_key: str | None) -> str:
    try:
        detail = resp.json().get("message", "")
    except ValueError:
        detail = ""
    hours = int(resp.headers.get("Retry-After", "0") or 0) // 3600
    who = "your API key's" if api_key else "the free per-IP"
    hint = (
        "" if api_key else
        " Get a free key (https://help.openalex.org/api/authentication/) and put OPENALEX_API_KEY=... in .env; "
        "anonymous requests share one daily budget with everyone behind your IP address (VPNs/proxies included)."
    )
    return f"OpenAlex rate limit: {who} daily budget is used up (resets in ~{hours} h).{hint} OpenAlex says: {detail[:300]}"


def _redact(text: str) -> str:
    """Strip the mailto address from URLs/messages that may be shown to users."""
    return re.sub(r"mailto=[^&\s'\"]+", "mailto=<redacted>", text)


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str | None:
    """Turn OpenAlex's abstract_inverted_index back into plain text."""
    if not inverted:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted.items():
        positions.extend((i, word) for i in idxs)
    positions.sort()
    return " ".join(word for _, word in positions)


def year_filter(years: tuple[int, int] | None) -> str:
    if not years:
        return ""
    lo, hi = years
    return f",publication_year:{lo}-{hi}"
