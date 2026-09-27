"""Fail-closed validation for the managed documentation manifest (#63).

``docs/docs_manifest.json`` is a checked-in inventory of the managed
documentation corpus: which files are managed, what each is for, who it is for,
where its facts come from, and whether a human has reviewed it. The JSON Schema
at ``schemas/docs_manifest.schema.json`` describes record *shape*. This module
enforces the invariants a schema cannot express:

- identity is unique and every ``parent`` resolves inside the manifest;
- every managed path exists on disk and none sits under an excluded path;
- every canonical source resolves (a file path, or a GitHub issue number);
- the reviewed digest matches the file's current bytes;
- relative markdown links resolve, and no private path enters the manifest.

Validation is pure Python with no extra runtime dependency, so it runs offline
wherever the package installs. Every failure raises :class:`DocsManifestError`
on the FIRST violation: nothing is repaired, defaulted, or inferred. The module
is read-only -- it never writes, generates, or rewrites a file or prose.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"

MANIFEST_SCHEMA = "docs_manifest.schema.json"
MANIFEST_PATH = REPO_ROOT / "docs" / "docs_manifest.json"
TREE_PAGE = REPO_ROOT / "docs" / "INDEX.md"

# Markdown files under ``docs/`` that are deliberately not inventoried. The
# continuity card is rewritten on every task, so any digest recorded for it
# would be stale on the next commit. (``docs/docs_manifest.json`` is not a
# markdown file and so is not scanned.)
NOT_INVENTORIED_DOCUMENTS = frozenset({"docs/CURRENT.md"})

MANIFEST_SCHEMA_ID = "jev-classifier.docs-manifest.v1"

MANIFEST_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
DOCUMENT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
ISSUE_NUMBER_PATTERN = re.compile(r"^[0-9]+$")
REVIEWED_COMMIT_PATTERN = re.compile(r"^(uncommitted|[a-f0-9]{40,64})$")
REVIEWED_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

AUDIENCES = frozenset({"newcomer", "contributor", "maintainer", "reviewer", "agent"})
DOC_STATUSES = frozenset({"shipped", "partial", "planned", "unknown"})
REVIEW_STATES = frozenset({"unreviewed", "reviewed", "stale"})
SOURCE_KINDS = frozenset({"code", "spec", "schema", "test", "script", "issue"})
_PATH_SOURCE_KINDS = frozenset({"code", "spec", "schema", "test", "script"})

# Secrets, local coordination/ops databases, caches, worktrees and restricted
# holdout material must never enter a public manifest.
PRIVATE_PATH_SEGMENTS = frozenset(
    {
        ".env",
        ".coord",
        ".ops",
        ".cache",
        "node_modules",
        "worktrees",
        ".worktrees",
        "holdout",
    }
)

_MANIFEST_KEYS = frozenset({"schema", "manifest_version", "excluded_paths", "documents"})
_EXCLUSION_KEYS = frozenset({"path", "reason"})
_SOURCE_REF_KEYS = frozenset({"kind", "ref"})
_DOCUMENT_KEYS = frozenset(
    {
        "id",
        "path",
        "title",
        "summary",
        "audience",
        "status",
        "owner_issue",
        "parent",
        "keywords",
        "related",
        "canonical_sources",
        "review_state",
        "reviewed_commit",
        "reviewed_sha256",
    }
)
# ``parent`` is the one optional document key; everything else is required.
_DOCUMENT_REQUIRED_KEYS = _DOCUMENT_KEYS - {"parent"}


class DocsManifestError(ValueError):
    """Raised when the manifest is malformed or breaks a manifest invariant."""

    def __init__(self, message: str, *, kind: str = "schema_error") -> None:
        super().__init__(message)
        self.kind = kind


def load_manifest(path: Any = None) -> dict[str, Any]:
    """Load the manifest from ``path`` (default :data:`MANIFEST_PATH`)."""
    target = Path(path) if path is not None else MANIFEST_PATH
    if not target.is_file():
        raise DocsManifestError(f"manifest not found: {target}", kind="schema_error")
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DocsManifestError(
            f"manifest {target} is not valid JSON: {exc}", kind="schema_error"
        ) from exc


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DocsManifestError(f"{label} must be an object", kind="schema_error")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DocsManifestError(f"{label} must be an array", kind="schema_error")
    return value


def _require_nonempty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocsManifestError(f"{label} must be a non-empty string", kind="schema_error")
    return value


def _require_nullable_str(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_nonempty_str(value, label)


def _require_nullable_issue(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise DocsManifestError(
            f"{label} must be null or a positive integer, got {value!r}",
            kind="schema_error",
        )
    return value


def _require_enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if value not in allowed:
        raise DocsManifestError(
            f"{label} must be one of {sorted(allowed)}, got {value!r}",
            kind="schema_error",
        )
    return value


def _require_str_matching(
    value: Any, pattern: re.Pattern[str], label: str, description: str
) -> str:
    if not isinstance(value, str) or not pattern.match(value):
        raise DocsManifestError(
            f"{label} must be {description}, got {value!r}", kind="schema_error"
        )
    return value


def _require_string_list(value: Any, label: str) -> list[Any]:
    items = _require_list(value, label)
    for idx, item in enumerate(items):
        _require_nonempty_str(item, f"{label}[{idx}]")
    return items


def _reject_unknown_keys(body: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    for key in body:
        if key not in allowed:
            raise DocsManifestError(
                f"{label} has unknown key {key!r}; allowed keys are {sorted(allowed)}",
                kind="schema_error",
            )


def _require_keys(body: Mapping[str, Any], required: frozenset[str], label: str) -> None:
    for key in sorted(required):
        if key not in body:
            raise DocsManifestError(f"{label} is missing required key {key!r}", kind="schema_error")


def _index_unique(items: list[Any], key: str, label: str) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in items:
        body = _require_mapping(item, label)
        ident = _require_nonempty_str(body.get(key), f"{label}.{key}")
        if ident in out:
            raise DocsManifestError(f"duplicate {label} id {ident!r}", kind="schema_error")
        out[ident] = body
    return out


def _segments(value: str) -> tuple[str, ...]:
    """Split a manifest path into ``/``-separated segments.

    ``.`` segments are dropped and ``..`` segments are resolved, so a path
    written with traversal (``docs/../private/x.md``) compares the same as its
    normalized form and cannot dodge an exclusion.
    """
    out: list[str] = []
    for segment in value.replace("\\", "/").split("/"):
        if not segment or segment == ".":
            continue
        if segment == "..":
            if out:
                out.pop()
            continue
        out.append(segment)
    return tuple(out)


def _is_within(path: str, ancestor: str) -> bool:
    """True when ``path`` equals ``ancestor`` or is nested under it, by segment."""
    path_parts = _segments(path)
    ancestor_parts = _segments(ancestor)
    if not ancestor_parts:
        return False
    return path_parts[: len(ancestor_parts)] == ancestor_parts


def _private_segment(value: str) -> str | None:
    for segment in _segments(value):
        if segment in PRIVATE_PATH_SEGMENTS:
            return segment
    return None


def _reject_private_path(value: str, label: str) -> None:
    segment = _private_segment(value)
    if segment is not None:
        raise DocsManifestError(
            f"{label} {value!r} contains private path segment {segment!r}; "
            f"secrets, coordination/ops stores, caches, worktrees and holdout data "
            f"must never enter the manifest",
            kind="excluded_path",
        )


def _link_targets(text: str) -> list[str]:
    """Extract raw markdown link targets ``[text](target)`` from ``text``."""
    return [match.group(1).strip() for match in _MARKDOWN_LINK_PATTERN.finditer(text)]


def _is_external_target(target: str) -> bool:
    return "#" == target[:1] or "://" in target or target.lower().startswith("mailto:")


def _resolve_link(base: Path, document_path: str, target: str) -> Path | None:
    """Resolve a markdown link target, or return ``None`` when it is not local.

    Bare fragments and external schemes are not local. A leading ``/`` is
    treated as root-relative; anything else resolves against the linking
    document's own directory.
    """
    raw = target.strip().strip("<>")
    if not raw or _is_external_target(raw):
        return None
    path_part = raw.split("#", 1)[0]
    if not path_part:
        return None
    if path_part.startswith("/"):
        candidate = base / path_part.lstrip("/")
    else:
        candidate = (base / document_path).parent / path_part
    return candidate.resolve()


def _within_root(base: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True


def _uninventoried_documents(base: Path, listed: set[str]) -> list[str]:
    """Return ``docs/*.md`` files the manifest neither lists nor exempts."""
    directory = base / "docs"
    if not directory.is_dir():
        return []
    out: list[str] = []
    for candidate in sorted(directory.glob("*.md")):
        relative = candidate.relative_to(base).as_posix()
        if relative in listed or relative in NOT_INVENTORIED_DOCUMENTS:
            continue
        out.append(relative)
    return out


def _validate_document_shape(document: Any, label: str) -> Mapping[str, Any]:
    body = _require_mapping(document, label)
    _reject_unknown_keys(body, _DOCUMENT_KEYS, label)
    _require_keys(body, _DOCUMENT_REQUIRED_KEYS, label)
    _require_str_matching(body.get("id"), DOCUMENT_ID_PATTERN, f"{label}.id", "an id slug")
    _require_nonempty_str(body.get("path"), f"{label}.path")
    _require_nonempty_str(body.get("title"), f"{label}.title")
    _require_nonempty_str(body.get("summary"), f"{label}.summary")
    _require_enum(body.get("audience"), AUDIENCES, f"{label}.audience")
    _require_enum(body.get("status"), DOC_STATUSES, f"{label}.status")
    _require_nullable_issue(body.get("owner_issue"), f"{label}.owner_issue")
    _require_nullable_str(body.get("parent"), f"{label}.parent")
    _require_string_list(body.get("keywords"), f"{label}.keywords")
    _require_string_list(body.get("related"), f"{label}.related")

    sources = _require_list(body.get("canonical_sources"), f"{label}.canonical_sources")
    for idx, source in enumerate(sources):
        source_label = f"{label}.canonical_sources[{idx}]"
        source_body = _require_mapping(source, source_label)
        _reject_unknown_keys(source_body, _SOURCE_REF_KEYS, source_label)
        _require_keys(source_body, _SOURCE_REF_KEYS, source_label)
        _require_enum(source_body.get("kind"), SOURCE_KINDS, f"{source_label}.kind")
        _require_nonempty_str(source_body.get("ref"), f"{source_label}.ref")

    _require_enum(body.get("review_state"), REVIEW_STATES, f"{label}.review_state")
    _require_str_matching(
        body.get("reviewed_commit"),
        REVIEWED_COMMIT_PATTERN,
        f"{label}.reviewed_commit",
        "'uncommitted' or a 40-64 character lowercase hex commit",
    )
    _require_str_matching(
        body.get("reviewed_sha256"),
        REVIEWED_SHA256_PATTERN,
        f"{label}.reviewed_sha256",
        "a 64 character lowercase hex digest",
    )
    return body


def validate_manifest(
    manifest: Any, *, root: Any = None, check_freshness: bool = True
) -> None:
    """Validate one managed documentation manifest; raise on the first violation.

    Checks shape, identity uniqueness, parent resolution, on-disk path and
    source resolution, exclusion of private/excluded paths, uninventoried
    documents, the tree page, the reviewed digest, relative markdown links, and
    the private-path scan.
    """
    base = Path(root).resolve() if root is not None else REPO_ROOT

    body = _require_mapping(manifest, "manifest")
    _reject_unknown_keys(body, _MANIFEST_KEYS, "manifest")
    _require_keys(body, _MANIFEST_KEYS, "manifest")

    if body.get("schema") != MANIFEST_SCHEMA_ID:
        raise DocsManifestError(
            f"schema must be {MANIFEST_SCHEMA_ID!r}, got {body.get('schema')!r}",
            kind="schema_error",
        )
    _require_str_matching(
        body.get("manifest_version"),
        MANIFEST_VERSION_PATTERN,
        "manifest_version",
        "a semver string",
    )

    exclusions = _require_list(body.get("excluded_paths"), "excluded_paths")
    excluded: list[str] = []
    for idx, exclusion in enumerate(exclusions):
        label = f"excluded_paths[{idx}]"
        exclusion_body = _require_mapping(exclusion, label)
        _reject_unknown_keys(exclusion_body, _EXCLUSION_KEYS, label)
        _require_keys(exclusion_body, _EXCLUSION_KEYS, label)
        excluded.append(_require_nonempty_str(exclusion_body.get("path"), f"{label}.path"))
        _require_nonempty_str(exclusion_body.get("reason"), f"{label}.reason")

    documents = _require_list(body.get("documents"), "documents")
    if not documents:
        raise DocsManifestError("documents must be non-empty", kind="schema_error")
    for idx, document in enumerate(documents):
        _validate_document_shape(document, f"documents[{idx}]")
    docs = _index_unique(documents, "id", "document")

    seen_paths: dict[str, str] = {}
    for doc_id, document in docs.items():
        path = _require_nonempty_str(document.get("path"), f"document[{doc_id}].path")
        if path in seen_paths:
            raise DocsManifestError(
                f"duplicate document path {path!r} shared by {seen_paths[path]!r} "
                f"and {doc_id!r}",
                kind="schema_error",
            )
        seen_paths[path] = doc_id

    for doc_id, document in docs.items():
        parent = document.get("parent")
        if parent is not None and parent not in docs:
            raise DocsManifestError(
                f"document {doc_id!r} parent {parent!r} does not resolve to a "
                f"document id in this manifest",
                kind="schema_error",
            )

    # The path-classification scans run before the on-disk checks so an
    # excluded or private path is always reported as ``excluded_path``, even
    # when the file it names does not exist. Existence would otherwise mask it
    # as a dangling reference. This also keeps the answer platform-independent:
    # on POSIX a ".." segment does not resolve unless every intermediate
    # directory exists, while on Windows it is folded away lexically, so an
    # existence check that ran first would decide the same manifest differently
    # on the two platforms.
    for doc_id, document in docs.items():
        path = document["path"]
        _reject_private_path(path, f"document {doc_id!r} path")
        for exclusion in excluded:
            if _is_within(path, exclusion):
                raise DocsManifestError(
                    f"document {doc_id!r} path {path!r} is excluded by {exclusion!r}",
                    kind="excluded_path",
                )
        for idx, source in enumerate(document["canonical_sources"]):
            _reject_private_path(
                source["ref"], f"document {doc_id!r} canonical source {idx} ref"
            )

    for doc_id, document in docs.items():
        path = document["path"]
        if not (base / path).is_file():
            raise DocsManifestError(
                f"document {doc_id!r} path {path!r} does not exist under {base}",
                kind="dangling_reference",
            )

    for doc_id, document in docs.items():
        for idx, source in enumerate(document["canonical_sources"]):
            kind = source["kind"]
            ref = source["ref"]
            label = f"document {doc_id!r} canonical source {idx}"
            if kind == "issue":
                if not ISSUE_NUMBER_PATTERN.match(ref):
                    raise DocsManifestError(
                        f"{label} ({kind}) ref {ref!r} must be a GitHub issue number "
                        f"(digits only)",
                        kind="dangling_reference",
                    )
            elif kind in _PATH_SOURCE_KINDS:
                if not (base / ref).is_file():
                    raise DocsManifestError(
                        f"{label} ({kind}) ref {ref!r} does not resolve to a file "
                        f"under {base}",
                        kind="dangling_reference",
                    )

    tree_page = base / "docs" / "INDEX.md"
    if tree_page.is_file():
        tree_text = tree_page.read_text(encoding="utf-8", errors="replace")
        for target in _link_targets(tree_text):
            resolved = _resolve_link(base, "docs/INDEX.md", target)
            if resolved is None or not _within_root(base, resolved):
                continue
            linked = resolved.relative_to(base).as_posix()
            for exclusion in excluded:
                if _is_within(linked, exclusion):
                    raise DocsManifestError(
                        f"tree page docs/INDEX.md references excluded path "
                        f"{exclusion!r} via {target!r}",
                        kind="excluded_path",
                    )

    if check_freshness:
        for doc_id, document in docs.items():
            path = document["path"]
            digest = hashlib.sha256((base / path).read_bytes()).hexdigest()
            if digest != document["reviewed_sha256"]:
                raise DocsManifestError(
                    f"document {doc_id!r} path {path!r} is stale: reviewed_sha256 "
                    f"{document['reviewed_sha256']} does not match {digest}",
                    kind="stale",
                )

    for doc_id, document in docs.items():
        path = document["path"]
        text = (base / path).read_bytes().decode("utf-8", errors="replace")
        for target in _link_targets(text):
            resolved = _resolve_link(base, path, target)
            if resolved is None:
                continue
            if not _within_root(base, resolved) or not resolved.is_file():
                raise DocsManifestError(
                    f"document {path!r} links to missing target {target!r}",
                    kind="broken_link",
                )

    # The reverse of the dangling-reference check: a document that exists but
    # has no manifest entry. Without this, a page can land and never be
    # inventoried, and nothing fails (docs/DATASET_CARD.md did exactly that
    # between #71 and #76). Runs last so it cannot mask a more specific error
    # about a document the manifest does list.
    uninventoried = _uninventoried_documents(base, set(seen_paths))
    if uninventoried:
        raise DocsManifestError(
            f"documentation exists but is not in the manifest: "
            f"{', '.join(uninventoried)}; add a document entry for each, or "
            f"record the path in NOT_INVENTORIED_DOCUMENTS with a reason",
            kind="uninventoried_document",
        )
