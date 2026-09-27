"""Evidence byte-span localization for classify predictions (Issue #86).

Offline only: fake Decisions clients. Proves the closed-candidate design:
deterministic code owns UTF-8 byte offsets, JEV makes one atomic selection,
failure/unknown leaves the span unset (honest miss, never invented offsets).
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

import pytest

from jev_classifier.classify import (
    candidate_spans,
    classify_fragment,
    load_fragment_fixture,
)
from jev_classifier.eval.metric import match_claims

FIX = Path(__file__).resolve().parent / "fixtures"

TEXT = (
    "The trial enrolled 402 participants across eleven clinics. "
    "The primary endpoint improved by 18% under condition X. "
    "Follow-up at twelve months sustained the gain."
)


def _fragment(**over: Any) -> dict[str, Any]:
    base = {
        "id": "frag-span-1",
        "source": "synthetic",
        "title": "Span test fragment",
        "text": TEXT,
        "closed_label_set": ["empirical_finding", "methodology", "other"],
        "question_id": "claim_kind",
        "instructions": "Classify the research fragment into exactly one closed label.",
        "criteria": {
            "empirical_finding": "Reports an observed result.",
            "methodology": "Describes methods.",
            "other": "None of the above.",
        },
    }
    base.update(over)
    return base


class SpanClient:
    """Fake Decisions client answering label + span questions from a canned map."""

    def __init__(self, answers: Mapping[str, Any], model: str = "typesafe/jev-1.13") -> None:
        self.model = model
        self._answers = dict(answers)
        self.last_questions: Mapping[str, Any] | None = None
        self.last_state: Mapping[str, Any] | None = None

    def decide(
        self,
        *,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        del model
        self.last_questions = copy.deepcopy(dict(questions))
        self.last_state = (
            copy.deepcopy(dict(state)) if isinstance(state, Mapping) else state
        )
        return {
            "id": "resp-span-1",
            "model": self.model,
            "answers": copy.deepcopy(self._answers),
        }


def _answers(span_choice: str | None, label: str = "empirical_finding") -> dict[str, Any]:
    out: dict[str, Any] = {"claim_kind": {"type": "choice", "choice": label}}
    if span_choice is not None:
        out["claim_kind_span"] = {"type": "choice", "choice": span_choice}
    return out


# --- deterministic splitter -------------------------------------------------


def test_candidate_spans_returns_all_sentences_in_order() -> None:
    spans = candidate_spans(TEXT)
    assert [s["id"] for s in spans] == ["c1", "c2", "c3"]
    for s in spans:
        assert s["byte_end"] > s["byte_start"] >= 0
    # exact slices, no trailing whitespace: one stray byte breaks containment
    slices = [
        TEXT.encode("utf-8")[s["byte_start"] : s["byte_end"]].decode("utf-8")
        for s in spans
    ]
    assert slices == [
        "The trial enrolled 402 participants across eleven clinics.",
        "The primary endpoint improved by 18% under condition X.",
        "Follow-up at twelve months sustained the gain.",
    ]
    assert spans[0]["byte_start"] == 0
    prev_end = 0
    for s in spans:
        assert s["byte_start"] >= prev_end
        prev_end = s["byte_end"]


def test_offsets_are_utf8_bytes_not_characters() -> None:
    text = "Café résumé effecto occurred. Second sentence here."
    spans = candidate_spans(text)
    assert len(spans) == 2
    first = spans[0]
    raw = text.encode("utf-8")
    assert raw[first["byte_start"] : first["byte_end"]].decode("utf-8") == (
        "Café résumé effecto occurred."
    )
    # two accented chars make char-count < byte-count: offsets prove byte semantics
    assert first["byte_end"] > len("Café résumé effecto occurred.")


def test_candidate_spans_empty_or_whitespace_yields_no_candidates() -> None:
    assert candidate_spans("") == []
    assert candidate_spans("   \n  ") == []


def test_single_sentence_fragment_span_equals_trimmed_text() -> None:
    text = "Only one sentence exists."
    spans = candidate_spans(text)
    assert len(spans) == 1
    assert spans[0]["byte_start"] == 0
    assert spans[0]["byte_end"] == len(text.encode("utf-8"))


# --- classify_fragment span wiring ------------------------------------------


def test_in_set_span_choice_writes_byte_offsets() -> None:
    client = SpanClient(_answers("c2"))
    claim = classify_fragment(_fragment(), client=client)
    ev = claim["evidence"]
    cands = client.last_state["evidence_candidates"]
    chosen = next(c for c in cands if c["id"] == "c2")
    assert ev["byte_start"] == chosen["byte_start"]
    assert ev["byte_end"] == chosen["byte_end"]
    assert ev["fragment_id"] == "frag-span-1"


def test_span_never_wider_than_chosen_candidate() -> None:
    client = SpanClient(_answers("c1"))
    claim = classify_fragment(_fragment(), client=client)
    cands = {c["id"]: c for c in client.last_state["evidence_candidates"]}
    ev = claim["evidence"]
    assert (ev["byte_end"] - ev["byte_start"]) <= (
        cands["c1"]["byte_end"] - cands["c1"]["byte_start"]
    )
    # multi-sentence fragment: the emitted span must not cover the whole text
    assert ev["byte_end"] - ev["byte_start"] < len(TEXT.encode("utf-8"))


def test_unknown_leaves_span_unset_and_label_ok() -> None:
    client = SpanClient(_answers("unknown"))
    claim = classify_fragment(_fragment(), client=client)
    assert claim["label"] == "empirical_finding"
    assert "byte_start" not in claim["evidence"]
    assert "byte_end" not in claim["evidence"]


def test_out_of_set_span_answer_invents_nothing() -> None:
    client = SpanClient(_answers("c99"))
    claim = classify_fragment(_fragment(), client=client)
    assert claim["label"] == "empirical_finding"
    assert "byte_start" not in claim["evidence"]


def test_missing_span_answer_is_honest_unset() -> None:
    client = SpanClient(
        {"claim_kind": {"type": "choice", "choice": "empirical_finding"}}
    )
    claim = classify_fragment(_fragment(), client=client)
    assert claim["label"] == "empirical_finding"
    assert "byte_start" not in claim["evidence"]


def test_span_question_rides_the_same_call_with_static_criteria() -> None:
    client = SpanClient(_answers("c2"))
    classify_fragment(_fragment(), client=client)
    qs = client.last_questions
    assert set(qs.keys()) == {"claim_kind", "claim_kind_span"}
    span_q = qs["claim_kind_span"]
    assert span_q["type"] == "choice"
    cands = client.last_state["evidence_candidates"]
    assert {c["id"] for c in cands} | {"unknown"} == set(span_q["criteria"].keys())
    # criteria stay fragment-independent: no quoted span text inside them
    for cid, crit in span_q["criteria"].items():
        assert "enrolled 402 participants" not in crit
        if cid != "unknown":
            assert "candidate span with this id" in crit
    # evidence lives in state only
    assert all("byte_start" in c and "text" in c for c in cands)


def test_no_candidates_means_no_span_question() -> None:
    client = SpanClient(_answers("unknown"))
    claim = classify_fragment(_fragment(text="   "), client=client)
    assert set(client.last_questions.keys()) == {"claim_kind"}
    assert "byte_start" not in claim["evidence"]


def test_existing_fixture_still_classifies_with_span_flow() -> None:
    frag = load_fragment_fixture(FIX / "fragment_empirical_001.json")
    qid = frag["question_id"]
    answers = {qid: {"type": "choice", "choice": frag["closed_label_set"][0]}}
    client = SpanClient(answers)
    claim = classify_fragment(frag, client=client)
    assert claim["label"] in frag["closed_label_set"]
    assert "byte_start" not in claim["evidence"]


# --- metric end-to-end: tight span matches, spanless and wide do not --------


def _reference_graph(span: tuple[int, int], sentence: str) -> dict[str, Any]:
    graph = {
        "schema_version": "1.0.0",
        "graph_id": "refgraph:span-test-1",
        "papers": [
            {
                "paper_id": "paper:span-demo",
                "title": "Span Demo",
                "version": "v1",
                "doi": None,
                "url": None,
            }
        ],
        "sources": [
            {
                "source_id": "source:span-demo-1",
                "paper_id": "paper:span-demo",
                "version": "v1",
                "content_sha256": None,
            }
        ],
        "claims": [
            {
                "claim_id": "claim:span-demo-1",
                "text": "Condition X improved the primary endpoint.",
                "paper_id": "paper:span-demo",
                "source_id": "source:span-demo-1",
                "evidence": {
                    "quote": sentence,
                    "byte_start": span[0],
                    "byte_end": span[1],
                },
                "epistemic_status": "inferred",
                "valid_from": None,
                "valid_to": None,
                "recorded_at": "2026-09-27T00:00:00+00:00",
            }
        ],
    }
    return graph


def _sentence_of(text: str, span: Mapping[str, Any]) -> str:
    return text.encode("utf-8")[span["byte_start"] : span["byte_end"]].decode("utf-8")


def test_tight_span_matches_reference_and_spanless_does_not() -> None:
    c2 = candidate_spans(TEXT)[1]
    graph = _reference_graph(
        (c2["byte_start"], c2["byte_end"]), _sentence_of(TEXT, c2)
    )
    ref_claim = graph["claims"][0]

    client = SpanClient(_answers("c2"))
    claim = classify_fragment(_fragment(), client=client)
    # #88 owns top-level identity; added by hand here to isolate the span property.
    claim = dict(claim, paper_id="paper:span-demo", source_id="source:span-demo-1")
    assert match_claims([ref_claim], [claim]) != []

    client2 = SpanClient(_answers("unknown"))
    claim2 = classify_fragment(_fragment(), client=client2)
    claim2 = dict(claim2, paper_id="paper:span-demo", source_id="source:span-demo-1")
    assert match_claims([ref_claim], [claim2]) == []


def test_whole_fragment_span_still_fails_containment() -> None:
    # The metric docstring's trap: a whole-fragment span is "usable" but cannot
    # be contained in a sentence-level reference span.
    c2 = candidate_spans(TEXT)[1]
    graph = _reference_graph(
        (c2["byte_start"], c2["byte_end"]), _sentence_of(TEXT, c2)
    )
    ref_claim = graph["claims"][0]
    wide = {
        "label": "empirical_finding",
        "paper_id": "paper:span-demo",
        "source_id": "source:span-demo-1",
        "epistemic_status": "Inferred",
        "evidence": {
            "fragment_id": "f",
            "byte_start": 0,
            "byte_end": len(TEXT.encode("utf-8")),
        },
    }
    assert match_claims([ref_claim], [wide]) == []
