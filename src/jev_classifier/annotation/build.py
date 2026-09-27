"""Mechanical assembly of a reference claim graph (#90).

An annotator supplies source text and a quote; this module turns that into the
record shape the validator accepts, so no human ever types a byte offset and no
offset is computed by hand. Every claim passes through :func:`pick_span`, and
the finished graph passes through ``validate_reference_graph`` before it is
returned -- a caller cannot receive a graph this repository would reject.

Fail closed: the builder never defaults a missing field or repairs a bad one.
A :class:`~jev_classifier.reference.ReferenceSchemaError` propagates unchanged.

Scope: this module assembles records. It does not choose what to annotate,
resolve disagreement, or write anything to disk.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from jev_classifier.annotation.spans import pick_span
from jev_classifier.reference import validate_reference_graph

SCHEMA_VERSION = "1.0.0"


def build_paper(
    *, paper_id: str, title: str, version: str, doi: str | None = None, url: str | None = None
) -> dict[str, Any]:
    """Build one paper record."""
    return {"paper_id": paper_id, "title": title, "version": version, "doi": doi, "url": url}


def build_source(
    *,
    source_id: str,
    paper_id: str,
    version: str,
    content_sha256: str | None = None,
) -> dict[str, Any]:
    """Build one source record.

    ``content_sha256`` stays ``None`` unless the caller hashes the exact bytes
    it annotated: a digest over re-encoded text would bind the record to
    something other than the annotated source.
    """
    return {
        "source_id": source_id,
        "paper_id": paper_id,
        "version": version,
        "content_sha256": content_sha256,
    }


def build_claim(
    *,
    claim_id: str,
    text: str,
    paper_id: str,
    source_id: str,
    source_text: str,
    quote: str,
    epistemic_status: str,
    recorded_at: str,
    occurrence: int | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Build one claim, deriving its byte span from ``source_text`` and ``quote``.

    The annotator never supplies ``byte_start``/``byte_end``. An absent or
    ambiguous quote raises from :func:`pick_span` rather than producing a claim
    with a guessed span.
    """
    byte_start, byte_end = pick_span(source_text, quote, occurrence=occurrence)
    claim: dict[str, Any] = {
        "claim_id": claim_id,
        "text": text,
        "paper_id": paper_id,
        "source_id": source_id,
        "evidence": {"quote": quote, "byte_start": byte_start, "byte_end": byte_end},
        "epistemic_status": epistemic_status,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recorded_at": recorded_at,
    }
    if notes is not None:
        claim["notes"] = notes
    return claim


def build_review(
    *,
    review_id: str,
    claim_id: str,
    annotator_id: str,
    decision: str,
    recorded_at: str,
    note: str | None = None,
    supersedes_review_id: str | None = None,
) -> dict[str, Any]:
    """Build one review record.

    A replacement review carries ``supersedes_review_id``; the superseded
    record stays in the graph, because a decision that overwrote another would
    destroy the disagreement the protocol exists to preserve.
    """
    review: dict[str, Any] = {
        "review_id": review_id,
        "claim_id": claim_id,
        "annotator_id": annotator_id,
        "decision": decision,
        "recorded_at": recorded_at,
        "supersedes_review_id": supersedes_review_id,
    }
    if note is not None:
        review["note"] = note
    return review


def build_graph(
    *,
    graph_id: str,
    papers: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]] = (),
    reviews: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Assemble a reference graph and validate it before returning.

    Validation is not optional and not advisory: a graph that fails
    :func:`validate_reference_graph` raises here, so an invalid graph cannot
    leave the builder.
    """
    graph: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "graph_id": graph_id,
        "papers": list(papers),
        "sources": list(sources),
        "claims": list(claims),
        "relationships": list(relationships),
        "reviews": list(reviews),
    }
    validate_reference_graph(graph)
    return graph
