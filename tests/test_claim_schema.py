"""Red-first / PCM claim-ledger alignment tests (Issue #10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.classify import (
    LEGACY_CLAIM_KEY_ALIASES,
    PCM_CLAIM_KEYS,
    REQUIRED_CLAIM_KEYS,
    build_claim_record,
    migrate_legacy_claim,
    normalize_claim_record,
    validate_claim_record,
)
from jev_classifier.normalize import NormalizeError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ONTOLOGY = ROOT / "ontology" / "jev_classifier_claims.ttl"
SCHEMA_DOC = ROOT / "docs" / "CLAIM_SCHEMA.md"


def test_claim_schema_doc_exists_and_lists_pcm_fields() -> None:
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    for key in (
        "epistemic_status",
        "valid_from",
        "valid_to",
        "recorded_at",
        "supersedes",
        "independence_class",
        "about",
    ):
        assert key in text
    assert "PCM" in text


def test_ontology_declares_independence_class() -> None:
    text = ONTOLOGY.read_text(encoding="utf-8")
    assert "jcc:independenceClass" in text
    assert "jcc:epistemicStatus" in text
    assert "jcc:supersedes" in text


def test_golden_claim_covers_pcm_optional_keys() -> None:
    claim = json.loads((FIXTURES / "claim_empirical_001.json").read_text(encoding="utf-8"))
    for key in (
        "epistemic_status",
        "valid_from",
        "valid_to",
        "recorded_at",
        "supersedes",
        "independence_class",
    ):
        assert key in claim
    assert REQUIRED_CLAIM_KEYS <= set(claim.keys())
    assert set(claim.keys()) <= (PCM_CLAIM_KEYS | {"notes"})


def test_required_keys_constant_matches_schema() -> None:
    assert REQUIRED_CLAIM_KEYS == frozenset(
        {"label", "epistemic_status", "recorded_at", "evidence", "model"}
    )


def test_migrate_legacy_camelcase_keys() -> None:
    legacy = {
        "label": "empirical_finding",
        "epistemicStatus": "Inferred",
        "recordedAt": "2026-09-26T18:00:00+00:00",
        "validFrom": "2026-09-01T00:00:00+00:00",
        "validTo": None,
        "independenceClass": "single-run",
        "evidence": {"fragment_id": "f1"},
        "model": "typesafe/jev-1.13",
        "supersedes": None,
    }
    migrated = migrate_legacy_claim(legacy)
    assert "epistemicStatus" not in migrated
    assert migrated["epistemic_status"] == "Inferred"
    assert migrated["recorded_at"] == "2026-09-26T18:00:00+00:00"
    assert migrated["valid_from"] == "2026-09-01T00:00:00+00:00"
    assert migrated["independence_class"] == "single-run"
    for legacy_key in LEGACY_CLAIM_KEY_ALIASES:
        assert legacy_key not in migrated


def test_migrate_canonical_wins_over_legacy() -> None:
    raw = {
        "epistemic_status": "Observed",
        "epistemicStatus": "Inferred",
        "recorded_at": "2026-09-26T18:00:00+00:00",
        "label": "other",
        "evidence": {"path": "x"},
        "model": "typesafe/jev-1.13",
    }
    out = normalize_claim_record(raw)
    assert out["epistemic_status"] == "Observed"
    assert "epistemicStatus" not in out


def test_validate_accepts_migrated_legacy_claim() -> None:
    legacy = {
        "label": "empirical_finding",
        "epistemicStatus": "Inferred",
        "recordedAt": "2026-09-26T18:00:00+00:00",
        "evidence": {"fragment_id": "f1", "path": "tests/fixtures/x.json"},
        "model": "typesafe/jev-1.13",
        "supersedes": "claim-prior-001",
        "independenceClass": "cross-source",
    }
    out = validate_claim_record(
        legacy, legal_labels={"empirical_finding", "other"}
    )
    assert out["epistemic_status"] == "Inferred"
    assert out["supersedes"] == "claim-prior-001"
    assert out["independence_class"] == "cross-source"


def test_supersedes_null_ok() -> None:
    claim = build_claim_record(
        label="other",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x"},
        supersedes=None,
    )
    validate_claim_record(claim, legal_labels={"other"})


def test_supersedes_nonempty_string_ok() -> None:
    claim = build_claim_record(
        label="other",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x"},
        supersedes="claim-old-1",
        claim_id="claim-new-1",
    )
    out = validate_claim_record(claim, legal_labels={"other"})
    assert out["supersedes"] == "claim-old-1"
    assert out["id"] == "claim-new-1"


def test_supersedes_empty_string_fails_closed() -> None:
    claim = build_claim_record(
        label="other",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x"},
        supersedes="   ",
    )
    with pytest.raises(NormalizeError, match="supersedes") as ei:
        validate_claim_record(claim, legal_labels={"other"})
    assert ei.value.kind == "parse_error"


def test_supersedes_non_string_fails_closed() -> None:
    claim = build_claim_record(
        label="other",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x"},
    )
    claim["supersedes"] = ["not", "a", "string"]
    with pytest.raises(NormalizeError, match="supersedes") as ei:
        validate_claim_record(claim, legal_labels={"other"})
    assert ei.value.kind == "parse_error"


def test_paper_golden_supersedes_link_shape() -> None:
    claims = json.loads(
        (FIXTURES / "paper" / "claims_golden.json").read_text(encoding="utf-8")
    )
    legal = {"empirical_finding", "hypothesis", "other"}
    for c in claims:
        out = validate_claim_record(c, legal_labels=legal)
        if out.get("supersedes") is not None:
            assert isinstance(out["supersedes"], str)
            assert out["supersedes"].strip()