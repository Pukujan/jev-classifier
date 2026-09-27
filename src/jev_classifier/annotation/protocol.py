"""The P1--P6 annotation protocol checks for a finished reference graph (#90).

A reference graph can pass structural validation and still be unusable as a
measurement: two claims that are really one, a span that does not occur where
it says it does, an ``inferred`` claim promoted to ``observed``, or a second
review that quietly replaced the first. These six properties are the ones that
would corrupt the metric if they went unchecked, so they are checked here
rather than trusted to the annotator.

Two levels of severity, deliberately:

- **Hard violations** raise :class:`AnnotationProtocolError` with a distinct
  ``kind`` (P1, P3, P4, P5, P6). They are facts, not judgments: a quote either
  occurs at its recorded bytes or it does not.
- **Advisory findings** are returned (P2 atomicity, and P3 when a source text
  was not supplied). Splitting a sentence is an editorial judgment, so the
  tool flags it and a human decides. A skipped P3 is recorded rather than
  silently passing, so "no findings" never means "not checked".

Scope: this module reads a finished graph. It does not annotate, split claims,
or fetch source text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Sequence

from jev_classifier.reference.validate import EPISTEMIC_STATUSES

# The vocabulary has exactly one definition in the tree (module R); P5 imports
# it rather than restating the set, so the two cannot drift apart.

_MIN_CLAUSE_WORDS = 3

# Conservative atomicity signal: a clause separator joining two independent
# assertions. Punctuation-anchored on purpose -- a bare "and" splits "research
# and development" as readily as it splits two findings, and a false warning
# trains an annotator to ignore warnings. This under-flags; the annotator
# supplies the judgment the heuristic cannot.
_CLAUSE_SEPARATOR = re.compile(
    r"(?P<sep>;|,\s+(?:and|but|or|nor|yet|so)\s+)", re.IGNORECASE
)


class AnnotationProtocolError(ValueError):
    """Raised when a finished graph violates a hard annotation property."""

    def __init__(self, message: str, *, kind: str = "schema_error") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Finding:
    """An advisory observation about a graph: a warning or a skipped check."""

    property_id: str
    kind: str
    level: str
    message: str
    claim_id: str | None = None
    detail: Mapping[str, Any] = field(default_factory=dict)


def _claims(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = graph.get("claims")
    if not isinstance(value, list):
        raise AnnotationProtocolError("graph.claims must be an array", kind="schema_error")
    for idx, claim in enumerate(value):
        if not isinstance(claim, Mapping):
            raise AnnotationProtocolError(
                f"claims[{idx}] must be an object", kind="schema_error"
            )
    return value


def _reviews(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    value = graph.get("reviews", [])
    if not isinstance(value, list):
        raise AnnotationProtocolError("graph.reviews must be an array", kind="schema_error")
    for idx, review in enumerate(value):
        if not isinstance(review, Mapping):
            raise AnnotationProtocolError(
                f"reviews[{idx}] must be an object", kind="schema_error"
            )
    return value


def _span(claim: Mapping[str, Any]) -> tuple[int, int] | None:
    evidence = claim.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    start = evidence.get("byte_start")
    end = evidence.get("byte_end")
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end <= start:
        return None
    return start, end


def _quote(claim: Mapping[str, Any]) -> str | None:
    evidence = claim.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    quote = evidence.get("quote")
    return quote if isinstance(quote, str) and quote else None


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    value = claim.get("claim_id")
    return value if isinstance(value, str) and value else f"claim[{index}]"


def _check_p1_minimality(claims: Sequence[Mapping[str, Any]]) -> None:
    """No claim's span strictly contains another's, unless they differ.

    A containing span with different text or a different epistemic status is a
    legitimate broader claim. Identical text on a strictly larger span is the
    same assertion recorded twice, which double-counts it in every recall
    denominator; that is a merge, and it raises.
    """
    by_source: dict[str, list[tuple[str, int, int, Mapping[str, Any]]]] = {}
    for idx, claim in enumerate(claims):
        span = _span(claim)
        source_id = claim.get("source_id")
        if span is None or not isinstance(source_id, str):
            continue
        by_source.setdefault(source_id, []).append(
            (_claim_id(claim, idx), span[0], span[1], claim)
        )

    for source_id, entries in by_source.items():
        for i in range(len(entries)):
            outer_id, outer_start, outer_end, outer = entries[i]
            for j in range(len(entries)):
                if i == j:
                    continue
                inner_id, inner_start, inner_end, inner = entries[j]
                strictly_contains = outer_start <= inner_start and outer_end >= inner_end and (
                    outer_start < inner_start or outer_end > inner_end
                )
                if not strictly_contains:
                    continue
                if outer.get("text") != inner.get("text"):
                    continue
                if outer.get("epistemic_status") != inner.get("epistemic_status"):
                    continue
                raise AnnotationProtocolError(
                    f"claim {outer_id!r} span [{outer_start}, {outer_end}) strictly "
                    f"contains claim {inner_id!r} span [{inner_start}, {inner_end}) on "
                    f"source {source_id!r} with identical text and epistemic_status; "
                    f"merge them into one claim",
                    kind="containment",
                )


def _atomicity_findings(claims: Sequence[Mapping[str, Any]]) -> list[Finding]:
    """Flag, never split, a span joining two independent assertions."""
    findings: list[Finding] = []
    for idx, claim in enumerate(claims):
        quote = _quote(claim)
        if quote is None:
            continue
        for match in _CLAUSE_SEPARATOR.finditer(quote):
            left = quote[: match.start()].split()
            right = quote[match.end() :].split()
            if len(left) < _MIN_CLAUSE_WORDS or len(right) < _MIN_CLAUSE_WORDS:
                continue
            findings.append(
                Finding(
                    property_id="P2",
                    kind="atomicity",
                    level="warning",
                    claim_id=_claim_id(claim, idx),
                    message=(
                        f"claim span may join two independent assertions at "
                        f"{match.group('sep')!r}; split it if each side stands alone"
                    ),
                    detail={
                        "quote": quote,
                        "separator": match.group("sep"),
                        "left_words": len(left),
                        "right_words": len(right),
                    },
                )
            )
            break
    return findings


def _check_p3_verbatim(
    claims: Sequence[Mapping[str, Any]], source_texts: Mapping[str, str] | None
) -> list[Finding]:
    """Every quote must occur byte-identically at its recorded offsets.

    Source text is caller-supplied because restricted full text is not
    committed. A claim whose source text was not supplied produces a recorded
    skip, never a silent pass: an unchecked claim and a verified one must not
    look the same.
    """
    findings: list[Finding] = []
    for idx, claim in enumerate(claims):
        claim_id = _claim_id(claim, idx)
        quote = _quote(claim)
        span = _span(claim)
        source_id = claim.get("source_id")
        if quote is None or span is None or not isinstance(source_id, str):
            raise AnnotationProtocolError(
                f"claim {claim_id!r} has no usable evidence quote/span to verify",
                kind="not_verbatim",
            )
        if source_texts is None or source_id not in source_texts:
            findings.append(
                Finding(
                    property_id="P3",
                    kind="source_not_supplied",
                    level="skipped",
                    claim_id=claim_id,
                    message=(
                        f"verbatim check skipped: no source text supplied for "
                        f"source {source_id!r}; the quote was not verified"
                    ),
                    detail={"source_id": source_id, "byte_start": span[0], "byte_end": span[1]},
                )
            )
            continue
        source_bytes = source_texts[source_id].encode("utf-8")
        start, end = span
        actual = source_bytes[start:end]
        if actual != quote.encode("utf-8"):
            raise AnnotationProtocolError(
                f"claim {claim_id!r} quote is not verbatim at source {source_id!r} "
                f"bytes [{start}, {end}): recorded {quote!r}",
                kind="not_verbatim",
            )
    return findings


def _instant(value: str) -> Any:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _check_p4_bitemporality(claims: Sequence[Mapping[str, Any]]) -> None:
    """Transaction time and valid time stay separate fields, and ordered.

    An absent valid-time bound stays ``None``; it is never inferred from
    ``recorded_at``, which records when the claim was written, not when it was
    true. The three keys must all be present so a builder cannot collapse them
    into one field.
    """
    for idx, claim in enumerate(claims):
        claim_id = _claim_id(claim, idx)
        for key in ("recorded_at", "valid_from", "valid_to"):
            if key not in claim:
                raise AnnotationProtocolError(
                    f"claim {claim_id!r} is missing {key!r}; transaction time and "
                    f"valid time are distinct fields and both must be present",
                    kind="bitemporal",
                )
        recorded_at = claim.get("recorded_at")
        if not isinstance(recorded_at, str) or not recorded_at:
            raise AnnotationProtocolError(
                f"claim {claim_id!r}.recorded_at must be a non-empty string",
                kind="bitemporal",
            )
        bounds: dict[str, str] = {}
        for key in ("valid_from", "valid_to"):
            value = claim.get(key)
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise AnnotationProtocolError(
                    f"claim {claim_id!r}.{key} must be a non-empty string or null",
                    kind="bitemporal",
                )
            bounds[key] = value
        if len(bounds) < 2:
            continue
        start, end = bounds["valid_from"], bounds["valid_to"]
        parsed_start, parsed_end = _instant(start), _instant(end)
        if parsed_start is not None and parsed_end is not None:
            try:
                inverted = parsed_start > parsed_end
            except TypeError:
                # Mixed aware/naive timestamps: fall back to a lexical compare.
                inverted = start > end
        else:
            inverted = start > end
        if inverted:
            raise AnnotationProtocolError(
                f"claim {claim_id!r} has valid_from {start!r} after valid_to {end!r}",
                kind="bitemporal",
            )


def _check_p5_epistemic_honesty(claims: Sequence[Mapping[str, Any]]) -> None:
    """Every status comes from the single vocabulary module R defines."""
    for idx, claim in enumerate(claims):
        status = claim.get("epistemic_status")
        if status not in EPISTEMIC_STATUSES:
            raise AnnotationProtocolError(
                f"claim {_claim_id(claim, idx)!r} has epistemic_status {status!r}; "
                f"allowed values are {sorted(EPISTEMIC_STATUSES)}",
                kind="unknown_status",
            )


def _check_p6_disagreement_preserved(
    claims: Sequence[Mapping[str, Any]], reviews: Sequence[Mapping[str, Any]]
) -> None:
    """Reviews accumulate; a replacement supersedes, and a chain terminates.

    Two reviews by one annotator on one claim with no supersession link means
    one overwrote the other and the graph no longer says which stands -- the
    disagreement is lost, so it raises. A supersession pointer that dangles or
    cycles never reaches a final decision, which is the same loss by another
    route.
    """
    claim_ids = {
        claim.get("claim_id")
        for claim in claims
        if isinstance(claim.get("claim_id"), str)
    }
    by_id: dict[str, Mapping[str, Any]] = {}
    for idx, review in enumerate(reviews):
        review_id = review.get("review_id")
        if not isinstance(review_id, str) or not review_id:
            raise AnnotationProtocolError(
                f"reviews[{idx}].review_id must be a non-empty string",
                kind="disagreement_lost",
            )
        if review_id in by_id:
            raise AnnotationProtocolError(
                f"duplicate review id {review_id!r}", kind="disagreement_lost"
            )
        by_id[review_id] = review

    seen_annotator: dict[tuple[str, str], list[str]] = {}
    for review_id, review in by_id.items():
        claim_id = review.get("claim_id")
        if claim_id not in claim_ids:
            raise AnnotationProtocolError(
                f"review {review_id!r} cites claim {claim_id!r}, which is not in the graph",
                kind="disagreement_lost",
            )
        annotator_id = review.get("annotator_id")
        if not isinstance(annotator_id, str) or not annotator_id:
            raise AnnotationProtocolError(
                f"review {review_id!r}.annotator_id must be a non-empty string",
                kind="disagreement_lost",
            )
        seen_annotator.setdefault((claim_id, annotator_id), []).append(review_id)

    for (claim_id, annotator_id), group in seen_annotator.items():
        if len(group) < 2:
            continue
        # A chain of replacements preserves every decision; N unlinked reviews
        # by one annotator on one claim means N-1 were overwritten and the graph
        # no longer says which stands. The edges restricted to this group must
        # form exactly one path: one head, every other review superseded by
        # exactly one member.
        members = set(group)
        superseded_by: dict[str, int] = {review_id: 0 for review_id in group}
        for review_id in group:
            target = by_id[review_id].get("supersedes_review_id")
            if target in members:
                superseded_by[target] += 1
        heads = [review_id for review_id in group if superseded_by[review_id] == 0]
        overlinked = [
            review_id for review_id in group if superseded_by[review_id] > 1
        ]
        if len(heads) != 1 or overlinked:
            raise AnnotationProtocolError(
                f"annotator {annotator_id!r} has {len(group)} reviews on claim "
                f"{claim_id!r} that do not form a single supersession chain "
                f"(heads={heads}, multiply-superseded={overlinked}); a decision has "
                f"been lost",
                kind="disagreement_lost",
            )

    for review_id, review in by_id.items():
        visited: set[str] = set()
        current = review_id
        while True:
            if current in visited:
                raise AnnotationProtocolError(
                    f"supersession chain from review {review_id!r} cycles at {current!r} "
                    f"and never terminates",
                    kind="disagreement_lost",
                )
            visited.add(current)
            target = by_id[current].get("supersedes_review_id")
            if target is None:
                break
            if not isinstance(target, str) or target not in by_id:
                raise AnnotationProtocolError(
                    f"review {current!r} supersedes {target!r}, which is not a review in "
                    f"the graph; the superseded decision is missing",
                    kind="disagreement_lost",
                )
            if target == current:
                raise AnnotationProtocolError(
                    f"review {current!r} supersedes itself", kind="disagreement_lost"
                )
            current = target


def validate_protocol(
    graph: Any, *, source_texts: Mapping[str, str] | None = None
) -> list[Finding]:
    """Run P1--P6 over a finished graph; raise on the first hard violation.

    Returns the advisory findings (P2 warnings, P3 skips) in property order.
    ``source_texts`` maps ``source_id`` to the exact annotated source text; a
    source absent from it makes P3 record a skip for its claims instead of
    passing them.
    """
    if not isinstance(graph, Mapping):
        raise AnnotationProtocolError("graph must be an object", kind="schema_error")
    claims = _claims(graph)
    reviews = _reviews(graph)

    _check_p1_minimality(claims)
    findings = _atomicity_findings(claims)
    findings.extend(_check_p3_verbatim(claims, source_texts))
    _check_p4_bitemporality(claims)
    _check_p5_epistemic_honesty(claims)
    _check_p6_disagreement_preserved(claims, reviews)
    return findings
