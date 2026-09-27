"""Inter-annotator agreement for reference-graph annotation (#90).

A raw percentage overstates agreement whenever one category dominates: two
annotators who both mark almost everything ``observed`` look 95% alike even if
their judgment is unrelated. Cohen's kappa corrects for that by subtracting the
agreement expected from the marginal distributions, so this module reports
both -- the raw figure because it is what a reader pictures, and kappa because
it is the one that survives a skewed label distribution.

The degenerate case is handled explicitly rather than by division:
``p_e == 1.0`` means one category carries both marginals, so the correction
term vanishes and kappa is undefined. The choice made here is documented on
:func:`cohen_kappa`.

Input is paired categorical labels -- decisions from review records, or
epistemic statuses on spans both annotators marked. This module computes a
statistic; it does not adjudicate disagreement or pick a winner.

Scope: two-annotator agreement only. More than two annotators needs Fleiss'
kappa or a pairwise matrix, which is not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


class AgreementError(ValueError):
    """Raised when agreement cannot be computed from the supplied records."""

    def __init__(self, message: str, *, kind: str = "schema_error") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class AgreementResult:
    """Observed and chance-corrected agreement, with the counts behind them.

    Every number is reported alongside the raw material it came from, so a
    reader can recompute ``kappa`` by hand rather than trusting the ratio.
    """

    n_items: int
    categories: tuple[str, ...]
    counts_a: Mapping[str, int]
    counts_b: Mapping[str, int]
    agreement_matrix: Mapping[tuple[str, str], int]
    agreements: int
    observed_agreement: float
    expected_agreement: float
    kappa: float
    degenerate: bool
    note: str = ""


@dataclass(frozen=True)
class AgreementReport:
    """An :class:`AgreementResult` plus how the paired items were selected.

    A kappa computed over three shared items is a much weaker statement than
    one computed over three hundred, so the pairing coverage travels with the
    number.
    """

    result: AgreementResult
    annotator_a: str
    annotator_b: str
    paired_item_ids: tuple[str, ...] = ()
    only_a: tuple[str, ...] = ()
    only_b: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)


def _pairs(pairs: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for idx, pair in enumerate(pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise AgreementError(
                f"pairs[{idx}] must be a (label_a, label_b) pair", kind="schema_error"
            )
        left, right = pair
        for label, side in ((left, "a"), (right, "b")):
            if not isinstance(label, str) or not label:
                raise AgreementError(
                    f"pairs[{idx}] label_{side} must be a non-empty string, got {label!r}",
                    kind="schema_error",
                )
        out.append((left, right))
    return out


def cohen_kappa(pairs: Sequence[tuple[str, str]]) -> AgreementResult:
    """Compute Cohen's kappa over paired categorical labels.

    ``kappa = (p_o - p_e) / (1 - p_e)`` where ``p_o`` is the fraction of pairs
    that agree and ``p_e`` is the agreement expected if each annotator drew
    independently from their own marginal distribution.

    Degenerate case: when ``p_e == 1.0`` the denominator is zero and kappa is
    mathematically undefined. Both annotators have used a single category, so
    observed agreement is necessarily perfect as well; this returns ``1.0`` and
    sets ``degenerate=True`` rather than dividing by zero or raising, because
    "both annotators used exactly one label and agreed on it" is genuinely
    perfect -- if uninformative -- agreement. The flag lets a reader discount it.

    Raises :class:`AgreementError` (``kind="no_items"``) on an empty input:
    agreement over zero items is undefined, not zero.
    """
    labelled = _pairs(pairs)
    n = len(labelled)
    if n == 0:
        raise AgreementError(
            "agreement is undefined over zero paired items", kind="no_items"
        )

    counts_a: dict[str, int] = {}
    counts_b: dict[str, int] = {}
    matrix: dict[tuple[str, str], int] = {}
    agreements = 0
    for left, right in labelled:
        counts_a[left] = counts_a.get(left, 0) + 1
        counts_b[right] = counts_b.get(right, 0) + 1
        matrix[(left, right)] = matrix.get((left, right), 0) + 1
        if left == right:
            agreements += 1

    categories = tuple(sorted(set(counts_a) | set(counts_b)))
    observed = agreements / n
    expected = sum(
        counts_a.get(c, 0) * counts_b.get(c, 0) for c in categories
    ) / (n * n)

    if expected == 1.0:
        return AgreementResult(
            n_items=n,
            categories=categories,
            counts_a=dict(sorted(counts_a.items())),
            counts_b=dict(sorted(counts_b.items())),
            agreement_matrix=dict(sorted(matrix.items())),
            agreements=agreements,
            observed_agreement=round(observed, 6),
            expected_agreement=1.0,
            kappa=1.0,
            degenerate=True,
            note=(
                "p_e == 1.0: both annotators used one category exclusively, so the "
                "chance correction is undefined; kappa is reported as 1.0 for perfect "
                "agreement and flagged degenerate. This is a weak result, not strong "
                "evidence of reliability."
            ),
        )

    kappa = (observed - expected) / (1 - expected)
    return AgreementResult(
        n_items=n,
        categories=categories,
        counts_a=dict(sorted(counts_a.items())),
        counts_b=dict(sorted(counts_b.items())),
        agreement_matrix=dict(sorted(matrix.items())),
        agreements=agreements,
        observed_agreement=round(observed, 6),
        expected_agreement=round(expected, 6),
        kappa=round(kappa, 6),
        degenerate=False,
        note=(
            "kappa = (p_o - p_e) / (1 - p_e). p_o is raw agreement; p_e is the "
            "agreement expected from the two marginal distributions alone."
        ),
    )


def _review_index(reviews: Sequence[Mapping[str, Any]], annotator: str) -> dict[str, str]:
    """Map claim id to this annotator's decision, refusing a silent overwrite."""
    index: dict[str, str] = {}
    for idx, review in enumerate(reviews):
        if not isinstance(review, Mapping):
            raise AgreementError(f"reviews[{idx}] must be an object", kind="schema_error")
        if review.get("annotator_id") != annotator:
            continue
        claim_id = review.get("claim_id")
        decision = review.get("decision")
        if not isinstance(claim_id, str) or not claim_id:
            raise AgreementError(
                f"reviews[{idx}].claim_id must be a non-empty string", kind="schema_error"
            )
        if not isinstance(decision, str) or not decision:
            raise AgreementError(
                f"reviews[{idx}].decision must be a non-empty string", kind="schema_error"
            )
        if claim_id in index and index[claim_id] != decision:
            # Two undecided reviews by one annotator on one claim: picking either
            # would fabricate a decision the records do not state.
            raise AgreementError(
                f"annotator {annotator!r} has two conflicting decisions on claim "
                f"{claim_id!r}; supersede one review explicitly",
                kind="duplicate_review",
            )
        index[claim_id] = decision
    return index


def agreement_from_reviews(
    reviews: Sequence[Mapping[str, Any]], *, annotator_a: str, annotator_b: str
) -> AgreementReport:
    """Compute agreement between two annotators over the claims both reviewed.

    A claim reviewed by only one annotator is reported in ``only_a``/``only_b``
    and excluded from the statistic -- pairing it against a missing decision
    would invent a label. The exclusion counts travel with the result.
    """
    if annotator_a == annotator_b:
        raise AgreementError(
            "annotator_a and annotator_b must be different annotators", kind="schema_error"
        )
    left = _review_index(reviews, annotator_a)
    right = _review_index(reviews, annotator_b)
    shared = sorted(set(left) & set(right))
    pairs = [(left[claim_id], right[claim_id]) for claim_id in shared]
    return AgreementReport(
        result=cohen_kappa(pairs),
        annotator_a=annotator_a,
        annotator_b=annotator_b,
        paired_item_ids=tuple(shared),
        only_a=tuple(sorted(set(left) - set(right))),
        only_b=tuple(sorted(set(right) - set(left))),
    )


def _span_key(claim: Mapping[str, Any]) -> tuple[str, int, int] | None:
    evidence = claim.get("evidence")
    if not isinstance(evidence, Mapping):
        return None
    start = evidence.get("byte_start")
    end = evidence.get("byte_end")
    if isinstance(start, bool) or isinstance(end, bool):
        return None
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    source_id = claim.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        return None
    return source_id, start, end


def _claims_by_span(claims: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int, int], str]:
    index: dict[tuple[str, int, int], str] = {}
    for idx, claim in enumerate(claims):
        if not isinstance(claim, Mapping):
            raise AgreementError(f"claims[{idx}] must be an object", kind="schema_error")
        key = _span_key(claim)
        if key is None:
            continue
        status = claim.get("epistemic_status")
        if not isinstance(status, str) or not status:
            raise AgreementError(
                f"claims[{idx}].epistemic_status must be a non-empty string",
                kind="schema_error",
            )
        if key in index:
            raise AgreementError(
                f"two claims share the span {key!r}; spans must be unique before "
                f"agreement can be computed",
                kind="duplicate_span",
            )
        index[key] = status
    return index


def agreement_from_claim_sets(
    claims_a: Sequence[Mapping[str, Any]],
    claims_b: Sequence[Mapping[str, Any]],
    *,
    annotator_a: str = "annotator-a",
    annotator_b: str = "annotator-b",
) -> AgreementReport:
    """Agreement over spans both annotators marked, labelled by epistemic status.

    Claims are paired by ``(source_id, byte_start, byte_end)``: a span is the
    unit both annotators can independently agree on, and the categorical label
    is the ``epistemic_status`` each assigned it. A span only one annotator
    marked is a coverage gap reported in ``only_a``/``only_b``, not an
    agreement item.
    """
    left = _claims_by_span(claims_a)
    right = _claims_by_span(claims_b)
    shared = sorted(set(left) & set(right))
    pairs = [(left[key], right[key]) for key in shared]
    return AgreementReport(
        result=cohen_kappa(pairs),
        annotator_a=annotator_a,
        annotator_b=annotator_b,
        paired_item_ids=tuple(f"{key[0]}:{key[1]}-{key[2]}" for key in shared),
        only_a=tuple(
            f"{key[0]}:{key[1]}-{key[2]}" for key in sorted(set(left) - set(right))
        ),
        only_b=tuple(
            f"{key[0]}:{key[1]}-{key[2]}" for key in sorted(set(right) - set(left))
        ),
    )
