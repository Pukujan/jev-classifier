"""Contract tests for the metadata-only paper-selection manifest (#29)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "datasets" / "reference_papers.json"
SCHEMA = ROOT / "schemas" / "reference_papers.schema.json"
VALIDATOR = ROOT / "scripts" / "validate_reference_papers.py"


def _canonical_write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _run(path: Path = MANIFEST) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--manifest", str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_schema_is_draft_2020_12_and_validates_manifest() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    jsonschema.Draft202012Validator.check_schema(schema)
    result = _run()
    assert result.returncode == 0, result.stderr
    assert "VALID: 10 reference-paper candidates" in result.stdout


def test_manifest_is_canonical_small_and_metadata_only() -> None:
    raw = MANIFEST.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    assert raw == canonical.encode("utf-8")
    assert len(raw) < 50_000
    assert all("abstract" not in paper and "full_text" not in paper for paper in value["papers"])
    assert len(value["papers"]) == 10


def test_duplicate_doi_fails_cross_record_validation(tmp_path: Path) -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    value["papers"][1]["doi"] = value["papers"][0]["doi"]
    candidate = tmp_path / "duplicate-doi.json"
    _canonical_write(candidate, value)
    result = _run(candidate)
    assert result.returncode == 1
    assert "duplicate DOI" in result.stderr


def test_missing_license_evidence_fails_schema(tmp_path: Path) -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    del value["papers"][0]["license"]["evidence_urls"]
    candidate = tmp_path / "missing-license-evidence.json"
    _canonical_write(candidate, value)
    result = _run(candidate)
    assert result.returncode == 1
    assert "schema error" in result.stderr


def test_manifest_rejects_paper_text_field(tmp_path: Path) -> None:
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    value["papers"][0]["abstract"] = "Paper text must not be committed here."
    candidate = tmp_path / "paper-text.json"
    _canonical_write(candidate, value)
    result = _run(candidate)
    assert result.returncode == 1
    assert "schema error" in result.stderr
