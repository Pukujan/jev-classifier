"""Multi-source classify → paper e2e with mocked JEV (Issue #12).

Offline only: FakeDecisionsClient returns fixture answers. No live API, no HF.
Two correlated synthetic sources → two claims → paper with cross-source lineage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

from jev_classifier.classify import (
    classify_fragment,
    load_fragment_fixture,
    validate_claim_record,
)
from jev_classifier.paper import assemble_paper, validate_paper_markdown

FIX = Path(__file__).resolve().parent / "fixtures" / "multisource"
FRAG_A = FIX / "fragment_method_a.json"
FRAG_B = FIX / "fragment_result_b.json"
MOCKS = FIX / "mock_jev_answers.json"


class FakeDecisionsClient:
    """Minimal stand-in for DecisionsClient; no network."""

    def __init__(self, responses_by_fragment_id: Mapping[str, Mapping[str, Any]]) -> None:
        self.model = "typesafe/jev-1.13"
        self._responses = dict(responses_by_fragment_id)

    def decide(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        del questions, model
        if not isinstance(state, Mapping):
            raise RuntimeError("fake client expects mapping state")
        fid = state.get("fragment_id")
        if fid not in self._responses:
            raise RuntimeError(f"no mock response for fragment_id={fid!r}")
        return dict(self._responses[fid])


def _load_mocks() -> dict[str, Any]:
    return json.loads(MOCKS.read_text(encoding="utf-8"))


def test_multisource_fixtures_exist_and_correlate() -> None:
    a = load_fragment_fixture(FRAG_A)
    b = load_fragment_fixture(FRAG_B)
    assert a["id"] != b["id"]
    assert a["source_id"] != b["source_id"]
    # Correlated: both refer to Study Alpha
    assert "Study Alpha" in a["text"] or "Study Alpha" in a.get("title", "")
    assert "Study Alpha" in b["text"]
    assert set(a["closed_label_set"]) == set(b["closed_label_set"])


def test_multisource_classify_mock_to_paper_e2e() -> None:
    mocks = _load_mocks()
    client = FakeDecisionsClient(mocks)

    frag_a = load_fragment_fixture(FRAG_A)
    frag_b = load_fragment_fixture(FRAG_B)

    claim_a = classify_fragment(
        frag_a,
        client=client,  # type: ignore[arg-type]
        evidence_path="tests/fixtures/multisource/fragment_method_a.json",
    )
    claim_b = classify_fragment(
        frag_b,
        client=client,  # type: ignore[arg-type]
        evidence_path="tests/fixtures/multisource/fragment_result_b.json",
    )

    legal = frozenset(frag_a["closed_label_set"])
    claim_a = validate_claim_record(claim_a, legal_labels=legal)
    claim_b = validate_claim_record(claim_b, legal_labels=legal)

    assert claim_a["label"] == "method_claim"
    assert claim_b["label"] == "empirical_finding"
    assert claim_a["evidence"]["fragment_id"] == "msrc-frag-method-a"
    assert claim_b["evidence"]["fragment_id"] == "msrc-frag-result-b"

    # Enrich with paper-facing lineage across sources (application-owned fields)
    claim_a = {
        **claim_a,
        "id": "C-method-alpha",
        "independence_class": "cross-source",
        "supersedes": None,
        "evidence": {
            **claim_a["evidence"],
            "source_id": frag_a["source_id"],
        },
    }
    claim_b = {
        **claim_b,
        "id": "C-result-alpha",
        "independence_class": "cross-source",
        "supersedes": "C-result-alpha-draft",
        "valid_from": "2026-09-01T00:00:00+00:00",
        "valid_to": None,
        "evidence": {
            **claim_b["evidence"],
            "source_id": frag_b["source_id"],
        },
    }
    # Consolidated claim citing both sources (lineage across sources)
    claim_joint = {
        "id": "C-alpha-joint",
        "label": "empirical_finding",
        "epistemic_status": "Inferred",
        "recorded_at": "2026-09-26T19:00:00+00:00",
        "valid_from": "2026-09-01T00:00:00+00:00",
        "valid_to": None,
        "supersedes": "C-result-alpha",
        "independence_class": "cross-source",
        "model": "typesafe/jev-1.13",
        "confidence": None,
        "probabilities": None,
        "evidence": {
            "fragment_id": "msrc-frag-result-b",
            "source_id": "src-preprint-alpha",
            "path": "tests/fixtures/multisource/fragment_result_b.json",
            "ids": ["msrc-frag-method-a", "src-lab-alpha"],
        },
    }
    for c in (claim_a, claim_b, claim_joint):
        validate_claim_record(c, legal_labels=legal)

    md = assemble_paper(
        [claim_a, claim_b, claim_joint],
        title="Study Alpha multi-source sketch",
        assembled_at="2026-09-26T19:05:00+00:00",
    )
    validate_paper_markdown(md, claims=[claim_a, claim_b, claim_joint])

    # Both source fragments / source_ids appear in citations + claims
    assert "`msrc-frag-method-a`" in md
    assert "`msrc-frag-result-b`" in md
    assert "`src-lab-alpha`" in md
    assert "`src-preprint-alpha`" in md
    assert "## Lineage" in md
    assert "supersedes: `C-result-alpha-draft`" in md
    assert "supersedes: `C-result-alpha`" in md
    assert "independence_class: `cross-source`" in md
    assert "C-method-alpha" in md and "C-result-alpha" in md and "C-alpha-joint" in md


def test_fake_client_unknown_fragment_fails_closed() -> None:
    client = FakeDecisionsClient({})
    frag = load_fragment_fixture(FRAG_A)
    with pytest.raises(RuntimeError, match="no mock response"):
        classify_fragment(frag, client=client)  # type: ignore[arg-type]