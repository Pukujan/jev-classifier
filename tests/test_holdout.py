"""Holdout split custody boundary tests (#81).

The module under test is the guard that keeps held-out papers out of the
development path. These tests use synthetic paper ids throughout: embedding the
real assignment, or the real ids of the held-out papers, would make the fixture
the leak it exists to prevent (docs/HOLDOUT_PROTOCOL.md section 7).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jev_classifier.holdout import (
    ASSIGNMENT_ENV_VAR,
    DEVELOPMENT_SPLIT,
    HOLDOUT_SPLIT,
    MINIMUM_HOLDOUT_FRACTION,
    MINIMUM_HOLDOUT_PAPERS,
    SPLIT_SCHEMA_VERSION,
    HoldoutError,
    SplitAssignment,
    assert_development_safe,
    assert_whole_paper,
    canonical_form,
    commitment_tag,
    load_assignment,
    load_configured_assignment,
    split_of,
    validate_assignment,
    verify_commitment,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
EVAL_SCRIPT = REPO_ROOT / "scripts" / "eval_claims.py"

SALT = b"synthetic-salt-not-the-real-one"

# Ten synthetic papers, the same corpus size as the real selection.
CORPUS = tuple(f"paper-{n:02d}" for n in range(1, 11))
DEV_IDS = CORPUS[:8]
HOLDOUT_IDS = CORPUS[8:]


def _body(**overrides) -> dict:
    body = {
        "split_version": SPLIT_SCHEMA_VERSION,
        "frozen_at": "2026-09-27T00:00:00Z",
        "custodian": "synthetic-custodian",
        "inputs": {
            "papers": "datasets/reference_papers.json@v1",
            "annotation_schema": "reference_claim_graph@v1",
        },
        "dev_paper_ids": list(DEV_IDS),
        "holdout_paper_ids": list(HOLDOUT_IDS),
    }
    body.update(overrides)
    return body


def _assignment(**overrides) -> SplitAssignment:
    return SplitAssignment(
        split_version=overrides.get("split_version", SPLIT_SCHEMA_VERSION),
        frozen_at=overrides.get("frozen_at", "2026-09-27T00:00:00Z"),
        custodian=overrides.get("custodian", "synthetic-custodian"),
        inputs=overrides.get(
            "inputs",
            {
                "papers": "datasets/reference_papers.json@v1",
                "annotation_schema": "reference_claim_graph@v1",
            },
        ),
        dev_paper_ids=tuple(overrides.get("dev_paper_ids", DEV_IDS)),
        holdout_paper_ids=tuple(overrides.get("holdout_paper_ids", HOLDOUT_IDS)),
    )


def _write(tmp_path: Path, body: object) -> Path:
    target = tmp_path / "assignment.json"
    target.write_text(json.dumps(body), encoding="utf-8")
    return target


# --- constants ---


def test_policy_constants_match_the_accepted_parent_threshold() -> None:
    # Parent #21: at least 20% and at least two papers held out.
    assert MINIMUM_HOLDOUT_FRACTION == 0.20
    assert MINIMUM_HOLDOUT_PAPERS == 2


def test_split_names_are_stable() -> None:
    assert DEVELOPMENT_SPLIT == "development"
    assert HOLDOUT_SPLIT == "holdout"


# --- the accepted split is valid ---


def test_ten_paper_split_with_two_held_out_is_valid() -> None:
    validate_assignment(_assignment())


def test_assignment_mapping_is_accepted_and_parsed() -> None:
    validate_assignment(_body())


def test_exactly_covering_the_corpus_is_valid() -> None:
    validate_assignment(_assignment(), corpus_ids=CORPUS)


# --- shape: fail closed ---


def test_unknown_key_fails_closed() -> None:
    body = _body()
    body["note"] = "x"
    with pytest.raises(HoldoutError, match="unknown key") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "schema_error"


def test_missing_required_key_fails_closed() -> None:
    body = _body()
    del body["custodian"]
    with pytest.raises(HoldoutError, match="custodian") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "schema_error"


def test_bad_paper_id_fails_closed() -> None:
    body = _body(dev_paper_ids=["Paper One", *DEV_IDS[1:]])
    with pytest.raises(HoldoutError, match="paper id") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "schema_error"


def test_non_string_input_value_fails_closed() -> None:
    body = _body(inputs={"papers": 7})
    with pytest.raises(HoldoutError, match="inputs") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "schema_error"


# --- split invariants ---


def test_overlapping_sides_fail_closed() -> None:
    body = _body(holdout_paper_ids=[DEV_IDS[0], HOLDOUT_IDS[0]])
    with pytest.raises(HoldoutError, match="overlap") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_repeated_paper_id_fails_closed() -> None:
    body = _body(dev_paper_ids=[DEV_IDS[0], DEV_IDS[0], *DEV_IDS[1:]])
    with pytest.raises(HoldoutError, match="repeats") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_empty_holdout_fails_closed() -> None:
    body = _body(holdout_paper_ids=[])
    with pytest.raises(HoldoutError, match="non-empty") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_empty_development_fails_closed() -> None:
    body = _body(dev_paper_ids=[])
    with pytest.raises(HoldoutError, match="non-empty") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_one_holdout_paper_is_below_the_minimum() -> None:
    body = _body(dev_paper_ids=[*DEV_IDS, HOLDOUT_IDS[0]], holdout_paper_ids=[HOLDOUT_IDS[1]])
    with pytest.raises(HoldoutError, match="minimum") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_holdout_fraction_below_the_floor_fails_closed() -> None:
    # 9 development + 1 holdout is 10%, below the 20% floor; this also trips the
    # two-paper minimum, so assert on the fraction directly with a larger corpus.
    dev = tuple(f"paper-{n:03d}" for n in range(1, 30))
    body = _body(dev_paper_ids=list(dev), holdout_paper_ids=["paper-030"])
    with pytest.raises(HoldoutError, match="fraction|minimum") as excinfo:
        validate_assignment(body)
    assert excinfo.value.kind == "invalid_split"


def test_corpus_coverage_gap_fails_closed() -> None:
    with pytest.raises(HoldoutError, match="does not cover") as excinfo:
        validate_assignment(_assignment(), corpus_ids=(*CORPUS, "paper-11"))
    assert excinfo.value.kind == "invalid_split"


def test_corpus_with_an_unrecognized_paper_fails_closed() -> None:
    with pytest.raises(HoldoutError, match="does not cover") as excinfo:
        validate_assignment(_assignment(), corpus_ids=CORPUS[:9])
    assert excinfo.value.kind == "invalid_split"


# --- loading ---


def test_load_assignment_reads_a_valid_file(tmp_path: Path) -> None:
    loaded = load_assignment(_write(tmp_path, _body()))
    assert loaded.holdout_paper_ids == tuple(sorted(HOLDOUT_IDS))
    assert loaded.dev_paper_ids == tuple(sorted(DEV_IDS))


def test_load_assignment_missing_file_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(HoldoutError, match="not found") as excinfo:
        load_assignment(tmp_path / "absent.json")
    assert excinfo.value.kind == "missing_assignment"


def test_load_assignment_bad_json_fails_closed(tmp_path: Path) -> None:
    target = tmp_path / "broken.json"
    target.write_text("{not json", encoding="utf-8")
    with pytest.raises(HoldoutError, match="could not be read") as excinfo:
        load_assignment(target)
    assert excinfo.value.kind == "schema_error"


def test_load_assignment_rejects_an_invalid_split(tmp_path: Path) -> None:
    # Shape is fine; the split invariant is not.
    with pytest.raises(HoldoutError) as excinfo:
        load_assignment(_write(tmp_path, _body(holdout_paper_ids=[])))
    assert excinfo.value.kind == "invalid_split"


def test_unconfigured_custody_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    assert load_configured_assignment() is None


def test_configured_custody_loads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(ASSIGNMENT_ENV_VAR, str(_write(tmp_path, _body())))
    loaded = load_configured_assignment()
    assert loaded is not None
    assert loaded.holdout_paper_ids == tuple(sorted(HOLDOUT_IDS))


def test_configured_but_missing_file_raises_rather_than_disabling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A typo in the variable must not silently turn custody off.
    monkeypatch.setenv(ASSIGNMENT_ENV_VAR, str(tmp_path / "typo.json"))
    with pytest.raises(HoldoutError, match="refusing to run") as excinfo:
        load_configured_assignment()
    assert excinfo.value.kind == "missing_assignment"


def test_blank_configured_value_is_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ASSIGNMENT_ENV_VAR, "   ")
    assert load_configured_assignment() is None


# --- the commitment ---


def test_commitment_is_deterministic_for_the_same_salt() -> None:
    assert commitment_tag(_assignment(), SALT) == commitment_tag(_assignment(), SALT)


def test_commitment_changes_with_the_salt() -> None:
    assert commitment_tag(_assignment(), SALT) != commitment_tag(_assignment(), b"other-salt")


def test_commitment_changes_with_the_split() -> None:
    moved = _assignment(dev_paper_ids=[*DEV_IDS[:-1], HOLDOUT_IDS[0]],
                        holdout_paper_ids=[HOLDOUT_IDS[1], DEV_IDS[-1]])
    assert commitment_tag(_assignment(), SALT) != commitment_tag(moved, SALT)


def test_commitment_binds_the_inputs() -> None:
    # A changed input version must change the tag, or the freeze would not
    # actually be bound to what it froze.
    changed = _assignment(inputs={"papers": "datasets/reference_papers.json@v2",
                                 "annotation_schema": "reference_claim_graph@v1"})
    assert commitment_tag(_assignment(), SALT) != commitment_tag(changed, SALT)


def test_empty_salt_is_rejected() -> None:
    for bad in (b"", b"   "):
        with pytest.raises(HoldoutError, match="salt") as excinfo:
            commitment_tag(_assignment(), bad)
        assert excinfo.value.kind == "schema_error"


def test_canonical_form_is_order_independent() -> None:
    assert canonical_form(_assignment()) == canonical_form(
        _assignment(dev_paper_ids=tuple(reversed(DEV_IDS)),
                    holdout_paper_ids=tuple(reversed(HOLDOUT_IDS)))
    )


def test_verify_commitment_accepts_the_matching_tag() -> None:
    tag = commitment_tag(_assignment(), SALT)
    verify_commitment(_assignment(), SALT, tag)


def test_verify_commitment_rejects_a_changed_split() -> None:
    tag = commitment_tag(_assignment(), SALT)
    moved = _assignment(dev_paper_ids=[*DEV_IDS[:-1], HOLDOUT_IDS[0]],
                        holdout_paper_ids=[HOLDOUT_IDS[1], DEV_IDS[-1]])
    with pytest.raises(HoldoutError, match="does not match") as excinfo:
        verify_commitment(moved, SALT, tag)
    assert excinfo.value.kind == "invalid_split"


def test_verify_commitment_rejects_a_malformed_tag() -> None:
    with pytest.raises(HoldoutError, match="64-character") as excinfo:
        verify_commitment(_assignment(), SALT, "not-a-digest")
    assert excinfo.value.kind == "schema_error"


def test_unsalted_digest_would_disclose_the_assignment() -> None:
    # This is why the salt is mandatory (docs/HOLDOUT_PROTOCOL.md section 4).
    # The corpus is small enough that every admissible split can be enumerated,
    # so an unsalted digest is invertible: exactly one candidate reproduces it.
    # The salted tag gives an attacker with no salt no such shortcut.
    real = _assignment()
    unsalted = hashlib.sha256(canonical_form(real).encode("utf-8")).hexdigest()

    matches = []
    for size in range(MINIMUM_HOLDOUT_PAPERS, len(CORPUS)):
        for holdout in itertools.combinations(CORPUS, size):
            dev = tuple(p for p in CORPUS if p not in holdout)
            if len(holdout) / len(CORPUS) < MINIMUM_HOLDOUT_FRACTION:
                continue
            candidate = _assignment(dev_paper_ids=dev, holdout_paper_ids=holdout)
            if hashlib.sha256(canonical_form(candidate).encode("utf-8")).hexdigest() == unsalted:
                matches.append(holdout)

    assert matches == [tuple(sorted(HOLDOUT_IDS))], "enumeration must recover the split"

    salted = commitment_tag(real, SALT)
    with pytest.raises(HoldoutError):
        # Without the custodian's salt the same enumeration cannot confirm a guess.
        verify_commitment(real, b"wrong-salt", salted)


# --- development access ---


def test_split_of_classifies_both_sides() -> None:
    assert split_of(DEV_IDS[0], _assignment()) == DEVELOPMENT_SPLIT
    assert split_of(HOLDOUT_IDS[0], _assignment()) == HOLDOUT_SPLIT


def test_split_of_an_unknown_paper_is_refused() -> None:
    # An unclassified paper is exactly what custody exists to catch.
    with pytest.raises(HoldoutError, match="not covered") as excinfo:
        split_of("paper-99", _assignment())
    assert excinfo.value.kind == "invalid_split"


def test_development_ids_are_allowed() -> None:
    assert_development_safe(DEV_IDS, _assignment())


def test_a_holdout_id_in_development_is_refused() -> None:
    with pytest.raises(HoldoutError, match=HOLDOUT_IDS[0]) as excinfo:
        assert_development_safe([DEV_IDS[0], HOLDOUT_IDS[0]], _assignment())
    assert excinfo.value.kind == "holdout_access"


def test_a_bare_string_is_not_silently_iterated() -> None:
    # A single string would iterate as characters, none of which match a paper
    # id, so the check would fail open on the very input it exists to catch.
    with pytest.raises(HoldoutError, match="not a single string") as excinfo:
        assert_development_safe(HOLDOUT_IDS[0], _assignment())
    assert excinfo.value.kind == "schema_error"


# --- whole-paper invariant ---


def test_records_following_one_split_are_valid() -> None:
    records = [{"paper_id": DEV_IDS[0]}, {"paper_id": DEV_IDS[1]}]
    assert_whole_paper(records, _assignment())


def test_a_record_declaring_the_wrong_split_is_refused() -> None:
    records = [{"paper_id": DEV_IDS[0], "split": HOLDOUT_SPLIT}]
    with pytest.raises(HoldoutError) as excinfo:
        assert_whole_paper(records, _assignment())
    assert excinfo.value.kind == "leakage"


def test_a_paper_split_across_both_sides_is_refused() -> None:
    records = [
        (HOLDOUT_IDS[0], DEVELOPMENT_SPLIT),
        (HOLDOUT_IDS[0], HOLDOUT_SPLIT),
    ]
    with pytest.raises(HoldoutError) as excinfo:
        assert_whole_paper(records, _assignment())
    assert excinfo.value.kind == "leakage"


def test_mapping_form_is_accepted() -> None:
    assert_whole_paper({DEV_IDS[0]: DEVELOPMENT_SPLIT}, _assignment())


# --- the scorer's development path ---


def _run_eval(tmp_path: Path, graph: dict, *, env: dict | None, argv: list[str] | None = None):
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    predictions_path = tmp_path / "predictions.json"
    predictions_path.write_text("[]", encoding="utf-8")
    command = [
        sys.executable,
        str(EVAL_SCRIPT),
        "--graph",
        str(graph_path),
        "--predictions",
        str(predictions_path),
    ]
    command.extend(argv or [])
    return subprocess.run(command, capture_output=True, text=True, env=env)


def _graph_for(paper_id: str) -> dict:
    """A minimal graph that passes the reference-graph validator."""
    return {
        "schema_version": "1.0.0",
        "graph_id": "g-synthetic",
        "papers": [{"paper_id": paper_id, "title": "Synthetic", "version": "v1"}],
        "sources": [{"source_id": "s-1", "paper_id": paper_id, "version": "v1"}],
        "claims": [
            {
                "claim_id": "c-1",
                "text": "A synthetic claim.",
                "paper_id": paper_id,
                "source_id": "s-1",
                "evidence": {"quote": "synthetic quote", "byte_start": 0, "byte_end": 15},
                "epistemic_status": "observed",
                "valid_from": None,
                "valid_to": None,
                "recorded_at": "2026-09-27T00:00:00Z",
            }
        ],
        "relationships": [],
        "reviews": [
            {
                "review_id": "r-1",
                "claim_id": "c-1",
                "annotator_id": "a-1",
                "decision": "accept",
                "recorded_at": "2026-09-27T00:00:00Z",
            }
        ],
    }


def test_scorer_refuses_a_holdout_graph_in_development(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    env = {**os.environ}
    env[ASSIGNMENT_ENV_VAR] = str(_write(tmp_path, _body()))
    result = _run_eval(tmp_path, _graph_for(HOLDOUT_IDS[0]), env=env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert HOLDOUT_IDS[0] in result.stderr


def test_scorer_scores_a_development_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    env = {**os.environ}
    env[ASSIGNMENT_ENV_VAR] = str(_write(tmp_path, _body()))
    result = _run_eval(tmp_path, _graph_for(DEV_IDS[0]), env=env)
    assert result.returncode == 0, result.stdout + result.stderr


def test_evaluator_path_requires_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    env = {**os.environ}
    env.pop(ASSIGNMENT_ENV_VAR, None)
    result = _run_eval(tmp_path, _graph_for(HOLDOUT_IDS[0]), env=env, argv=["--evaluator"])
    assert result.returncode == 2, result.stdout + result.stderr


def test_evaluator_path_scores_a_holdout_graph(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    env = {**os.environ}
    env[ASSIGNMENT_ENV_VAR] = str(_write(tmp_path, _body()))
    result = _run_eval(
        tmp_path, _graph_for(HOLDOUT_IDS[0]), env=env, argv=["--evaluator"]
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_scorer_without_custody_is_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # No assignment configured: the scorer must behave exactly as before.
    monkeypatch.delenv(ASSIGNMENT_ENV_VAR, raising=False)
    env = {**os.environ}
    env.pop(ASSIGNMENT_ENV_VAR, None)
    result = _run_eval(tmp_path, _graph_for(HOLDOUT_IDS[0]), env=env)
    assert result.returncode == 0, result.stdout + result.stderr


# --- custody code stays local ---


def test_custody_module_is_offline_and_writes_nothing() -> None:
    # Custody is a security boundary: it must not reach the network, and it must
    # not write the assignment anywhere a development path could read it back.
    source = (REPO_ROOT / "src" / "jev_classifier" / "holdout.py").read_text(
        encoding="utf-8"
    )
    for token in (
        "httpx",
        "requests",
        "openrouter",
        "DecisionsClient",
        "socket",
        "urllib",
        ".write(",
        ".write_text(",
        ".write_bytes(",
        "mkdir(",
        "open(",
    ):
        assert token not in source, f"custody module must stay local; found {token!r}"


def test_custody_module_uses_a_real_hmac() -> None:
    source = (REPO_ROOT / "src" / "jev_classifier" / "holdout.py").read_text(
        encoding="utf-8"
    )
    assert "hmac.new(" in source
    assert "compare_digest" in source

