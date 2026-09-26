"""Fail-closed noul normalization (no live API)."""

from __future__ import annotations

import pytest

from jev_classifier.normalize import NormalizeError, normalize_noul_answer


def test_noul_happy_path_yes() -> None:
    out = normalize_noul_answer({"type": "noul", "p_yes": 0.9})
    assert out["label"] == "yes"
    assert out["p_yes"] == 0.9


def test_noul_happy_path_no() -> None:
    out = normalize_noul_answer({"type": "noul", "noul": 0.2})
    assert out["label"] == "no"
    assert out["p_yes"] == 0.2


def test_noul_wrong_type_fails() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_noul_answer({"type": "choice", "choice": "a"})
    assert ei.value.kind == "parse_error"


def test_noul_missing_answer_type_is_accepted() -> None:
    out = normalize_noul_answer({"noul": 0.8}, question_id="signal")
    assert out["label"] == "yes"
    assert out["p_yes"] == 0.8
