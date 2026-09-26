"""Fail-closed normalization of OpenRouter Decisions API answers."""

from __future__ import annotations

from typing import Any, Mapping


class NormalizeError(ValueError):
    """Raised when an answer is malformed or out of the legal option set."""

    def __init__(self, message: str, *, kind: str = "parse_error") -> None:
        super().__init__(message)
        self.kind = kind


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NormalizeError(f"{label} must be an object", kind="parse_error")
    return value


def normalize_choice_answer(
    answer: Any,
    *,
    legal_options: set[str] | frozenset[str],
    question_id: str = "choice",
) -> dict[str, Any]:
    """Validate a choice answer; fail closed on malformed/out-of-set.

    Preserves native probabilities and confidence when present.
    Never fabricates a label.
    """
    if not legal_options:
        raise NormalizeError("legal_options must be non-empty", kind="parse_error")

    body = _require_mapping(answer, f"answers.{question_id}")
    ans_type = body.get("type")
    if ans_type is not None and ans_type != "choice":
        raise NormalizeError(
            f"answers.{question_id}: expected type=choice, got {ans_type!r}",
            kind="parse_error",
        )

    choice = body.get("choice")
    if not isinstance(choice, str) or not choice:
        raise NormalizeError(
            f"answers.{question_id}: missing or non-string choice",
            kind="parse_error",
        )
    if choice not in legal_options:
        raise NormalizeError(
            f"answers.{question_id}: choice {choice!r} not in legal set "
            f"{sorted(legal_options)}",
            kind="parse_error",
        )

    probabilities = body.get("probabilities")
    probs_out: dict[str, float] | None = None
    if probabilities is not None:
        probs_map = _require_mapping(probabilities, f"answers.{question_id}.probabilities")
        probs_out = {}
        for key, val in probs_map.items():
            if key not in legal_options:
                raise NormalizeError(
                    f"answers.{question_id}: probability key {key!r} not in legal set",
                    kind="parse_error",
                )
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                raise NormalizeError(
                    f"answers.{question_id}: probability for {key!r} must be numeric",
                    kind="parse_error",
                )
            probs_out[str(key)] = float(val)

    confidence = body.get("confidence")
    conf_out: float | None = None
    if confidence is not None:
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise NormalizeError(
                f"answers.{question_id}: confidence must be numeric",
                kind="parse_error",
            )
        conf_out = float(confidence)

    return {
        "type": "choice",
        "choice": choice,
        "probabilities": probs_out,
        "confidence": conf_out,
    }


def extract_choice_from_response(
    response: Any,
    *,
    question_id: str,
    legal_options: set[str] | frozenset[str],
) -> dict[str, Any]:
    """Pull and normalize one choice answer from a Decisions response body."""
    body = _require_mapping(response, "response")
    answers = body.get("answers")
    answers_map = _require_mapping(answers, "answers")
    if question_id not in answers_map:
        raise NormalizeError(
            f"answers missing question_id {question_id!r}",
            kind="parse_error",
        )
    normalized = normalize_choice_answer(
        answers_map[question_id],
        legal_options=legal_options,
        question_id=question_id,
    )
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise NormalizeError("response.model must be a string when present", kind="parse_error")
    return {
        **normalized,
        "model": model,
        "response_id": body.get("id") if isinstance(body.get("id"), str) else None,
    }


def normalize_noul_answer(
    answer: Any,
    *,
    question_id: str = "noul",
    yes_threshold: float = 0.5,
) -> dict[str, Any]:
    """Validate a noul answer; fail closed on malformed values.

    OpenRouter noul returns P(yes) as the primary value (no separate confidence).
    We preserve p_yes and derive a closed yes/no label locally via threshold.
    """
    body = _require_mapping(answer, f"answers.{question_id}")
    ans_type = body.get("type")
    if ans_type is not None and ans_type != "noul":
        raise NormalizeError(
            f"answers.{question_id}: expected type=noul, got {ans_type!r}",
            kind="parse_error",
        )

    # Accept common shapes: {"noul": 0.7} or {"value": 0.7} or {"p_yes": 0.7}
    raw = None
    for key in ("noul", "p_yes", "value", "probability"):
        if key in body:
            raw = body[key]
            break
    if raw is None:
        raise NormalizeError(
            f"answers.{question_id}: missing noul/p_yes value",
            kind="parse_error",
        )
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise NormalizeError(
            f"answers.{question_id}: noul value must be numeric P(yes)",
            kind="parse_error",
        )
    p_yes = float(raw)
    if p_yes < 0.0 or p_yes > 1.0:
        raise NormalizeError(
            f"answers.{question_id}: noul P(yes)={p_yes} out of [0,1]",
            kind="parse_error",
        )
    label = "yes" if p_yes >= yes_threshold else "no"
    return {
        "type": "noul",
        "p_yes": p_yes,
        "label": label,
        "yes_threshold": float(yes_threshold),
    }


def extract_noul_from_response(
    response: Any,
    *,
    question_id: str,
    yes_threshold: float = 0.5,
) -> dict[str, Any]:
    """Pull and normalize one noul answer from a Decisions response body."""
    body = _require_mapping(response, "response")
    answers = body.get("answers")
    answers_map = _require_mapping(answers, "answers")
    if question_id not in answers_map:
        raise NormalizeError(
            f"answers missing question_id {question_id!r}",
            kind="parse_error",
        )
    normalized = normalize_noul_answer(
        answers_map[question_id],
        question_id=question_id,
        yes_threshold=yes_threshold,
    )
    model = body.get("model")
    if model is not None and not isinstance(model, str):
        raise NormalizeError("response.model must be a string when present", kind="parse_error")
    return {
        **normalized,
        "model": model,
        "response_id": body.get("id") if isinstance(body.get("id"), str) else None,
    }

