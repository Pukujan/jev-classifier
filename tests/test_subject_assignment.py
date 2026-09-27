"""Closed-taxonomy subject assignment onto claim.about (Issue #72)."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from jev_classifier.classify import (
    SUBJECT_QUESTION_ID,
    UNKNOWN_SUBJECT,
    classify_fragment,
    derive_subject_candidates,
    load_fragment_fixture,
    require_subject_taxonomy,
    subject_choice_options,
)
from jev_classifier.normalize import NormalizeError

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EMPIRICAL = FIXTURES / "fragment_empirical_001.json"


class FakeDecisionsClient:
    """Minimal stand-in; returns a fixed Decisions response body."""

    def __init__(self, response: Mapping[str, Any]) -> None:
        self.model = "typesafe/jev-1.13"
        self._response = dict(response)
        self.calls: list[dict[str, Any]] = []

    def decide(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        del model
        self.calls.append({"state": state, "questions": dict(questions)})
        return dict(self._response)


def _base_fragment(**overrides: Any) -> dict[str, Any]:
    frag = load_fragment_fixture(EMPIRICAL)
    frag.update(overrides)
    return frag


def _label_answer(choice: str = "empirical_finding") -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": choice,
        "probabilities": {
            "empirical_finding": 0.9,
            "method_claim": 0.05,
            "opinion": 0.03,
            "other": 0.02,
        },
        "confidence": 0.85,
    }


def _subject_answer(choice: str, taxonomy: list[str]) -> dict[str, Any]:
    options = subject_choice_options(taxonomy)
    probs = {opt: (0.85 if opt == choice else 0.05) for opt in options}
    # renormalize roughly for fixture realism
    total = sum(probs.values())
    probs = {k: v / total for k, v in probs.items()}
    return {
        "type": "choice",
        "choice": choice,
        "probabilities": probs,
        "confidence": 0.85,
    }


def _response(label: str, subject: str, taxonomy: list[str]) -> dict[str, Any]:
    return {
        "id": "mock-resp-subject",
        "model": "typesafe/jev-1.13",
        "answers": {
            "claim_kind": _label_answer(label),
            SUBJECT_QUESTION_ID: _subject_answer(subject, taxonomy),
        },
    }


def test_derive_subject_candidates_from_title_section() -> None:
    frag = load_fragment_fixture(EMPIRICAL)
    assert derive_subject_candidates(frag) == ["controlled_study_primary_endpoint"]
    assert frag["subject_candidates"] == ["controlled_study_primary_endpoint"]


def test_in_set_subject_lands_on_claim_about() -> None:
    frag = _base_fragment()
    taxonomy = require_subject_taxonomy(frag)
    client = FakeDecisionsClient(
        _response("empirical_finding", "controlled_study_primary_endpoint", taxonomy)
    )
    claim = classify_fragment(frag, client=client)  # type: ignore[arg-type]
    assert claim["about"] == "controlled_study_primary_endpoint"
    assert claim["label"] == "empirical_finding"
    assert SUBJECT_QUESTION_ID in client.calls[0]["questions"]
    assert set(client.calls[0]["questions"][SUBJECT_QUESTION_ID]["criteria"]) == set(
        subject_choice_options(taxonomy)
    )


def test_out_of_set_subject_fails_closed() -> None:
    frag = _base_fragment()
    taxonomy = require_subject_taxonomy(frag)
    client = FakeDecisionsClient(_response("empirical_finding", "not_in_taxonomy", taxonomy))
    # Force out-of-set choice past the helper's option list.
    client._response["answers"][SUBJECT_QUESTION_ID]["choice"] = "not_in_taxonomy"
    client._response["answers"][SUBJECT_QUESTION_ID]["probabilities"] = {
        "not_in_taxonomy": 1.0
    }
    with pytest.raises(NormalizeError) as ei:
        classify_fragment(frag, client=client)  # type: ignore[arg-type]
    assert ei.value.kind == "parse_error"
    assert "not_in_taxonomy" in str(ei.value)


def test_unknown_subject_leaves_about_unset() -> None:
    frag = _base_fragment()
    taxonomy = require_subject_taxonomy(frag)
    client = FakeDecisionsClient(_response("empirical_finding", UNKNOWN_SUBJECT, taxonomy))
    claim = classify_fragment(frag, client=client)  # type: ignore[arg-type]
    assert "about" not in claim
    assert claim["label"] == "empirical_finding"


def test_empty_taxonomy_errors() -> None:
    frag = _base_fragment(subject_taxonomy=[], subject_candidates=[])
    with pytest.raises(NormalizeError, match="subject_taxonomy"):
        classify_fragment(frag, client=FakeDecisionsClient({}))  # type: ignore[arg-type]


def test_missing_taxonomy_errors() -> None:
    frag = _base_fragment()
    del frag["subject_taxonomy"]
    frag.pop("subject_candidates", None)
    with pytest.raises(NormalizeError, match="subject_taxonomy"):
        classify_fragment(frag, client=FakeDecisionsClient({}))  # type: ignore[arg-type]


def test_load_fixture_rejects_mismatched_committed_candidates() -> None:
    # Write a temp bad fixture under fixtures dir then load — use in-memory path via tmp.
    import json
    import tempfile

    good = json.loads(EMPIRICAL.read_text(encoding="utf-8"))
    good["subject_candidates"] = ["enrollment_methods"]  # not derived from title/section
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", delete=False
    ) as fh:
        json.dump(good, fh)
        path = Path(fh.name)
    try:
        with pytest.raises(ValueError, match="subject_candidates"):
            load_fragment_fixture(path)
    finally:
        path.unlink(missing_ok=True)
