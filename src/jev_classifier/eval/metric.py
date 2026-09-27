"""Pre-registered claim-level metric: ``claim_metric_v1`` (issue #66).

Scores predicted claims against a human-reviewed reference claim graph
(module ``R``, #37). Deterministic, offline, and produces no labels: it scores
already-structured claims and never calls a model.

The matching rule is versioned. A predicted claim **matches** a reference claim
iff all hold:

1. same ``paper_id`` and same ``source_id``;
2. the predicted evidence span is *contained* in the reference span
   (``pred.byte_start >= ref.byte_start`` and ``pred.byte_end <= ref.byte_end``);
3. ``epistemic_status`` is equal, compared case-insensitively.

Matching is one-to-one. When several predictions fall inside reference spans,
the smallest predicted span wins, ties broken by claim id, so the assignment is
deterministic.

Containment rather than overlap is deliberate: overlap would let one sprawling
prediction take credit for several reference claims at once, inflating recall
without fidelity.

Fail closed: a prediction with no usable span, an inverted span, or a
non-integer offset is a **miss**, never excluded. Lexical similarity and any
LLM-as-judge are prohibited substitutes for claim fidelity (parent ruling
5849173786) and are not implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from jev_classifier.reference import validate_reference_graph

METRIC_VERSION = "claim_metric_v1"

MATCH_RULE = "span_containment_v1"

# Case normalization at a real subsystem boundary: module R uses lowercase
# epistemic values (observed/inferred/hypothesized) while classify.py emits
# capitalized ones (Inferred). Reconciling the two vocabularies is a separate
# leaf; until then the comparison normalizes case and the report says so.
STATUS_COMPARISON = "case_insensitive"


@dataclass(frozen=True)
class Match:
    """One reference claim matched to one predicted claim."""

    reference_claim_id: str
    predicted_claim_id: str
    paper_id: str


def _as_span(evidence: Any) -> tuple[int, int] | None:
    """Return ``(start, end)`` when evidence carries a usable span, else ``None``."""
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


def _status(value: Any) -> str:
    return value.strip().lower() if isinstance(value, str) else ""


def _predicted_id(prediction: Mapping[str, Any], index: int) -> str:
    for key in ("claim_id", "id"):
        value = prediction.get(key)
        if isinstance(value, str) and value:
            return value
    return f"pred-{index}"


def match_claims(
    reference_claims: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> list[Match]:
    """One-to-one assignment of predictions to reference claims (deterministic)."""
    reference_by_id: dict[str, Mapping[str, Any]] = {}
    reference_spans: dict[str, tuple[int, int]] = {}
    for claim in reference_claims:
        span = _as_span(claim.get("evidence"))
        if span is None:
            # Module R guarantees a span on every reference claim; a graph that
            # reached here without one is malformed, not merely unscorable.
            continue
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            continue
        reference_by_id[claim_id] = claim
        reference_spans[claim_id] = span

    predicted_by_id: dict[str, Mapping[str, Any]] = {}
    predicted_spans: dict[str, tuple[int, int]] = {}
    for index, prediction in enumerate(predictions):
        span = _as_span(prediction.get("evidence"))
        if span is None:
            continue
        pred_id = _predicted_id(prediction, index)
        predicted_by_id[pred_id] = prediction
        predicted_spans[pred_id] = span

    # (predicted span length, reference id, predicted id) — smallest span wins.
    candidates: list[tuple[int, str, str]] = []
    for ref_id, (ref_start, ref_end) in reference_spans.items():
        reference = reference_by_id[ref_id]
        for pred_id, (pred_start, pred_end) in predicted_spans.items():
            prediction = predicted_by_id[pred_id]
            if reference.get("paper_id") != prediction.get("paper_id"):
                continue
            if reference.get("source_id") != prediction.get("source_id"):
                continue
            if _status(reference.get("epistemic_status")) != _status(
                prediction.get("epistemic_status")
            ):
                continue
            if pred_start >= ref_start and pred_end <= ref_end:
                candidates.append((pred_end - pred_start, ref_id, pred_id))
    candidates.sort()

    used_reference: set[str] = set()
    used_predicted: set[str] = set()
    matches: list[Match] = []
    for _, ref_id, pred_id in candidates:
        if ref_id in used_reference or pred_id in used_predicted:
            continue
        used_reference.add(ref_id)
        used_predicted.add(pred_id)
        matches.append(
            Match(
                reference_claim_id=ref_id,
                predicted_claim_id=pred_id,
                paper_id=str(reference_by_id[ref_id].get("paper_id", "")),
            )
        )
    return matches


def _prf(true_positives: int, predicted: int, reference: int) -> dict[str, Any]:
    precision = true_positives / predicted if predicted else 0.0
    recall = true_positives / reference if reference else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "true_positives": true_positives,
        "predicted": predicted,
        "reference": reference,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _citation_coverage(
    graph: Mapping[str, Any], predictions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Fraction of predictions whose cited source resolves in the graph."""
    sources = {
        s.get("source_id")
        for s in graph.get("sources", [])
        if isinstance(s, Mapping)
    }
    resolved = 0
    for prediction in predictions:
        source_id = prediction.get("source_id")
        if isinstance(source_id, str) and source_id in sources:
            resolved += 1
    total = len(predictions)
    return {
        "predictions_citing_a_resolved_source": resolved,
        "predictions": total,
        "coverage": round(resolved / total, 4) if total else None,
    }


def score_claims(
    graph: Any, predictions: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Score predictions against a reference claim graph.

    Validates the graph through module ``R`` and raises ``ReferenceSchemaError``
    on a malformed graph rather than scoring a partial one. Returns the primary
    micro P/R/F1, per-paper results, and the secondary coverage numbers.
    """
    validate_reference_graph(graph)

    reference_claims = list(graph["claims"])
    predictions = list(predictions)

    matches = match_claims(reference_claims, predictions)
    primary = _prf(len(matches), len(predictions), len(reference_claims))

    per_paper: dict[str, dict[str, Any]] = {}
    papers = sorted({str(c.get("paper_id", "")) for c in reference_claims})
    for paper_id in papers:
        ref_count = sum(
            1 for c in reference_claims if str(c.get("paper_id", "")) == paper_id
        )
        pred_count = sum(
            1
            for p in predictions
            if str(p.get("paper_id", "")) == paper_id
        )
        matched = sum(1 for m in matches if m.paper_id == paper_id)
        per_paper[paper_id] = _prf(matched, pred_count, ref_count)

    with_span = sum(1 for p in predictions if _as_span(p.get("evidence")) is not None)

    return {
        "metric_version": METRIC_VERSION,
        "match_rule": MATCH_RULE,
        "status_comparison": STATUS_COMPARISON,
        "primary": primary,
        "per_paper": per_paper,
        "predictions_total": len(predictions),
        "predictions_with_usable_span": with_span,
        "predictions_unmatched": len(predictions) - len(matches),
        "citation_coverage": _citation_coverage(graph, predictions),
        "ontology": {
            "graph_validated_by_module_r": True,
            "shacl": "not_implemented",
        },
        "note": (
            "Primary metric is claim-level micro-F1 under claim_metric_v1. A "
            "prediction without a usable span is a miss, not an exclusion; the "
            "predictions_with_usable_span count exposes that gap plainly. "
            "Secondary coverage numbers are reported separately and are never "
            "folded into the primary F1."
        ),
    }
