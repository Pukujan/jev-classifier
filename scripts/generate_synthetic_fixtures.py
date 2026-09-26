"""Deterministic first-party synthetic offline fixtures (Issue #33).

Writes tiny JSON samples under tests/fixtures/datasets/ modeled on SciCite
claim-type label shapes and SciNLI contradiction/agreement label shapes.
Corpus text from SciCite / SciNLI / SciFact is NEVER fetched or committed —
arbiter synthetic-first ruling on #33.

Also writes tests/fixtures/datasets/PROVENANCE.json with sha256 of each
fixture file and a machine-readable record of omissions.

Usage:
    python scripts/generate_synthetic_fixtures.py [--check]

--check exits 0 iff committed fixtures match what this script would write
(content + hashes); used by offline tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "tests" / "fixtures" / "datasets"
CLAIM_TYPE_PATH = OUT_DIR / "claim_type_shapes.json"
CONTRADICTION_PATH = OUT_DIR / "contradiction_shapes.json"
PROVENANCE_PATH = OUT_DIR / "PROVENANCE.json"

# Stable seed token recorded in provenance (not used for RNG — samples are fixed).
GENERATOR_ID = "generate_synthetic_fixtures.py"
GENERATOR_VERSION = "1"
SEED = 33

CLAIM_TYPE_LABELS = ("background", "method", "result")
CONTRADICTION_LABELS = ("entailment", "contrasting", "neutral", "reasoning")


def _claim_type_payload() -> dict:
    """Hand-authored synthetic citation-intent snippets (not from any corpus)."""
    samples = [
        {
            "id": "syn-ct-bg-001",
            "label": "background",
            "text": (
                "Prior reviews of ambulatory glucose sensing emphasize drift "
                "and calibration burden as recurring deployment constraints."
            ),
        },
        {
            "id": "syn-ct-bg-002",
            "label": "background",
            "text": (
                "Several observational cohorts have linked overnight "
                "hypoglycemia alerts with next-day cognitive fatigue scores."
            ),
        },
        {
            "id": "syn-ct-bg-003",
            "label": "background",
            "text": (
                "The broader literature treats sensor wear-time adherence as "
                "a known moderator of real-world accuracy estimates."
            ),
        },
        {
            "id": "syn-ct-me-001",
            "label": "method",
            "text": (
                "We randomized 120 adults 1:1 using permuted blocks of size four "
                "and locked the analysis plan before unblinding."
            ),
        },
        {
            "id": "syn-ct-me-002",
            "label": "method",
            "text": (
                "Feature vectors were built from five-minute interstitial glucose "
                "windows and scored with a fixed ridge regression pipeline."
            ),
        },
        {
            "id": "syn-ct-me-003",
            "label": "method",
            "text": (
                "Inter-annotator agreement was measured with Cohen's kappa on a "
                "held-out double-coded subset of twenty fragments."
            ),
        },
        {
            "id": "syn-ct-re-001",
            "label": "result",
            "text": (
                "Mean absolute relative difference fell from 11.4% to 8.1% "
                "(95% CI 2.1–4.5) in the intervention arm."
            ),
        },
        {
            "id": "syn-ct-re-002",
            "label": "result",
            "text": (
                "Nighttime alert precision was 0.73 versus 0.51 for the "
                "baseline rule set (McNemar p = 0.004)."
            ),
        },
        {
            "id": "syn-ct-re-003",
            "label": "result",
            "text": (
                "No serious device-related adverse events were observed across "
                "ninety days of continuous wear."
            ),
        },
    ]
    return {
        "schema": "jev.synthetic_fixtures.claim_type.v1",
        "provenance": {
            "kind": "synthetic",
            "generator": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "seed": SEED,
            "modeled_on_label_shapes": "SciCite closed set background/method/result",
            "corpus_text": "none",
            "license": "first-party; no external corpus",
        },
        "label_set": list(CLAIM_TYPE_LABELS),
        "samples": samples,
    }


def _contradiction_payload() -> dict:
    """Hand-authored synthetic premise/hypothesis pairs (not from any corpus)."""
    samples = [
        {
            "id": "syn-cx-en-001",
            "label": "entailment",
            "premise": "The sensor reported two nocturnal lows between midnight and 06:00.",
            "hypothesis": "At least one overnight hypoglycemia alert occurred.",
        },
        {
            "id": "syn-cx-en-002",
            "label": "entailment",
            "premise": "All enrolled participants completed the fourteen-day wear protocol.",
            "hypothesis": "No participant discontinued the study before day fourteen.",
        },
        {
            "id": "syn-cx-co-001",
            "label": "contrasting",
            "premise": "Arm A reduced false alarms by forty percent versus control.",
            "hypothesis": "Arm A increased false alarms relative to control.",
        },
        {
            "id": "syn-cx-co-002",
            "label": "contrasting",
            "premise": "Calibration every twelve hours was required for the device.",
            "hypothesis": "The device required no user calibration during wear.",
        },
        {
            "id": "syn-cx-ne-001",
            "label": "neutral",
            "premise": "The clinic enrolled adults aged eighteen to sixty-five.",
            "hypothesis": "Rainfall in the catchment area rose during the trial window.",
        },
        {
            "id": "syn-cx-ne-002",
            "label": "neutral",
            "premise": "Primary endpoint was change in time-in-range at day twenty-eight.",
            "hypothesis": "The cafeteria introduced a new lunch menu that week.",
        },
        {
            "id": "syn-cx-re-001",
            "label": "reasoning",
            "premise": "If MARD exceeds twelve percent, clinicians delay therapy titration.",
            "hypothesis": "High MARD is treated as a reason to postpone dose changes.",
        },
        {
            "id": "syn-cx-re-002",
            "label": "reasoning",
            "premise": "Missing overnight readings bias hypoglycemia prevalence downward.",
            "hypothesis": "Incomplete night coverage underestimates true overnight lows.",
        },
    ]
    return {
        "schema": "jev.synthetic_fixtures.contradiction.v1",
        "provenance": {
            "kind": "synthetic",
            "generator": GENERATOR_ID,
            "generator_version": GENERATOR_VERSION,
            "seed": SEED,
            "modeled_on_label_shapes": (
                "SciNLI closed set entailment/contrasting/neutral/reasoning"
            ),
            "corpus_text": "none",
            "license": "first-party; no external corpus",
        },
        "label_set": list(CONTRADICTION_LABELS),
        "samples": samples,
    }


def dumps_stable(obj: object) -> str:
    """Canonical JSON: UTF-8, sorted keys, 2-space indent, trailing newline."""
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_outputs() -> dict[str, str]:
    """Return mapping of absolute path string -> file body."""
    claim_body = dumps_stable(_claim_type_payload())
    contra_body = dumps_stable(_contradiction_payload())
    provenance = {
        "schema": "jev.synthetic_fixtures.provenance.v1",
        "issue": 33,
        "ruling": "synthetic-first; no SciCite/SciNLI/SciFact corpus text committed",
        "generator": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "seed": SEED,
        "files": {
            CLAIM_TYPE_PATH.name: {
                "path": "tests/fixtures/datasets/claim_type_shapes.json",
                "sha256": sha256_text(claim_body),
                "bytes": len(claim_body.encode("utf-8")),
                "kind": "synthetic",
                "label_shapes_modeled_on": "SciCite",
            },
            CONTRADICTION_PATH.name: {
                "path": "tests/fixtures/datasets/contradiction_shapes.json",
                "sha256": sha256_text(contra_body),
                "bytes": len(contra_body.encode("utf-8")),
                "kind": "synthetic",
                "label_shapes_modeled_on": "SciNLI",
            },
        },
        "omissions": [
            {
                "name": "SciCite corpus text",
                "reason": (
                    "Dataset card license unknown (HF license empty); code-repo "
                    "Apache-2.0 does not clear corpus text. Synthetic label-shape "
                    "fixtures only; optional runtime fetch into .research_cache/."
                ),
            },
            {
                "name": "SciNLI corpus text",
                "reason": (
                    "Distribution URL/license unverified for commit; treat as "
                    "unlicensed-for-commit until a pinned dataset card license "
                    "is recorded. Synthetic label-shape fixtures only."
                ),
            },
            {
                "name": "SciFact any component",
                "reason": (
                    "Issue research and arbiter ruling: NEVER commit. Runtime "
                    "fetch into gitignored .research_cache/ only if used."
                ),
            },
        ],
        "runtime_fetch_note": (
            "Larger or uncleared corpora may be fetched locally into the "
            "already-gitignored .research_cache/ directory; that path is not "
            "required for offline CI and is out of scope for this PR."
        ),
    }
    prov_body = dumps_stable(provenance)
    return {
        str(CLAIM_TYPE_PATH): claim_body,
        str(CONTRADICTION_PATH): contra_body,
        str(PROVENANCE_PATH): prov_body,
    }


def write_outputs(outputs: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path_str, body in outputs.items():
        Path(path_str).write_text(body, encoding="utf-8", newline="\n")


def check_outputs(outputs: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for path_str, expected in outputs.items():
        path = Path(path_str)
        if not path.is_file():
            errors.append(f"missing: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"mismatch: {path} (sha expected {sha256_text(expected)[:12]}… "
                f"got {sha256_text(actual)[:12]}…)"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed fixtures match generator output; do not write.",
    )
    args = parser.parse_args(argv)
    outputs = build_outputs()
    if args.check:
        errors = check_outputs(outputs)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print("synthetic fixtures match generator output")
        return 0
    write_outputs(outputs)
    for path_str in outputs:
        path = Path(path_str)
        digest = sha256_text(outputs[path_str])
        print(f"wrote {path.relative_to(ROOT)} sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
