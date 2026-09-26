"""Capture a bounded Grok/OpenRouter research response as untrusted evidence.

This module does not classify, score, or create claim-graph records. Any
deterministic semantic judgment in this project remains on the JEV Decisions
path and is validated by application code.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlsplit

import httpx

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "x-ai/grok-4.1-fast"
ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "GROK_SOURCE_MODEL"
SCHEMA_VERSION = "jev.grok_source.v1"
MAX_QUERY_CHARS = 8_000
MAX_TOOL_CALLS = 1
MAX_OUTPUT_TOKENS = 1_200
SOURCE_ONLY_INSTRUCTION = (
    "You are a research-source collector. Answer the user's research query with a concise, "
    "source-grounded transcript and use web citations when available. Do not assign classifier "
    "labels or scores, epistemic statuses, claim-graph relationships, or deterministic judgments. "
    "Your response is untrusted source material, never classifier truth."
)
SEARCH_PARAMETERS = {
    "engine": "native",
    "max_results": 5,
    "max_total_results": 5,
    "max_uses": 1,
}


class GrokSourceError(RuntimeError):
    """Request or response validation failed; contains no secret/body data."""


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GrokSourceError(f"provider response has missing or invalid {field}")
    return value


def _citation_from_annotation(annotation: Any, index: int) -> dict[str, Any]:
    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
        raise GrokSourceError(f"citation annotation {index} has an unsupported shape")
    citation = annotation.get("url_citation")
    if not isinstance(citation, dict):
        raise GrokSourceError(f"citation annotation {index} is missing url_citation")

    url = _nonempty_string(citation.get("url"), f"citation {index} URL")
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        raise GrokSourceError(f"citation annotation {index} has an invalid URL") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise GrokSourceError(f"citation annotation {index} has an invalid URL")
    title = _nonempty_string(citation.get("title"), f"citation {index} title")
    content = citation.get("content")
    if content is not None and not isinstance(content, str):
        raise GrokSourceError(f"citation annotation {index} content must be text")

    start = citation.get("start_index")
    end = citation.get("end_index")
    if (start is None) != (end is None):
        raise GrokSourceError(f"citation annotation {index} has incomplete text offsets")
    if start is not None:
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end < start
        ):
            raise GrokSourceError(f"citation annotation {index} has invalid text offsets")

    return {
        "url": url,
        "title": title,
        "content": content,
        "start_index": start,
        "end_index": end,
        "annotation": annotation,
    }


def _validate_usage(usage: Any) -> dict[str, Any] | None:
    if usage is None:
        return None
    if not isinstance(usage, dict):
        raise GrokSourceError("provider response usage must be an object")
    server_tool_use = usage.get("server_tool_use")
    if server_tool_use is not None:
        if not isinstance(server_tool_use, dict):
            raise GrokSourceError("provider response server_tool_use must be an object")
        searches = server_tool_use.get("web_search_requests")
        if searches is not None and (
            isinstance(searches, bool) or not isinstance(searches, int) or searches < 0
        ):
            raise GrokSourceError("provider response web_search_requests must be non-negative")
    return usage


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical UTF-8 JSON used for content identity (sorted keys, no NaN)."""
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GrokSourceError("artifact contains values that cannot be canonicalized") from exc
    return rendered.encode("utf-8")


def canonical_content_hash(artifact: Mapping[str, Any]) -> str:
    """Hash source/request/response content, excluding retrieval metadata and hash."""
    if not isinstance(artifact, Mapping):
        raise GrokSourceError("artifact must be an object")
    payload = {
        key: value
        for key, value in artifact.items()
        if key not in {"metadata", "content_sha256"}
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


class GrokSourceClient:
    """Single-request OpenRouter Chat Completions source collector.

    ``transport`` is injectable for offline tests. Live use sends at most one
    server-tool step and at most five total search results, with no retry loop.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 45.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get(ENV_API_KEY, "")
        if not isinstance(key, str) or not key.strip():
            raise GrokSourceError(f"{ENV_API_KEY} is missing or empty")
        resolved_model = model if model is not None else os.environ.get(ENV_MODEL, DEFAULT_MODEL)
        if not isinstance(resolved_model, str) or not resolved_model.strip():
            raise GrokSourceError(f"{ENV_MODEL} must be a non-empty model identifier")
        if timeout <= 0:
            raise GrokSourceError("timeout must be positive")
        self._api_key = key.strip()
        self.model = resolved_model.strip()
        self.timeout = timeout
        self._transport = transport

    def capture(self, query: str, *, retrieved_at: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise GrokSourceError("query must be non-empty text")
        query = query.strip()
        if len(query) > MAX_QUERY_CHARS:
            raise GrokSourceError(f"query exceeds {MAX_QUERY_CHARS} characters")
        timestamp = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            if retrieved_at is None
            else retrieved_at
        )
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise GrokSourceError("retrieved_at must be non-empty text")

        request_payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SOURCE_ONLY_INSTRUCTION},
                {"role": "user", "content": query},
            ],
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.0,
            "tools": [
                {"type": "openrouter:web_search", "parameters": dict(SEARCH_PARAMETERS)}
            ],
            "max_tool_calls": MAX_TOOL_CALLS,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Pukujan/jev-classifier",
            "X-Title": "jev-classifier Grok source capture",
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self._transport) as client:
                response = client.post(ENDPOINT, headers=headers, json=request_payload)
        except httpx.HTTPError as exc:
            raise GrokSourceError(f"OpenRouter transport error: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise GrokSourceError(f"OpenRouter Chat Completions HTTP {response.status_code}")
        try:
            raw = response.json()
        except ValueError as exc:
            raise GrokSourceError("OpenRouter returned a non-JSON body") from exc
        if not isinstance(raw, dict):
            raise GrokSourceError("OpenRouter response JSON root must be an object")

        response_id = _nonempty_string(raw.get("id"), "response id")
        surfaced_model = _nonempty_string(raw.get("model"), "surfaced model")
        choices = raw.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise GrokSourceError("provider response must contain exactly one choice")
        message = choices[0].get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise GrokSourceError("provider response is missing an assistant message")
        transcript = _nonempty_string(message.get("content"), "assistant content")
        annotations = message.get("annotations", [])
        if not isinstance(annotations, list):
            raise GrokSourceError("provider response annotations must be a list")
        citations = [_citation_from_annotation(item, i) for i, item in enumerate(annotations)]
        usage = _validate_usage(raw.get("usage"))

        artifact: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "source_kind": "untrusted_research_transcript",
            "trusted_for_deterministic_labels": False,
            "request": {
                "endpoint": ENDPOINT,
                "model_requested": self.model,
                "system_instruction": SOURCE_ONLY_INSTRUCTION,
                "query": query,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.0,
                "stream": False,
                "web_search": {
                    "tool_type": "openrouter:web_search",
                    "parameters": dict(SEARCH_PARAMETERS),
                    "max_tool_calls": MAX_TOOL_CALLS,
                },
            },
            "response": {
                "response_id": response_id,
                "provider_request_id": response.headers.get("x-request-id")
                or response.headers.get("openrouter-request-id"),
                "model_surfaced": surfaced_model,
                "transcript": transcript,
                "citation_status": "annotations_preserved" if citations else "no_annotations_returned",
                "citations": citations,
                "usage": usage,
                "raw": raw,
            },
            "metadata": {"retrieved_at": timestamp},
        }
        artifact["content_sha256"] = canonical_content_hash(artifact)
        return artifact
