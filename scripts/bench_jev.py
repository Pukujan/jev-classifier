#!/usr/bin/env python3
"""JEV-only synthetic-plumbing bench over the committed first-party fixtures (#57).

Runs each sample in tests/fixtures/datasets/*.json through ONE atomic JEV
`choice` question (pinned typesafe/jev-1.13 via the same DecisionsClient as
smoke_jev.py), then scores exact-match accuracy in PURE PYTHON.

WHAT THIS MEASURES: whether the bench plumbing (fixture load -> JEV request ->
normalize -> score -> report) works end to end on live JEV, and how the pinned
model performs on deliberately-classifiable first-party synthetic label shapes.

WHAT THIS DOES NOT MEASURE: it is NOT the #21 quality target. #21's bar is
claim-level F1 >= 0.80 against human-reviewed reference graphs of real papers
(hidden holdout). These fixtures are synthetic, tiny (17 samples), 3-4 label
sets written to be classifiable (arbiter ruling on #33: "plumbing, not
benchmark"), and the numbers here are labeled *_accuracy / plumbing-F1 on
purpose. Never quote them as research fidelity.

Modes:
  live (default)     sequential JEV calls; MacBook owner-bench host only.
  --stub             deterministic offline stub decider (keyword rules), used
                     by tests/CI; never contacts the network.

Exit codes: 0 ok, 2 config (live without key/client), 3 provider/parse error
(fail closed: the affected sample is counted invalid, run continues; a total
failure to answer any sample exits 3).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = {
    "claim_type": REPO_ROOT / "tests" / "fixtures" / "datasets" / "claim_type_shapes.json",
    "contradiction": REPO_ROOT / "tests" / "fixtures" / "datasets" / "contradiction_shapes.json",
}

# Per-label criteria (atomic question; every option described, per AGENTS.md).
CRITERIA = {
    "background": "States general context, prior work, or established knowledge.",
    "method": "Describes how something was done, built, or measured.",
    "result": "Reports an observation, measurement, or outcome.",
    "entailment": "The hypothesis follows from / is supported by the premise.",
    "contrasting": "The hypothesis conflicts with or contradicts the premise.",
    "neutral": "The premise neither supports nor conflicts with the hypothesis.",
    "reasoning": "The hypothesis requires multi-step inference from the premise.",
}

BENCH_NAME = "jev_synthetic_plumbing_v1"
DISCLAIMER = (
    "Synthetic plumbing bench: numbers measure the bench path and pinned-model "
    "behavior on tiny first-party fixtures, NOT #21 claim-level fidelity and NOT "
    "a hidden-holdout result. Do not quote as research quality."
)


def load_fixtures() -> list[dict]:
    """Return flat sample list with task, gold label, text, fixture hash."""
    rows = []
    for task, path in FIXTURES.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        fhash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        for s in data["samples"]:
            text = s.get("text") or f"PREMISE: {s.get('premise','')}\nHYPOTHESIS: {s.get('hypothesis','')}"
            rows.append({
                "task": task,
                "sample_id": s["id"],
                "gold": s["label"],
                "text": text,
                "options": list(data["label_set"]),
                "fixture_sha256_16": fhash,
            })
    return rows


def _stub_decide(row: dict) -> str:
    """Deterministic offline stub: keyword rules ONLY for plumbing checks.

    Deliberately imperfect (it will miss some gold labels) so accuracy is a
    real measurement of the scoring path, not a tautology.
    """
    t = row["text"].lower()
    if row["task"] == "claim_type":
        if any(w in t for w in ("we ", "using", "measured", "protocol", "model maps")):
            return "method"
        if any(w in t for w in ("showed", "reported", "found", "achieved", "improved", "occurred")):
            return "result"
        if any(w in t for w in ("prior", "known", "established", "typically", "recurring")):
            return "background"
        return "unknown"
    # contradiction
    if "conflict" in t or "never" in t or "no " in t or "disagree" in t:
        return "contrasting"
    if "therefore" in t or "implies" in t or "so " in t:
        return "reasoning"
    if "follows" in t or "also" in t or "both" in t:
        return "entailment"
    return "neutral"


def _live_decider():
    from jev_classifier.decisions import DecisionsClient
    from jev_classifier.normalize import extract_choice_from_response

    client = DecisionsClient()

    def decide(row: dict) -> tuple[str, dict]:
        legal = set(row["options"]) | {"unknown"}
        state = {"sample_text": row["text"], "source": BENCH_NAME}
        questions = {
            row["sample_id"]: {
                "type": "choice",
                "instructions": (
                    "Classify this research text into exactly one label. If none "
                    "clearly fits, answer unknown."
                ),
                "criteria": {k: CRITERIA[k] for k in row["options"]}
                | {"unknown": "No listed label clearly applies."},
            }
        }
        raw = client.decide(state=state, questions=questions)
        norm = extract_choice_from_response(
            raw, question_id=row["sample_id"], legal_options=legal
        )
        meta = {
            "confidence": norm.get("confidence"),
            "model_surfaced": norm.get("model"),
            "probabilities": norm.get("probabilities"),
        }
        return norm["choice"], meta

    return decide


def score(results: list[dict]) -> dict:
    """Pure-Python exact-match + macro-F1 over valid answers."""
    per_task: dict[str, dict] = {}
    for task in sorted({r["task"] for r in results}):
        rows = [r for r in results if r["task"] == task]
        valid = [r for r in rows if not r.get("invalid")]
        correct = sum(1 for r in valid if r["pred"] == r["gold"])
        labels = sorted({r["gold"] for r in rows})
        f1s = []
        for lab in labels:
            tp = sum(1 for r in valid if r["gold"] == lab and r["pred"] == lab)
            fp = sum(1 for r in valid if r["gold"] != lab and r["pred"] == lab)
            fn = sum(1 for r in valid if r["gold"] == lab and r["pred"] != lab)
            prec = tp / (tp + fp) if (tp + fp) else 0.0
            rec = tp / (tp + fn) if (tp + fn) else 0.0
            f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
        per_task[task] = {
            "samples": len(rows),
            "valid": len(valid),
            "invalid_or_out_of_set": len(rows) - len(valid),
            "correct": correct,
            "synthetic_plumbing_accuracy": round(correct / len(valid), 4) if valid else None,
            "macro_f1_synthetic_only": round(sum(f1s) / len(f1s), 4) if f1s else None,
        }
    return per_task


def host_record() -> dict:
    rec = {
        "platform": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        import shutil
        du = shutil.disk_usage(REPO_ROOT)
        rec["free_gb"] = round(du.free / 1e9, 1)
    except OSError:
        pass
    try:
        rec["load_avg_1m"] = round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        pass
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stub", action="store_true",
                    help="offline deterministic stub (tests/CI); no network")
    ap.add_argument("--report", default=None,
                    help="write JSON report to this path (default: none)")
    args = ap.parse_args(argv)

    rows = load_fixtures()
    if args.stub:
        decide = _stub_decide
        def call(row):  # normalize to (pred, meta)
            return decide(row), {}
    else:
        try:
            # Live mode needs OPENROUTER_API_KEY from the gitignored .env
            # (same sourcing as scripts/smoke_jev.py, incl. its manual-parser
            # fallback so a bare interpreter still finds the key).
            try:
                from dotenv import load_dotenv
                load_dotenv(REPO_ROOT / ".env", override=False)
            except ImportError:
                env_path = REPO_ROOT / ".env"
                if env_path.is_file():
                    for raw in env_path.read_text(encoding="utf-8").splitlines():
                        line = raw.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        key, _, val = line.partition("=")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val
            decide = _live_decider()
        except Exception as exc:  # noqa: BLE001 — config/dependency error
            print(f"bench_jev: config_error: {exc}", file=sys.stderr)
            return 2

        def call(row):
            return decide(row)

    results = []
    errored = 0
    for row in rows:
        try:
            pred, meta = call(row)
            if pred not in row["options"]:
                # fail closed: out-of-set (incl. unknown) is a real answer but
                # never credit; recorded so it can't silently inflate scores
                results.append({**row, "pred": pred, "invalid": pred == "unknown", **meta})
            else:
                results.append({**row, "pred": pred, **meta})
        except Exception as exc:  # noqa: BLE001 — provider/parse per sample
            errored += 1
            results.append({**row, "pred": None, "invalid": True,
                            "error": str(exc)[:200]})
            print(f"bench_jev: sample {row['sample_id']} failed: {str(exc)[:120]}",
                  file=sys.stderr)

    answered_ok = sum(1 for r in results if r.get("pred") is not None)
    report = {
        "bench": BENCH_NAME,
        "mode": "stub" if args.stub else "live",
        "disclaimer": DISCLAIMER,
        "host": host_record(),
        "requested_model": None if args.stub else "typesafe/jev-1.13",
        "surfaced_models": sorted({r.get("model_surfaced") for r in results
                                   if r.get("model_surfaced")}),
        "samples": len(rows),
        "provider_errors": errored,
        "per_task": score(results),
        "per_sample": [
            {"sample_id": r["sample_id"], "task": r["task"], "gold": r["gold"],
             "pred": r["pred"], "valid": not r.get("invalid", False)}
            for r in results
        ],
    }
    print(json.dumps({k: report[k] for k in
                      ("bench", "mode", "samples", "provider_errors", "per_task")},
                     indent=2, sort_keys=True))
    print(DISCLAIMER, file=sys.stderr)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if answered_ok == 0:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
