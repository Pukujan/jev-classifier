"""Offline behavior tests for the OpenRouter Decisions client contract."""

from __future__ import annotations

from typing import Any

import pytest

import jev_classifier.decisions as decisions
from jev_classifier.decisions import DEFAULT_MODEL, DEFAULT_URL, DecisionsClient, DecisionsError


class _Response:
    def __init__(self, status_code: int, payload: Any = None, *, json_error: bool = False):
        self.status_code = status_code
        self.payload = payload
        self.json_error = json_error

    def json(self) -> Any:
        if self.json_error:
            raise ValueError("not JSON")
        return self.payload


class _HttpClient:
    def __init__(self, response: _Response):
        self.response = response
        self.request: dict[str, Any] | None = None

    def __enter__(self) -> _HttpClient:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> _Response:
        self.request = {"url": url, "headers": headers, "json": json}
        return self.response


def test_default_is_pinned_openrouter_decisions_endpoint_and_model() -> None:
    client = DecisionsClient(api_key="fixture-key")
    assert client.base_url == DEFAULT_URL
    assert client.model == DEFAULT_MODEL


def test_chat_completion_url_is_not_used_as_decisions_endpoint() -> None:
    client = DecisionsClient(
        api_key="fixture-key",
        base_url="https://openrouter.ai/api/v1/chat/completions",
    )
    assert client.base_url == DEFAULT_URL


def test_tilde_latest_alias_falls_back_to_pinned_model_in_current_client() -> None:
    client = DecisionsClient(api_key="fixture-key", model="~typesafe/jev-latest")
    assert client.model == DEFAULT_MODEL


def test_decide_sends_typed_question_and_returns_raw_object(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _Response(200, {"answers": {"kind": {"type": "choice", "choice": "finding"}}})
    http = _HttpClient(response)
    monkeypatch.setattr(decisions.httpx, "Client", lambda timeout: http)
    client = DecisionsClient(api_key="fixture-key")

    result = client.decide(
        state={"text": "fixture"},
        questions={"kind": {"type": "choice", "criteria": {"finding": "A finding"}}},
    )

    assert result == response.payload
    assert http.request is not None
    assert http.request["url"] == DEFAULT_URL
    assert http.request["json"]["model"] == DEFAULT_MODEL
    assert http.request["json"]["questions"]["kind"]["type"] == "choice"


@pytest.mark.parametrize(
    "response, message",
    [
        (_Response(503, {"error": "unavailable"}), "HTTP 503"),
        (_Response(200, json_error=True), "non-JSON"),
        (_Response(200, ["not", "an object"]), "root must be an object"),
    ],
)
def test_provider_failures_fail_closed(
    response: _Response, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    http = _HttpClient(response)
    monkeypatch.setattr(decisions.httpx, "Client", lambda timeout: http)
    client = DecisionsClient(api_key="fixture-key")

    with pytest.raises(DecisionsError, match=message):
        client.decide(state={"text": "fixture"}, questions={"kind": {"type": "choice"}})


def test_empty_question_mapping_fails_before_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(**kwargs: Any) -> None:
        pytest.fail("HTTP client should not be constructed for an empty question set")

    monkeypatch.setattr(decisions.httpx, "Client", fail_if_called)
    client = DecisionsClient(api_key="fixture-key")
    with pytest.raises(DecisionsError, match="non-empty mapping"):
        client.decide(state={"text": "fixture"}, questions={})
