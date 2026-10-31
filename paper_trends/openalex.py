"""Thin OpenAlex API client: polite pool, cursor paging, retries, abstract reconstruction."""

from __future__ import annotations

import os
import re
import time
import math
from collections.abc import Iterator
from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, quote_plus

import requests
from dotenv import load_dotenv

BASE_URL = "https://api.openalex.org"
PER_PAGE = 100
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
    """Read the API key required for cursor paging beyond the first page.

    Basic anonymous queries share a small daily budget with the caller's IP.
    """
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
                last = f"{type(e).__name__}: {_redact(str(e), (self.mailto, self.api_key))[:200]}"
            else:
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except ValueError:
                        last = "truncated/non-JSON body"
                elif resp.status_code == 401:
                    if not self.api_key:
                        raise OpenAlexError(
                            "OpenAlex requires an API key for complete fetches: cursor paging "
                            "beyond the first page is unavailable without one (HTTP 401). "
                            "Get a free key at https://help.openalex.org/api/authentication/ "
                            "and set OPENALEX_API_KEY in .env or the environment."
                        )
                    raise OpenAlexError(
                        "OpenAlex rejected the API key (HTTP 401). Check that OPENALEX_API_KEY "
                        "is valid and activated, or replace it in .env or the environment. "
                        "See https://help.openalex.org/api/authentication/."
                    )
                elif resp.status_code == 429 or resp.status_code >= 500:
                    last = f"HTTP {resp.status_code}"
                    retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
                    if retry_after is not None:
                        wait = max(wait, retry_after)
                    if resp.status_code == 429 and (wait > MAX_BACKOFF or _budget_exhausted(resp)):
                        # Do not hammer a spent daily budget or truncate a long cooldown
                        # into several immediate retries. The caller can try again later.
                        raise OpenAlexError(_redact(
                            _budget_message(resp, self.api_key, retry_after),
                            (self.mailto, self.api_key),
                        )[:800])
                else:
                    message = f"HTTP {resp.status_code} for {resp.url}: {resp.text}"
                    raise OpenAlexError(_redact(message, (self.mailto, self.api_key))[:500])
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


def _retry_after_seconds(value: str | None, *, now: float | None = None) -> float | None:
    """Accept HTTP Retry-After dates and finite, nonnegative delay seconds."""
    if not value:
        return None
    try:
        seconds = float(value.strip())
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0.0, date.timestamp() - (time.time() if now is None else now))
        except (TypeError, ValueError, OverflowError):
            return None


def _response_detail(resp: Any) -> str:
    try:
        body = resp.json()
    except ValueError:
        return ""
    if isinstance(body, dict):
        return str(body.get("message") or body.get("error") or "")
    return ""


def _budget_exhausted(resp: Any) -> bool:
    detail = _response_detail(resp).lower()
    return any(phrase in detail for phrase in (
        "insufficient budget", "budget exhausted", "budget is exhausted",
        "daily budget", "daily quota exceeded", "daily limit exceeded",
    ))


def _budget_message(resp: Any, api_key: str | None, retry_after: float | None = None) -> str:
    detail = _response_detail(resp)
    if retry_after is None:
        retry_after = _retry_after_seconds(resp.headers.get("Retry-After"))
    if retry_after is None:
        reset = "reset time not provided"
    elif retry_after >= 3600:
        reset = f"resets in ~{int(retry_after) // 3600} h"
    else:
        reset = f"retry in ~{max(1, round(retry_after / 60))} min"
    if not _budget_exhausted(resp):
        return f"OpenAlex rate limit: {reset}; retry later. OpenAlex says: {detail}"
    who = "your API key's" if api_key else "the free per-IP"
    hint = (
        "" if api_key else
        " Get a free key (https://help.openalex.org/api/authentication/) and put OPENALEX_API_KEY=... in .env; "
        "anonymous requests share one daily budget with everyone behind your IP address (VPNs/proxies included)."
    )
    return f"OpenAlex rate limit: {who} daily budget is used up ({reset}).{hint} OpenAlex says: {detail}"


def _redact(text: str, secrets: tuple[str | None, ...] = ()) -> str:
    """Remove request credentials before a URL, response or error is displayed."""
    text = re.sub(r"(mailto|api_key)=[^&\s'\"]+", r"\1=<redacted>", text, flags=re.I)
    text = re.sub(r"\bBearer\s+[^\s'\"]+", "Bearer <redacted>", text, flags=re.I)
    for secret in secrets:
        if secret:
            for value in {secret, quote(secret, safe=""), quote_plus(secret)}:
                text = text.replace(value, "<redacted>")
    return text


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
