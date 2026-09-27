"""Pre-registered claim-level metric tests (issue #66).

The matching rule is the deliverable, so these tests pin its boundaries: a
perfect match scores 1.0, an empty prediction set scores 0.0 recall, a spanless
or out-of-span prediction is a miss (never excluded), a malformed graph is
rejected rather than partially scored, and identical inputs give identical
output.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from jev_classifier.eval import (
    MATCH_RULE,
    METRIC_VERSION,
    STATUS_COMPARISON,
    match_claims,
    score_claims,
)
from jev_classifier.reference import ReferenceSchemaError

FIX = Path(__file__).resolve().parent / "fixtures" / "reference"


def _graph() -> dict:
    return json.loads((FIX / "claim_graph_ok.json").read_text(encoding="utf-8"))


def _prediction(
    claim_id: str,
    *,
    paper_id: str = "paper:demo-a",
    source_id: str = "source:demo-a-abstract",
    status: str = "observed",
    byte_start: int = 130,
    byte_end: int = 160,
) -> dict:
    return {
        "claim_id": claim_id,
        "paper_id": paper_id,
        "source_id": source_id,
        "epistemic_status": status,
        "evidence": {"byte_start": byte_start, "byte_end": byte_end},
    }


def _perfect_predictions() -> list[dict]:
    return [
        _prediction("p1", status="observed", byte_start=130, byte_end=160),
        _prediction("p2", status="inferred", byte_start=210, byte_end=240),
    ]


# --- versioned rule ---


def test_metric_version_and_rule_are_recorded() -> None:
    report = score_claims(_graph(), _perfect_predictions())
    assert report["metric_version"] == METRIC_VERSION
    assert report["match_rule"] == MATCH_RULE
    assert report["status_comparison"] == STATUS_COMPARISON
    assert METRIC_VERSION == "claim_metric_v1"


def test_identical_inputs_give_identical_output() -> None:
    graph = _graph()
    predictions = _perfect_predictions()
    first = score_claims(graph, predictions)
    second = score_claims(copy.deepcopy(graph), copy.deepcopy(predictions))
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


# --- boundaries ---


def test_perfect_match_scores_one() -> None:
    report = score_claims(_graph(), _perfect_predictions())
    assert report["primary"]["f1"] == 1.0
    assert report["primary"]["precision"] == 1.0
    assert report["primary"]["recall"] == 1.0
    assert report["primary"]["true_positives"] == 2
    assert report["predictions_unmatched"] == 0


def test_empty_predictions_scores_zero_recall() -> None:
    report = score_claims(_graph(), [])
    assert report["primary"]["recall"] == 0.0
    assert report["primary"]["f1"] == 0.0
    assert report["predictions_total"] == 0


def test_spanless_prediction_is_a_miss_not_excluded() -> None:
    # classify.py emits {fragment_id, path} with no byte span. That must count
    # as a miss and must show up in the usable-span count, not vanish.
    spanless = {
        "claim_id": "p1",
        "paper_id": "paper:demo-a",
        "source_id": "source:demo-a-abstract",
        "epistemic_status": "observed",
        "evidence": {"fragment_id": "frag-1", "path": "tests/fixtures/x.json"},
    }
    report = score_claims(_graph(), [spanless])
    assert report["primary"]["true_positives"] == 0
    assert report["predictions_total"] == 1
    assert report["predictions_with_usable_span"] == 0
    assert report["predictions_unmatched"] == 1


def test_inverted_span_is_a_miss() -> None:
    bad = _prediction("p1", status="observed", byte_start=160, byte_end=130)
    report = score_claims(_graph(), [bad])
    assert report["predictions_with_usable_span"] == 0
    assert report["primary"]["true_positives"] == 0


def test_span_outside_the_reference_span_is_a_miss() -> None:
    # Starts inside claim:demo-1's span but ends past its end (163).
    outside = _prediction("p1", status="observed", byte_start=150, byte_end=180)
    report = score_claims(_graph(), [outside])
    assert report["primary"]["true_positives"] == 0


def test_mismatched_epistemic_status_is_a_miss() -> None:
    wrong = _prediction("p1", status="hypothesized", byte_start=130, byte_end=160)
    report = score_claims(_graph(), [wrong])
    assert report["primary"]["true_positives"] == 0


def test_mismatched_source_is_a_miss() -> None:
    wrong = _prediction("p1", source_id="source:other", byte_start=130, byte_end=160)
    report = score_claims(_graph(), [wrong])
    assert report["primary"]["true_positives"] == 0


# --- the case-normalization amendment ---


def test_epistemic_status_compares_case_insensitively() -> None:
    # classify.py emits "Inferred"; module R uses "inferred".
    capitalized = _prediction("p1", status="Inferred", byte_start=210, byte_end=240)
    report = score_claims(_graph(), [capitalized])
    assert report["primary"]["true_positives"] == 1


# --- one-to-one, smallest span wins ---


def test_a_span_wider_than_the_reference_span_is_a_miss() -> None:
    # Containment is strict: a sprawling prediction that starts before and ends
    # after the reference span is not a match, so it cannot inflate recall.
    wide = _prediction("wide", status="observed", byte_start=100, byte_end=250)
    report = score_claims(_graph(), [wide])
    assert report["primary"]["true_positives"] == 0
    assert report["predictions_with_usable_span"] == 1
    assert report["predictions_unmatched"] == 1


def test_a_whole_fragment_span_is_still_a_miss_against_a_tighter_reference() -> None:
    # Measured consequence of the rule, pinned so it cannot be lost: the live
    # pipeline classifies a whole fragment, so its natural evidence unit is the
    # fragment. claim:demo-1's reference span is 120..163, a sentence inside it.
    # A prediction covering the whole fragment (0..185) is *wider* than the
    # reference span and therefore fails containment. Emitting a span is not
    # enough to score — the span must be at least as tight as the human's.
    whole_fragment = _prediction("p", status="observed", byte_start=0, byte_end=185)
    report = score_claims(_graph(), [whole_fragment])
    assert report["predictions_with_usable_span"] == 1  # it is a real span...
    assert report["primary"]["true_positives"] == 0  # ...and still a miss
    assert report["primary"]["recall"] == 0.0


def test_one_prediction_matches_only_one_of_two_overlapping_reference_claims() -> None:
    # Two reference spans overlap; a prediction inside the overlap is contained
    # in both. It must take exactly one, deterministically.
    graph = _graph()
    graph["claims"] = [
        {
            "claim_id": "claim:overlap-a",
            "paper_id": "paper:demo-a",
            "source_id": "source:demo-a-abstract",
            "text": "A",
            "epistemic_status": "observed",
            "recorded_at": "2026-09-26T00:00:00+00:00",
            "valid_from": None,
            "valid_to": None,
            "evidence": {"quote": "a", "byte_start": 100, "byte_end": 200},
        },
        {
            "claim_id": "claim:overlap-b",
            "paper_id": "paper:demo-a",
            "source_id": "source:demo-a-abstract",
            "text": "B",
            "epistemic_status": "observed",
            "recorded_at": "2026-09-26T00:00:00+00:00",
            "valid_from": None,
            "valid_to": None,
            "evidence": {"quote": "b", "byte_start": 150, "byte_end": 250},
        },
    ]
    graph["relationships"] = []
    graph["reviews"] = []
    inside_both = _prediction("p", status="observed", byte_start=160, byte_end=190)
    matches = match_claims(graph["claims"], [inside_both])
    assert len(matches) == 1
    # Deterministic: re-running gives the same single assignment.
    again = match_claims(graph["claims"], [inside_both])
    assert [m.reference_claim_id for m in again] == [m.reference_claim_id for m in matches]


def test_smallest_span_wins_the_assignment() -> None:
    refs = _graph()["claims"]
    wide = _prediction("wide", status="observed", byte_start=100, byte_end=250)
    tight = _prediction("tight", status="observed", byte_start=130, byte_end=140)
    matches = match_claims(refs, [wide, tight])
    assert len(matches) == 1
    assert matches[0].predicted_claim_id == "tight"


def test_two_predictions_do_not_both_take_the_same_reference_claim() -> None:
    a = _prediction("a", status="observed", byte_start=130, byte_end=150)
    b = _prediction("b", status="observed", byte_start=140, byte_end=160)
    matches = match_claims(_graph()["claims"], [a, b])
    assert len(matches) == 1
    assert {m.predicted_claim_id for m in matches} == {"a"}


# --- aggregation and secondary numbers ---


def test_per_paper_results_are_reported_alongside_the_aggregate() -> None:
    report = score_claims(_graph(), _perfect_predictions())
    assert "paper:demo-a" in report["per_paper"]
    row = report["per_paper"]["paper:demo-a"]
    assert row["reference"] == 2
    assert row["predicted"] == 2
    assert row["f1"] == 1.0


def test_citation_coverage_is_reported_separately() -> None:
    report = score_claims(_graph(), _perfect_predictions())
    coverage = report["citation_coverage"]
    assert coverage["predictions_citing_a_resolved_source"] == 2
    assert coverage["coverage"] == 1.0
    # Never folded into the primary metric.
    assert "citation" not in json.dumps(report["primary"])


def test_citation_coverage_is_independent_of_match_quality() -> None:
    # A single prediction matches one of two reference claims: recall is 0.5,
    # yet its citation still resolves, so coverage is 1.0. The two numbers
    # measure different things and are reported separately.
    prediction = _prediction("p1", status="observed", byte_start=130, byte_end=160)
    report = score_claims(_graph(), [prediction])
    assert report["primary"]["true_positives"] == 1
    assert report["primary"]["recall"] == 0.5
    assert report["citation_coverage"]["coverage"] == 1.0

    # A prediction citing a source that is not in the graph has no coverage.
    orphan = _prediction("p9", source_id="source:missing", byte_start=130, byte_end=160)
    report2 = score_claims(_graph(), [orphan])
    assert report2["citation_coverage"]["coverage"] == 0.0


def test_shacl_status_is_reported_and_not_claimed_as_passing() -> None:
    report = score_claims(_graph(), _perfect_predictions())
    assert report["ontology"]["shacl"] == "not_implemented"
    assert report["ontology"]["graph_validated_by_module_r"] is True


# --- fail closed on a malformed graph ---


def test_malformed_graph_is_rejected_not_partially_scored() -> None:
    graph = _graph()
    graph["claims"][0]["source_id"] = "source:missing"
    with pytest.raises(ReferenceSchemaError, match="does not resolve to a source"):
        score_claims(graph, _perfect_predictions())


def test_graph_missing_required_key_is_rejected() -> None:
    graph = _graph()
    del graph["relationships"]
    with pytest.raises(ReferenceSchemaError):
        score_claims(graph, _perfect_predictions())


# --- no model, no network ---


def _metric_source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "src"
        / "jev_classifier"
        / "eval"
        / "metric.py"
    ).read_text(encoding="utf-8")


def test_metric_module_makes_no_network_or_model_calls() -> None:
    source = _metric_source()
    for forbidden in ("httpx", "requests", "openrouter", "DecisionsClient", "socket"):
        assert forbidden not in source, f"metric must not reference {forbidden}"


def test_metric_module_imports_only_the_reference_validator() -> None:
    # The only *project* import is module R's graph validator; nothing else from
    # the package (no decisions client, no normalizer) may be pulled in.
    project_imports = [
        line.strip()
        for line in _metric_source().splitlines()
        if line.startswith(("import jev_classifier", "from jev_classifier"))
    ]
    assert project_imports == [
        "from jev_classifier.reference import validate_reference_graph"
    ], f"unexpected project imports in metric: {project_imports}"


def test_no_lexical_similarity_or_llm_judge_substitute() -> None:
    # The docstring names these as prohibited; the check is that none is
    # actually imported or called.
    source = _metric_source()
    for forbidden in (
        "import difflib",
        "SequenceMatcher(",
        "from difflib",
        "cosine(",
        "embedding",
        "llm_judge",
        "as_judge",
    ):
        assert forbidden not in source, f"prohibited substitute {forbidden} in metric"
