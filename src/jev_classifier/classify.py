"""Minimal classify path: JEV choice → validated claim JSON record."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from jev_classifier.decisions import DecisionsClient, DecisionsError
from jev_classifier.normalize import NormalizeError, extract_choice_from_response

# Required for application validation (see docs/CLAIM_SCHEMA.md).
REQUIRED_CLAIM_KEYS = frozenset(
    {
        "label",
        "epistemic_status",
        "recorded_at",
        "evidence",
        "model",
    }
)

# Full PCM-0050-friendly ledger field set (required + optional documented keys).
PCM_CLAIM_KEYS = frozenset(
    {
        "id",
        "label",
        "epistemic_status",
        "recorded_at",
        "valid_from",
        "valid_to",
        "supersedes",
        "evidence",
        "model",
        "probabilities",
        "confidence",
        "independence_class",
        "response_id",
        "notes",
        "provenance",
    }
)

# Ontology / graph namespaces used by attach_claim_prov_edges.
JCC_NS = "https://github.com/Pukujan/jev-classifier/ontology/claims#"
PROV_NS = "http://www.w3.org/ns/prov#"

# Legacy / camelCase → canonical snake_case (PCM-friendly). Canonical wins on clash.
LEGACY_CLAIM_KEY_ALIASES: dict[str, str] = {
    "epistemicStatus": "epistemic_status",
    "status": "epistemic_status",
    "validFrom": "valid_from",
    "validTo": "valid_to",
    "recordedAt": "recorded_at",
    "created_at": "recorded_at",
    "createdAt": "recorded_at",
    "independenceClass": "independence_class",
}


def migrate_legacy_claim(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Rewrite legacy/camelCase claim keys to PCM-friendly snake_case.

    Does not install or import PCM. If both legacy and canonical keys are
    present, the canonical value is kept. Unknown keys pass through unchanged.
    """
    if not isinstance(raw, Mapping):
        raise NormalizeError("claim must be an object", kind="parse_error")
    out: dict[str, Any] = dict(raw)
    for legacy, canonical in LEGACY_CLAIM_KEY_ALIASES.items():
        if legacy not in out:
            continue
        if canonical not in out:
            out[canonical] = out[legacy]
        del out[legacy]
    return out


def normalize_claim_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Migrate legacy keys then return a plain dict (no validation)."""
    return migrate_legacy_claim(raw)


def load_fragment_fixture(path: str | Path) -> dict[str, Any]:
    import json

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fragment fixture must be a JSON object")
    for key in ("id", "text", "closed_label_set", "question_id", "criteria"):
        if key not in data:
            raise ValueError(f"fragment fixture missing required key: {key}")
    labels = data["closed_label_set"]
    if not isinstance(labels, list) or not labels or not all(isinstance(x, str) for x in labels):
        raise ValueError("closed_label_set must be a non-empty list of strings")
    return data


def _validate_supersedes(value: Any) -> None:
    """Supersession link: null/absent OK; else non-empty string claim id."""
    if value is None:
        return
    if not isinstance(value, str):
        raise NormalizeError(
            "supersedes must be a string claim id or null",
            kind="parse_error",
        )
    if not value.strip():
        raise NormalizeError(
            "supersedes must be a non-empty claim id when set",
            kind="parse_error",
        )


def _validate_optional_iso_or_null(value: Any, key: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise NormalizeError(
            f"{key} must be a non-empty ISO-8601 string or null",
            kind="parse_error",
        )


def _validate_provenance(value: Any) -> None:
    """Optional nested provenance: claim→activity→agent and activity→used.

    Shape only. Never invents model ids; ``surfaced_model_id`` may be absent.
    """
    if value is None:
        return
    if not isinstance(value, Mapping):
        raise NormalizeError("provenance must be an object or null", kind="parse_error")
    if "was_generated_by" not in value:
        raise NormalizeError(
            "provenance requires was_generated_by (ClassificationActivity)",
            kind="parse_error",
        )
    activity = value["was_generated_by"]
    if not isinstance(activity, Mapping):
        raise NormalizeError(
            "provenance.was_generated_by must be an object",
            kind="parse_error",
        )
    if "id" in activity and activity["id"] is not None:
        if not isinstance(activity["id"], str) or not activity["id"].strip():
            raise NormalizeError(
                "provenance.was_generated_by.id must be a non-empty string or null",
                kind="parse_error",
            )
    if "surfaced_model_id" in activity and activity["surfaced_model_id"] is not None:
        sm = activity["surfaced_model_id"]
        if not isinstance(sm, str) or not sm.strip():
            raise NormalizeError(
                "provenance.was_generated_by.surfaced_model_id must be a "
                "non-empty string when set (omit or null when provider did not surface one)",
                kind="parse_error",
            )
    agent = activity.get("was_associated_with")
    if agent is None:
        raise NormalizeError(
            "provenance.was_generated_by requires was_associated_with (ClassifierAgent)",
            kind="parse_error",
        )
    if not isinstance(agent, Mapping):
        raise NormalizeError(
            "provenance.was_generated_by.was_associated_with must be an object",
            kind="parse_error",
        )
    model_id = agent.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        raise NormalizeError(
            "provenance agent model_id (requested) must be a non-empty string",
            kind="parse_error",
        )
    if "id" in agent and agent["id"] is not None:
        if not isinstance(agent["id"], str) or not agent["id"].strip():
            raise NormalizeError(
                "provenance agent id must be a non-empty string or null",
                kind="parse_error",
            )
    used = activity.get("used")
    if used is not None:
        if not isinstance(used, Mapping):
            raise NormalizeError(
                "provenance.was_generated_by.used must be an object or null",
                kind="parse_error",
            )
        if "fragment_id" not in used and "path" not in used:
            raise NormalizeError(
                "provenance.was_generated_by.used needs fragment_id and/or path",
                kind="parse_error",
            )


def build_provenance(
    *,
    requested_model: str,
    fragment_id: str | None = None,
    evidence_path: str | None = None,
    surfaced_model: str | None = None,
    activity_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Build nested provenance for claim→activity→agent and activity→used.

    ``requested_model`` is always recorded on the agent as ``model_id``.
    ``surfaced_model`` is recorded on the activity only when the provider
    returned a non-empty string — never copied from the requested model.
    """
    if not isinstance(requested_model, str) or not requested_model.strip():
        raise NormalizeError(
            "requested_model must be a non-empty string",
            kind="parse_error",
        )
    agent: dict[str, Any] = {"model_id": requested_model}
    if agent_id is not None:
        agent["id"] = agent_id

    activity: dict[str, Any] = {"was_associated_with": agent}
    if activity_id is not None:
        activity["id"] = activity_id
    if isinstance(surfaced_model, str) and surfaced_model.strip():
        activity["surfaced_model_id"] = surfaced_model

    used: dict[str, Any] = {}
    if fragment_id is not None:
        used["fragment_id"] = fragment_id
    if evidence_path is not None:
        used["path"] = evidence_path
    if used:
        activity["used"] = used

    return {"was_generated_by": activity}


def validate_claim_record(
    claim: Mapping[str, Any],
    *,
    legal_labels: set[str] | frozenset[str],
    migrate: bool = True,
) -> dict[str, Any]:
    """Validate a claim record; optionally migrate legacy keys first.

    Returns the (possibly migrated) claim dict. Fail closed on shape errors.
    """
    body: Mapping[str, Any] = migrate_legacy_claim(claim) if migrate else claim
    missing = REQUIRED_CLAIM_KEYS - set(body.keys())
    if missing:
        raise NormalizeError(
            f"claim missing required keys: {sorted(missing)}",
            kind="parse_error",
        )
    label = body["label"]
    if not isinstance(label, str) or label not in legal_labels:
        raise NormalizeError(
            f"claim label {label!r} not in legal set {sorted(legal_labels)}",
            kind="parse_error",
        )
    if not isinstance(body["epistemic_status"], str) or not body["epistemic_status"]:
        raise NormalizeError("epistemic_status must be a non-empty string", kind="parse_error")
    if not isinstance(body["recorded_at"], str) or not body["recorded_at"]:
        raise NormalizeError("recorded_at must be a non-empty ISO-8601 string", kind="parse_error")
    evidence = body["evidence"]
    if not isinstance(evidence, Mapping):
        raise NormalizeError("evidence must be an object pointer", kind="parse_error")
    if "fragment_id" not in evidence and "path" not in evidence:
        raise NormalizeError("evidence needs fragment_id and/or path", kind="parse_error")
    if not isinstance(body["model"], str) or not body["model"]:
        raise NormalizeError("model must be a non-empty string", kind="parse_error")

    if "supersedes" in body:
        _validate_supersedes(body["supersedes"])
    if "valid_from" in body:
        _validate_optional_iso_or_null(body["valid_from"], "valid_from")
    if "valid_to" in body:
        _validate_optional_iso_or_null(body["valid_to"], "valid_to")
    if "independence_class" in body and body["independence_class"] is not None:
        ic = body["independence_class"]
        if not isinstance(ic, str) or not ic.strip():
            raise NormalizeError(
                "independence_class must be a non-empty string or null",
                kind="parse_error",
            )
    if "provenance" in body:
        _validate_provenance(body["provenance"])

    return dict(body)


def build_claim_record(
    *,
    label: str,
    model: str,
    evidence: Mapping[str, Any],
    probabilities: Mapping[str, float] | None = None,
    confidence: float | None = None,
    epistemic_status: str = "Inferred",
    recorded_at: str | None = None,
    valid_from: str | None = None,
    valid_to: str | None = None,
    supersedes: str | None = None,
    response_id: str | None = None,
    independence_class: str | None = None,
    claim_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
    requested_model: str | None = None,
    surfaced_model: str | None = None,
    activity_id: str | None = None,
    agent_id: str | None = None,
) -> dict[str, Any]:
    """Build a claim JSON record.

    ``model`` remains the application-required requested model id (maps to
    ``jcc:modelId`` on the ClassifierAgent). When ``provenance`` is omitted,
    a nested block is built from ``requested_model`` (defaults to ``model``),
    evidence fragment pointer, and optional ``surfaced_model`` (activity only;
    never fabricated from the requested id).
    """
    ts = recorded_at or datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "label": label,
        "epistemic_status": epistemic_status,
        "recorded_at": ts,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "supersedes": supersedes,
        "evidence": dict(evidence),
        "model": model,
        "probabilities": dict(probabilities) if probabilities is not None else None,
        "confidence": confidence,
        "response_id": response_id,
        "independence_class": independence_class,
    }
    if claim_id is not None:
        record["id"] = claim_id

    if provenance is not None:
        record["provenance"] = dict(provenance)
    else:
        req = requested_model if requested_model is not None else model
        frag_id = evidence.get("fragment_id") if isinstance(evidence, Mapping) else None
        path = evidence.get("path") if isinstance(evidence, Mapping) else None
        record["provenance"] = build_provenance(
            requested_model=req,
            fragment_id=frag_id if isinstance(frag_id, str) else None,
            evidence_path=path if isinstance(path, str) else None,
            surfaced_model=surfaced_model,
            activity_id=activity_id if activity_id is not None else response_id,
            agent_id=agent_id,
        )
    return record



def _claim_graph_key(claim: Mapping[str, Any]) -> str:
    """Stable claim URI key: claim.id -> evidence.fragment_id -> error.

    Never falls back to ``label`` (closed-set labels collapse distinct claims
    onto one graph node). Does not invent new identities.
    """
    claim_id = claim.get("id")
    if isinstance(claim_id, str) and claim_id.strip():
        return claim_id.strip()
    evidence = claim.get("evidence")
    if isinstance(evidence, Mapping):
        frag_id = evidence.get("fragment_id")
        if isinstance(frag_id, str) and frag_id.strip():
            return frag_id.strip()
    raise NormalizeError(
        "claim graph key requires claim.id or evidence.fragment_id "
        "(label is not an identity)",
        kind="parse_error",
    )


def attach_claim_prov_edges(graph: Any, claim: Mapping[str, Any]) -> None:
    """Attach claim→activity→agent and activity→used triples onto an rdflib Graph.

    Reads the nested ``provenance`` block emitted by ``build_claim_record`` /
    ``classify_fragment``. Does not invent ``surfaced_model_id`` when absent.
    Claim URI key is ``id`` then evidence ``fragment_id`` (never ``label``).
    Path-only evidence raises ``NormalizeError`` rather than silently omitting
    ``prov:used``. Requires the optional ``ontology`` extra (rdflib).
    """
    try:
        import rdflib
        from rdflib import Literal, Namespace, URIRef
        from rdflib.namespace import RDF
    except ImportError as exc:  # pragma: no cover - env without ontology extra
        raise ImportError(
            "attach_claim_prov_edges requires rdflib (install ontology extra)"
        ) from exc

    if "provenance" not in claim or claim["provenance"] is None:
        raise NormalizeError(
            "claim missing provenance block for graph edges",
            kind="parse_error",
        )
    _validate_provenance(claim["provenance"])

    jcc = Namespace(JCC_NS)
    prov = Namespace(PROV_NS)
    activity = claim["provenance"]["was_generated_by"]
    agent = activity["was_associated_with"]

    claim_key = _claim_graph_key(claim)
    claim_uri = URIRef(JCC_NS + f"claim-{claim_key}")
    act_key = activity.get("id")
    if not (isinstance(act_key, str) and act_key.strip()):
        act_key = f"act-{claim_key}"
    act_uri = URIRef(JCC_NS + str(act_key))
    agent_key = agent.get("id") or f"agent-{agent['model_id']}"
    agent_uri = URIRef(JCC_NS + str(agent_key).replace("/", "-"))

    # Resolve fragment_id before mutating the graph so path-only fails closed
    # without leaving a half-written Claim / Activity / Agent.
    used = activity.get("used") or {}
    frag_id = used.get("fragment_id")
    if not frag_id and isinstance(claim.get("evidence"), Mapping):
        frag_id = claim["evidence"].get("fragment_id")
    if not (isinstance(frag_id, str) and frag_id.strip()):
        raise NormalizeError(
            "attach_claim_prov_edges requires evidence fragment_id to emit prov:used "
            "(path-only evidence cannot be serialized to a SourceFragment node)",
            kind="parse_error",
        )
    frag_uri = URIRef(JCC_NS + f"frag-{frag_id}")

    graph.add((claim_uri, RDF.type, jcc.Claim))
    graph.add((claim_uri, prov.wasGeneratedBy, act_uri))
    graph.add((act_uri, RDF.type, jcc.ClassificationActivity))
    graph.add((act_uri, prov.wasAssociatedWith, agent_uri))
    graph.add((agent_uri, RDF.type, jcc.ClassifierAgent))
    graph.add((agent_uri, jcc.modelId, Literal(agent["model_id"])))

    if "surfaced_model_id" in activity and activity["surfaced_model_id"] is not None:
        graph.add((act_uri, jcc.surfacedModelId, Literal(activity["surfaced_model_id"])))

    graph.add((frag_uri, RDF.type, jcc.SourceFragment))
    graph.add((act_uri, prov.used, frag_uri))


def classify_fragment(
    fragment: Mapping[str, Any],
    *,
    client: DecisionsClient | None = None,
    evidence_path: str | None = None,
) -> dict[str, Any]:
    """Call JEV choice on a fragment fixture dict; return a claim JSON record.

    Fail closed: DecisionsError / NormalizeError propagate; never fabricates labels.
    Emits nested ``provenance`` so a serializer can attach claim→activity→agent
    and activity→used SourceFragment edges. Top-level ``model`` is the
    *requested* model id; provider-surfaced model (when present) lives only on
    the activity as ``surfaced_model_id``.
    """
    legal = frozenset(fragment["closed_label_set"])
    qid = fragment["question_id"]
    criteria = fragment["criteria"]
    if set(criteria.keys()) != set(legal):
        raise NormalizeError(
            "criteria keys must match closed_label_set exactly",
            kind="parse_error",
        )

    questions = {
        qid: {
            "type": "choice",
            "instructions": fragment.get(
                "instructions",
                "Classify the research fragment into exactly one closed label.",
            ),
            "criteria": dict(criteria),
        }
    }
    state = {
        "fragment_id": fragment.get("id"),
        "fragment": fragment["text"],
        "source": fragment.get("source"),
        "title": fragment.get("title"),
    }

    svc = client or DecisionsClient()
    try:
        raw = svc.decide(state=state, questions=questions)
    except DecisionsError:
        raise

    normalized = extract_choice_from_response(
        raw,
        question_id=qid,
        legal_options=legal,
    )
    requested_model = svc.model
    surfaced_raw = normalized.get("model")
    surfaced_model = (
        surfaced_raw
        if isinstance(surfaced_raw, str) and surfaced_raw.strip()
        else None
    )
    evidence = {
        "fragment_id": fragment.get("id"),
        "path": evidence_path,
    }
    response_id = normalized.get("response_id")
    claim = build_claim_record(
        label=normalized["choice"],
        model=requested_model,
        evidence=evidence,
        probabilities=normalized.get("probabilities"),
        confidence=normalized.get("confidence"),
        epistemic_status="Inferred",
        response_id=response_id,
        requested_model=requested_model,
        surfaced_model=surfaced_model,
        activity_id=response_id if isinstance(response_id, str) else None,
    )
    return validate_claim_record(claim, legal_labels=legal)
