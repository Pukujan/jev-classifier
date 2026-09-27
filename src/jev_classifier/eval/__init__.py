"""Pre-registered claim-level metric and offline evaluation harness (#66)."""

from jev_classifier.eval.metric import (
    MATCH_RULE,
    METRIC_VERSION,
    STATUS_COMPARISON,
    Match,
    match_claims,
    score_claims,
)

__all__ = [
    "MATCH_RULE",
    "METRIC_VERSION",
    "STATUS_COMPARISON",
    "Match",
    "match_claims",
    "score_claims",
]
