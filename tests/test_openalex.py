from unittest.mock import MagicMock

import pytest
import requests

from paper_trends import openalex
from paper_trends.openalex import OpenAlex, OpenAlexError, _redact, reconstruct_abstract


def _client(responses):
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = responses
    return OpenAlex(mailto="x@example.com", session=session), session


def _resp(status, body=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    r.url = "https://api.openalex.org/works?mailto=x@example.com"
    r.text = ""
    if body is None:
        r.json.side_effect = ValueError("bad json")
    else:
        r.json.return_value = body
    return r


def test_retries_connection_errors_then_succeeds(monkeypatch):
    monkeypatch.setattr(openalex.time, "sleep", lambda s: None)
    client, session = _client([requests.exceptions.SSLError("EOF"), _resp(429, headers={"Retry-After": "1"}), _resp(200, {"ok": 1})])
    assert client.get("works") == {"ok": 1}
    assert session.get.call_count == 3


def test_gives_up_with_redacted_message(monkeypatch):
    monkeypatch.setattr(openalex.time, "sleep", lambda s: None)
    client, _ = _client([requests.exceptions.ConnectionError("reset")] * openalex.MAX_RETRIES)
    with pytest.raises(OpenAlexError) as ei:
        client.get("works")
    assert "x@example.com" not in str(ei.value) and "ConnectionError" in str(ei.value)


def test_redact_and_abstract():
    assert _redact("https://api.openalex.org/works?per-page=1&mailto=a@b.c&x=1") == "https://api.openalex.org/works?per-page=1&mailto=<redacted>&x=1"
    assert reconstruct_abstract({"world": [1], "hello": [0]}) == "hello world"


def test_budget_exhausted_fails_fast(monkeypatch):
    monkeypatch.setattr(openalex.time, "sleep", lambda s: None)
    monkeypatch.setenv("OPENALEX_API_KEY", "")  # behave as an anonymous client even if .env has a key
    r = _resp(429, {"error": "Rate limit exceeded", "message": "Insufficient budget"}, headers={"Retry-After": "63485"})
    client, session = _client([r])
    with pytest.raises(OpenAlexError) as ei:
        client.get("works")
    assert session.get.call_count == 1
    assert "OPENALEX_API_KEY" in str(ei.value) and "17 h" in str(ei.value)


def test_api_key_header():
    session = MagicMock(); session.headers = {}
    OpenAlex(mailto="x@example.com", session=session, api_key="k123")
    assert session.headers["Authorization"] == "Bearer k123"


def test_search_sources_strips_commas():
    client, session = _client([_resp(200, {"results": [], "meta": {"next_cursor": None}})])
    client.search_sources("Thermal, Mechanical and Multi-Physics Simulation")
    sent = session.get.call_args.kwargs["params"]["filter"]
    assert "," not in sent and "Thermal  Mechanical" in sent
