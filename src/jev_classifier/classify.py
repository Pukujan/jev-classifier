"""Minimal classify path: JEV choice → validated claim JSON record."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jev_classifier.decisions import DecisionsClient, DecisionsError
from jev_classifier.normalize import NormalizeError, extract_choice_from_response

REQUIRED_CLAIM_KEYS = frozenset(
    {
        "label",
        "epistemic_status",
        "recorded_at",
        "evidence",
        "model",
    }
)


def load_fragment_fixture(path: str | Path) -> dict[str, Any]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fragment fixture must be a JSON object")
    for key in ("id", "text", "closed_label_set", "question_id", "criteria"):
        if key not in data:
            raise ValueError(f"fragment fixture missing required key: {key}")
    labels = data["closed_label_set"]
    if not isinstance(labels, list) or not labels or not all(isinstance(x, str) for x in labels):
        raise ValueError("closed_label_set must be a non-empty list of strings")
    return data


def validate_claim_record(claim: Mapping[str, Any], *, legal_labels: set[str] | frozenset[str]) -> None:
    missing = REQUIRED_CLAIM_KEYS - set(claim.keys())
    if missing:
        raise NormalizeError(
            f"claim missing required keys: {sorted(missing)}",
            kind="parse_error",
        )
    label = claim["label"]
    if not isinstance(label, str) or label not in legal_labels:
        raise NormalizeError(
            f"claim label {label!r} not in legal set {sorted(legal_labels)}",
            kind="parse_error",
        )
    if not isinstance(claim["epistemic_status"], str) or not claim["epistemic_status"]:
        raise NormalizeError("epistemic_status must be a non-empty string", kind="parse_error")
    if not isinstance(claim["recorded_at"], str) or not claim["recorded_at"]:
        raise NormalizeError("recorded_at must be a non-empty ISO-8601 string", kind="parse_error")
    evidence = claim["evidence"]
    if not isinstance(evidence, Mapping):
        raise NormalizeError("evidence must be an object pointer", kind="parse_error")
    if "fragment_id" not in evidence and "path" not in evidence:
        raise NormalizeError("evidence needs fragment_id and/or path", kind="parse_error")
    if not isinstance(claim["model"], str) or not claim["model"]:
        raise NormalizeError("model must be a non-empty string", kind="parse_error")


def build_claim_record(
    *,
    label: str,
    model: str,
    evidence: Mapping[str, Any],
    probabilities: Mapping[str, float] | None = None,
    confidence: float | None = None,
    epistemic_status: str = "Inferred",
    recorded_at: str | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    supersedes: str | None = None,
    response_id: str | None = None,
    independence_class: str | None = None,
) -> dict[str, Any]:
    ts = recorded_at or datetime.now(timezone.utc).isoformat()
    return {
        "label": label,
        "epistemic_status": epistemic_status,
        "recorded_at": ts,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "supersedes": supersedes,
        "evidence": dict(evidence),
        "model": model,
        "probabilities": dict(probabilities) if probabilities is not None else None,
        "confidence": confidence,
        "response_id": response_id,
        "independence_class": independence_class,
    }


def classify_fragment(
    fragment: Mapping[str, Any],
    *,
    client: DecisionsClient | None = None,
    evidence_path: str | None = None,
) -> dict[str, Any]:
    """Call JEV choice on a fragment fixture dict; return a claim JSON record.

    Fail closed: DecisionsError / NormalizeError propagate; never fabricates labels.
    """
    legal = frozenset(fragment["closed_label_set"])
    qid = fragment["question_id"]
    criteria = fragment["criteria"]
    if set(criteria.keys()) != set(legal):
        raise NormalizeError(
            "criteria keys must match closed_label_set exactly",
            kind="parse_error",
        )

    questions = {
        qid: {
            "type": "choice",
            "instructions": fragment.get(
                "instructions",
                "Classify the research fragment into exactly one closed label.",
            ),
            "criteria": dict(criteria),
        }
    }
    state = {
        "fragment_id": fragment.get("id"),
        "fragment": fragment["text"],
        "source": fragment.get("source"),
        "title": fragment.get("title"),
    }

    svc = client or DecisionsClient()
    try:
        raw = svc.decide(state=state, questions=questions)
    except DecisionsError:
        raise

    normalized = extract_choice_from_response(
        raw,
        question_id=qid,
        legal_options=legal,
    )
    model = normalized.get("model") or svc.model
    evidence = {
        "fragment_id": fragment.get("id"),
        "path": evidence_path,
    }
    claim = build_claim_record(
        label=normalized["choice"],
        model=model,
        evidence=evidence,
        probabilities=normalized.get("probabilities"),
        confidence=normalized.get("confidence"),
        epistemic_status="Inferred",
        response_id=normalized.get("response_id"),
    )
    validate_claim_record(claim, legal_labels=legal)
    return claim
