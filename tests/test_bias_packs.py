"""Bias pack fixtures: legal option sets + fail-closed aggregation (no live API)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.bias import (
    BIAS_PACK_V1,
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
