"""Bias pack fixtures: legal option sets + fail-closed aggregation (no live API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.bias import (
    BIAS_PACK_V1,
    BiasPack,
    BiasQuestion,
    apply_normalized_answers,
    get_pack,
    legal_options_for,
    validate_pack,
)
from jev_classifier.normalize import NormalizeError, normalize_noul_answer

FIX = Path(__file__).resolve().parent / "fixtures" / "bias"


def _legal_fixture() -> dict:
    return json.loads((FIX / "legal_options_v1.json").read_text(encoding="utf-8"))


def _answers_ok() -> dict:
    return json.loads((FIX / "answers_ok.json").read_text(encoding="utf-8"))


def test_pack_v1_has_at_least_three_closed_questions() -> None:
    pack = get_pack("bias_pack_v1")
    validate_pack(pack)
    assert pack is BIAS_PACK_V1
    assert len(pack.questions) >= 3
    types = {q.type for q in pack.questions}
    assert "choice" in types
    assert "noul" in types


def test_fixture_legal_options_match_pack() -> None:
    pack = get_pack()
    expected = _legal_fixture()["legal_options"]
    assert set(expected.keys()) == set(pack.question_ids())
    for qid, opts in expected.items():
        assert legal_options_for(pack, qid) == frozenset(opts)


def test_apply_ok_answers_raises_expected_flags() -> None:
    pack = get_pack()
    record = apply_normalized_answers(
        pack,
        _answers_ok(),
        model="typesafe/jev-1.13",
        evidence={"state_path": "tests/fixtures/bias/claim_source_state.json"},
        recorded_at="2026-09-26T18:45:00+00:00",
    )
    d = record.to_dict()
    assert d["pack_id"] == "bias_pack_v1"
    assert d["model"] == "typesafe/jev-1.13"
    assert "source_authority_inflation" in d["raised_flags"]
    assert "recency_bias" in d["raised_flags"]
    assert "anthropomorphism" in d["raised_flags"]
    assert "overconfidence" in d["raised_flags"]
    assert d["signals"]["confirmation_cherry_pick"]["choice"] == "mild"
    assert "confirmation_cherry_pick" not in d["raised_flags"]


def test_out_of_set_choice_fails_closed() -> None:
    pack = get_pack()
    bad = _answers_ok()
    bad["recency_bias"] = {
        "type": "choice",
        "choice": "totally_illegal",
        "probabilities": {"totally_illegal": 1.0},
    }
    with pytest.raises(NormalizeError) as ei:
        apply_normalized_answers(pack, bad)
    assert ei.value.kind == "parse_error"
    assert "not in legal set" in str(ei.value)


def test_missing_question_fails_closed() -> None:
    pack = get_pack()
    bad = _answers_ok()
    del bad["overconfidence"]
    with pytest.raises(NormalizeError, match="missing answer"):
        apply_normalized_answers(pack, bad)


def test_noul_out_of_range_fails_closed() -> None:
    with pytest.raises(NormalizeError) as ei:
        normalize_noul_answer({"type": "noul", "p_yes": 1.5}, question_id="overconfidence")
    assert ei.value.kind == "parse_error"


def test_noul_missing_value_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="missing noul"):
        normalize_noul_answer({"type": "noul"}, question_id="anthropomorphism")


def test_jev_questions_map_is_well_formed() -> None:
    pack = get_pack()
    qs = pack.as_jev_questions()
    assert set(qs.keys()) == set(pack.question_ids())
    for q in pack.questions:
        body = qs[q.id]
        assert body["type"] == q.type
        if q.type == "choice":
            assert set(body["criteria"].keys()) == set(q.criteria.keys())


# --- Issue #32: score primitive wiring + flag-surface hygiene ---


def _score_pack() -> BiasPack:
    return BiasPack(
        pack_id="score_pack",
        version="0.1.0",
        description="score plumbing fixture",
        questions=(
            BiasQuestion(
                id="hedge_confidence_mismatch",
                type="score",
                signal="hedge_confidence_mismatch",
                instructions=(
                    "Does the claim's hedging language disagree with the "
                    "classifier's own stated confidence?"
                ),
                legend=("aligned", "mild_mismatch", "severe_mismatch"),
                flags_on=("severe_mismatch",),
            ),
        ),
    )


def test_score_question_is_wired_through_the_pack() -> None:
    pack = _score_pack()
    validate_pack(pack)
    assert legal_options_for(pack, "hedge_confidence_mismatch") == frozenset(
        {"aligned", "mild_mismatch", "severe_mismatch"}
    )
    qs = pack.as_jev_questions()
    assert qs["hedge_confidence_mismatch"]["type"] == "score"
    assert qs["hedge_confidence_mismatch"]["legend"] == [
        "aligned",
        "mild_mismatch",
        "severe_mismatch",
    ]


def test_score_question_aggregates_and_raises_its_declared_flag() -> None:
    pack = _score_pack()
    answers = {
        "hedge_confidence_mismatch": {
            "type": "score",
            "score": "severe_mismatch",
            "probabilities": {
                "aligned": 0.05,
                "mild_mismatch": 0.2,
                "severe_mismatch": 0.75,
            },
            "confidence": 0.7,
        }
    }
    record = apply_normalized_answers(pack, answers, model="typesafe/jev-1.13")
    d = record.to_dict()
    sig = d["signals"]["hedge_confidence_mismatch"]
    assert sig["type"] == "score"
    assert sig["score"] == "severe_mismatch"
    assert sig["legend"] == ["aligned", "mild_mismatch", "severe_mismatch"]
    assert sig["confidence"] == 0.7
    assert d["raised_flags"] == ["hedge_confidence_mismatch"]


def test_score_question_without_legend_fails_closed() -> None:
    with pytest.raises(NormalizeError, match="legend"):
        validate_pack(
            BiasPack(
                pack_id="p",
                version="1",
                description="d",
                questions=(BiasQuestion(id="s", type="score", instructions="x"),),
            )
        )


def test_score_out_of_rubric_fails_closed_in_aggregate() -> None:
    bad = {"hedge_confidence_mismatch": {"type": "score", "score": "nope"}}
    with pytest.raises(NormalizeError, match="not in"):
        apply_normalized_answers(_score_pack(), bad)


def test_flags_on_value_must_be_a_legal_value() -> None:
    # The old defect was a hardcoded flag set holding values no question could
    # return. Declaring flags per question makes that drift a validation error.
    with pytest.raises(NormalizeError, match="not a legal value"):
        validate_pack(
            BiasPack(
                pack_id="p",
                version="1",
                description="d",
                questions=(
                    BiasQuestion(
                        id="q",
                        type="choice",
                        instructions="x",
                        criteria={"a": "A", "b": "B"},
                        flags_on=("high",),
                    ),
                ),
            )
        )


def test_pack_v1_declared_flags_are_all_legal() -> None:
    pack = get_pack()
    for q in pack.questions:
        legal = legal_options_for(pack, q.id)
        for value in q.flags_on:
            assert value in legal, f"{q.id}: {value!r} not in {sorted(legal)}"


def test_noul_signal_records_the_threshold_used() -> None:
    pack = get_pack()
    record = apply_normalized_answers(pack, _answers_ok(), yes_threshold=0.6)
    assert record.to_dict()["signals"]["overconfidence"]["yes_threshold"] == 0.6


def test_question_type_surface_includes_score() -> None:
    import typing

    from jev_classifier.bias.packs import QuestionType

    assert "score" in typing.get_args(QuestionType)


def test_overconfidence_question_measures_classifier_calibration() -> None:
    # The category error (#32): the question used to ask whether the *claim text*
    # was stated with certainty beyond its support — a property of the evidence.
    # It must now be a calibration measure of the classifier's own confidence.
    q = next(q for q in get_pack().questions if q.id == "overconfidence")
    text = q.instructions.lower()
    assert "classifier" in text
    assert "confidence" in text
    assert "is the claim stated with certainty" not in text


