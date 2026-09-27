"""Offline tests for cross-source claim consolidation (#69) + paper synthesis.

Everything is pure and deterministic: hand-built validated claim records, a
fixed evaluation instant, no model, no network. The fail-closed paths are the
point of the module, so most cases are rejections.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from jev_classifier.consolidate import (  # noqa: E402
    ConsolidationError,
    consolidate_claims,
    topic_digest,
)
from jev_classifier.paper.assemble import AssembleError, assemble_paper  # noqa: E402

AT = "2026-09-15T00:00:00+00:00"


def claim(cid: str, label: str, source: str, *, subject: str = "study-alpha",
          **over: Any) -> dict[str, Any]:
    base = {
        "id": cid,
        "label": label,
        "epistemic_status": "Inferred",
        "recorded_at": "2026-09-01T00:00:00+00:00",
        "evidence": {"fragment_id": f"frag-{cid}", "source_id": source},
        "model": "typesafe/jev-1.13",
        "about": subject,
        "valid_from": None,
        "valid_to": None,
        "supersedes": None,
    }
    base.update(over)
    return base


def by_state(topics: list[dict]) -> dict[str, str]:
    return {t["about"]: t["state"] for t in topics}


class TestAgreement:
    def test_two_sources_same_label_agree(self):
        topics = consolidate_claims(
            [claim("c1", "empirical_finding", "src-a"),
             claim("c2", "empirical_finding", "src-b")], at=AT)
        assert len(topics) == 1
        assert topics[0]["state"] == "agreement"
        assert topics[0]["distinct_sources"] == ["src-a", "src-b"]

    def test_same_source_twice_is_not_corroboration(self):
        topics = consolidate_claims(
            [claim("c1", "empirical_finding", "src-a"),
             claim("c2", "empirical_finding", "src-a")], at=AT)
        assert topics[0]["state"] == "single-source"
        assert topics[0]["distinct_sources"] == ["src-a"]

    def test_topics_grouped_by_about_not_by_wording(self):
        topics = consolidate_claims(
            [claim("c1", "empirical_finding", "src-a", subject="alpha"),
             claim("c2", "empirical_finding", "src-b", subject="beta")], at=AT)
        assert [t["about"] for t in topics] == ["alpha", "beta"]
        assert all(t["state"] == "single-source" for t in topics)


class TestConflict:
    def test_differing_labels_conflict_and_keep_both(self):
        a = claim("c1", "empirical_finding", "src-a")
        b = claim("c2", "method_claim", "src-b")
        topics = consolidate_claims([a, b], at=AT)
        assert topics[0]["state"] == "conflict"
        assert topics[0]["labels"] == ["empirical_finding", "method_claim"]
        # disagreement is preserved: both sides stay listed as current
        assert {c["id"] for c in topics[0]["current"]} == {"c1", "c2"}

    def test_conflict_is_not_resolved_by_majority(self):
        topics = consolidate_claims(
            [claim("c1", "empirical_finding", "src-a"),
             claim("c2", "empirical_finding", "src-b"),
             claim("c3", "opinion", "src-c")], at=AT)
        assert topics[0]["state"] == "conflict", "2-vs-1 stays a conflict"


class TestBitemporal:
    def test_expired_claim_retires_and_leaves_sole_survivor(self):
        old = claim("c1", "empirical_finding", "src-a", valid_to="2026-09-01T00:00:00+00:00")
        fresh = claim("c2", "empirical_finding", "src-b")
        topics = consolidate_claims([old, fresh], at=AT)
        assert topics[0]["state"] == "single-source"
        assert [c["id"] for c in topics[0]["current"]] == ["c2"]
        assert [c["id"] for c in topics[0]["retired"]] == ["c1"]

    def test_not_yet_valid_is_retired(self):
        future = claim("c1", "empirical_finding", "src-a",
                       valid_from="2026-10-01T00:00:00+00:00")
        topics = consolidate_claims([future], at=AT)
        assert topics[0]["state"] == "unknown"
        assert topics[0]["current"] == []

    def test_superseded_claim_retired_even_when_still_valid(self):
        prior = claim("c1", "empirical_finding", "src-a")
        rev = claim("c2", "empirical_finding", "src-b", supersedes="c1")
        topics = consolidate_claims([prior, rev], at=AT)
        assert [c["id"] for c in topics[0]["current"]] == ["c2"]
        assert [c["id"] for c in topics[0]["retired"]] == ["c1"]

    def test_chain_supersedes_two_levels(self):
        a = claim("c1", "opinion", "src-a")
        b = claim("c2", "empirical_finding", "src-b", supersedes="c1")
        c = claim("c3", "empirical_finding", "src-c", supersedes="c2")
        topics = consolidate_claims([a, b, c], at=AT)
        assert topics[0]["state"] == "single-source"
        assert [x["id"] for x in topics[0]["current"]] == ["c3"]
        assert {x["id"] for x in topics[0]["retired"]} == {"c1", "c2"}

    def test_explicit_instant_makes_output_reproducible(self):
        a = claim("c1", "empirical_finding", "src-a",
                  valid_to="2026-09-10T00:00:00+00:00")
        at_before = consolidate_claims([a], at="2026-09-05T00:00:00+00:00")
        at_after = consolidate_claims([a], at=AT)
        assert at_before[0]["state"] == "single-source"
        assert at_after[0]["state"] == "unknown"

    def test_same_input_same_output(self):
        claims = [claim("c1", "empirical_finding", "src-a"),
                  claim("c2", "method_claim", "src-b")]
        assert consolidate_claims(claims, at=AT) == consolidate_claims(claims, at=AT)


class TestFailClosed:
    def test_missing_about_rejected(self):
        bad = claim("c1", "empirical_finding", "src-a")
        del bad["about"]
        with pytest.raises(ConsolidationError, match="about"):
            consolidate_claims([bad], at=AT)

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ConsolidationError, match="duplicate claim ids"):
            consolidate_claims([claim("c1", "opinion", "src-a"),
                                claim("c1", "method_claim", "src-b")], at=AT)

    def test_dangling_supersedes_rejected(self):
        rev = claim("c2", "opinion", "src-b", supersedes="ghost")
        with pytest.raises(ConsolidationError, match="unknown claim"):
            consolidate_claims([rev], at=AT)

    def test_cyclic_supersession_rejected(self):
        a = claim("c1", "opinion", "src-a", supersedes="c2")
        b = claim("c2", "opinion", "src-b", supersedes="c1")
        with pytest.raises(ConsolidationError, match="cyclic"):
            consolidate_claims([a, b], at=AT)

    def test_inverted_time_range_rejected(self):
        bad = claim("c1", "opinion", "src-a",
                    valid_from="2026-09-20T00:00:00+00:00",
                    valid_to="2026-09-10T00:00:00+00:00")
        with pytest.raises(ConsolidationError, match="is after"):
            consolidate_claims([bad], at=AT)

    def test_naive_timestamp_rejected(self):
        bad = claim("c1", "opinion", "src-a", valid_from="2026-09-01T00:00:00")
        with pytest.raises(ConsolidationError, match="timezone"):
            consolidate_claims([bad], at=AT)

    def test_mixed_naive_and_aware_rejected(self):
        a = claim("c1", "opinion", "src-a")
        b = claim("c2", "opinion", "src-b", recorded_at="2026-09-01T00:00:00")
        with pytest.raises(ConsolidationError, match="naive"):
            consolidate_claims([a, b], at=AT)

    def test_unparseable_at_rejected(self):
        with pytest.raises(ConsolidationError):
            consolidate_claims([claim("c1", "opinion", "src-a")], at="yesterday")

    def test_all_anonymous_batch_rejected(self):
        a, b = claim("c1", "opinion", "src-a"), claim("c2", "opinion", "src-b")
        for c in (a, b):
            del c["id"]
        with pytest.raises(ConsolidationError, match="missing id"):
            consolidate_claims([a, b], at=AT)

    def test_empty_run_is_empty_list(self):
        assert consolidate_claims([], at=AT) == []


class TestDigest:
    def test_each_state_has_an_honest_line(self):
        agree = consolidate_claims([claim("c1", "empirical_finding", "src-a"),
                                    claim("c2", "empirical_finding", "src-b")], at=AT)
        conflict = consolidate_claims([claim("c1", "opinion", "src-a"),
                                       claim("c2", "method_claim", "src-b")], at=AT)
        assert "corroborated (empirical_finding) by 2 sources" in topic_digest(agree[0])
        text = topic_digest(conflict[0])
        assert text.startswith("disputed (method_claim vs opinion)")
        assert "as of" in text

    def test_unknown_state_names_retired(self):
        topics = consolidate_claims(
            [claim("c1", "opinion", "src-a", valid_to="2026-01-01T00:00:00+00:00")], at=AT)
        assert topic_digest(topics[0]).startswith("no currently-valid claim")
        assert "retired: 1" in topic_digest(topics[0])


class TestPaperIntegration:
    def test_synthesis_section_renders_between_abstract_and_claims(self):
        a = claim("c1", "empirical_finding", "src-a")
        b = claim("c2", "empirical_finding", "src-b")
        topics = consolidate_claims([a, b], at=AT)
        paper = assemble_paper([a, b], topics=topics, assembled_at="2026-09-20T00:00:00+00:00")
        assert "## Synthesis" in paper
        assert "study-alpha" in paper and "corroborated" in paper
        # ordering: Abstract -> Synthesis -> Claims
        assert (paper.index("## Abstract") < paper.index("## Synthesis")
                < paper.index("## Claims"))
        # evidence still cited (existing invariant holds)
        assert "`frag-c1`" in paper and "`frag-c2`" in paper

    def test_without_topics_output_unchanged_shape(self):
        a = claim("c1", "opinion", "src-a")
        plain = assemble_paper([a], assembled_at="2026-09-20T00:00:00+00:00")
        assert "## Synthesis" not in plain
        for section in ("Title", "Abstract", "Claims", "Provenance", "Lineage",
                        "Citations"):
            assert (f"## {section}" in plain) or (section == "Title")

    def test_malformed_topic_fails_closed(self):
        a = claim("c1", "opinion", "src-a")
        bad = [{"about": "x", "state": "consensus", "labels": [], "evaluated_at": AT,
                "current": [], "retired": []}]
        with pytest.raises(AssembleError, match="state"):
            assemble_paper([a], topics=bad)

    def test_topic_missing_keys_fails_closed(self):
        a = claim("c1", "opinion", "src-a")
        with pytest.raises(AssembleError, match="missing key"):
            assemble_paper([a], topics=[{"about": "x"}])

    def test_conflict_survives_into_the_paper(self):
        a = claim("c1", "empirical_finding", "src-a")
        b = claim("c2", "method_claim", "src-b")
        topics = consolidate_claims([a, b], at=AT)
        paper = assemble_paper([a, b], topics=topics,
                               assembled_at="2026-09-20T00:00:00+00:00")
        assert "disputed" in paper
        # both contradictory claims remain visible in the Claims section
        assert "c1" in paper.split("## Claims")[1] and "c2" in paper.split("## Claims")[1]

    def test_topics_must_be_a_sequence_of_objects(self):
        a = claim("c1", "opinion", "src-a")
        with pytest.raises(AssembleError):
            assemble_paper([a], topics="not-a-list")
        with pytest.raises(AssembleError):
            assemble_paper([a], topics=[42])
