from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from jev_classifier.sources.grok import (
    DEFAULT_MODEL,
    ENDPOINT,
    GrokSourceClient,
    GrokSourceError,
    canonical_content_hash,
)


FIXTURE = Path(__file__).parent / "fixtures" / "grok" / "success.json"
CLI_PATH = Path(__file__).parents[1] / "scripts" / "grok_research.py"


def response_data() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def client_for(data: object, *, status_code: int = 200, body: bytes | None = None):
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["payload"] = json.loads(request.content)
        if body is not None:
            return httpx.Response(status_code, content=body)
        return httpx.Response(status_code, json=data, headers={"x-request-id": "req-test-01"})

    transport = httpx.MockTransport(handler)
    return GrokSourceClient(api_key="test-secret", transport=transport), seen


def test_capture_uses_one_bounded_source_only_request_and_preserves_evidence():
    client, seen = client_for(response_data())
    artifact = client.capture("Research this claim", retrieved_at="2026-01-01T00:00:00Z")

    assert seen["url"] == ENDPOINT
    assert seen["headers"]["authorization"] == "Bearer test-secret"
    payload = seen["payload"]
    assert payload["model"] == DEFAULT_MODEL
    assert payload["max_tokens"] == 1200
    assert payload["max_tool_calls"] == 1
    assert payload["stream"] is False
    assert payload["temperature"] == 0.0
    assert payload["messages"][0]["role"] == "system"
    assert "Do not assign classifier labels" in payload["messages"][0]["content"]
    assert payload["messages"][1] == {"role": "user", "content": "Research this claim"}
    assert payload["tools"] == [
        {
            "type": "openrouter:web_search",
            "parameters": {
                "engine": "native",
                "max_results": 5,
                "max_total_results": 5,
                "max_uses": 1,
            },
        }
    ]
    assert "x_search" not in json.dumps(payload)
    assert artifact["request"]["query"] == "Research this claim"
    assert artifact["response"]["response_id"] == "gen-test-001"
    assert artifact["response"]["provider_request_id"] == "req-test-01"
    assert artifact["response"]["model_surfaced"] == DEFAULT_MODEL
    assert artifact["response"]["transcript"] == "The cited page reports a sample finding."
    assert artifact["response"]["citations"][0]["url"] == "https://example.org/paper"
    assert artifact["response"]["citations"][0]["annotation"]["type"] == "url_citation"
    assert artifact["response"]["usage"]["server_tool_use"]["web_search_requests"] == 1
    assert artifact["response"]["raw"] == response_data()
    assert artifact["trusted_for_deterministic_labels"] is False
    assert "test-secret" not in json.dumps(artifact)
    assert not any(k in artifact for k in ("labels", "claims", "scores"))


def test_content_hash_excludes_retrieval_time_and_is_key_order_independent():
    client, _ = client_for(response_data())
    first = client.capture("café", retrieved_at="2026-01-01T00:00:00Z")
    second = client.capture("café", retrieved_at="2026-02-01T00:00:00Z")
    assert first["content_sha256"] == second["content_sha256"]

    def reverse_mapping_order(value):
        if isinstance(value, dict):
            return {key: reverse_mapping_order(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse_mapping_order(item) for item in value]
        return value

    reordered = reverse_mapping_order(copy.deepcopy(first))
    assert canonical_content_hash(reordered) == first["content_sha256"]


def test_content_hash_changes_when_source_content_changes():
    client, _ = client_for(response_data())
    original = client.capture("Research this claim", retrieved_at="2026-01-01T00:00:00Z")
    changed = copy.deepcopy(original)
    changed["response"]["transcript"] += " Changed."
    assert canonical_content_hash(changed) != original["content_sha256"]


def test_no_annotations_are_recorded_without_scraping_links_from_prose():
    data = response_data()
    message = data["choices"][0]["message"]
    message["content"] = "A URL in prose is not a provider citation: https://example.org"
    message["annotations"] = []
    client, _ = client_for(data)
    artifact = client.capture("Research this claim")
    assert artifact["response"]["citations"] == []
    assert artifact["response"]["citation_status"] == "no_annotations_returned"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.pop("id"),
        lambda data: data.update(id="  "),
        lambda data: data.pop("model"),
        lambda data: data.update(choices=[]),
        lambda data: data["choices"][0]["message"].update(content=""),
        lambda data: data["choices"][0]["message"]["annotations"][0]["url_citation"].update(
            url="javascript:alert(1)"
        ),
        lambda data: data["choices"][0]["message"]["annotations"][0]["url_citation"].update(
            url="https://[invalid"
        ),
        lambda data: data["choices"][0]["message"].update(annotations={}),
        lambda data: data.update(usage={"server_tool_use": {"web_search_requests": -1}}),
        lambda data: data.update(usage=[]),
    ],
)
def test_malformed_provider_payload_fails_closed(mutate):
    data = response_data()
    mutate(data)
    client, _ = client_for(data)
    with pytest.raises(GrokSourceError):
        client.capture("Research this claim")


def test_http_and_non_json_errors_do_not_echo_credentials():
    client, _ = client_for({"error": "denied"}, status_code=401)
    with pytest.raises(GrokSourceError) as error:
        client.capture("query")
    assert "test-secret" not in str(error.value)

    client, _ = client_for(None, body=b"not-json")
    with pytest.raises(GrokSourceError, match="non-JSON"):
        client.capture("query")


def test_missing_key_fails_before_network():
    with pytest.raises(GrokSourceError, match="OPENROUTER_API_KEY"):
        GrokSourceClient(api_key=" ")

    client, _ = client_for(response_data())
    with pytest.raises(GrokSourceError, match="retrieved_at"):
        client.capture("query", retrieved_at="")


def _load_cli():
    spec = importlib.util.spec_from_file_location("grok_research_cli", CLI_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_writes_inspectable_artifact_without_overwrite_or_secret(monkeypatch, tmp_path, capsys):
    cli = _load_cli()
    monkeypatch.setenv("OPENROUTER_API_KEY", "cli-test-secret")
    monkeypatch.setattr(
        GrokSourceClient,
        "capture",
        lambda self, query: {
            "schema_version": "jev.grok_source.v1",
            "request": {"query": query},
            "response": {"response_id": "gen-cli-1"},
            "metadata": {"retrieved_at": "2026-01-01T00:00:00Z"},
            "content_sha256": "a" * 64,
        },
    )
    assert cli.main(["--query", "offline mocked query", "--output", "results/source.json"], root=tmp_path) == 0
    output = tmp_path / "results" / "source.json"
    content = output.read_text(encoding="utf-8")
    assert json.loads(content)["response"]["response_id"] == "gen-cli-1"
    assert "cli-test-secret" not in content
    assert cli.main(["--query", "offline mocked query", "--output", "results/source.json"], root=tmp_path) == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_rejects_artifact_paths_outside_controlled_folder(tmp_path):
    cli = _load_cli()
    with pytest.raises(ValueError, match="inside the controlled project folder"):
        cli.write_artifact({"ok": True}, tmp_path.parent / "outside.json", root=tmp_path)
