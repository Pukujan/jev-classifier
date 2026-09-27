"""Annotation tooling tests: span picking, building, agreement, P1--P6 (#90).

All sources here are synthetic. No network, no model calls, no real paper text,
and no restricted full text: the byte-offset defect this suite exists to catch
is reproducible on an invented string.
"""

from __future__ import annotations

import ast
import random
from pathlib import Path

import pytest

from jev_classifier.annotation import (
    AgreementError,
    AnnotationProtocolError,
    SpanError,
    agreement_from_claim_sets,
    agreement_from_reviews,
    build_claim,
    build_graph,
    build_paper,
    build_review,
    build_source,
    cohen_kappa,
    pick_span,
    validate_protocol,
)
from jev_classifier.reference import ReferenceSchemaError

REPO_ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_DIR = REPO_ROOT / "src" / "jev_classifier" / "annotation"

# A source that exercises one-, two-, and four-byte UTF-8 sequences.
MULTIBYTE_SOURCE = "Préface: 研究 shows 🙂 growth.\nSecond line follows here."


def _byte_span(source: str, char_start: int, char_end: int) -> tuple[int, int]:
    return (
        len(source[:char_start].encode("utf-8")),
        len(source[:char_end].encode("utf-8")),
    )


def _occurrence_ordinal(source: str, quote: str, char_index: int) -> int:
    """1-based occurrence number of the match starting at ``char_index``."""
    cursor = 0
    ordinal = 0
    while True:
        found = source.find(quote, cursor)
        if found < 0:
            raise AssertionError("quote occurrence not found")
        ordinal += 1
        if found == char_index:
            return ordinal
        cursor = found + 1


# --- span picking: byte offsets, not character indices ---


def test_multibyte_round_trip_returns_byte_offsets() -> None:
    # é (2 bytes), 研/究 (3 bytes each), 🙂 (4 bytes) all precede the quote, so a
    # character index would be smaller than the byte offset by 2+3+3+4+... and
    # silently mismatch the metric's reference span.
    quote = "研究 shows 🙂 growth"
    char_start = MULTIBYTE_SOURCE.index(quote)
    byte_start, byte_end = pick_span(MULTIBYTE_SOURCE, quote)

    assert (byte_start, byte_end) == _byte_span(
        MULTIBYTE_SOURCE, char_start, char_start + len(quote)
    )
    assert byte_start != char_start, "the quote must follow multi-byte characters"
    assert MULTIBYTE_SOURCE.encode("utf-8")[byte_start:byte_end].decode("utf-8") == quote


def test_ascii_prefix_has_equal_byte_and_character_offsets() -> None:
    # A control: where the defect cannot appear, byte and character agree.
    source = "alpha beta gamma"
    quote = "gamma"
    byte_start, byte_end = pick_span(source, quote)
    assert (byte_start, byte_end) == (source.index(quote), len(source))


def test_emoji_only_quote_round_trips() -> None:
    source = "flag 🙂 here"
    byte_start, byte_end = pick_span(source, "🙂")
    assert (byte_start, byte_end) == (5, 9)
    assert source.encode("utf-8")[byte_start:byte_end].decode("utf-8") == "🙂"


# --- metamorphic: a prefix shifts every offset by its byte length ---


def test_byte_prefix_shifts_offsets_by_exactly_n_bytes() -> None:
    quote = "growth"
    base_start, base_end = pick_span(MULTIBYTE_SOURCE, quote)
    for filler in ("X" * 7, "é" * 5, "研究" * 3, "🙂"):
        shift = len(filler.encode("utf-8"))
        prefixed = filler + MULTIBYTE_SOURCE
        start, end = pick_span(prefixed, quote)
        assert start == base_start + shift
        assert end == base_end + shift
        assert prefixed.encode("utf-8")[start:end].decode("utf-8") == quote


# --- metamorphic: line endings do not move a pre-newline quote ---


def test_line_endings_leave_a_pre_newline_quote_byte_identical() -> None:
    # The quote precedes every line break, so switching LF for CRLF elsewhere in
    # the source must not move it. This is the invariant the repo has broken
    # four times by writing text through a newline-translating API.
    lf = "Header line\nbody line one\nbody line two"
    crlf = lf.replace("\n", "\r\n")
    quote = "Header line"
    assert pick_span(lf, quote) == pick_span(crlf, quote)


def test_a_post_newline_quote_shifts_with_the_line_ending() -> None:
    # The honest boundary of the invariant above: offsets are over the exact
    # bytes supplied, so a source's line-ending normalization is part of the
    # contract. A CRLF source must be annotated as CRLF.
    lf = "Header line\nbody line one"
    crlf = lf.replace("\n", "\r\n")
    lf_span = pick_span(lf, "body line one")
    crlf_span = pick_span(crlf, "body line one")
    assert crlf_span[0] - lf_span[0] == 1


# --- differential: containment is what the metric scores on ---


def test_whole_source_span_strictly_contains_a_tight_quote_span() -> None:
    tight_start, tight_end = pick_span(MULTIBYTE_SOURCE, "研究 shows")
    whole_start, whole_end = pick_span(MULTIBYTE_SOURCE, MULTIBYTE_SOURCE)
    total = len(MULTIBYTE_SOURCE.encode("utf-8"))

    assert (whole_start, whole_end) == (0, total)
    assert whole_start <= tight_start
    assert tight_end <= whole_end
    assert tight_end - tight_start < whole_end - whole_start


# --- ambiguity: never guess an occurrence ---


def test_a_quote_appearing_once_returns_its_offsets() -> None:
    source = "one unique phrase here"
    assert pick_span(source, "unique phrase") == (4, 17)


def test_a_quote_appearing_twice_raises_as_ambiguous() -> None:
    source = "repeat me, then repeat me again"
    with pytest.raises(SpanError, match="appears 2 times") as excinfo:
        pick_span(source, "repeat me")
    assert excinfo.value.kind == "ambiguous_match"


def test_an_absent_quote_raises() -> None:
    with pytest.raises(SpanError, match="does not appear") as excinfo:
        pick_span("a short source", "absent phrase")
    assert excinfo.value.kind == "not_found"


def test_occurrence_disambiguates_a_repeated_quote() -> None:
    source = "repeat me, then repeat me again"
    first = pick_span(source, "repeat me", occurrence=1)
    second = pick_span(source, "repeat me", occurrence=2)
    assert first == (0, 9)
    assert second == (16, 25)
    assert second[0] > first[0]


def test_occurrence_out_of_range_raises() -> None:
    with pytest.raises(SpanError, match="appears 1 time") as excinfo:
        pick_span("only once here", "once", occurrence=3)
    assert excinfo.value.kind == "occurrence_out_of_range"


def test_empty_quote_raises() -> None:
    with pytest.raises(SpanError, match="non-empty") as excinfo:
        pick_span("some source", "")
    assert excinfo.value.kind == "empty_quote"


# --- seeded randomized property test ---

_ALPHABET = ("a", "b", "c", " ", "x", "y", "z", "é", "字", "🙂", "\n", ",", "-")


def test_seeded_random_sources_round_trip() -> None:
    rng = random.Random(1234)
    successes = 0
    ambiguous = 0
    for _ in range(400):
        length = rng.randint(1, 80)
        source = "".join(rng.choice(_ALPHABET) for _ in range(length))
        char_start = rng.randrange(length)
        char_end = rng.randint(char_start + 1, length)
        quote = source[char_start:char_end]
        expected = _byte_span(source, char_start, char_end)

        try:
            start, end = pick_span(source, quote)
        except SpanError as exc:
            assert exc.kind == "ambiguous_match"
            ambiguous += 1
            ordinal = _occurrence_ordinal(source, quote, char_start)
            assert pick_span(source, quote, occurrence=ordinal) == expected
            continue

        successes += 1
        assert (start, end) == expected
        assert source.encode("utf-8")[start:end].decode("utf-8") == quote

    assert successes > 0
    assert successes + ambiguous == 400


# --- building a graph ---


def _built_graph() -> tuple[dict, dict[str, str]]:
    source_text = (
        "The trial measured an effect. "
        "The effect is consistent with a driver. "
        "Nothing else follows."
    )
    claim_a = build_claim(
        claim_id="claim:a",
        text="The trial measured an effect.",
        paper_id="paper:x",
        source_id="source:x",
        source_text=source_text,
        quote="The trial measured an effect.",
        epistemic_status="observed",
        recorded_at="2026-09-26T00:00:00+00:00",
    )
    claim_b = build_claim(
        claim_id="claim:b",
        text="The effect is consistent with a driver.",
        paper_id="paper:x",
        source_id="source:x",
        source_text=source_text,
        quote="consistent with a driver",
        epistemic_status="inferred",
        recorded_at="2026-09-26T00:00:00+00:00",
    )
    graph = build_graph(
        graph_id="graph:synthetic",
        papers=[build_paper(paper_id="paper:x", title="Synthetic", version="v1")],
        sources=[build_source(source_id="source:x", paper_id="paper:x", version="v1")],
        claims=[claim_a, claim_b],
        reviews=[
            build_review(
                review_id="review:a",
                claim_id="claim:b",
                annotator_id="annotator:alpha",
                decision="uncertain",
                recorded_at="2026-09-26T01:00:00+00:00",
            ),
            build_review(
                review_id="review:b",
                claim_id="claim:b",
                annotator_id="annotator:beta",
                decision="revise",
                recorded_at="2026-09-26T02:00:00+00:00",
            ),
        ],
    )
    return graph, {"source:x": source_text}


def test_build_claim_derives_offsets_from_text_and_quote() -> None:
    source_text = "Préface: 研究 shows 🙂 growth."
    quote = "研究 shows"
    claim = build_claim(
        claim_id="claim:1",
        text="A claim.",
        paper_id="paper:x",
        source_id="source:x",
        source_text=source_text,
        quote=quote,
        epistemic_status="observed",
        recorded_at="2026-09-26T00:00:00+00:00",
    )
    assert claim["evidence"]["byte_start"] == len("Préface: ".encode("utf-8"))
    assert claim["evidence"]["byte_end"] == claim["evidence"]["byte_start"] + len(
        quote.encode("utf-8")
    )


def test_build_graph_returns_a_validated_graph() -> None:
    graph, _ = _built_graph()
    assert graph["schema_version"] == "1.0.0"
    assert [c["claim_id"] for c in graph["claims"]] == ["claim:a", "claim:b"]


def test_build_graph_propagates_schema_errors_unchanged() -> None:
    claim = build_claim(
        claim_id="claim:a",
        text="A claim.",
        paper_id="paper:x",
        source_id="source:missing",
        source_text="some source text",
        quote="some source",
        epistemic_status="observed",
        recorded_at="2026-09-26T00:00:00+00:00",
    )
    with pytest.raises(ReferenceSchemaError) as excinfo:
        build_graph(
            graph_id="graph:bad",
            papers=[build_paper(paper_id="paper:x", title="Synthetic", version="v1")],
            sources=[build_source(source_id="source:x", paper_id="paper:x", version="v1")],
            claims=[claim],
        )
    assert excinfo.value.kind == "schema_error"


# --- P1--P6 ---


def _protocol_graph(claims, *, reviews=(), source_texts=None):
    return (
        {
            "schema_version": "1.0.0",
            "graph_id": "graph:synthetic",
            "papers": [{"paper_id": "paper:x", "title": "Synthetic", "version": "v1"}],
            "sources": [{"source_id": "source:x", "paper_id": "paper:x", "version": "v1"}],
            "claims": list(claims),
            "relationships": [],
            "reviews": list(reviews),
        },
        source_texts,
    )


def _claim_record(
    claim_id,
    source_text,
    quote,
    *,
    text=None,
    status="observed",
    valid_from=None,
    valid_to=None,
    occurrence=None,
):
    start, end = pick_span(source_text, quote, occurrence=occurrence)
    return {
        "claim_id": claim_id,
        "text": text if text is not None else quote,
        "paper_id": "paper:x",
        "source_id": "source:x",
        "evidence": {"quote": quote, "byte_start": start, "byte_end": end},
        "epistemic_status": status,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "recorded_at": "2026-09-26T00:00:00+00:00",
    }


def test_valid_graph_passes_all_six_properties() -> None:
    graph, source_texts = _built_graph()
    assert validate_protocol(graph, source_texts=source_texts) == []


def test_p1_identical_text_in_a_containing_span_raises() -> None:
    source = "abcdefghij"
    claims = [
        _claim_record("claim:outer", source, "cdefgh", text="shared assertion"),
        _claim_record("claim:inner", source, "defg", text="shared assertion"),
    ]
    graph, texts = _protocol_graph(claims)
    with pytest.raises(AnnotationProtocolError, match="strictly") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "containment"


def test_p1_a_containing_span_with_different_text_is_allowed() -> None:
    # A broader claim legitimately contains a narrower one; only the same text
    # on a strictly larger span is a merge candidate.
    source = "abcdefghij"
    claims = [
        _claim_record("claim:outer", source, "cdefgh", text="broad claim"),
        _claim_record("claim:inner", source, "defg", text="narrow claim"),
    ]
    graph, texts = _protocol_graph(claims, source_texts={"source:x": source})
    assert validate_protocol(graph, source_texts=texts) == []


def test_p2_coordinated_assertions_are_a_warning_not_a_raise() -> None:
    source = "The trial measured an effect, and the authors inferred a driver."
    claims = [_claim_record("claim:1", source, source, status="inferred")]
    graph, texts = _protocol_graph(claims)
    findings = validate_protocol(graph, source_texts=texts)
    atomicity = [f for f in findings if f.property_id == "P2"]
    assert len(atomicity) == 1
    assert atomicity[0].kind == "atomicity"
    assert atomicity[0].level == "warning"
    assert atomicity[0].claim_id == "claim:1"


def test_p2_does_not_flag_a_short_list() -> None:
    source = "salt, and pepper were added."
    claims = [_claim_record("claim:1", source, source)]
    graph, texts = _protocol_graph(claims)
    assert [f for f in validate_protocol(graph, source_texts=texts) if f.property_id == "P2"] == []


def test_p3_verbatim_mismatch_raises() -> None:
    source = "the real annotated source text"
    claim = _claim_record("claim:1", source, "real annotated")
    graph, _ = _protocol_graph([claim])
    with pytest.raises(AnnotationProtocolError, match="not verbatim") as excinfo:
        validate_protocol(graph, source_texts={"source:x": "the REAL annotated source text"})
    assert excinfo.value.kind == "not_verbatim"


def test_p3_missing_source_text_records_a_skip() -> None:
    source = "the real annotated source text"
    graph, _ = _protocol_graph([_claim_record("claim:1", source, "real annotated")])
    findings = validate_protocol(graph, source_texts=None)
    skips = [f for f in findings if f.property_id == "P3"]
    assert len(skips) == 1
    assert skips[0].kind == "source_not_supplied"
    assert skips[0].level == "skipped"


def test_p4_inverted_valid_time_raises() -> None:
    source = "a synthetic claim span"
    claim = _claim_record(
        "claim:1", source, source, valid_from="2026-05-01", valid_to="2026-01-01"
    )
    graph, texts = _protocol_graph([claim])
    with pytest.raises(AnnotationProtocolError, match="after valid_to") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "bitemporal"


def test_p4_missing_bitemporal_field_raises() -> None:
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source)
    del claim["valid_to"]
    graph, texts = _protocol_graph([claim])
    with pytest.raises(AnnotationProtocolError, match="valid_to") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "bitemporal"


def test_p5_unknown_epistemic_status_raises() -> None:
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source, status="believed")
    graph, texts = _protocol_graph([claim])
    with pytest.raises(AnnotationProtocolError, match="believed") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "unknown_status"


def test_p5_vocabulary_comes_from_module_r() -> None:
    from jev_classifier.reference.validate import EPISTEMIC_STATUSES

    source = "a synthetic claim span"
    for status in sorted(EPISTEMIC_STATUSES):
        claim = _claim_record("claim:1", source, source, status=status)
        graph, texts = _protocol_graph([claim])
        validate_protocol(graph, source_texts=texts)


def test_p6_unlinked_duplicate_review_raises() -> None:
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source)
    reviews = [
        {
            "review_id": "review:1",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "accept",
            "recorded_at": "2026-09-26T01:00:00+00:00",
            "supersedes_review_id": None,
        },
        {
            "review_id": "review:2",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "reject",
            "recorded_at": "2026-09-26T02:00:00+00:00",
            "supersedes_review_id": None,
        },
    ]
    graph, texts = _protocol_graph([claim], reviews=reviews)
    with pytest.raises(AnnotationProtocolError, match="single supersession chain") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "disagreement_lost"


def test_p6_a_three_link_supersession_chain_is_preserved() -> None:
    # A chain of replacements is not a duplicate: every decision stays, and the
    # newest one is unambiguous.
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source)
    reviews = [
        {
            "review_id": f"review:{n}",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": decision,
            "recorded_at": f"2026-09-26T0{n}:00:00+00:00",
            "supersedes_review_id": f"review:{n - 1}" if n > 1 else None,
        }
        for n, decision in ((1, "accept"), (2, "revise"), (3, "reject"))
    ]
    graph, texts = _protocol_graph(
        [claim], reviews=reviews, source_texts={"source:x": source}
    )
    assert validate_protocol(graph, source_texts=texts) == []


def test_p6_linked_supersession_is_preserved() -> None:
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source)
    reviews = [
        {
            "review_id": "review:1",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "accept",
            "recorded_at": "2026-09-26T01:00:00+00:00",
            "supersedes_review_id": None,
        },
        {
            "review_id": "review:2",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "reject",
            "recorded_at": "2026-09-26T02:00:00+00:00",
            "supersedes_review_id": "review:1",
        },
    ]
    graph, texts = _protocol_graph(
        [claim], reviews=reviews, source_texts={"source:x": source}
    )
    assert validate_protocol(graph, source_texts=texts) == []


def test_p6_dangling_supersession_raises() -> None:
    source = "a synthetic claim span"
    claim = _claim_record("claim:1", source, source)
    reviews = [
        {
            "review_id": "review:1",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "accept",
            "recorded_at": "2026-09-26T01:00:00+00:00",
            "supersedes_review_id": "review:missing",
        }
    ]
    graph, texts = _protocol_graph([claim], reviews=reviews)
    with pytest.raises(AnnotationProtocolError, match="missing") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "disagreement_lost"


def test_p6_supersession_cycle_raises() -> None:
    source = "a synthetic claim span"
    claims = [
        _claim_record("claim:1", source, source),
        _claim_record("claim:2", source, "synthetic claim", text="second"),
    ]
    reviews = [
        {
            "review_id": "review:1",
            "claim_id": "claim:1",
            "annotator_id": "annotator:alpha",
            "decision": "accept",
            "recorded_at": "2026-09-26T01:00:00+00:00",
            "supersedes_review_id": "review:2",
        },
        {
            "review_id": "review:2",
            "claim_id": "claim:2",
            "annotator_id": "annotator:beta",
            "decision": "reject",
            "recorded_at": "2026-09-26T02:00:00+00:00",
            "supersedes_review_id": "review:1",
        },
    ]
    graph, texts = _protocol_graph(claims, reviews=reviews)
    with pytest.raises(AnnotationProtocolError, match="cycles") as excinfo:
        validate_protocol(graph, source_texts=texts)
    assert excinfo.value.kind == "disagreement_lost"


# --- inter-annotator agreement ---


def test_kappa_matches_a_hand_computed_case() -> None:
    # p_o = 0.5; both marginals are 2/2, so p_e = 0.5 and kappa = 0.0.
    result = cohen_kappa(
        [
            ("observed", "observed"),
            ("inferred", "inferred"),
            ("observed", "inferred"),
            ("inferred", "observed"),
        ]
    )
    assert result.n_items == 4
    assert result.agreements == 2
    assert result.observed_agreement == 0.5
    assert result.expected_agreement == 0.5
    assert result.kappa == 0.0
    assert result.counts_a == {"inferred": 2, "observed": 2}
    assert result.agreement_matrix[("observed", "inferred")] == 1


def test_kappa_is_one_for_perfect_agreement_with_variation() -> None:
    result = cohen_kappa([("a", "a"), ("b", "b")])
    assert result.observed_agreement == 1.0
    assert result.expected_agreement == 0.5
    assert result.kappa == 1.0
    assert result.degenerate is False


def test_kappa_is_negative_below_chance() -> None:
    result = cohen_kappa([("a", "b"), ("b", "a")])
    assert result.observed_agreement == 0.0
    assert result.expected_agreement == 0.5
    assert result.kappa == -1.0


def test_kappa_degenerate_single_category_returns_one_and_flags_it() -> None:
    result = cohen_kappa([("observed", "observed"), ("observed", "observed")])
    assert result.expected_agreement == 1.0
    assert result.kappa == 1.0
    assert result.degenerate is True
    assert "undefined" in result.note


def test_kappa_over_zero_items_raises() -> None:
    with pytest.raises(AgreementError, match="zero") as excinfo:
        cohen_kappa([])
    assert excinfo.value.kind == "no_items"


def test_agreement_from_reviews_pairs_only_shared_claims() -> None:
    reviews = [
        {"claim_id": "c1", "annotator_id": "a", "decision": "accept"},
        {"claim_id": "c2", "annotator_id": "a", "decision": "reject"},
        {"claim_id": "c1", "annotator_id": "b", "decision": "accept"},
        {"claim_id": "c3", "annotator_id": "b", "decision": "revise"},
    ]
    report = agreement_from_reviews(reviews, annotator_a="a", annotator_b="b")
    assert report.paired_item_ids == ("c1",)
    assert report.only_a == ("c2",)
    assert report.only_b == ("c3",)
    assert report.result.agreements == 1


def test_agreement_from_reviews_refuses_conflicting_duplicates() -> None:
    reviews = [
        {"claim_id": "c1", "annotator_id": "a", "decision": "accept"},
        {"claim_id": "c1", "annotator_id": "a", "decision": "reject"},
        {"claim_id": "c1", "annotator_id": "b", "decision": "accept"},
    ]
    with pytest.raises(AgreementError, match="conflicting") as excinfo:
        agreement_from_reviews(reviews, annotator_a="a", annotator_b="b")
    assert excinfo.value.kind == "duplicate_review"


def test_agreement_from_claim_sets_pairs_by_span_and_status() -> None:
    def claim(source_id, start, end, status):
        return {
            "source_id": source_id,
            "evidence": {"quote": "q", "byte_start": start, "byte_end": end},
            "epistemic_status": status,
        }

    left = [claim("s1", 0, 10, "observed"), claim("s1", 20, 30, "inferred")]
    right = [claim("s1", 0, 10, "observed"), claim("s1", 20, 30, "observed")]
    report = agreement_from_claim_sets(left, right, annotator_a="a", annotator_b="b")
    assert report.result.n_items == 2
    assert report.result.agreements == 1
    assert report.only_a == ()
    assert report.only_b == ()


# --- offline guard ---


def test_annotation_package_imports_nothing_networked() -> None:
    allowed_roots = {"__future__", "re", "dataclasses", "datetime", "typing", "jev_classifier"}
    denied_tokens = (
        "httpx",
        "requests",
        "urllib",
        "socket",
        "aiohttp",
        "openrouter",
        "DecisionsClient",
        "http.client",
    )
    files = sorted(ANNOTATION_DIR.glob("*.py"))
    assert files, "annotation package must contain modules"
    for path in files:
        source = path.read_text(encoding="utf-8")
        for token in denied_tokens:
            assert token not in source, f"{path.name} must stay offline; found {token!r}"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            unexpected = roots - allowed_roots
            assert not unexpected, f"{path.name} imports {sorted(unexpected)}"
