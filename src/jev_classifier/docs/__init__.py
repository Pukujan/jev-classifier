"""Managed documentation manifest: schema constants and fail-closed validator (#63)."""

from jev_classifier.docs.validate import (
    AUDIENCES,
    DOC_STATUSES,
    MANIFEST_PATH,
    MANIFEST_SCHEMA,
    REVIEW_STATES,
    SOURCE_KINDS,
    TREE_PAGE,
    DocsManifestError,
    load_manifest,
    validate_manifest,
)

__all__ = [
    "AUDIENCES",
    "DOC_STATUSES",
    "MANIFEST_PATH",
    "MANIFEST_SCHEMA",
    "REVIEW_STATES",
    "SOURCE_KINDS",
    "TREE_PAGE",
    "DocsManifestError",
    "load_manifest",
    "validate_manifest",
]
