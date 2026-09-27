"""Deterministic tooling for human reference-graph annotation (#90).

Three pieces, all offline and model-free:

- :mod:`~jev_classifier.annotation.spans` maps a quote to UTF-8 byte offsets.
- :mod:`~jev_classifier.annotation.build` assembles a validated graph.
- :mod:`~jev_classifier.annotation.agreement` reports inter-annotator agreement.
- :mod:`~jev_classifier.annotation.protocol` checks the P1--P6 properties.

The package exists because a human must supply text and quotes, never offsets:
an offset typed by hand is unauditable, and a character index is a silent
mismatch against the metric's byte spans.
"""

from jev_classifier.annotation.agreement import (
    AgreementError,
    AgreementReport,
    AgreementResult,
    agreement_from_claim_sets,
    agreement_from_reviews,
    cohen_kappa,
)
from jev_classifier.annotation.build import (
    SCHEMA_VERSION,
    build_claim,
    build_graph,
    build_paper,
    build_review,
    build_source,
)
from jev_classifier.annotation.protocol import (
    AnnotationProtocolError,
    Finding,
    validate_protocol,
)
from jev_classifier.annotation.spans import SpanError, pick_span

__all__ = [
    "SCHEMA_VERSION",
    "AgreementError",
    "AgreementReport",
    "AgreementResult",
    "AnnotationProtocolError",
    "Finding",
    "SpanError",
    "agreement_from_claim_sets",
    "agreement_from_reviews",
    "build_claim",
    "build_graph",
    "build_paper",
    "build_review",
    "build_source",
    "cohen_kappa",
    "pick_span",
    "validate_protocol",
]
