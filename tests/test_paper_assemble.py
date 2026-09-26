"""Golden claim JSON ? paper markdown; required sections + evidence citations."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.paper import (
    REQUIRED_SECTIONS,
    AssembleError,
    assemble_paper,
    validate_paper_markdown,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "paper"


def _golden_claims() -> list[dict]:
    return json.loads((FIX / "claims_golden.json").read_text(encoding="utf-8"))


def test_assemble_paper_has_required_sections_and_cites_evidence() -> None:
    claims = _golden_claims()
    md = assemble_paper(
        claims,
        title="Golden fixture research sketch",
        assembled_at="2026-09-26T18:30:00+00:00",
    )
    assert md.lstrip().startswith("# Golden fixture research sketch")
    for name in REQUIRED_SECTIONS:
        if name == "Title":
            continue
        assert f"## {name}" in md
    # Evidence ids from both claims must appear as citations
    assert "`fragment_empirical_001`" in md
    assert "`fragment_hypothesis_002`" in md
    assert "`tests/fixtures/fragment_empirical_001.json`" in md
    assert "C1" in md and "C2" in md
    validate_paper_markdown(md, claims=claims)


def test_assemble_empty_claims_fails_closed() -> None:
    with pytest.raises(AssembleError):
        assemble_paper([])


def test_assemble_missing_evidence_id_fails_closed() -> None:
    bad = {
        "label": "other",
        "epistemic_status": "Inferred",
        "recorded_at": "2026-09-26T00:00:00+00:00",
        "evidence": {},
        "model": "typesafe/jev-1.13",
    }
    with pytest.raises(AssembleError, match="evidence"):
        assemble_paper([bad])


def test_validate_detects_missing_section() -> None:
    with pytest.raises(AssembleError, match="Claims"):
        validate_paper_markdown("# T\n\n## Abstract\n\nx\n")


def test_deterministic_for_fixed_timestamp() -> None:
    claims = _golden_claims()
    a = assemble_paper(claims, assembled_at="2026-09-26T18:30:00+00:00")
    b = assemble_paper(claims, assembled_at="2026-09-26T18:30:00+00:00")
    assert a == b
