"""Offline tests for Issue #33 synthetic dataset fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "datasets"
CLAIM_TYPE = FIXTURES / "claim_type_shapes.json"
CONTRADICTION = FIXTURES / "contradiction_shapes.json"
PROVENANCE = FIXTURES / "PROVENANCE.json"
GENERATOR = ROOT / "scripts" / "generate_synthetic_fixtures.py"

CLAIM_TYPE_LABELS = frozenset({"background", "method", "result"})
CONTRADICTION_LABELS = frozenset(
    {"entailment", "contrasting", "neutral", "reasoning"}
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    # Normalize newlines so Windows checkout CRLF cannot drift hashes;
    # committed fixtures and generator emit LF-only (see .gitattributes).
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _load_generator_module():
    spec = importlib.util.spec_from_file_location(
        "generate_synthetic_fixtures", GENERATOR
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixture_files_exist_and_are_tiny() -> None:
    for path in (CLAIM_TYPE, CONTRADICTION, PROVENANCE):
        assert path.is_file(), path
        size = path.stat().st_size
        assert size > 0
        assert size < 50_000, f"{path.name} unexpectedly large: {size}"


def test_claim_type_label_set_and_samples() -> None:
    data = _load(CLAIM_TYPE)
    assert data["schema"] == "jev.synthetic_fixtures.claim_type.v1"
    assert data["provenance"]["kind"] == "synthetic"
    assert data["provenance"]["corpus_text"] == "none"
    assert set(data["label_set"]) == CLAIM_TYPE_LABELS
    samples = data["samples"]
    assert len(samples) >= len(CLAIM_TYPE_LABELS)
    labels_seen = {s["label"] for s in samples}
    assert labels_seen == CLAIM_TYPE_LABELS
    for sample in samples:
        assert sample["label"] in CLAIM_TYPE_LABELS
        assert isinstance(sample["id"], str) and sample["id"]
        assert isinstance(sample["text"], str) and len(sample["text"]) > 10
        # Guard against accidental corpus leakage markers
        low = sample["text"].lower()
        assert "scicite" not in low
        assert "scifact" not in low
        assert "scinli" not in low


def test_contradiction_label_set_and_samples() -> None:
    data = _load(CONTRADICTION)
    assert data["schema"] == "jev.synthetic_fixtures.contradiction.v1"
    assert data["provenance"]["kind"] == "synthetic"
    assert data["provenance"]["corpus_text"] == "none"
    assert set(data["label_set"]) == CONTRADICTION_LABELS
    samples = data["samples"]
    assert len(samples) >= len(CONTRADICTION_LABELS)
    labels_seen = {s["label"] for s in samples}
    assert labels_seen == CONTRADICTION_LABELS
    for sample in samples:
        assert sample["label"] in CONTRADICTION_LABELS
        assert sample["premise"] and sample["hypothesis"]
        blob = f"{sample['premise']} {sample['hypothesis']}".lower()
        assert "scicite" not in blob
        assert "scifact" not in blob
        assert "scinli" not in blob


def test_provenance_hashes_match_fixture_bytes() -> None:
    prov = _load(PROVENANCE)
    assert prov["schema"] == "jev.synthetic_fixtures.provenance.v1"
    assert prov["issue"] == 33
    assert prov["ruling"].startswith("synthetic-first")
    files = prov["files"]
    assert "claim_type_shapes.json" in files
    assert "contradiction_shapes.json" in files
    for name, meta in files.items():
        path = FIXTURES / name
        raw = path.read_bytes()
        normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert meta["sha256"] == _sha256_bytes(raw)
        assert meta["bytes"] == len(normalized)
        assert meta["kind"] == "synthetic"
    omission_names = {o["name"] for o in prov["omissions"]}
    assert "SciCite corpus text" in omission_names
    assert "SciNLI corpus text" in omission_names
    assert "SciFact any component" in omission_names


def test_generator_check_mode_passes() -> None:
    mod = _load_generator_module()
    assert mod.main(["--check"]) == 0


def test_datasets_md_records_synthetic_provenance() -> None:
    doc = (ROOT / "docs" / "DATASETS.md").read_text(encoding="utf-8")
    assert "synthetic" in doc.lower()
    assert "SciCite" in doc
    assert "SciNLI" in doc
    assert "SciFact" in doc
    assert "claim_type_shapes.json" in doc
    assert "contradiction_shapes.json" in doc
    # Hashes from provenance must appear in the dataset card
    prov = _load(PROVENANCE)
    for meta in prov["files"].values():
        assert meta["sha256"] in doc
