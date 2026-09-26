"""Closed bias question packs for claim+source state (JEV choice/noul only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from jev_classifier.normalize import NormalizeError


QuestionType = Literal["choice", "noul"]


@dataclass(frozen=True)
class BiasQuestion:
    id: str
    type: QuestionType
    instructions: str
    criteria: dict[str, str] | None = None  # required for choice
    signal: str = ""  # local aggregation key, e.g. source_authority_inflation


@dataclass(frozen=True)
class BiasPack:
    pack_id: str
    version: str
    description: str
    questions: tuple[BiasQuestion, ...]

    def question_ids(self) -> list[str]:
        return [q.id for q in self.questions]

    def as_jev_questions(self) -> dict[str, dict[str, Any]]:
        """Build OpenRouter Decisions ``questions`` map (no live call)."""
        out: dict[str, dict[str, Any]] = {}
        for q in self.questions:
            if q.type == "choice":
                if not q.criteria:
                    raise NormalizeError(
                        f"choice question {q.id!r} missing criteria",
                        kind="parse_error",
                    )
                out[q.id] = {
                    "type": "choice",
                    "instructions": q.instructions,
                    "criteria": dict(q.criteria),
                }
            elif q.type == "noul":
                out[q.id] = {
                    "type": "noul",
                    "instructions": q.instructions,
                }
            else:
                raise NormalizeError(
                    f"unsupported question type {q.type!r}",
                    kind="parse_error",
                )
        return out


def validate_pack(pack: BiasPack) -> None:
    if not pack.pack_id or not pack.version:
        raise NormalizeError("pack_id and version required", kind="parse_error")
    if len(pack.questions) < 1:
        raise NormalizeError("pack must contain at least one question", kind="parse_error")
    seen: set[str] = set()
    for q in pack.questions:
        if not q.id or q.id in seen:
            raise NormalizeError(f"duplicate or empty question id: {q.id!r}", kind="parse_error")
        seen.add(q.id)
        if q.type == "choice":
            if not q.criteria or len(q.criteria) < 2:
                raise NormalizeError(
                    f"{q.id}: choice criteria must have >=2 options",
                    kind="parse_error",
                )
            for opt, desc in q.criteria.items():
                if not opt or not isinstance(desc, str) or not desc.strip():
                    raise NormalizeError(
                        f"{q.id}: each choice option needs non-empty criteria text",
                        kind="parse_error",
                    )
        elif q.type == "noul":
            if not q.instructions.strip():
                raise NormalizeError(f"{q.id}: noul instructions required", kind="parse_error")
        else:
            raise NormalizeError(f"{q.id}: bad type {q.type!r}", kind="parse_error")


def legal_options_for(pack: BiasPack, question_id: str) -> frozenset[str]:
    for q in pack.questions:
        if q.id != question_id:
            continue
        if q.type == "choice":
            assert q.criteria is not None
            return frozenset(q.criteria.keys())
        if q.type == "noul":
            return frozenset({"yes", "no"})
        raise NormalizeError(f"bad type for {question_id}", kind="parse_error")
    raise NormalizeError(f"unknown question_id {question_id!r}", kind="parse_error")


def aggregate_bias_answers(
    pack: BiasPack,
    normalized: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Local aggregation only ? never invents missing answers."""
    validate_pack(pack)
    missing = [qid for qid in pack.question_ids() if qid not in normalized]
    if missing:
        raise NormalizeError(
            f"missing normalized answers for: {missing}",
            kind="parse_error",
        )
    signals: dict[str, Any] = {}
    flags: list[str] = []
    for q in pack.questions:
        ans = normalized[q.id]
        key = q.signal or q.id
        if q.type == "choice":
            choice = ans.get("choice")
            legal = legal_options_for(pack, q.id)
            if choice not in legal:
                raise NormalizeError(
                    f"{q.id}: choice {choice!r} not in {sorted(legal)}",
                    kind="parse_error",
                )
            signals[key] = {
                "type": "choice",
                "choice": choice,
                "probabilities": ans.get("probabilities"),
                "confidence": ans.get("confidence"),
            }
            # Heuristic local flags for concerning options (code, not LLM)
            if choice in {"inflated", "present", "high", "yes_biased"}:
                flags.append(key)
        else:
            label = ans.get("label")
            if label not in {"yes", "no"}:
                raise NormalizeError(
                    f"{q.id}: noul label must be yes/no after normalize",
                    kind="parse_error",
                )
            signals[key] = {
                "type": "noul",
                "label": label,
                "p_yes": ans.get("p_yes"),
            }
            if label == "yes":
                flags.append(key)
    return {
        "pack_id": pack.pack_id,
        "pack_version": pack.version,
        "signals": signals,
        "raised_flags": sorted(set(flags)),
        "question_ids": pack.question_ids(),
    }


# --- v1 pack: common LLM bias signals over claim+source state ---

BIAS_PACK_V1 = BiasPack(
    pack_id="bias_pack_v1",
    version="1.0.0",
    description=(
        "Closed JEV questions for common LLM bias signals over claim+source state. "
        "Deterministic labels via TypeSafe JEV only when live; unit tests use fixtures."
    ),
    questions=(
        BiasQuestion(
            id="source_authority_inflation",
            type="choice",
            signal="source_authority_inflation",
            instructions=(
                "Given the claim label and source metadata in state, does the claim "
                "over-weight source prestige/authority beyond the evidence strength?"
            ),
            criteria={
                "absent": "No authority inflation; claim weight matches evidence.",
                "mild": "Mild prestige lean without overturning the evidence.",
                "inflated": "Authority/prestige clearly outweighs evidence strength.",
                "unknown": "Insufficient source metadata to judge.",
            },
        ),
        BiasQuestion(
            id="recency_bias",
            type="choice",
            signal="recency_bias",
            instructions=(
                "Does the claim preferentially trust newer fragments solely because "
                "they are newer, ignoring stronger older evidence in state?"
            ),
            criteria={
                "absent": "Recency is not driving the judgment.",
                "mild": "Slight recency preference with residual attention to older evidence.",
                "present": "Newer material dominates despite weaker support.",
                "unknown": "Timestamps/ordering insufficient to judge.",
            },
        ),
        BiasQuestion(
            id="confirmation_cherry_pick",
            type="choice",
            signal="confirmation_cherry_pick",
            instructions=(
                "Does the claim cherry-pick confirming fragments and ignore "
                "contradictory evidence present in state?"
            ),
            criteria={
                "absent": "Confirming and disconfirming evidence treated proportionally.",
                "mild": "Slight confirming lean.",
                "present": "Clear cherry-picking of confirming fragments.",
                "unknown": "Evidence set too thin to judge.",
            },
        ),
        BiasQuestion(
            id="anthropomorphism",
            type="noul",
            signal="anthropomorphism",
            instructions=(
                "Does the claim text attribute human-like intentions, feelings, or "
                "agency to the model/system beyond metaphorical shorthand? Answer yes "
                "if anthropomorphism is present."
            ),
        ),
        BiasQuestion(
            id="overconfidence",
            type="noul",
            signal="overconfidence",
            instructions=(
                "Is the claim stated with certainty that exceeds the support in the "
                "source fragments (overconfidence)? Answer yes if overconfident."
            ),
        ),
    ),
)


_PACKS: dict[str, BiasPack] = {
    BIAS_PACK_V1.pack_id: BIAS_PACK_V1,
}


def get_pack(pack_id: str = "bias_pack_v1") -> BiasPack:
    if pack_id not in _PACKS:
        raise NormalizeError(f"unknown bias pack {pack_id!r}", kind="parse_error")
    pack = _PACKS[pack_id]
    validate_pack(pack)
    return pack
