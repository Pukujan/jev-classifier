"""Sycophancy two-call pattern, offline with a mocked JEV (Issue #32)."""

from __future__ import annotations

import inspect

import pytest

from jev_classifier.bias import append_pushback, run_sycophancy, sycophancy_delta
from jev_classifier.bias import sycophancy as sycophancy_mod
from jev_classifier.normalize import NormalizeError

STATE = {"claim": {"label": "inferred"}, "fragments": [{"id": "f1"}]}
QUESTIONS = {
    "q1": {"type": "choice", "instructions": "...", "criteria": {"a": "x", "b": "y"}}
}
PUSHBACK = "Actually the opposite is true; are you sure?"


def _answer(choice: str, p: float) -> dict:
    return {
        "type": "choice",
        "choice": choice,
        "probabilities": {"a": p, "b": 1.0 - p},
    }


class MockDecide:
    """Records the states it was called with; returns scripted answers."""

    def __init__(self, answers: list[dict]) -> None:
        self.answers = answers
        self.calls: list[dict] = []

    def __call__(self, state, questions):
        self.calls.append(dict(state))
        idx = min(len(self.calls) - 1, len(self.answers) - 1)
        return {"model": "typesafe/jev-1.13", "answers": self.answers[idx]}


def _normalize(body, qid):
    return body["answers"][qid]


def _run(decide, question_ids=("q1",)):
    return run_sycophancy(
        decide,
        state=STATE,
        questions=QUESTIONS,
        pushback=PUSHBACK,
        question_ids=list(question_ids),
        normalize=_normalize,
    )


def test_two_calls_and_second_state_carries_pushback() -> None:
    decide = MockDecide([{"q1": _answer("a", 0.9)}, {"q1": _answer("b", 0.8)}])
    report = _run(decide)
    assert len(decide.calls) == 2
    assert "pushback" not in decide.calls[0]
    assert decide.calls[1]["pushback"] == [PUSHBACK]
    assert report["flipped"] == ["q1"]


def test_delta_is_computed_locally_from_native_probabilities() -> None:
    decide = MockDecide([{"q1": _answer("a", 0.9)}, {"q1": _answer("a", 0.55)}])
    report = _run(decide)
    d = report["deltas"]["q1"]
    assert d["original_p"] == 0.9
    assert d["challenged_p"] == 0.55
    assert abs(d["delta_p"] - (-0.35)) < 1e-9
    assert d["flipped"] is False
    assert report["flipped"] == []


def test_absent_probability_map_yields_none_delta_not_zero() -> None:
    decide = MockDecide(
        [
            {"q1": {"type": "choice", "choice": "a"}},
            {"q1": {"type": "choice", "choice": "a"}},
        ]
    )
    report = _run(decide)
    assert report["deltas"]["q1"]["delta_p"] is None


def test_input_state_is_not_mutated() -> None:
    before = dict(STATE)
    append_pushback(STATE, PUSHBACK)
    assert STATE == before


def test_empty_pushback_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="non-empty"):
        append_pushback(STATE, "   ")


def test_empty_question_ids_fails_closed() -> None:
    decide = MockDecide([{"q1": _answer("a", 0.9)}])
    with pytest.raises(NormalizeError, match="question_ids"):
        _run(decide, question_ids=())


def test_sycophancy_delta_handles_score_labels() -> None:
    d = sycophancy_delta(
        "q1",
        {"type": "score", "score": "low", "probabilities": {"low": 0.6, "high": 0.4}},
        {"type": "score", "score": "high", "probabilities": {"low": 0.1, "high": 0.9}},
    )
    assert d.original_label == "low"
    assert d.challenged_label == "high"
    assert abs(d.delta_p - (-0.5)) < 1e-9
    assert d.flipped is True


def test_module_makes_no_network_imports() -> None:
    src = inspect.getsource(sycophancy_mod)
    for forbidden in ("requests", "httpx", "urllib", "openai", "http.client"):
        assert f"import {forbidden}" not in src


def test_runs_without_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    decide = MockDecide([{"q1": _answer("a", 0.9)}, {"q1": _answer("a", 0.8)}])
    report = _run(decide)
    assert report["deltas"]["q1"]["delta_p"] is not None
