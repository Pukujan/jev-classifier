"""Reference claim graph + privacy-safe stimulus manifest schema tests (#37)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from jev_classifier.reference import (
    CONTEXT_STIMULUS_MANIFEST_SCHEMA,
    REFERENCE_CLAIM_GRAPH_SCHEMA,
    ReferenceSchemaError,
    load_schema,
    validate_reference_graph,
    validate_stimulus_manifest,
)

FIX = Path(__file__).resolve().parent / "fixtures" / "reference"


def _graph() -> dict:
    return json.loads((FIX / "claim_graph_ok.json").read_text(encoding="utf-8"))


def _manifest() -> dict:
    return json.loads((FIX / "stimulus_manifest_ok.json").read_text(encoding="utf-8"))


# --- schema documents ---


def test_schemas_are_draft_2020_12_and_parse() -> None:
    for name in (REFERENCE_CLAIM_GRAPH_SCHEMA, CONTEXT_STIMULUS_MANIFEST_SCHEMA):
        schema = load_schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        jsonschema.Draft202012Validator.check_schema(schema)


def test_unknown_schema_name_fails_closed() -> None:
    with pytest.raises(ReferenceSchemaError, match="schema not found"):
        load_schema("does_not_exist.schema.json")


def test_positive_fixtures_validate_against_schemas() -> None:
    jsonschema.validate(_graph(), load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))
    jsonschema.validate(_manifest(), load_schema(CONTEXT_STIMULUS_MANIFEST_SCHEMA))


def test_positive_fixtures_pass_cross_record_validation() -> None:
    validate_reference_graph(_graph())
    validate_stimulus_manifest(_manifest())


# --- schema shape: fail closed ---


def test_claim_missing_source_id_fails_schema() -> None:
    graph = _graph()
    del graph["claims"][0]["source_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(graph, load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))


def test_claim_missing_evidence_fails_schema() -> None:
    graph = _graph()
    del graph["claims"][0]["evidence"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(graph, load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))


def test_unknown_epistemic_status_fails_schema() -> None:
    graph = _graph()
    graph["claims"][0]["epistemic_status"] = "believed"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(graph, load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))


def test_unknown_relationship_type_fails_schema() -> None:
    graph = _graph()
    graph["relationships"][0]["type"] = "implies"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(graph, load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))


def test_empty_claims_fails_schema() -> None:
    graph = _graph()
    graph["claims"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(graph, load_schema(REFERENCE_CLAIM_GRAPH_SCHEMA))


# --- cross-record invariants: fail closed ---


def test_unresolvable_source_fails_closed() -> None:
    graph = _graph()
    graph["claims"][0]["source_id"] = "source:missing"
    with pytest.raises(ReferenceSchemaError, match="does not resolve to a source"):
        validate_reference_graph(graph)


def test_unresolvable_paper_fails_closed() -> None:
    graph = _graph()
    graph["claims"][0]["paper_id"] = "paper:missing"
    with pytest.raises(ReferenceSchemaError, match="does not resolve to a paper"):
        validate_reference_graph(graph)


def test_claim_citing_a_source_from_another_paper_fails_closed() -> None:
    graph = _graph()
    graph["papers"].append(
        {"paper_id": "paper:demo-b", "title": "B", "version": "v1", "doi": None, "url": None}
    )
    graph["sources"].append(
        {
            "source_id": "source:demo-b",
            "paper_id": "paper:demo-b",
            "version": "v1",
            "content_sha256": None,
        }
    )
    graph["claims"][0]["source_id"] = "source:demo-b"
    with pytest.raises(ReferenceSchemaError, match="not 'paper:demo-a'"):
        validate_reference_graph(graph)


def test_relationship_to_missing_claim_fails_closed() -> None:
    graph = _graph()
    graph["relationships"][0]["to_claim_id"] = "claim:missing"
    with pytest.raises(ReferenceSchemaError, match="endpoint"):
        validate_reference_graph(graph)


def test_self_relationship_fails_closed() -> None:
    graph = _graph()
    graph["relationships"][0]["to_claim_id"] = graph["relationships"][0]["from_claim_id"]
    with pytest.raises(ReferenceSchemaError, match="irreflexive"):
        validate_reference_graph(graph)


def test_byte_end_not_exceeding_start_fails_closed() -> None:
    graph = _graph()
    graph["claims"][0]["evidence"]["byte_end"] = graph["claims"][0]["evidence"]["byte_start"]
    with pytest.raises(ReferenceSchemaError, match="byte_end"):
        validate_reference_graph(graph)


def test_empty_quote_fails_closed() -> None:
    graph = _graph()
    graph["claims"][0]["evidence"]["quote"] = ""
    with pytest.raises(ReferenceSchemaError, match="quote"):
        validate_reference_graph(graph)


def test_duplicate_claim_ids_fail_closed() -> None:
    graph = _graph()
    graph["claims"].append(copy.deepcopy(graph["claims"][0]))
    with pytest.raises(ReferenceSchemaError, match="duplicate claim id"):
        validate_reference_graph(graph)


def test_bad_schema_version_fails_closed() -> None:
    graph = _graph()
    graph["schema_version"] = "1.0"
    with pytest.raises(ReferenceSchemaError, match="semver"):
        validate_reference_graph(graph)


def test_review_on_missing_claim_fails_closed() -> None:
    graph = _graph()
    graph["reviews"][0]["claim_id"] = "claim:missing"
    with pytest.raises(ReferenceSchemaError, match="review\\[review:demo-1\\]"):
        validate_reference_graph(graph)


def test_review_superseding_itself_fails_closed() -> None:
    graph = _graph()
    graph["reviews"][0]["supersedes_review_id"] = "review:demo-1"
    with pytest.raises(ReferenceSchemaError, match="supersedes itself"):
        validate_reference_graph(graph)


def test_review_superseding_a_missing_review_fails_closed() -> None:
    graph = _graph()
    graph["reviews"][0]["supersedes_review_id"] = "review:missing"
    with pytest.raises(ReferenceSchemaError, match="does not resolve to a review"):
        validate_reference_graph(graph)


# --- invariants the issue names explicitly ---


def test_disagreement_is_preserved_across_reviews() -> None:
    # Two annotators disagree on claim:demo-2; both records must survive.
    graph = _graph()
    validate_reference_graph(graph)
    decisions = {
        r["decision"] for r in graph["reviews"] if r["claim_id"] == "claim:demo-2"
    }
    assert decisions == {"uncertain", "revise"}


def test_uncertain_dates_stay_null_and_are_not_defaulted() -> None:
    graph = _graph()
    graph["claims"][0]["valid_from"] = None
    graph["claims"][0]["valid_to"] = None
    validate_reference_graph(graph)
    assert graph["claims"][0]["valid_from"] is None
    assert graph["claims"][0]["valid_to"] is None
    # recorded_at is transaction time and is always present.
    assert graph["claims"][0]["recorded_at"]


def test_valid_time_and_transaction_time_are_separate_fields() -> None:
    graph = _graph()
    graph["claims"][0]["valid_from"] = "2020-01-01T00:00:00+00:00"
    graph["claims"][0]["recorded_at"] = "2026-09-26T00:00:00+00:00"
    validate_reference_graph(graph)
    assert graph["claims"][0]["valid_from"] != graph["claims"][0]["recorded_at"]


# --- privacy-safe stimulus manifest ---


def test_pair_spanning_two_families_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][1]["condition_family_id"] = "family:other"
    with pytest.raises(ReferenceSchemaError, match="condition families"):
        validate_stimulus_manifest(manifest)


def test_pair_spanning_two_source_packets_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][1]["source_packet_id"] = "packet:other"
    with pytest.raises(ReferenceSchemaError, match="source packets"):
        validate_stimulus_manifest(manifest)


def test_duplicate_pair_role_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][1]["pair_role"] = "control"
    with pytest.raises(ReferenceSchemaError, match="pair_role more than once"):
        validate_stimulus_manifest(manifest)


def test_multi_case_pair_without_roles_fails_closed() -> None:
    manifest = _manifest()
    for case in manifest["cases"]:
        del case["pair_role"]
    with pytest.raises(ReferenceSchemaError, match="missing pair_role"):
        validate_stimulus_manifest(manifest)


def test_url_in_a_public_record_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][0]["notes"] = "see https://example.com/private/thread"
    with pytest.raises(ReferenceSchemaError, match="must not contain URLs"):
        validate_stimulus_manifest(manifest)


def test_url_nested_in_a_public_record_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][0]["seed_provenance"] = "https://example.com/share/abc"
    with pytest.raises(ReferenceSchemaError, match="must not contain URLs"):
        validate_stimulus_manifest(manifest)


def test_private_audit_ref_must_be_an_opaque_pointer() -> None:
    manifest = _manifest()
    manifest["cases"][0]["private_audit_ref"] = "C:/Users/someone/private/notes.txt"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, load_schema(CONTEXT_STIMULUS_MANIFEST_SCHEMA))


def test_manifest_requires_no_raw_context_content() -> None:
    # The schema has no field that can carry raw private text; extra keys are
    # rejected, so a producer cannot smuggle transcript content into a case.
    manifest = _manifest()
    manifest["cases"][0]["raw_context"] = "verbatim private transcript..."
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(manifest, load_schema(CONTEXT_STIMULUS_MANIFEST_SCHEMA))


def test_unknown_stimulus_method_fails_closed() -> None:
    manifest = _manifest()
    manifest["cases"][0]["stimulus_method"] = "real_user_data"
    with pytest.raises(ReferenceSchemaError, match="stimulus_method"):
        validate_stimulus_manifest(manifest)


def test_validation_status_is_closed() -> None:
    manifest = _manifest()
    manifest["cases"][0]["validation_status"] = "trusted"
    with pytest.raises(ReferenceSchemaError, match="validation_status"):
        validate_stimulus_manifest(manifest)
