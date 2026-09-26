"""Fail-closed validation for the reference claim graph and stimulus manifest (#37).

Two layers:

- The JSON Schemas under ``schemas/`` describe record *shape*. They are the
  normative format for adopters and are checked in the tests.
- This module enforces the *cross-record* invariants a schema cannot express:
  reference integrity, relationship endpoints, byte-offset bounds, paired
  counterfactual consistency, and the public-record privacy rule.

Validation is pure Python with no new runtime dependency, so it runs anywhere
the package installs. Every failure raises :class:`ReferenceSchemaError` with
``kind="schema_error"`` — nothing is repaired, defaulted, or inferred. In
particular an absent or uncertain date stays ``null`` and is never replaced
with "now", and review records accumulate rather than overwrite.

Scope: this module defines and checks records only. It does not select a corpus
(#29), run a benchmark (#23), or assign gold labels.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"

REFERENCE_CLAIM_GRAPH_SCHEMA = "reference_claim_graph.schema.json"
CONTEXT_STIMULUS_MANIFEST_SCHEMA = "context_stimulus_manifest.schema.json"

EPISTEMIC_STATUSES = frozenset({"observed", "inferred", "hypothesized"})
RELATIONSHIP_TYPES = frozenset(
    {"supports", "contradicts", "refines", "corrects", "supersedes", "retracts", "unknown"}
)
REVIEW_DECISIONS = frozenset({"accept", "reject", "revise", "uncertain"})
STIMULUS_METHODS = frozenset({"synthetic", "deidentified", "paraphrase", "template"})
CONTEXT_SIZE_BUCKETS = frozenset({"xs", "s", "m", "l", "xl"})
VALIDATION_STATUSES = frozenset({"unvalidated", "synthetic_reviewed", "privacy_reviewed"})

_URL_PATTERN = re.compile(r"https?://", re.IGNORECASE)


class ReferenceSchemaError(ValueError):
    """Raised when a record is malformed or breaks a cross-record invariant."""

    def __init__(self, message: str, *, kind: str = "schema_error") -> None:
        super().__init__(message)
        self.kind = kind


def load_schema(name: str) -> dict[str, Any]:
    """Load a schema from the repo's ``schemas/`` directory."""
    path = SCHEMAS_DIR / name
    if not path.is_file():
        raise ReferenceSchemaError(f"schema not found: {name}", kind="schema_error")
    return json.loads(path.read_text(encoding="utf-8"))


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReferenceSchemaError(f"{label} must be an object", kind="schema_error")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReferenceSchemaError(f"{label} must be an array", kind="schema_error")
    return value


def _require_nonempty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReferenceSchemaError(f"{label} must be a non-empty string", kind="schema_error")
    return value


def _require_nullable_str(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _require_nonempty_str(value, label)


def _require_enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if value not in allowed:
        raise ReferenceSchemaError(
            f"{label} must be one of {sorted(allowed)}, got {value!r}",
            kind="schema_error",
        )
    return value


def _require_version(graph: Mapping[str, Any]) -> None:
    version = graph.get("schema_version")
    if not isinstance(version, str) or not SCHEMA_VERSION_PATTERN.match(version):
        raise ReferenceSchemaError(
            f"schema_version must be a semver string, got {version!r}",
            kind="schema_error",
        )


def _index_unique(items: list[Any], key: str, label: str) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    for item in items:
        body = _require_mapping(item, label)
        ident = _require_nonempty_str(body.get(key), f"{label}.{key}")
        if ident in out:
            raise ReferenceSchemaError(f"duplicate {label} id {ident!r}", kind="schema_error")
        out[ident] = body
    return out


def validate_reference_graph(graph: Any) -> None:
    """Validate one reference claim graph; raise on the first violation.

    Checks shape, then reference integrity, relationship endpoints, evidence
    offsets, bitemporal shape, and that a superseding review never removes the
    review it replaces.
    """
    body = _require_mapping(graph, "graph")
    _require_version(body)
    _require_nonempty_str(body.get("graph_id"), "graph_id")

    papers = _index_unique(_require_list(body.get("papers"), "papers"), "paper_id", "paper")
    sources = _index_unique(_require_list(body.get("sources"), "sources"), "source_id", "source")
    claims = _index_unique(
        _require_list(body.get("claims"), "claims"), "claim_id", "claim"
    )
    relationships = _index_unique(
        _require_list(body.get("relationships"), "relationships"), "rel_id", "relationship"
    )
    reviews = _index_unique(_require_list(body.get("reviews"), "reviews"), "review_id", "review")

    if not claims:
        raise ReferenceSchemaError("claims must be non-empty", kind="schema_error")

    for sid, source in sources.items():
        pid = _require_nonempty_str(source.get("paper_id"), f"source[{sid}].paper_id")
        if pid not in papers:
            raise ReferenceSchemaError(
                f"source[{sid}].paper_id {pid!r} does not resolve to a paper",
                kind="schema_error",
            )
        _require_nonempty_str(source.get("version"), f"source[{sid}].version")

    for cid, claim in claims.items():
        pid = _require_nonempty_str(claim.get("paper_id"), f"claim[{cid}].paper_id")
        sid = _require_nonempty_str(claim.get("source_id"), f"claim[{cid}].source_id")
        if pid not in papers:
            raise ReferenceSchemaError(
                f"claim[{cid}].paper_id {pid!r} does not resolve to a paper",
                kind="schema_error",
            )
        if sid not in sources:
            raise ReferenceSchemaError(
                f"claim[{cid}].source_id {sid!r} does not resolve to a source",
                kind="schema_error",
            )
        if sources[sid]["paper_id"] != pid:
            raise ReferenceSchemaError(
                f"claim[{cid}] cites source {sid!r} from paper "
                f"{sources[sid]['paper_id']!r}, not {pid!r}",
                kind="schema_error",
            )

        _require_nonempty_str(claim.get("text"), f"claim[{cid}].text")
        _require_enum(
            claim.get("epistemic_status"), EPISTEMIC_STATUSES, f"claim[{cid}].epistemic_status"
        )

        evidence = _require_mapping(claim.get("evidence"), f"claim[{cid}].evidence")
        _require_nonempty_str(evidence.get("quote"), f"claim[{cid}].evidence.quote")
        start = evidence.get("byte_start")
        end = evidence.get("byte_end")
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise ReferenceSchemaError(
                f"claim[{cid}].evidence.byte_start must be a non-negative integer",
                kind="schema_error",
            )
        if not isinstance(end, int) or isinstance(end, bool) or end <= start:
            raise ReferenceSchemaError(
                f"claim[{cid}].evidence.byte_end must exceed byte_start",
                kind="schema_error",
            )

        # Bitemporal shape: valid time and transaction time stay separate, and
        # an absent date stays null rather than being inferred.
        _require_nonempty_str(claim.get("recorded_at"), f"claim[{cid}].recorded_at")
        _require_nullable_str(claim.get("valid_from"), f"claim[{cid}].valid_from")
        _require_nullable_str(claim.get("valid_to"), f"claim[{cid}].valid_to")

    for rid, rel in relationships.items():
        _require_enum(rel.get("type"), RELATIONSHIP_TYPES, f"relationship[{rid}].type")
        src = _require_nonempty_str(rel.get("from_claim_id"), f"relationship[{rid}].from_claim_id")
        dst = _require_nonempty_str(rel.get("to_claim_id"), f"relationship[{rid}].to_claim_id")
        for endpoint in (src, dst):
            if endpoint not in claims:
                raise ReferenceSchemaError(
                    f"relationship[{rid}] endpoint {endpoint!r} does not resolve to a claim",
                    kind="schema_error",
                )
        if src == dst:
            raise ReferenceSchemaError(
                f"relationship[{rid}] relates claim {src!r} to itself; relationships are "
                f"irreflexive",
                kind="schema_error",
            )

    for rvid, review in reviews.items():
        cid = _require_nonempty_str(review.get("claim_id"), f"review[{rvid}].claim_id")
        if cid not in claims:
            raise ReferenceSchemaError(
                f"review[{rvid}].claim_id {cid!r} does not resolve to a claim",
                kind="schema_error",
            )
        _require_nonempty_str(review.get("annotator_id"), f"review[{rvid}].annotator_id")
        _require_enum(review.get("decision"), REVIEW_DECISIONS, f"review[{rvid}].decision")
        _require_nonempty_str(review.get("recorded_at"), f"review[{rvid}].recorded_at")
        supersedes = _require_nullable_str(
            review.get("supersedes_review_id"), f"review[{rvid}].supersedes_review_id"
        )
        if supersedes is not None:
            if supersedes not in reviews:
                raise ReferenceSchemaError(
                    f"review[{rvid}].supersedes_review_id {supersedes!r} does not resolve "
                    f"to a review",
                    kind="schema_error",
                )
            if supersedes == rvid:
                raise ReferenceSchemaError(
                    f"review[{rvid}] supersedes itself", kind="schema_error"
                )


def _scan_public_strings(value: Any, path: str) -> None:
    """Reject URLs and other public-record privacy violations, recursively."""
    if isinstance(value, str):
        if _URL_PATTERN.search(value):
            raise ReferenceSchemaError(
                f"{path}: public records must not contain URLs (found {value!r}); "
                f"link private material by opaque id only",
                kind="schema_error",
            )
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _scan_public_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            _scan_public_strings(item, f"{path}[{idx}]")


def validate_stimulus_manifest(manifest: Any) -> None:
    """Validate one privacy-safe stimulus manifest; raise on the first violation.

    Beyond shape, this enforces paired-counterfactual consistency (a pair shares
    one condition family and one source packet, and its roles are distinct) and
    the public-record privacy rule (no URLs anywhere in the record).
    """
    body = _require_mapping(manifest, "manifest")
    _require_version(body)
    _require_nonempty_str(body.get("manifest_id"), "manifest_id")

    cases = _index_unique(
        _require_list(body.get("cases"), "cases"), "case_id", "case"
    )
    if not cases:
        raise ReferenceSchemaError("cases must be non-empty", kind="schema_error")

    pairs: dict[str, list[Mapping[str, Any]]] = {}
    for case_id, case in cases.items():
        _require_nonempty_str(
            case.get("condition_family_id"), f"case[{case_id}].condition_family_id"
        )
        _require_enum(
            case.get("stimulus_method"), STIMULUS_METHODS, f"case[{case_id}].stimulus_method"
        )
        _require_nonempty_str(
            case.get("stimulus_version"), f"case[{case_id}].stimulus_version"
        )
        _require_nonempty_str(case.get("seed_provenance"), f"case[{case_id}].seed_provenance")
        _require_enum(
            case.get("context_size_bucket"),
            CONTEXT_SIZE_BUCKETS,
            f"case[{case_id}].context_size_bucket",
        )
        _require_nonempty_str(
            case.get("source_packet_id"), f"case[{case_id}].source_packet_id"
        )
        _require_nonempty_str(
            case.get("source_packet_version"), f"case[{case_id}].source_packet_version"
        )
        _require_enum(
            case.get("validation_status"),
            VALIDATION_STATUSES,
            f"case[{case_id}].validation_status",
        )
        pair_id = _require_nonempty_str(case.get("pair_id"), f"case[{case_id}].pair_id")
        pairs.setdefault(pair_id, []).append(case)

    for pair_id, members in pairs.items():
        families = {m.get("condition_family_id") for m in members}
        if len(families) != 1:
            raise ReferenceSchemaError(
                f"pair {pair_id!r} spans condition families {sorted(map(str, families))}; "
                f"paired cases must share one family",
                kind="schema_error",
            )
        packets = {m.get("source_packet_id") for m in members}
        if len(packets) != 1:
            raise ReferenceSchemaError(
                f"pair {pair_id!r} spans source packets {sorted(map(str, packets))}",
                kind="schema_error",
            )
        roles = [m.get("pair_role") for m in members]
        if len(members) > 1 and None in roles:
            raise ReferenceSchemaError(
                f"pair {pair_id!r} has multiple cases but a case is missing pair_role",
                kind="schema_error",
            )
        assigned = [r for r in roles if r is not None]
        if len(set(assigned)) != len(assigned):
            raise ReferenceSchemaError(
                f"pair {pair_id!r} assigns a pair_role more than once: {roles}",
                kind="schema_error",
            )

    _scan_public_strings(body, "manifest")
