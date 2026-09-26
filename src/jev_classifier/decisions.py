"""Thin OpenRouter Decisions API client for TypeSafe JEV.

Hard constraints:
- Endpoint: POST https://openrouter.ai/api/alpha/decisions
- Pin model: typesafe/jev-1.13
- Primitives: choice / score / noul only; no stream; no Chat Completions
- Do NOT use OpenCode defaults (opencode.ai / OPENCODE_API_KEY / jev-1.13-free)
- Ignore ambient OPENROUTER_API_URL / OPENROUTER_MODEL when they are not JEV Decisions-safe
"""

from __future__ import annotations

import os
from typing import Any, Mapping

import httpx

DEFAULT_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "typesafe/jev-1.13"
ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_API_URL = "OPENROUTER_API_URL"
ENV_MODEL = "OPENROUTER_MODEL"


class DecisionsError(RuntimeError):
    """Provider/HTTP/config failure for Decisions API (fail closed; no fabricated labels)."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _resolve_url(explicit: str | None) -> str:
    candidates = []
    if explicit is not None and str(explicit).strip():
        candidates.append(str(explicit).strip())
    env_url = os.environ.get(ENV_API_URL, "").strip()
    if env_url:
        candidates.append(env_url)
    candidates.append(DEFAULT_URL)
    for url in candidates:
        lowered = url.lower().rstrip("/")
        if "opencode.ai" in lowered or "chat/completions" in lowered:
            continue
        if lowered.endswith("/api/alpha/decisions") or lowered.endswith("/alpha/decisions"):
            return url.rstrip("/")
        # Bare openrouter base is not Decisions — skip ambient v1 bases
        if "openrouter.ai" in lowered and "decisions" not in lowered:
            continue
    return DEFAULT_URL


def _resolve_model(explicit: str | None) -> str:
    candidates = []
    if explicit is not None and str(explicit).strip():
        candidates.append(str(explicit).strip())
    env_model = os.environ.get(ENV_MODEL, "").strip()
    if env_model:
        candidates.append(env_model)
    candidates.append(DEFAULT_MODEL)
    for mdl in candidates:
        if "jev-1.13-free" in mdl:
            continue
        if mdl.startswith("opencode"):
            continue
        # Accept pinned family only
        if mdl == DEFAULT_MODEL or mdl.startswith("typesafe/jev-1.13"):
            return DEFAULT_MODEL if mdl == DEFAULT_MODEL else mdl
        if mdl.startswith("typesafe/jev"):
            # Rolling/canary allowed only when explicitly requested via constructor
            if explicit is not None and mdl == explicit.strip():
                return mdl
            continue
    return DEFAULT_MODEL


class DecisionsClient:
    """Minimal HTTP client for OpenRouter alpha Decisions."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get(ENV_API_KEY, "")
        if not key or not str(key).strip():
            raise DecisionsError(
                f"{ENV_API_KEY} is missing or empty; set it in the environment or .env"
            )
        self.api_key = str(key).strip()
        self.base_url = _resolve_url(base_url)
        self.model = _resolve_model(model)
        self.timeout = timeout

    def decide(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        """POST a Decisions request; return parsed JSON body.

        Does not normalize answers — callers use normalize.py and fail closed.
        """
        if not isinstance(questions, Mapping) or not questions:
            raise DecisionsError("questions must be a non-empty mapping")
        use_model = _resolve_model(model) if model is not None else self.model
        payload = {
            "model": use_model,
            "state": state,
            "questions": dict(questions),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Pukujan/jev-classifier",
            "X-Title": "jev-classifier",
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(self.base_url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise DecisionsError(f"Decisions HTTP transport error: {type(exc).__name__}") from exc

        if resp.status_code >= 400:
            raise DecisionsError(
                f"Decisions API HTTP {resp.status_code}",
                status_code=resp.status_code,
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise DecisionsError("Decisions API returned non-JSON body") from exc
        if not isinstance(data, dict):
            raise DecisionsError("Decisions API JSON root must be an object")
        return data