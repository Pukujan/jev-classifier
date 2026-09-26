"""Iteration 2 tests: ontology parse, fixture keys, fail-closed classify shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.classify import (
    REQUIRED_CLAIM_KEYS,
    build_claim_record,
    load_fragment_fixture,
    validate_claim_record,
)
from jev_classifier.normalize import NormalizeError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ONTOLOGY = ROOT / "ontology" / "jev_classifier_claims.ttl"


def test_rdflib_parses_claims_ttl() -> None:
    rdflib = pytest.importorskip("rdflib")
    g = rdflib.Graph()
    g.parse(str(ONTOLOGY), format="turtle")
    assert len(g) > 0
    # Spot-check class URIs exist as subjects
    text = ONTOLOGY.read_text(encoding="utf-8")
    assert "jcc:Claim" in text
    assert "jcc:SourceFragment" in text
    assert "jcc:epistemicStatus" in text
    assert "jcc:validFrom" in text
    assert "jcc:validTo" in text
    assert "jcc:recordedAt" in text
    assert "jcc:supersedes" in text


def test_fragment_fixture_has_closed_set() -> None:
    frag = load_fragment_fixture(FIXTURES / "fragment_empirical_001.json")
    assert "empirical_finding" in frag["closed_label_set"]
    assert frag["question_id"] == "claim_kind"
    assert set(frag["criteria"].keys()) == set(frag["closed_label_set"])


def test_golden_claim_has_required_keys() -> None:
    claim = json.loads((FIXTURES / "claim_empirical_001.json").read_text(encoding="utf-8"))
    legal = set(
        json.loads((FIXTURES / "fragment_empirical_001.json").read_text(encoding="utf-8"))[
            "closed_label_set"
        ]
    )
    validate_claim_record(claim, legal_labels=legal)
    assert REQUIRED_CLAIM_KEYS <= set(claim.keys())


def test_out_of_set_claim_label_fails_closed() -> None:
    claim = build_claim_record(
        label="not_a_real_label",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x", "path": "tests/fixtures/x.json"},
    )
    with pytest.raises(NormalizeError) as ei:
        validate_claim_record(claim, legal_labels={"empirical_finding", "other"})
    assert ei.value.kind == "parse_error"


def test_missing_required_claim_key_fails_closed() -> None:
    with pytest.raises(NormalizeError) as ei:
        validate_claim_record(
            {
                "label": "other",
                "epistemic_status": "Inferred",
                "recorded_at": "2026-09-26T00:00:00+00:00",
                # missing evidence + model
            },
            legal_labels={"other"},
        )
    assert ei.value.kind == "parse_error"
