"""Assemble claim JSON records into a markdown research-paper skeleton.

v1 constraint: prose is code/string templates only. Claim labels and evidence
ids come from input records ? never from a non-JEV LLM call.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence


REQUIRED_SECTIONS = (
    "Title",
    "Abstract",
    "Claims",
    "Provenance",
    "Lineage",
    "Citations",
)


class AssembleError(ValueError):
    """Raised when claim records or assembled markdown fail validation."""


def _require_claim(claim: Mapping[str, Any], index: int) -> dict[str, Any]:
    if not isinstance(claim, Mapping):
        raise AssembleError(f"claim[{index}] must be an object")
    for key in ("label", "epistemic_status", "recorded_at", "evidence", "model"):
        if key not in claim:
            raise AssembleError(f"claim[{index}] missing required key: {key}")
    label = claim["label"]
    if not isinstance(label, str) or not label.strip():
        raise AssembleError(f"claim[{index}].label must be a non-empty string")
    evidence = claim["evidence"]
    if not isinstance(evidence, Mapping):
        raise AssembleError(f"claim[{index}].evidence must be an object")
    return dict(claim)


def _evidence_ids(claim: Mapping[str, Any]) -> list[str]:
    ev = claim["evidence"]
    ids: list[str] = []
    for key in ("fragment_id", "source_id", "path", "uri"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            ids.append(val.strip())
    extra = ev.get("ids")
    if isinstance(extra, list):
        ids.extend(str(x).strip() for x in extra if str(x).strip())
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    if not out:
        raise AssembleError("claim evidence must include at least one id (fragment_id/path/...)")
    return out


def _claim_bullet(claim: Mapping[str, Any], index: int) -> str:
    claim_id = claim.get("id") or f"C{index + 1}"
    label = claim["label"]
    status = claim["epistemic_status"]
    model = claim["model"]
    probs = claim.get("probabilities")
    conf = claim.get("confidence")
    parts = [
        f"- **{claim_id}** ? label=`{label}`; epistemic_status=`{status}`; model=`{model}`"
    ]
    if conf is not None:
        parts.append(f"  - confidence: {conf}")
    if isinstance(probs, Mapping) and probs:
        rendered = ", ".join(f"{k}={v}" for k, v in sorted(probs.items()))
        parts.append(f"  - probabilities: {rendered}")
    eids = _evidence_ids(claim)
    parts.append(f"  - evidence_ids: {', '.join(f'`{e}`' for e in eids)}")
    return "\n".join(parts)


def _synthesis_block(topics: Sequence[Mapping[str, Any]]) -> str:
    """Cross-source topic state, one bullet per topic (#69).

    Rendered from topic records produced by ``jev_classifier.consolidate``; no
    wording is invented here. Disagreement stays visible: a conflicted topic
    names every live label and current claim id, and retired claims are named
    rather than silently dropped.
    """
    from jev_classifier.consolidate import topic_digest

    lines: list[str] = []
    for topic in topics:
        lines.append(f"- **{topic['about']}** — {topic_digest(topic)}")
        retired = topic.get("retired") or []
        if retired:
            rids = ", ".join(str(c.get("id") or "?") for c in retired)
            lines.append(f"  - retired (superseded or outside valid time): {rids}")
    return "\n".join(lines)


def _validate_topics(topics: Sequence[Mapping[str, Any]]) -> None:
    """Fail closed on topic records that do not look like consolidate output.

    Checks shape only (keys, state vocabulary, list types); it never recomputes
    or repairs a topic, because a repaired state here would silently disagree
    with the consolidation module's own verdict.
    """
    from jev_classifier.consolidate import TOPIC_STATES

    if isinstance(topics, (str, bytes)) or not isinstance(topics, Sequence):
        raise AssembleError("topics must be a sequence of topic objects")
    for i, topic in enumerate(topics):
        if not isinstance(topic, Mapping):
            raise AssembleError(f"topics[{i}] must be an object")
        for key in ("about", "state", "labels", "evaluated_at", "current", "retired"):
            if key not in topic:
                raise AssembleError(f"topics[{i}] missing key: {key}")
        if not isinstance(topic["about"], str) or not topic["about"].strip():
            raise AssembleError(f"topics[{i}].about must be a non-empty string")
        if topic["state"] not in TOPIC_STATES:
            raise AssembleError(
                f"topics[{i}].state {topic['state']!r} not in {list(TOPIC_STATES)}"
            )
        for key in ("labels", "current", "retired"):
            val = topic[key]
            if isinstance(val, (str, bytes)) or not isinstance(val, Sequence):
                raise AssembleError(f"topics[{i}].{key} must be a list")


def _provenance_block(claims: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "| Claim | Recorded at | Model | Epistemic status |",
        "|-------|-------------|---------|------------------|",
    ]
    for i, c in enumerate(claims):
        cid = c.get("id") or f"C{i + 1}"
        lines.append(
            f"| {cid} | {c['recorded_at']} | `{c['model']}` | {c['epistemic_status']} |"
        )
    return "\n".join(lines)


def _lineage_block(claims: Sequence[Mapping[str, Any]]) -> str:
    lines: list[str] = []
    for i, c in enumerate(claims):
        cid = c.get("id") or f"C{i + 1}"
        supersedes = c.get("supersedes")
        valid_from = c.get("valid_from")
        valid_to = c.get("valid_to")
        independence = c.get("independence_class")
        lines.append(f"- **{cid}**")
        if supersedes:
            lines.append(f"  - supersedes: `{supersedes}`")
        else:
            lines.append("  - supersedes: _(none)_")
        if valid_from or valid_to:
            lines.append(f"  - valid_time: [{valid_from or '?'} .. {valid_to or '?'}]")
        if independence:
            lines.append(f"  - independence_class: `{independence}`")
    if not lines:
        lines.append("- _(no claims)_")
    return "\n".join(lines)


def _citations_block(claims: Sequence[Mapping[str, Any]]) -> str:
    # Collect unique evidence ids with backrefs to claims
    index: dict[str, list[str]] = {}
    for i, c in enumerate(claims):
        cid = str(c.get("id") or f"C{i + 1}")
        for eid in _evidence_ids(c):
            index.setdefault(eid, []).append(cid)
    lines = [
        "| Evidence ID | Cited by claims |",
        "|-------------|-----------------|",
    ]
    for eid in sorted(index.keys()):
        cited = ", ".join(index[eid])
        lines.append(f"| `{eid}` | {cited} |")
    return "\n".join(lines)


def assemble_paper(
    claims: Sequence[Mapping[str, Any]],
    *,
    title: str = "JEV-classified research sketch",
    abstract: str | None = None,
    assembled_at: str | None = None,
    topics: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Build a medium-quality markdown paper skeleton from claim records.

    ``topics`` (optional) is a sequence of topic records from
    ``jev_classifier.consolidate.consolidate_claims``; when given, a Synthesis
    section renders the cross-source state between Abstract and Claims. Passing
    malformed topics fails closed rather than dropping the section.

    Deterministic: same inputs -> same markdown (aside from ``assembled_at`` default).
    """
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        raise AssembleError("claims must be a sequence of claim objects")
    if not claims:
        raise AssembleError("claims must be non-empty")
    normalized = [_require_claim(c, i) for i, c in enumerate(claims)]
    # validate evidence ids exist
    for c in normalized:
        _evidence_ids(c)

    ts = assembled_at or datetime.now(timezone.utc).isoformat()
    labels = sorted({c["label"] for c in normalized})
    if abstract is None:
        abstract = (
            "This sketch was assembled deterministically from "
            f"{len(normalized)} validated claim record(s). "
            f"Closed labels present: {', '.join(f'`{x}`' for x in labels)}. "
            "No non-JEV LLM was used to invent labels or prose; body text is "
            "template-generated from claim JSON fields only."
        )

    claim_blocks = "\n".join(_claim_bullet(c, i) for i, c in enumerate(normalized))
    sections = {
        "Title": f"# {title}",
        "Abstract": f"## Abstract\n\n{abstract}",
        "Claims": f"## Claims\n\n{claim_blocks}",
        "Provenance": f"## Provenance\n\n{_provenance_block(normalized)}\n\n_Assembled at: `{ts}`_",
        "Lineage": f"## Lineage\n\n{_lineage_block(normalized)}",
        "Citations": f"## Citations\n\n{_citations_block(normalized)}",
    }
    order = list(REQUIRED_SECTIONS)
    if topics is not None:
        _validate_topics(topics)
        sections["Synthesis"] = f"## Synthesis\n\n{_synthesis_block(topics)}"
        order.insert(order.index("Claims"), "Synthesis")
    body = "\n\n".join(sections[name] for name in order)
    validate_paper_markdown(body, claims=normalized)
    return body + "\n"


def validate_paper_markdown(
    markdown: str,
    *,
    claims: Iterable[Mapping[str, Any]] | None = None,
) -> None:
    """Fail closed if required sections or evidence citations are missing."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise AssembleError("paper markdown must be a non-empty string")
    for name in REQUIRED_SECTIONS:
        if name == "Title":
            if not markdown.lstrip().startswith("# "):
                raise AssembleError("missing Title heading (# ...)")
            continue
        heading = f"## {name}"
        if heading not in markdown:
            raise AssembleError(f"missing required section: {name}")
    if claims is not None:
        for i, c in enumerate(claims):
            for eid in _evidence_ids(c):
                token = f"`{eid}`"
                if token not in markdown:
                    raise AssembleError(
                        f"evidence id {eid!r} from claim[{i}] not cited in paper"
                    )
