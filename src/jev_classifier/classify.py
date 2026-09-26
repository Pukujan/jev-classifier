"""Minimal classify path: JEV choice → validated claim JSON record."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jev_classifier.decisions import DecisionsClient, DecisionsError
from jev_classifier.normalize import NormalizeError, extract_choice_from_response

# Required for application validation (see docs/CLAIM_SCHEMA.md).
REQUIRED_CLAIM_KEYS = frozenset(
    {
        "label",
        "epistemic_status",
        "recorded_at",
        "evidence",
        "model",
    }
)

# Full PCM-0050-friendly ledger field set (required + optional documented keys).
PCM_CLAIM_KEYS = frozenset(
    {
        "id",
        "label",
        "epistemic_status",
        "recorded_at",
        "valid_from",
        "valid_to",
        "supersedes",
        "evidence",
        "model",
        "probabilities",
        "confidence",
        "independence_class",
        "response_id",
        "notes",
    }
)

# Legacy / camelCase → canonical snake_case (PCM-friendly). Canonical wins on clash.
LEGACY_CLAIM_KEY_ALIASES: dict[str, str] = {
    "epistemicStatus": "epistemic_status",
    "status": "epistemic_status",
    "validFrom": "valid_from",
    "validTo": "valid_to",
    "recordedAt": "recorded_at",
    "created_at": "recorded_at",
    "createdAt": "recorded_at",
    "independenceClass": "independence_class",
}


def migrate_legacy_claim(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Rewrite legacy/camelCase claim keys to PCM-friendly snake_case.

    Does not install or import PCM. If both legacy and canonical keys are
    present, the canonical value is kept. Unknown keys pass through unchanged.
    """
    if not isinstance(raw, Mapping):
        raise NormalizeError("claim must be an object", kind="parse_error")
    out: dict[str, Any] = dict(raw)
    for legacy, canonical in LEGACY_CLAIM_KEY_ALIASES.items():
        if legacy not in out:
            continue
        if canonical not in out:
            out[canonical] = out[legacy]
        del out[legacy]
    return out


def normalize_claim_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate legacy keys then return a plain dict (no validation)."""
    return migrate_legacy_claim(raw)


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


def _validate_supersedes(value: Any) -> None:
    """Supersession link: null/absent OK; else non-empty string claim id."""
    if value is None:
        return
    if not isinstance(value, str):
        raise NormalizeError(
            "supersedes must be a string claim id or null",
            kind="parse_error",
        )
    if not value.strip():
        raise NormalizeError(
            "supersedes must be a non-empty claim id when set",
            kind="parse_error",
        )


def _validate_optional_iso_or_null(value: Any, key: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise NormalizeError(
            f"{key} must be a non-empty ISO-8601 string or null",
            kind="parse_error",
        )


def validate_claim_record(
    claim: Mapping[str, Any],
    *,
    legal_labels: set[str] | frozenset[str],
    migrate: bool = True,
) -> dict[str, Any]:
    """Validate a claim record; optionally migrate legacy keys first.

    Returns the (possibly migrated) claim dict. Fail closed on shape errors.
    """
    body: Mapping[str, Any] = migrate_legacy_claim(claim) if migrate else claim
    missing = REQUIRED_CLAIM_KEYS - set(body.keys())
    if missing:
        raise NormalizeError(
            f"claim missing required keys: {sorted(missing)}",
            kind="parse_error",
        )
    label = body["label"]
    if not isinstance(label, str) or label not in legal_labels:
        raise NormalizeError(
            f"claim label {label!r} not in legal set {sorted(legal_labels)}",
            kind="parse_error",
        )
    if not isinstance(body["epistemic_status"], str) or not body["epistemic_status"]:
        raise NormalizeError("epistemic_status must be a non-empty string", kind="parse_error")
    if not isinstance(body["recorded_at"], str) or not body["recorded_at"]:
        raise NormalizeError("recorded_at must be a non-empty ISO-8601 string", kind="parse_error")
    evidence = body["evidence"]
    if not isinstance(evidence, Mapping):
        raise NormalizeError("evidence must be an object pointer", kind="parse_error")
    if "fragment_id" not in evidence and "path" not in evidence:
        raise NormalizeError("evidence needs fragment_id and/or path", kind="parse_error")
    if not isinstance(body["model"], str) or not body["model"]:
        raise NormalizeError("model must be a non-empty string", kind="parse_error")

    if "supersedes" in body:
        _validate_supersedes(body["supersedes"])
    if "valid_from" in body:
        _validate_optional_iso_or_null(body["valid_from"], "valid_from")
    if "valid_to" in body:
        _validate_optional_iso_or_null(body["valid_to"], "valid_to")
    if "independence_class" in body and body["independence_class"] is not None:
        ic = body["independence_class"]
        if not isinstance(ic, str) or not ic.strip():
            raise NormalizeError(
                "independence_class must be a non-empty string or null",
                kind="parse_error",
            )

    return dict(body)


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
    claim_id: str | None = None,
) -> dict[str, Any]:
    ts = recorded_at or datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
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
    if claim_id is not None:
        record["id"] = claim_id
    return record


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
    return validate_claim_record(claim, legal_labels=legal)
