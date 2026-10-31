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


def test_cursor_paging_uses_supported_page_size_and_follows_cursor():
    client, session = _client([
        _resp(200, {"results": [{"id": "W1"}], "meta": {"next_cursor": "next"}}),
        _resp(200, {"results": [{"id": "W2"}], "meta": {"next_cursor": None}}),
    ])
    params = {"filter": "publication_year:2025"}
    assert list(client.paginate("works", params)) == [{"id": "W1"}, {"id": "W2"}]
    requests_sent = [call.kwargs["params"] for call in session.get.call_args_list]
    assert [p["cursor"] for p in requests_sent] == ["*", "next"]
    assert all(p["per-page"] == 100 for p in requests_sent)
    assert params == {"filter": "publication_year:2025"}


@pytest.mark.parametrize("key", ["", "private-rejected-key"])
def test_unauthorized_gives_actionable_advice_without_retrying_or_leaking(monkeypatch, key):
    monkeypatch.setenv("OPENALEX_API_KEY", key)
    response = _resp(401)
    response.text = f"Rejected credential {key}, contact x@example.com"
    client, session = _client([response])
    waits = []
    monkeypatch.setattr(openalex.time, "sleep", waits.append)
    with pytest.raises(OpenAlexError) as caught:
        client.get("works", {"cursor": "next"})
    message = str(caught.value)
    assert "HTTP 401" in message and "OPENALEX_API_KEY" in message
    assert "x@example.com" not in message
    assert session.get.call_count == 1 and waits == []
    if key:
        assert key not in message and "rejected" in message
    else:
        assert "free key" in message and "beyond the first page" in message


def test_search_sources_strips_commas():
    client, session = _client([_resp(200, {"results": [], "meta": {"next_cursor": None}})])
    client.search_sources("Thermal, Mechanical and Multi-Physics Simulation")
    sent = session.get.call_args.kwargs["params"]["filter"]
    assert "," not in sent and "Thermal  Mechanical" in sent


@pytest.mark.parametrize("header, expected", [("2.5", 2.5), (" 5 ", 5.0),
                                              ("Wed, 21 Oct 2015 07:28:03 GMT", 3.0)])
def test_retry_after_seconds_or_http_date_controls_retry(monkeypatch, header, expected):
    from datetime import datetime, timezone

    now = datetime(2015, 10, 21, 7, 28, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(openalex.time, "time", lambda: now)
    waits = []
    monkeypatch.setattr(openalex.time, "sleep", waits.append)
    client, session = _client([_resp(429, headers={"Retry-After": header}), _resp(200, {"ok": 1})])
    assert client.get("works") == {"ok": 1}
    assert session.get.call_count == 2 and waits == [expected]


@pytest.mark.parametrize("value", [None, "", "invalid", "NaN", "inf", "-2", "1e999"])
def test_invalid_retry_after_does_not_break_client(value):
    assert openalex._retry_after_seconds(value) is None


def test_retry_after_in_past_is_zero():
    assert openalex._retry_after_seconds("Wed, 21 Oct 2015 07:28:00 GMT", now=2_000_000_000) == 0


@pytest.mark.parametrize("header", ["3600.0", "Wed, 21 Oct 2015 08:28:00 GMT"])
def test_budget_exhaustion_with_float_or_date_fails_fast(monkeypatch, header):
    from datetime import datetime, timezone

    now = datetime(2015, 10, 21, 7, 28, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(openalex.time, "time", lambda: now)
    monkeypatch.setenv("OPENALEX_API_KEY", "")
    waits = []
    monkeypatch.setattr(openalex.time, "sleep", waits.append)
    client, session = _client([_resp(429, {"message": "Insufficient budget"}, headers={"Retry-After": header})])
    with pytest.raises(OpenAlexError, match="daily budget.*1 h"):
        client.get("works")
    assert session.get.call_count == 1 and waits == []


def test_budget_exhaustion_without_retry_after_fails_fast(monkeypatch):
    waits = []
    monkeypatch.setattr(openalex.time, "sleep", waits.append)
    client, session = _client([_resp(429, {"message": "Insufficient budget"})])
    with pytest.raises(OpenAlexError, match="reset time not provided"):
        client.get("works")
    assert session.get.call_count == 1 and waits == []


def test_long_nonbudget_cooldown_does_not_claim_daily_budget_exhaustion(monkeypatch):
    waits = []
    monkeypatch.setattr(openalex.time, "sleep", waits.append)
    client, session = _client([_resp(429, {"message": "Slow down"}, headers={"Retry-After": "90"})])
    with pytest.raises(OpenAlexError) as caught:
        client.get("works")
    assert "retry later" in str(caught.value) and "daily budget" not in str(caught.value)
    assert session.get.call_count == 1 and waits == []


@pytest.mark.parametrize("status", [400, 429])
def test_response_errors_redact_credentials_before_truncating(monkeypatch, status):
    from urllib.parse import quote

    key = "sensitive-api-key"
    mailto = "contact+private@example.com"
    message = f"mailto={quote(mailto)}&api_key={key} Bearer {key}; contact {mailto} key {key}"
    response = _resp(status, {"message": "Insufficient budget: " + message}, headers={"Retry-After": "3600.0"})
    response.url = "https://api.openalex.org/works?" + message
    response.text = message
    session = MagicMock()
    session.headers = {}
    session.get.return_value = response
    client = OpenAlex(mailto=mailto, api_key=key, session=session)
    with pytest.raises(OpenAlexError) as caught:
        client.get("works")
    displayed = str(caught.value)
    assert key not in displayed and mailto not in displayed and quote(mailto) not in displayed
    assert "redacted" in displayed
