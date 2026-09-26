#!/usr/bin/env python3
"""Smoke: run BIAS_PACK_V1 once against pinned typesafe/jev-1.13.

Skips cleanly (exit 0) when OPENROUTER_API_KEY is absent.
Loads .env from repo root without printing values.
Prints ONLY non-secret fields: pack_id, model, per-question choice/p_yes,
raised_flags. Never prints API keys, Authorization headers, or raw auth bodies.
Fail closed: provider/parse errors → non-zero exit (no fabricated labels).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

ENV_API_KEY = "OPENROUTER_API_KEY"
STATE_PATH = REPO_ROOT / "tests" / "fixtures" / "bias" / "claim_source_state.json"


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        if not env_path.is_file():
            return
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        return
    load_dotenv(env_path, override=False)


def _has_api_key() -> bool:
    return bool(os.environ.get(ENV_API_KEY, "").strip())


def _safe_summary(record: dict) -> dict:
    """Strip to non-secret fields only."""
    signals_out: dict = {}
    for qid, sig in (record.get("signals") or {}).items():
        if not isinstance(sig, dict):
            continue
        if sig.get("type") == "choice":
            signals_out[qid] = {
                "type": "choice",
                "choice": sig.get("choice"),
                "confidence": sig.get("confidence"),
                "probability_keys": sorted((sig.get("probabilities") or {}).keys()),
            }
        elif sig.get("type") == "noul":
            signals_out[qid] = {
                "type": "noul",
                "label": sig.get("label"),
                "p_yes": sig.get("p_yes"),
            }
    return {
        "pack_id": record.get("pack_id"),
        "pack_version": record.get("pack_version"),
        "model": record.get("model"),
        "raised_flags": record.get("raised_flags"),
        "signals": signals_out,
        "question_ids": record.get("question_ids"),
    }


def run_live_bias_smoke() -> dict:
    """Call Decisions with BIAS_PACK_V1; return BiasSignalRecord.to_dict().

    Raises DecisionsError / NormalizeError on failure (fail closed).
    """
    from jev_classifier.bias import apply_normalized_answers, get_pack
    from jev_classifier.decisions import DecisionsClient
    from jev_classifier.normalize import (
        NormalizeError,
        extract_choice_from_response,
        extract_noul_from_response,
    )

    pack = get_pack("bias_pack_v1")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    client = DecisionsClient()
    raw = client.decide(state=state, questions=pack.as_jev_questions())

    # Fail-closed per-question extract into raw answer bodies for apply_*
    answers: dict = {}
    body = raw if isinstance(raw, dict) else {}
    ans_map = body.get("answers")
    if not isinstance(ans_map, dict):
        raise NormalizeError("answers missing or not an object", kind="parse_error")

    for q in pack.questions:
        if q.id not in ans_map:
            raise NormalizeError(f"answers missing question_id {q.id!r}", kind="parse_error")
        # Re-validate via extract helpers (also checks legal sets for choice)
        if q.type == "choice":
            from jev_classifier.bias import legal_options_for

            extracted = extract_choice_from_response(
                raw,
                question_id=q.id,
                legal_options=legal_options_for(pack, q.id),
            )
            answers[q.id] = {
                "type": "choice",
                "choice": extracted["choice"],
                "probabilities": extracted.get("probabilities"),
                "confidence": extracted.get("confidence"),
            }
        else:
            extracted = extract_noul_from_response(raw, question_id=q.id)
            answers[q.id] = {
                "type": "noul",
                "p_yes": extracted["p_yes"],
            }

    model = body.get("model") if isinstance(body.get("model"), str) else client.model
    record = apply_normalized_answers(
        pack,
        answers,
        model=model,
        evidence={"state_path": str(STATE_PATH.relative_to(REPO_ROOT)).replace("\\", "/")},
    )
    return record.to_dict()


def main() -> int:
    _load_dotenv()
    if not _has_api_key():
        print(
            "smoke_bias: SKIP -- OPENROUTER_API_KEY absent "
            "(set it to run live BIAS_PACK_V1 against typesafe/jev-1.13)"
        )
        return 0

    from jev_classifier.decisions import DecisionsError
    from jev_classifier.normalize import NormalizeError

    try:
        record = run_live_bias_smoke()
    except DecisionsError as exc:
        print(f"smoke_bias: provider_error: {exc}", file=sys.stderr)
        return 3
    except NormalizeError as exc:
        print(f"smoke_bias: parse_error: {exc}", file=sys.stderr)
        return 4
    except Exception as exc:  # noqa: BLE001 — surface unexpected fail-closed
        print(f"smoke_bias: error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 5

    print(json.dumps(_safe_summary(record), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())