"""Managed documentation manifest validator tests (#63)."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from jev_classifier.docs import (
    MANIFEST_PATH,
    MANIFEST_SCHEMA,
    DocsManifestError,
    load_manifest,
    validate_manifest,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "docs"
VALIDATOR_SOURCE = (
    Path(__file__).resolve().parents[1] / "src" / "jev_classifier" / "docs" / "validate.py"
)


def _fixture() -> dict:
    return json.loads((FIX / "manifest_ok.json").read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialize(tmp_path: Path, files: dict[str, str]) -> Path:
    """Create ``files`` (relative path -> text) under a fresh tmp root."""
    root = tmp_path / "root"
    for relative, text in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return root


def _document(document_id: str, path: str, sha256: str, **overrides) -> dict:
    document = {
        "id": document_id,
        "path": path,
        "title": document_id.title(),
        "summary": f"{document_id} summary.",
        "audience": "newcomer",
        "status": "shipped",
        "owner_issue": 63,
        "parent": None,
        "keywords": ["fixture"],
        "related": [],
        "canonical_sources": [],
        "review_state": "reviewed",
        "reviewed_commit": "uncommitted",
        "reviewed_sha256": sha256,
    }
    document.update(overrides)
    return document


def _manifest(documents: list[dict], excluded_paths: list[dict] | None = None) -> dict:
    return {
        "schema": "jev-classifier.docs-manifest.v1",
        "manifest_version": "1.0.0",
        "excluded_paths": excluded_paths if excluded_paths is not None else [],
        "documents": documents,
    }


# --- constants and loading ---


def test_manifest_schema_file_exists() -> None:
    assert MANIFEST_SCHEMA == "docs_manifest.schema.json"
    assert (Path(__file__).resolve().parents[1] / "schemas" / MANIFEST_SCHEMA).is_file()


def test_load_manifest_reads_the_fixture() -> None:
    manifest = load_manifest(FIX / "manifest_ok.json")
    assert manifest["schema"] == "jev-classifier.docs-manifest.v1"
    assert len(manifest["documents"]) == 2


def test_load_manifest_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(DocsManifestError, match="not found") as excinfo:
        load_manifest(tmp_path / "absent.json")
    assert excinfo.value.kind == "schema_error"


def test_default_manifest_path_is_docs_docs_manifest_json() -> None:
    assert MANIFEST_PATH.as_posix().endswith("docs/docs_manifest.json")


# --- positive case ---


def test_valid_fixture_manifest_passes() -> None:
    validate_manifest(_fixture(), root=FIX)


def test_freshness_can_be_skipped() -> None:
    manifest = _fixture()
    manifest["documents"][0]["reviewed_sha256"] = "0" * 64
    validate_manifest(manifest, root=FIX, check_freshness=False)


# --- shape: fail closed ---


def test_unknown_manifest_key_fails_closed() -> None:
    manifest = _fixture()
    manifest["extra"] = True
    with pytest.raises(DocsManifestError, match="unknown key") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "schema_error"


def test_unknown_document_key_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["note"] = "x"
    with pytest.raises(DocsManifestError, match="unknown key"):
        validate_manifest(manifest, root=FIX)


def test_unknown_source_ref_key_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["canonical_sources"][0]["note"] = "x"
    with pytest.raises(DocsManifestError, match="unknown key"):
        validate_manifest(manifest, root=FIX)


def test_bad_schema_id_fails_closed() -> None:
    manifest = _fixture()
    manifest["schema"] = "jev-classifier.docs-manifest.v2"
    with pytest.raises(DocsManifestError, match="schema must be"):
        validate_manifest(manifest, root=FIX)


def test_bad_manifest_version_fails_closed() -> None:
    manifest = _fixture()
    manifest["manifest_version"] = "1.0"
    with pytest.raises(DocsManifestError, match="semver"):
        validate_manifest(manifest, root=FIX)


def test_empty_documents_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"] = []
    with pytest.raises(DocsManifestError, match="non-empty"):
        validate_manifest(manifest, root=FIX)


def test_bad_document_id_pattern_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["id"] = "Alpha Doc"
    with pytest.raises(DocsManifestError, match="id"):
        validate_manifest(manifest, root=FIX)


def test_unknown_audience_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["audience"] = "public"
    with pytest.raises(DocsManifestError, match="audience") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "schema_error"


def test_unknown_status_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["status"] = "done"
    with pytest.raises(DocsManifestError, match="status"):
        validate_manifest(manifest, root=FIX)


def test_unknown_review_state_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["review_state"] = "approved"
    with pytest.raises(DocsManifestError, match="review_state"):
        validate_manifest(manifest, root=FIX)


def test_unknown_source_kind_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["canonical_sources"][0]["kind"] = "blog"
    with pytest.raises(DocsManifestError, match="kind"):
        validate_manifest(manifest, root=FIX)


def test_zero_owner_issue_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["owner_issue"] = 0
    with pytest.raises(DocsManifestError, match="owner_issue"):
        validate_manifest(manifest, root=FIX)


def test_bad_reviewed_commit_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["reviewed_commit"] = "deadbeef"
    with pytest.raises(DocsManifestError, match="reviewed_commit"):
        validate_manifest(manifest, root=FIX)


def test_bad_reviewed_sha256_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["reviewed_sha256"] = "abc"
    with pytest.raises(DocsManifestError, match="reviewed_sha256"):
        validate_manifest(manifest, root=FIX)


def test_empty_keyword_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["keywords"] = [""]
    with pytest.raises(DocsManifestError, match="keywords"):
        validate_manifest(manifest, root=FIX)


def test_missing_required_document_key_fails_closed() -> None:
    manifest = _fixture()
    del manifest["documents"][0]["summary"]
    with pytest.raises(DocsManifestError, match="summary"):
        validate_manifest(manifest, root=FIX)


def test_missing_owner_issue_fails_closed() -> None:
    # owner_issue is required even though it may be null.
    manifest = _fixture()
    del manifest["documents"][0]["owner_issue"]
    with pytest.raises(DocsManifestError, match="owner_issue"):
        validate_manifest(manifest, root=FIX)


def test_absent_parent_is_allowed() -> None:
    # parent is the one optional document key.
    manifest = _fixture()
    del manifest["documents"][1]["parent"]
    validate_manifest(manifest, root=FIX)


# --- identity and reference integrity ---


def test_duplicate_document_id_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"].append(copy.deepcopy(manifest["documents"][0]))
    with pytest.raises(DocsManifestError, match="duplicate document id") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "schema_error"


def test_duplicate_document_path_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][1]["path"] = manifest["documents"][0]["path"]
    with pytest.raises(DocsManifestError, match="duplicate document path"):
        validate_manifest(manifest, root=FIX)


def test_dangling_parent_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["parent"] = "nonexistent"
    with pytest.raises(DocsManifestError, match="does not resolve to a") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "schema_error"


def test_missing_document_path_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["path"] = "missing.md"
    with pytest.raises(DocsManifestError, match="does not exist") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "dangling_reference"


def test_unresolved_canonical_file_source_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["canonical_sources"][0]["ref"] = "canonical/missing.py"
    with pytest.raises(DocsManifestError, match="does not resolve to a file") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "dangling_reference"


def test_issue_source_must_be_a_number() -> None:
    manifest = _fixture()
    manifest["documents"][1]["canonical_sources"][0]["ref"] = "issue-63"
    with pytest.raises(DocsManifestError, match="issue number") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "dangling_reference"


def test_non_ascii_digits_are_not_an_issue_number() -> None:
    manifest = _fixture()
    manifest["documents"][1]["canonical_sources"][0]["ref"] = "٦٣"
    with pytest.raises(DocsManifestError, match="issue number"):
        validate_manifest(manifest, root=FIX)


# --- exclusions, freshness, links, privacy ---


def test_document_inside_an_excluded_path_fails_closed(tmp_path: Path) -> None:
    root = _materialize(tmp_path, {"private/secret.md": "# Secret\n"})
    manifest = _manifest(
        [_document("secret", "private/secret.md", "0" * 64)],
        excluded_paths=[{"path": "private", "reason": "not managed"}],
    )
    with pytest.raises(DocsManifestError, match="is excluded by") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_sibling_prefix_is_not_excluded(tmp_path: Path) -> None:
    # ``docsx`` must not be treated as nested under the excluded ``docs``.
    root = _materialize(tmp_path, {"docsx/guide.md": "# Guide\n"})
    manifest = _manifest(
        [_document("guide", "docsx/guide.md", "0" * 64)],
        excluded_paths=[{"path": "docs", "reason": "not managed"}],
    )
    validate_manifest(manifest, root=root, check_freshness=False)


def test_tree_page_referencing_an_excluded_path_fails_closed(tmp_path: Path) -> None:
    root = _materialize(
        tmp_path,
        {
            "docs/INDEX.md": "# Docs\n\n- [Guide](guide.md)\n- [Holdout](holdout/secret.md)\n",
            "docs/guide.md": "# Guide\n",
        },
    )
    manifest = _manifest(
        [_document("guide", "docs/guide.md", "0" * 64)],
        excluded_paths=[{"path": "docs/holdout", "reason": "restricted"}],
    )
    with pytest.raises(DocsManifestError, match="tree page") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_absent_tree_page_is_skipped(tmp_path: Path) -> None:
    root = _materialize(tmp_path, {"guide.md": "# Guide\n"})
    manifest = _manifest([_document("guide", "guide.md", "0" * 64)])
    validate_manifest(manifest, root=root, check_freshness=False)


def test_stale_sha256_fails_closed() -> None:
    manifest = _fixture()
    manifest["documents"][0]["reviewed_sha256"] = "0" * 64
    with pytest.raises(DocsManifestError, match="stale") as excinfo:
        validate_manifest(manifest, root=FIX)
    assert excinfo.value.kind == "stale"


def test_correct_sha256_is_accepted() -> None:
    manifest = _fixture()
    assert manifest["documents"][0]["reviewed_sha256"] == _sha256(FIX / "alpha.md")
    validate_manifest(manifest, root=FIX)


def test_broken_local_link_fails_closed(tmp_path: Path) -> None:
    root = _materialize(
        tmp_path,
        {"bad.md": "# Bad\n\nSee [gone](missing.md).\n"},
    )
    manifest = _manifest([_document("bad", "bad.md", "0" * 64)])
    with pytest.raises(DocsManifestError, match="missing target") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "broken_link"


def test_fragment_and_external_links_are_skipped(tmp_path: Path) -> None:
    root = _materialize(
        tmp_path,
        {
            "ok.md": (
                "# Ok\n\n[frag](#section)\n[web](https://example.com/x)\n"
                "[mail](mailto:someone@example.com)\n"
            )
        },
    )
    manifest = _manifest([_document("ok", "ok.md", "0" * 64)])
    validate_manifest(manifest, root=root, check_freshness=False)


def test_private_segment_in_document_path_fails_closed(tmp_path: Path) -> None:
    root = _materialize(tmp_path, {"holdout/secret.md": "# Secret\n"})
    manifest = _manifest([_document("secret", "holdout/secret.md", "0" * 64)])
    with pytest.raises(DocsManifestError, match="private path segment") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_private_segment_in_canonical_source_fails_closed(tmp_path: Path) -> None:
    root = _materialize(
        tmp_path,
        {
            "ok.md": "# Ok\n",
            ".coord/state.db": "not a real database\n",
        },
    )
    manifest = _manifest(
        [
            _document(
                "ok",
                "ok.md",
                "0" * 64,
                canonical_sources=[{"kind": "code", "ref": ".coord/state.db"}],
            )
        ]
    )
    with pytest.raises(DocsManifestError, match="private path segment") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_private_path_is_excluded_even_when_absent(tmp_path: Path) -> None:
    # The privacy classification must not be masked by a dangling reference.
    root = _materialize(tmp_path, {"ok.md": "# Ok\n"})
    manifest = _manifest([_document("ok", ".coord/state.db", "0" * 64)])
    with pytest.raises(DocsManifestError, match="private path segment") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_traversal_cannot_dodge_an_excluded_path(tmp_path: Path) -> None:
    root = _materialize(tmp_path, {"private/secret.md": "# Secret\n"})
    manifest = _manifest(
        [_document("secret", "docs/../private/secret.md", "0" * 64)],
        excluded_paths=[{"path": "private", "reason": "not managed"}],
    )
    with pytest.raises(DocsManifestError, match="is excluded by") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


def test_excluded_path_wins_over_missing_file_on_every_platform(tmp_path: Path) -> None:
    # Exclusion is decided from the path alone, so it must not depend on the
    # file existing. Before the ordering fix, an excluded path that did not
    # exist was reported as dangling_reference on POSIX, where "docs/../x"
    # fails to resolve unless docs/ exists, while Windows folded the ".."
    # away and reached the exclusion check. Same manifest, two verdicts.
    root = _materialize(tmp_path, {"ok.md": "# Ok\n"})
    manifest = _manifest(
        [_document("gone", "docs/../private/gone.md", "0" * 64)],
        excluded_paths=[{"path": "private", "reason": "not managed"}],
    )
    with pytest.raises(DocsManifestError, match="is excluded by") as excinfo:
        validate_manifest(manifest, root=root, check_freshness=False)
    assert excinfo.value.kind == "excluded_path"


# --- read-only and offline guarantees ---


def test_validator_source_is_read_only() -> None:
    source = VALIDATOR_SOURCE.read_text(encoding="utf-8")
    for token in (".write(", ".write_text(", ".write_bytes(", ".mkdir(", "open("):
        assert token not in source, f"validator must not write; found {token!r}"


def test_validator_source_is_network_and_model_free() -> None:
    source = VALIDATOR_SOURCE.read_text(encoding="utf-8")
    for token in ("httpx", "requests", "openrouter", "DecisionsClient", "socket", "jsonschema"):
        assert token not in source, f"validator must stay offline; found {token!r}"
