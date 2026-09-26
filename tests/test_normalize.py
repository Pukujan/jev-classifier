"""Unit tests for fail-closed choice normalization (no live API)."""

from __future__ import annotations

import pytest

from jev_classifier.normalize import (
    NormalizeError,
    extract_choice_from_response,
    normalize_choice_answer,
)

LEGAL = frozenset({"a", "b", "c"})


def test_normalize_choice_happy_path() -> None:
    out = normalize_choice_answer(
        {
            "type": "choice",
            "choice": "b",
            "confidence": 0.8,
            "probabilities": {"a": 0.1, "b": 0.7, "c": 0.2},
        },
        legal_options=LEGAL,
    )
    assert out["choice"] == "b"
    assert out["confidence"] == 0.8
    assert out["probabilities"]["b"] == 0.7


def test_missing_answer_type_is_accepted_when_choice_is_valid() -> None:
    out = normalize_choice_answer(
        {"choice": "b", "probabilities": {"a": 0.1, "b": 0.7, "c": 0.2}},
        legal_options=LEGAL,
        question_id="label",
    )
    assert out["choice"] == "b"


def test_out_of_set_choice_is_parse_error() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_choice_answer(
            {"type": "choice", "choice": "z", "probabilities": {"z": 1.0}},
            legal_options=LEGAL,
            question_id="label",
        )
    assert ei.value.kind == "parse_error"
    assert "not in legal set" in str(ei.value)


def test_out_of_set_probability_key_is_parse_error() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_choice_answer(
            {
                "type": "choice",
                "choice": "a",
                "probabilities": {"a": 0.5, "evil": 0.5},
            },
            legal_options=LEGAL,
        )
    assert ei.value.kind == "parse_error"


def test_missing_choice_is_parse_error() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_choice_answer({"type": "choice"}, legal_options=LEGAL)
    assert ei.value.kind == "parse_error"


def test_wrong_type_is_parse_error() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_choice_answer(
            {"type": "noul", "noul": 0.9},
            legal_options=LEGAL,
        )
    assert ei.value.kind == "parse_error"


def test_extract_from_response_preserves_model() -> None:
    raw = {
        "id": "gen-dec-test",
        "model": "typesafe/jev-1.13-20260917",
        "answers": {
            "label": {
                "type": "choice",
                "choice": "a",
                "confidence": 0.5,
                "probabilities": {"a": 1.0, "b": 0.0, "c": 0.0},
            }
        },
    }
    out = extract_choice_from_response(
        raw, question_id="label", legal_options=LEGAL
    )
    assert out["choice"] == "a"
    assert out["model"] == "typesafe/jev-1.13-20260917"
    assert out["response_id"] == "gen-dec-test"


def test_missing_question_id_is_parse_error() -> None:
    with pytest.raises(NormalizeError) as ei:
        extract_choice_from_response(
            {"answers": {}, "model": "typesafe/jev-1.13"},
            question_id="label",
            legal_options=LEGAL,
        )
    assert ei.value.kind == "parse_error"
