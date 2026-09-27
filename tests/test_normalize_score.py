"""Score primitive normalization: fail-closed and rubric-ordered (Issue #32)."""

from __future__ import annotations

import pytest

from jev_classifier.normalize import (
    NormalizeError,
    extract_score_from_response,
    normalize_score_answer,
)

RUBRIC = ("low", "medium", "high")


def _ok() -> dict:
    return {
        "type": "score",
        "score": "medium",
        "probabilities": {"low": 0.2, "medium": 0.7, "high": 0.1},
        "confidence": 0.66,
    }


def test_happy_path_preserves_native_map_and_confidence() -> None:
    out = normalize_score_answer(_ok(), legal_scores=RUBRIC, question_id="q1")
    assert out["type"] == "score"
    assert out["score"] == "medium"
    assert out["legend"] == ["low", "medium", "high"]
    assert out["probabilities"] == {"low": 0.2, "medium": 0.7, "high": 0.1}
    assert out["confidence"] == 0.66


def test_surfaced_legend_is_preserved_when_it_matches() -> None:
    body = _ok()
    body["legend"] = ["low", "medium", "high"]
    out = normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")
    assert out["legend"] == ["low", "medium", "high"]


def test_requested_legend_order_is_kept() -> None:
    out = normalize_score_answer(
        _ok(), legal_scores=("high", "medium", "low"), question_id="q1"
    )
    assert out["legend"] == ["high", "medium", "low"]


def test_set_rubric_is_sorted_deterministically() -> None:
    out = normalize_score_answer(
        _ok(), legal_scores={"medium", "low", "high"}, question_id="q1"
    )
    assert out["legend"] == ["high", "low", "medium"]


def test_score_outside_rubric_fails_closed() -> None:
    body = _ok()
    body["score"] = "catastrophic"
    with pytest.raises(NormalizeError) as ei:
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")
    assert ei.value.kind == "parse_error"
    assert "not in rubric" in str(ei.value)


def test_probability_key_outside_rubric_fails_closed() -> None:
    body = _ok()
    body["probabilities"]["catastrophic"] = 0.0
    with pytest.raises(NormalizeError, match="not in legal set"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_missing_score_fails_closed() -> None:
    body = _ok()
    del body["score"]
    with pytest.raises(NormalizeError, match="missing or non-string score"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_wrong_type_fails_closed() -> None:
    body = _ok()
    body["type"] = "choice"
    with pytest.raises(NormalizeError, match="expected type=score"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_empty_rubric_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="must be non-empty"):
        normalize_score_answer(_ok(), legal_scores=(), question_id="q1")


def test_duplicate_rubric_levels_fail_closed() -> None:
    with pytest.raises(NormalizeError, match="unique"):
        normalize_score_answer(_ok(), legal_scores=("low", "low"), question_id="q1")


def test_surfaced_legend_mismatch_fails_closed() -> None:
    body = _ok()
    body["legend"] = ["low", "medium", "very_high"]
    with pytest.raises(NormalizeError, match="does not"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_string_legend_fails_closed() -> None:
    body = _ok()
    body["legend"] = "low, medium, high"
    with pytest.raises(NormalizeError, match="ordered list"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_non_numeric_probability_fails_closed() -> None:
    body = _ok()
    body["probabilities"]["high"] = "0.1"
    with pytest.raises(NormalizeError, match="must be numeric"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_bool_confidence_fails_closed() -> None:
    body = _ok()
    body["confidence"] = True
    with pytest.raises(NormalizeError, match="confidence must be numeric"):
        normalize_score_answer(body, legal_scores=RUBRIC, question_id="q1")


def test_absent_probabilities_and_confidence_are_none_not_fabricated() -> None:
    out = normalize_score_answer(
        {"type": "score", "score": "low"}, legal_scores=RUBRIC, question_id="q1"
    )
    assert out["probabilities"] is None
    assert out["confidence"] is None


def test_extract_from_response_preserves_model_and_response_id() -> None:
    resp = {
        "id": "gen-abc",
        "model": "typesafe/jev-1.13",
        "answers": {"q1": _ok()},
    }
    out = extract_score_from_response(resp, question_id="q1", legal_scores=RUBRIC)
    assert out["score"] == "medium"
    assert out["model"] == "typesafe/jev-1.13"
    assert out["response_id"] == "gen-abc"


def test_extract_missing_question_id_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="missing question_id"):
        extract_score_from_response({"answers": {}}, question_id="q1", legal_scores=RUBRIC)


def test_extract_missing_answers_object_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="answers"):
        extract_score_from_response({}, question_id="q1", legal_scores=RUBRIC)


def test_extract_non_string_model_fails_closed() -> None:
    resp = {"model": 7, "answers": {"q1": _ok()}}
    with pytest.raises(NormalizeError, match="model must be a string"):
        extract_score_from_response(resp, question_id="q1", legal_scores=RUBRIC)
