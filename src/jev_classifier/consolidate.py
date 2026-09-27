"""Deterministic cross-source claim consolidation (#69).

Correlates validated claim records into topics by the explicit ``about``
subject key carried on each record, then derives each topic's state from claim
fields only — never from text similarity and never from a model call. This is
the join the classifier was missing: fragments from co-related sources produce
individual claims (M4), and the paper assembler renders claim lists (M7), but
nothing between them decided "are these claims about the same thing, do they
agree, and which one currently holds?" (owner kickoff: epistemic bitemporal
summarization over *multiple co-related* sources).

Rules (all fail-closed; disagreement is preserved, never averaged):

- Correlation is by ``about``. A claim without ``about`` cannot join any topic
  and raises — inferring subjects from wording would be a model judgment
  wearing a deterministic costume.
- Agreement requires the same label from at least two *distinct* evidence
  sources; a second claim from the same source is repetition, not corroboration.
- Conflict is same topic, differing labels, both currently valid. Both sides
  are reported with their provenance; the tool never picks a winner by count.
- Current-holds resolution is bitemporal: a claim is superseded when another
  claim in the topic declares ``supersedes`` pointing at it; ``valid_to`` in
  the past (relative to the evaluation instant) marks a claim no longer valid.
  Timestamps are parsed strictly here (M5's validator deliberately does not
  parse them); unparseable, mixed naive/aware, dangling, or cyclic supersession
  chains raise instead of guessing an order.
- Duplicate claim ids inside one run raise: two records claiming one id is an
  integrity fault, not a merge candidate.

No I/O, no network, no model: pure functions over validated claim mappings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

SCHEMA_VERSION = "1"

TOPIC_STATES = ("agreement", "conflict", "single-source", "unknown")


class ConsolidationError(ValueError):
    """Raised when claims cannot be consolidated honestly."""


def _parse_instant(value: Any, *, claim_id: str, field: str) -> datetime | None:
    """Strict ISO-8601 parse; None passes through as 'open-ended'."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConsolidationError(
            f"claim {claim_id!r}: {field} must be a non-empty ISO-8601 string or null"
        )
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ConsolidationError(
            f"claim {claim_id!r}: {field} {value!r} is not ISO-8601 ({exc})"
        ) from exc
    if stamp.tzinfo is None:
        raise ConsolidationError(
            f"claim {claim_id!r}: {field} {value!r} has no timezone offset; "
            "naive and aware times cannot be ordered against each other"
        )
    return stamp


def _check_coherence(claims: Sequence[Mapping[str, Any]]) -> None:
    """Reject duplicate ids and an all-anonymous batch.

    Ids are what make supersession and per-topic provenance auditable, so a run
    where no claim carries one cannot be consolidated honestly at all.
    """
    ids = [c.get("id") for c in claims]
    named = [i for i in ids if i]
    if len(claims) > 1 and not named:
        raise ConsolidationError(
            "every claim is missing id; consolidation needs ids to record "
            "supersession and provenance honestly"
        )
    dupes = sorted({i for i in named if list(named).count(i) > 1})
    if dupes:
        raise ConsolidationError(f"duplicate claim ids: {dupes}")


def _source_of(claim: Mapping[str, Any]) -> str:
    """Evidence source attribution, most-specific key first."""
    ev = claim.get("evidence") or {}
    for key in ("source_id", "source", "uri", "path", "fragment_id"):
        val = ev.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    raise ConsolidationError(
        f"claim {claim.get('id')!r} has no evidence source key to attribute it to"
    )


def _is_valid_at(claim: Mapping[str, Any], instant: datetime) -> bool:
    cid = str(claim.get("id") or "?")
    start = _parse_instant(claim.get("valid_from"), claim_id=cid, field="valid_from")
    end = _parse_instant(claim.get("valid_to"), claim_id=cid, field="valid_to")
    if start is not None and end is not None and start > end:
        raise ConsolidationError(
            f"claim {cid}: valid_from {claim['valid_from']!r} is after "
            f"valid_to {claim['valid_to']!r}"
        )
    if start is not None and start > instant:
        return False
    if end is not None and instant >= end:
        return False
    return True


def _assert_timezones_comparable(claims: Sequence[Mapping[str, Any]]) -> None:
    """Reject a mix of naive and aware instants across the run."""
    aware: bool | None = None
    for c in claims:
        cid = str(c.get("id") or "?")
        for field in ("valid_from", "valid_to", "recorded_at"):
            stamp = _parse_instant(c.get(field), claim_id=cid, field=field)
            if stamp is None:
                continue
            flag = stamp.tzinfo is not None
            if aware is None:
                aware = flag
            elif flag != aware:
                raise ConsolidationError(
                    f"claim {cid}: mixes timezone-aware and naive times; "
                    "ordering would be a guess"
                )


def _resolve_supersession(claims: Sequence[Mapping[str, Any]]) -> set[str]:
    """Ids superseded by another claim in the run, with dangling/cycle rejection."""
    by_id = {c.get("id") for c in claims if c.get("id")}
    superseded: set[str] = set()
    successors: dict[str, list[str]] = {}
    for claim in claims:
        target = claim.get("supersedes")
        if target is None:
            continue
        if target not in by_id:
            raise ConsolidationError(
                f"claim {claim.get('id')!r} supersedes unknown claim {target!r}; "
                "a dangling revision pointer must not be treated as fresh"
            )
        superseded.add(str(target))
        if claim.get("id"):
            successors.setdefault(str(target), []).append(str(claim["id"]))

    def walk(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            raise ConsolidationError(
                f"cyclic supersession chain: {' -> '.join((*path, node))}"
            )
        for nxt in successors.get(node, ()):
            walk(nxt, (*path, node))

    for start in sorted(successors):
        walk(start, ())
    return superseded


def consolidate_claims(
    claims: Sequence[Mapping[str, Any]],
    *,
    at: str,
) -> list[dict[str, Any]]:
    """Group validated claim records by ``about`` and derive topic state.

    ``at`` is the evaluation instant (timezone-aware ISO-8601): "what holds as
    of when". It is required explicitly because a hidden clock would make the
    same inputs produce different outputs on different days, and a classifier
    that drifts with the wall clock is not deterministic.
    """
    instant = _parse_instant(at, claim_id="<at>", field="at")
    if instant is None:
        raise ConsolidationError("at must be a timezone-aware ISO-8601 instant")
    claims = list(claims)
    if not claims:
        return []
    _check_coherence(claims)
    _assert_timezones_comparable(claims)
    superseded = _resolve_supersession(claims)

    topics: dict[str, list[Mapping[str, Any]]] = {}
    for claim in claims:
        subject = claim.get("about")
        if not isinstance(subject, str) or not subject.strip():
            raise ConsolidationError(
                f"claim {claim.get('id')!r} has no about key; correlating by "
                "wording would be an inference, not a rule"
            )
        topics.setdefault(subject.strip(), []).append(claim)

    out: list[dict[str, Any]] = []
    for subject in sorted(topics):
        members = sorted(topics[subject], key=lambda c: str(c.get("id") or ""))
        live: list[Mapping[str, Any]] = []
        retired: list[Mapping[str, Any]] = []
        for claim in members:
            cid = claim.get("id")
            if cid in superseded:
                retired.append(claim)
            elif not _is_valid_at(claim, instant):
                retired.append(claim)
            else:
                live.append(claim)
        labels = sorted({c["label"] for c in live})
        # attribution covers live claims only: a retired claim stays reported
        # in the topic but cannot vote on state, so it never needs a source key
        sources = sorted({_source_of(c) for c in live}) if live else []
        if not labels:
            state = "unknown"
        elif len(labels) > 1:
            state = "conflict"
        elif len(sources) > 1:
            state = "agreement"
        else:
            state = "single-source"
        out.append({
            "schema_version": SCHEMA_VERSION,
            "about": subject,
            "state": state,
            "labels": labels,
            "distinct_sources": sources,
            "evaluated_at": at,
            "current": [dict(c) for c in live],
            "retired": [dict(c) for c in retired],
            "claim_ids": [c.get("id") for c in members],
        })
    return out


def topic_digest(topic: Mapping[str, Any]) -> str:
    """One-line honest summary for paper assembly (no numbers invented)."""
    state = topic["state"]
    current = topic.get("current") or []
    ids = ", ".join(str(c.get("id") or "?") for c in current) or "-"
    srcs = len(topic.get("distinct_sources", []))
    retired = len(topic.get("retired", []))
    stamp = topic["evaluated_at"]
    if state == "conflict":
        return (f"disputed ({' vs '.join(topic['labels'])}) across {srcs} "
                f"sources as of {stamp}: {ids}")
    if state == "agreement":
        return (f"corroborated ({topic['labels'][0]}) by {srcs} sources as of "
                f"{stamp}: {ids}")
    if state == "single-source":
        return f"single-source ({topic['labels'][0]}) as of {stamp}: {ids}"
    return f"no currently-valid claim as of {stamp} (retired: {retired})"
