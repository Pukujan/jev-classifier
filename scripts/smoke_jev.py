#!/usr/bin/env python3
"""Smoke: one OpenRouter Decisions choice call with pinned typesafe/jev-1.13.

Loads .env from repo root without printing values.
Prints ONLY: choice, probability keys, model, confidence.
Exit 0 on success; non-zero if key missing or call/normalize fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QUESTION_ID = "claim_kind"
LEGAL = frozenset({"empirical_finding", "method_claim", "opinion", "other"})


def _load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    try:
        from dotenv import load_dotenv
    except ImportError:
        # Minimal fallback: parse KEY=VAL lines without printing values
        if not env_path.is_file():
            return
        import os

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


def main() -> int:
    _load_dotenv()
    from jev_classifier.decisions import DecisionsClient, DecisionsError
    from jev_classifier.normalize import NormalizeError, extract_choice_from_response

    try:
        client = DecisionsClient()
    except DecisionsError as exc:
        print(f"smoke_jev: config_error: {exc}", file=sys.stderr)
        return 2

    state = {
        "fragment": (
            "In a controlled study of 120 participants, the treatment group "
            "showed a statistically significant improvement (p < 0.01) on the "
            "primary endpoint compared to placebo."
        ),
        "source": "synthetic_fixture",
    }
    questions = {
        QUESTION_ID: {
            "type": "choice",
            "instructions": (
                "Classify the research fragment into exactly one claim kind."
            ),
            "criteria": {
                "empirical_finding": (
                    "Reports observed data, measurements, or statistical results "
                    "from a study or experiment."
                ),
                "method_claim": (
                    "Describes a method, procedure, architecture, or how something "
                    "was done rather than what was observed."
                ),
                "opinion": (
                    "Authorial judgment, speculation, or recommendation without "
                    "direct empirical support in the fragment."
                ),
                "other": (
                    "Does not clearly fit empirical finding, method claim, or opinion."
                ),
            },
        }
    }

    try:
        raw = client.decide(state=state, questions=questions)
        normalized = extract_choice_from_response(
            raw,
            question_id=QUESTION_ID,
            legal_options=LEGAL,
        )
    except DecisionsError as exc:
        print(f"smoke_jev: provider_error: {exc}", file=sys.stderr)
        return 3
    except NormalizeError as exc:
        print(f"smoke_jev: parse_error: {exc}", file=sys.stderr)
        return 4

    probs = normalized.get("probabilities") or {}
    summary = {
        "choice": normalized["choice"],
        "probability_keys": sorted(probs.keys()),
        "model": normalized.get("model"),
        "confidence": normalized.get("confidence"),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
