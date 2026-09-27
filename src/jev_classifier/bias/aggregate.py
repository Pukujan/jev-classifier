"""Apply normalized JEV answers to a bias pack ? BiasSignalRecord (local only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from jev_classifier.bias.packs import BiasPack, aggregate_bias_answers, legal_options_for
from jev_classifier.normalize import (
    NormalizeError,
    normalize_choice_answer,
    normalize_noul_answer,
    normalize_score_answer,
)


@dataclass(frozen=True)
class BiasSignalRecord:
    pack_id: str
    pack_version: str
    signals: dict[str, Any]
    raised_flags: list[str]
    question_ids: list[str]
    model: str | None
    recorded_at: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_normalized_answers(
    pack: BiasPack,
    answers: Mapping[str, Any],
    *,
    model: str | None = None,
    evidence: Mapping[str, Any] | None = None,
    recorded_at: str | None = None,
    yes_threshold: float = 0.5,
) -> BiasSignalRecord:
    """Normalize raw per-question answer bodies against pack legal sets; aggregate.

    ``answers`` maps question_id ? raw answer object (as Decisions would return
    under ``answers.<id>``). Fail closed on missing/out-of-set/malformed.
    """
    normalized: dict[str, dict[str, Any]] = {}
    for q in pack.questions:
        if q.id not in answers:
            raise NormalizeError(f"missing answer for {q.id!r}", kind="parse_error")
        raw = answers[q.id]
        if q.type == "choice":
            normalized[q.id] = normalize_choice_answer(
                raw,
                legal_options=legal_options_for(pack, q.id),
                question_id=q.id,
            )
        elif q.type == "score":
            if not q.legend:
                raise NormalizeError(
                    f"score question {q.id!r} missing legend", kind="parse_error"
                )
            normalized[q.id] = normalize_score_answer(
                raw,
                legal_scores=q.legend,
                question_id=q.id,
            )
        elif q.type == "noul":
            normalized[q.id] = normalize_noul_answer(
                raw,
                question_id=q.id,
                yes_threshold=yes_threshold,
            )
        else:
            raise NormalizeError(f"{q.id}: bad type {q.type!r}", kind="parse_error")
    agg = aggregate_bias_answers(pack, normalized)
    return BiasSignalRecord(
        pack_id=agg["pack_id"],
        pack_version=agg["pack_version"],
        signals=agg["signals"],
        raised_flags=list(agg["raised_flags"]),
        question_ids=list(agg["question_ids"]),
        model=model,
        recorded_at=recorded_at or datetime.now(timezone.utc).isoformat(),
        evidence=dict(evidence or {}),
    )
