"""Fail-closed custody for the paper-level development/holdout split (#81).

The benchmark is only honest if some papers never enter development: a holdout
label must not reach a prompt, a fixture, an iteration log, or a routine score.
Parent issue #21 fixes that requirement -- at least 20% of papers and at least
two papers, frozen before any tuning -- but nothing in the tree enforced it, so
development code could open an annotated holdout graph and the offline scorer
had no notion of a split at all.

This module is the enforcement boundary. It reads a split assignment, checks it
against the policy minimums, and refuses development work that touches a
holdout paper. Enforcement is *default* rather than flag-gated: the assignment
is discovered through :func:`load_configured_assignment`, so a checkout with
custody configured is checked without any caller opting in.

Fail closed: every failure raises :class:`HoldoutError` on the FIRST violation
with a machine-readable ``kind`` -- nothing is repaired, defaulted, or inferred.

Error kinds, and what each one means:

``schema_error``
    The record is malformed: unreadable or non-JSON input, a missing or unknown
    key, a wrong type, or a paper id that does not match the id pattern.
``invalid_split``
    The record is well formed but is not a valid split: an empty, duplicated,
    overlapping, too-few-holdout, too-small, or non-covering assignment, or a
    commitment tag that does not match the frozen assignment.
``holdout_access``
    Development code named a paper that belongs to the holdout.
``leakage``
    One paper appears on both sides of the boundary.
``missing_assignment``
    A custody file was named but is absent.

Scope: this module reads and checks an assignment. It does not choose the
split, annotate a paper, or run a benchmark.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SPLIT_SCHEMA_VERSION = "holdout_split_v1"
MINIMUM_HOLDOUT_FRACTION = 0.20
MINIMUM_HOLDOUT_PAPERS = 2
ASSIGNMENT_ENV_VAR = "JEV_HOLDOUT_ASSIGNMENT"

DEVELOPMENT_SPLIT = "development"
HOLDOUT_SPLIT = "holdout"

_PAPER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMITMENT_TAG_PATTERN = re.compile(r"^[a-f0-9]{64}$")

_ASSIGNMENT_KEYS = frozenset(
    {
        "split_version",
        "frozen_at",
        "custodian",
        "inputs",
        "dev_paper_ids",
        "holdout_paper_ids",
    }
)
_SPLITS = frozenset({DEVELOPMENT_SPLIT, HOLDOUT_SPLIT})


class HoldoutError(ValueError):
    """Raised when a split assignment is malformed or breaks a custody rule."""

    def __init__(self, message: str, *, kind: str = "schema_error") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class SplitAssignment:
    """A frozen, custodian-owned division of the paper corpus.

    ``inputs`` binds the freeze to the material it was computed over, so a
    changed corpus or annotation schema is visible as a changed input set
    rather than a silent reinterpretation of the same split.
    """

    split_version: str
    frozen_at: str
    custodian: str
    inputs: Mapping[str, str]
    dev_paper_ids: tuple[str, ...]
    holdout_paper_ids: tuple[str, ...]


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HoldoutError(f"{label} must be an object", kind="schema_error")
    return value


def _require_nonempty_str(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HoldoutError(f"{label} must be a non-empty string", kind="schema_error")
    return value


def _require_enum(value: Any, allowed: frozenset[str], label: str) -> str:
    if value not in allowed:
        raise HoldoutError(
            f"{label} must be one of {sorted(allowed)}, got {value!r}", kind="schema_error"
        )
    return value


def _require_paper_ids(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise HoldoutError(f"{label} must be an array", kind="schema_error")
    out: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not _PAPER_ID_PATTERN.match(item):
            raise HoldoutError(
                f"{label}[{idx}] must be a paper id matching "
                f"{_PAPER_ID_PATTERN.pattern}, got {item!r}",
                kind="schema_error",
            )
        out.append(item)
    return tuple(out)


def _require_inputs(value: Any, label: str) -> dict[str, str]:
    body = _require_mapping(value, label)
    out: dict[str, str] = {}
    for key, item in body.items():
        out[_require_nonempty_str(key, f"{label} key")] = _require_nonempty_str(
            item, f"{label}[{key!r}]"
        )
    return out


def _parse_assignment(body: Any) -> SplitAssignment:
    """Build a :class:`SplitAssignment` from a JSON body, checking only shape."""
    document = _require_mapping(body, "assignment")
    for key in sorted(document):
        if key not in _ASSIGNMENT_KEYS:
            raise HoldoutError(
                f"assignment has unknown key {key!r}; allowed keys are "
                f"{sorted(_ASSIGNMENT_KEYS)}",
                kind="schema_error",
            )
    for key in sorted(_ASSIGNMENT_KEYS):
        if key not in document:
            raise HoldoutError(
                f"assignment is missing required key {key!r}", kind="schema_error"
            )
    return SplitAssignment(
        split_version=_require_nonempty_str(
            document.get("split_version"), "split_version"
        ),
        frozen_at=_require_nonempty_str(document.get("frozen_at"), "frozen_at"),
        custodian=_require_nonempty_str(document.get("custodian"), "custodian"),
        inputs=_require_inputs(document.get("inputs"), "inputs"),
        dev_paper_ids=tuple(
            sorted(_require_paper_ids(document.get("dev_paper_ids"), "dev_paper_ids"))
        ),
        holdout_paper_ids=tuple(
            sorted(_require_paper_ids(document.get("holdout_paper_ids"), "holdout_paper_ids"))
        ),
    )


def _check_assignment_shape(assignment: SplitAssignment) -> None:
    if not isinstance(assignment.split_version, str) or not assignment.split_version:
        raise HoldoutError("split_version must be a non-empty string", kind="schema_error")
    if assignment.split_version != SPLIT_SCHEMA_VERSION:
        raise HoldoutError(
            f"split_version must be {SPLIT_SCHEMA_VERSION!r}, got "
            f"{assignment.split_version!r}",
            kind="schema_error",
        )
    if not isinstance(assignment.frozen_at, str) or not assignment.frozen_at:
        raise HoldoutError("frozen_at must be a non-empty string", kind="schema_error")
    if not isinstance(assignment.custodian, str) or not assignment.custodian:
        raise HoldoutError("custodian must be a non-empty string", kind="schema_error")
    _require_inputs(assignment.inputs, "inputs")
    for label, ids in (
        ("dev_paper_ids", assignment.dev_paper_ids),
        ("holdout_paper_ids", assignment.holdout_paper_ids),
    ):
        if not isinstance(ids, (list, tuple)):
            raise HoldoutError(f"{label} must be a sequence of paper ids", kind="schema_error")
        for idx, paper_id in enumerate(ids):
            if not isinstance(paper_id, str) or not _PAPER_ID_PATTERN.match(paper_id):
                raise HoldoutError(
                    f"{label}[{idx}] must be a paper id matching "
                    f"{_PAPER_ID_PATTERN.pattern}, got {paper_id!r}",
                    kind="schema_error",
                )


def _validate_split(assignment: SplitAssignment, corpus_ids: Iterable[str] | None) -> None:
    dev = tuple(assignment.dev_paper_ids)
    holdout = tuple(assignment.holdout_paper_ids)

    if not dev:
        raise HoldoutError("dev_paper_ids must be non-empty", kind="invalid_split")
    if not holdout:
        raise HoldoutError("holdout_paper_ids must be non-empty", kind="invalid_split")

    for label, ids in (("dev_paper_ids", dev), ("holdout_paper_ids", holdout)):
        if len(set(ids)) != len(ids):
            raise HoldoutError(
                f"{label} repeats a paper id: {sorted(ids)}", kind="invalid_split"
            )

    overlap = sorted(set(dev) & set(holdout))
    if overlap:
        raise HoldoutError(
            f"dev_paper_ids and holdout_paper_ids overlap on {overlap}; a paper "
            f"belongs to exactly one split",
            kind="invalid_split",
        )

    if len(holdout) < MINIMUM_HOLDOUT_PAPERS:
        raise HoldoutError(
            f"holdout has {len(holdout)} paper(s); the policy minimum is "
            f"{MINIMUM_HOLDOUT_PAPERS}",
            kind="invalid_split",
        )

    total = len(dev) + len(holdout)
    fraction = len(holdout) / total
    if fraction < MINIMUM_HOLDOUT_FRACTION:
        raise HoldoutError(
            f"holdout fraction {fraction:.4f} is below the policy minimum "
            f"{MINIMUM_HOLDOUT_FRACTION}",
            kind="invalid_split",
        )

    if corpus_ids is not None:
        corpus = set(corpus_ids)
        covered = set(dev) | set(holdout)
        missing = sorted(corpus - covered)
        extra = sorted(covered - corpus)
        if missing or extra:
            raise HoldoutError(
                f"split does not cover the corpus exactly: missing {missing}, "
                f"unrecognized {extra}",
                kind="invalid_split",
            )


def validate_assignment(
    assignment: SplitAssignment | Mapping[str, Any],
    *,
    corpus_ids: Iterable[str] | None = None,
) -> None:
    """Validate one split assignment; raise on the first violation.

    Checks record shape, then the split invariants a JSON Schema cannot
    express: non-empty and duplicate-free sides, a disjoint dev/holdout
    boundary, the holdout paper and fraction minimums, and -- when
    ``corpus_ids`` is supplied -- exact coverage of the corpus.
    """
    parsed = _parse_assignment(assignment) if isinstance(assignment, Mapping) else assignment
    _check_assignment_shape(parsed)
    _validate_split(parsed, corpus_ids)


def load_assignment(path: str | Path) -> SplitAssignment:
    """Load and validate a split assignment; raise on the first violation."""
    target = Path(path)
    if not target.is_file():
        raise HoldoutError(
            f"holdout split assignment not found: {target}", kind="missing_assignment"
        )
    try:
        body = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HoldoutError(
            f"holdout split assignment {target} could not be read as JSON: {exc}",
            kind="schema_error",
        ) from exc
    assignment = _parse_assignment(body)
    validate_assignment(assignment)
    return assignment


def load_configured_assignment() -> SplitAssignment | None:
    """Load the assignment named by :data:`ASSIGNMENT_ENV_VAR`, or ``None``.

    ``None`` means custody is not configured at all. A configured variable that
    names a missing file raises rather than silently disabling enforcement,
    because a typo would otherwise turn custody off without anyone noticing.
    """
    configured = os.environ.get(ASSIGNMENT_ENV_VAR)
    if configured is None or not configured.strip():
        return None
    target = Path(configured)
    if not target.is_file():
        raise HoldoutError(
            f"{ASSIGNMENT_ENV_VAR} names {configured!r}, which does not exist; "
            f"refusing to run without the configured custody file",
            kind="missing_assignment",
        )
    return load_assignment(target)


def canonical_form(assignment: SplitAssignment) -> str:
    """Serialize every assignment field, including ``inputs``, unambiguously.

    Keys and paper ids are sorted and the encoding is fixed, so two equivalent
    assignments always produce the same bytes regardless of input order.
    """
    body = {
        "split_version": assignment.split_version,
        "frozen_at": assignment.frozen_at,
        "custodian": assignment.custodian,
        "inputs": dict(assignment.inputs),
        "dev_paper_ids": sorted(assignment.dev_paper_ids),
        "holdout_paper_ids": sorted(assignment.holdout_paper_ids),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def commitment_tag(assignment: SplitAssignment, salt: bytes) -> str:
    """Return a salted HMAC-SHA256 hex digest over :func:`canonical_form`.

    The salt is mandatory. The split space is tiny -- ten papers with a
    two-paper minimum give only 45 candidate splits -- so an unsalted digest
    would be brute-forced in milliseconds and would disclose the very
    assignment it claims to protect.
    """
    if not isinstance(salt, (bytes, bytearray)) or not bytes(salt).strip():
        raise HoldoutError(
            "commitment salt must be non-empty, non-whitespace bytes; an unsalted "
            "digest over so few candidate splits is brute-forceable",
            kind="schema_error",
        )
    message = canonical_form(assignment).encode("utf-8")
    return hmac.new(bytes(salt), message, hashlib.sha256).hexdigest()


def verify_commitment(assignment: SplitAssignment, salt: bytes, tag: str) -> None:
    """Confirm ``tag`` is the commitment for ``assignment``; raise otherwise."""
    if not isinstance(tag, str) or not _COMMITMENT_TAG_PATTERN.match(tag):
        raise HoldoutError(
            f"commitment tag must be a 64-character lowercase hex digest, got {tag!r}",
            kind="schema_error",
        )
    expected = commitment_tag(assignment, salt)
    if not hmac.compare_digest(expected, tag):
        raise HoldoutError(
            "commitment tag does not match the frozen assignment; the split changed "
            "after it was frozen",
            kind="invalid_split",
        )


def split_of(paper_id: str, assignment: SplitAssignment) -> str:
    """Return ``"development"`` or ``"holdout"`` for ``paper_id``.

    A paper the assignment does not name is refused rather than assumed to be
    development: an unclassified paper is exactly the case custody exists to
    catch.
    """
    if paper_id in assignment.dev_paper_ids:
        return DEVELOPMENT_SPLIT
    if paper_id in assignment.holdout_paper_ids:
        return HOLDOUT_SPLIT
    raise HoldoutError(
        f"paper {paper_id!r} is not covered by split assignment "
        f"{assignment.split_version!r}",
        kind="invalid_split",
    )


def assert_development_safe(paper_ids: Iterable[str], assignment: SplitAssignment) -> None:
    """Refuse development work that names a holdout paper; raise on the first."""
    if isinstance(paper_ids, str):
        # A bare string would iterate as characters, none of which match a paper
        # id, so the check would pass silently -- a fail-open on the exact input
        # this function exists to catch.
        raise HoldoutError(
            "paper_ids must be a sequence of paper ids, not a single string",
            kind="schema_error",
        )
    holdout = set(assignment.holdout_paper_ids)
    for paper_id in paper_ids:
        if paper_id in holdout:
            raise HoldoutError(
                f"paper {paper_id!r} is held out for evaluation and must not be read, "
                f"prompted, or scored in development; use the evaluator path with custody",
                kind="holdout_access",
            )


def _record_paper_and_split(record: Any, label: str) -> tuple[str, str | None]:
    if isinstance(record, str):
        return _require_nonempty_str(record, label), None
    if isinstance(record, Mapping):
        paper_id = _require_nonempty_str(record.get("paper_id"), f"{label}.paper_id")
        declared = record.get("split")
        if declared is None:
            return paper_id, None
        return paper_id, _require_enum(declared, _SPLITS, f"{label}.split")
    if isinstance(record, (list, tuple)) and len(record) == 2:
        return (
            _require_nonempty_str(record[0], f"{label}[0]"),
            _require_enum(record[1], _SPLITS, f"{label}[1]"),
        )
    raise HoldoutError(
        f"{label} must be a paper id, an object with a paper_id, or a "
        f"(paper_id, split) pair",
        kind="schema_error",
    )


def assert_whole_paper(records: Any, assignment: SplitAssignment) -> None:
    """Refuse records that split one paper across the boundary; raise on the first.

    ``records`` is a sequence of records -- paper id strings, objects carrying
    ``paper_id`` and optionally ``split``, or ``(paper_id, split)`` pairs -- or
    a mapping of paper id to split. Every record for a paper must agree with
    that paper's single assigned split.
    """
    items = records.items() if isinstance(records, Mapping) else records
    if isinstance(items, (str, bytes)):
        raise HoldoutError(
            "records must be a sequence of records or a paper_id -> split mapping, "
            "not a single string",
            kind="schema_error",
        )
    seen: dict[str, str] = {}
    for idx, record in enumerate(items):
        paper_id, declared = _record_paper_and_split(record, f"records[{idx}]")
        expected = split_of(paper_id, assignment)
        if declared is None:
            declared = expected
        elif declared != expected:
            raise HoldoutError(
                f"records[{idx}] places paper {paper_id!r} in {declared!r} but the "
                f"assignment places it in {expected!r}; a whole paper belongs to "
                f"exactly one split",
                kind="leakage",
            )
        prior = seen.get(paper_id)
        if prior is not None and prior != declared:
            raise HoldoutError(
                f"paper {paper_id!r} appears as both {prior!r} and {declared!r}; a "
                f"whole paper belongs to exactly one split",
                kind="leakage",
            )
        seen[paper_id] = declared
