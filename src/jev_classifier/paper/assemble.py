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
) -> str:
    """Build a medium-quality markdown paper skeleton from claim records.

    Deterministic: same inputs ? same markdown (aside from ``assembled_at`` default).
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
    body = "\n\n".join(sections[name] for name in REQUIRED_SECTIONS)
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
