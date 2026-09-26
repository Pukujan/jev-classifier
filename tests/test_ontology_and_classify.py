"""Iteration 2 tests: ontology parse, fixture keys, fail-closed classify shape."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jev_classifier.classify import (
    REQUIRED_CLAIM_KEYS,
    build_claim_record,
    load_fragment_fixture,
    validate_claim_record,
)
from jev_classifier.normalize import NormalizeError

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
ONTOLOGY = ROOT / "ontology" / "jev_classifier_claims.ttl"


def test_rdflib_parses_claims_ttl() -> None:
    rdflib = pytest.importorskip("rdflib")
    g = rdflib.Graph()
    g.parse(str(ONTOLOGY), format="turtle")
    assert len(g) > 0
    # a floor, not an exact count: adding a term should not fail this, but
    # losing the file's substance (a truncated parse) should
    assert len(g) >= 115, f"ontology looks truncated: {len(g)} triples"
    # Spot-check class URIs exist as subjects
    text = ONTOLOGY.read_text(encoding="utf-8")
    assert "jcc:Claim" in text
    assert "jcc:SourceFragment" in text
    assert "jcc:ClassificationActivity" in text
    assert "jcc:ClassifierAgent" in text
    assert "jcc:epistemicStatus" in text
    assert "jcc:validFrom" in text
    assert "jcc:validTo" in text
    assert "jcc:recordedAt" in text
    assert "jcc:supersedes" in text
    assert "jcc:independenceClass" in text
    # the PROV activity/agent edges and the relocated model id are declared
    assert "prov:wasGeneratedBy" in text
    assert "prov:wasAssociatedWith" in text
    assert "prov:used" in text
    assert "jcc:surfacedModelId" in text


# --- PROV activity/agent modelling (#31) ---------------------------------

JCC = "https://github.com/Pukujan/jev-classifier/ontology/claims#"
PROV = "http://www.w3.org/ns/prov#"
NANOPUB_SUPERSEDES = "http://purl.org/nanopub/x/supersedes"


def _graph():
    rdflib = pytest.importorskip("rdflib")
    g = rdflib.Graph()
    g.parse(str(ONTOLOGY), format="turtle")
    return rdflib, g


def test_ontology_declares_prov_terms_locally_without_imports() -> None:
    """Offline syntax check must stay green: prov: terms are declared, not fetched."""
    rdflib, g = _graph()
    assert not list(g.objects(None, rdflib.OWL.imports)), (
        "no remote owl:imports: the parse must work with no network"
    )
    for term in ("Entity", "Activity", "Agent", "SoftwareAgent",
                 "wasGeneratedBy", "wasAssociatedWith", "used", "wasRevisionOf"):
        assert (rdflib.URIRef(PROV + term), None, None) in g, term


def test_activity_and_agent_subclass_prov() -> None:
    rdflib, g = _graph()
    RDFS, OWL = rdflib.RDFS, rdflib.OWL
    jcc = rdflib.Namespace(JCC)
    prov = rdflib.Namespace(PROV)
    assert (jcc.ClassificationActivity, RDFS.subClassOf, prov.Activity) in g
    assert (jcc.ClassifierAgent, RDFS.subClassOf, prov.SoftwareAgent) in g
    assert (prov.SoftwareAgent, RDFS.subClassOf, prov.Agent) in g
    assert (jcc.ClassificationActivity, rdflib.RDF.type, OWL.Class) in g
    assert (jcc.ClassifierAgent, rdflib.RDF.type, OWL.Class) in g


def test_model_id_moved_off_the_claim() -> None:
    """jcc:modelId is a PROV anti-pattern on the entity; it belongs to the agent."""
    rdflib, g = _graph()
    RDFS = rdflib.RDFS
    jcc = rdflib.Namespace(JCC)
    domains = set(g.objects(jcc.modelId, RDFS.domain))
    assert jcc.ClassifierAgent in domains
    assert jcc.Claim not in domains, "model id must no longer hang on the Claim"
    assert jcc.ClassificationActivity in set(g.objects(jcc.surfacedModelId, RDFS.domain))


def test_supersedes_aligned_to_prov_and_nanopub() -> None:
    rdflib, g = _graph()
    RDFS, OWL = rdflib.RDFS, rdflib.OWL
    jcc = rdflib.Namespace(JCC)
    prov = rdflib.Namespace(PROV)
    assert (jcc.supersedes, RDFS.subPropertyOf, prov.wasRevisionOf) in g
    # rdflib's closed OWL namespace omits this term, so build the IRI directly
    irreflexive = rdflib.URIRef("http://www.w3.org/2002/07/owl#IrreflexiveObjectProperty")
    assert (jcc.supersedes, rdflib.RDF.type, irreflexive) in g
    assert (jcc.supersedes, RDFS.seeAlso, rdflib.URIRef(NANOPUB_SUPERSEDES)) in g


def test_epistemic_status_domain_allows_a_source_fragment() -> None:
    """A fragment can be graded, not only a Claim (the domain was Claim-only)."""
    rdflib, g = _graph()
    RDFS, OWL = rdflib.RDFS, rdflib.OWL
    jcc = rdflib.Namespace(JCC)
    members: set = set()
    for dom in g.objects(jcc.epistemicStatus, RDFS.domain):
        for lst in g.objects(dom, OWL.unionOf):
            members.update(g.items(lst))
    assert members, "expected an explicit union domain"
    assert jcc.Claim in members and jcc.SourceFragment in members


def test_flat_validity_hooks_are_kept() -> None:
    """PROV-O has no valid-time construct; the domain extension stays flat."""
    rdflib, g = _graph()
    jcc = rdflib.Namespace(JCC)
    for prop in (jcc.validFrom, jcc.validTo, jcc.recordedAt):
        assert (prop, None, None) in g
        assert not list(g.objects(prop, rdflib.OWL.unionOf)), (
            "validity must stay flat datatype properties, not reified intervals"
        )


def test_sample_claim_graph_serializes_activity_and_agent_edges() -> None:
    """A claim graph built with the declared terms wires the PROV edges."""
    rdflib, g = _graph()
    RDF = rdflib.RDF
    jcc = rdflib.Namespace(JCC)
    prov = rdflib.Namespace(PROV)
    claim, frag = jcc["claim-001"], jcc["frag-001"]
    act, agent = jcc["act-001"], jcc["agent-jev"]
    g.add((claim, RDF.type, jcc.Claim))
    g.add((claim, prov.wasGeneratedBy, act))
    g.add((act, RDF.type, jcc.ClassificationActivity))
    g.add((act, prov.wasAssociatedWith, agent))
    g.add((act, prov.used, frag))
    g.add((agent, RDF.type, jcc.ClassifierAgent))
    g.add((agent, jcc.modelId, rdflib.Literal("typesafe/jev-1.13")))
    assert (claim, prov.wasGeneratedBy, act) in g
    assert (act, prov.wasAssociatedWith, agent) in g
    assert (act, prov.used, frag) in g
    # the produced claim carries no model id of its own
    assert not list(g.objects(claim, jcc.modelId))
    # and it survives a round-trip through the serializer
    back = rdflib.Graph()
    back.parse(data=g.serialize(format="turtle"), format="turtle")
    assert (claim, prov.wasGeneratedBy, act) in back


def test_fragment_fixture_has_closed_set() -> None:
    frag = load_fragment_fixture(FIXTURES / "fragment_empirical_001.json")
    assert "empirical_finding" in frag["closed_label_set"]
    assert frag["question_id"] == "claim_kind"
    assert set(frag["criteria"].keys()) == set(frag["closed_label_set"])


def test_golden_claim_has_required_keys() -> None:
    claim = json.loads((FIXTURES / "claim_empirical_001.json").read_text(encoding="utf-8"))
    legal = set(
        json.loads((FIXTURES / "fragment_empirical_001.json").read_text(encoding="utf-8"))[
            "closed_label_set"
        ]
    )
    validate_claim_record(claim, legal_labels=legal)
    assert REQUIRED_CLAIM_KEYS <= set(claim.keys())


def test_out_of_set_claim_label_fails_closed() -> None:
    claim = build_claim_record(
        label="not_a_real_label",
        model="typesafe/jev-1.13",
        evidence={"fragment_id": "x", "path": "tests/fixtures/x.json"},
    )
    with pytest.raises(NormalizeError) as ei:
        validate_claim_record(claim, legal_labels={"empirical_finding", "other"})
    assert ei.value.kind == "parse_error"


def test_missing_required_claim_key_fails_closed() -> None:
    with pytest.raises(NormalizeError) as ei:
        validate_claim_record(
            {
                "label": "other",
                "epistemic_status": "Inferred",
                "recorded_at": "2026-09-26T00:00:00+00:00",
                # missing evidence + model
            },
            legal_labels={"other"},
        )
    assert ei.value.kind == "parse_error"
