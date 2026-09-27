"""Validate the metadata-only reference-paper manifest for issue #29."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "datasets" / "reference_papers.json"
SCHEMA_PATH = ROOT / "schemas" / "reference_papers.schema.json"
MAX_MANIFEST_BYTES = 50_000


def _unique(values: list[str], label: str) -> None:
    duplicates = sorted(value for value in set(values) if values.count(value) > 1)
    if duplicates:
        raise ValueError(f"duplicate {label}: {', '.join(duplicates)}")


def validate_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES:
        raise ValueError(f"manifest exceeds {MAX_MANIFEST_BYTES} bytes")

    try:
        text = raw.decode("utf-8")
        manifest = json.loads(text)
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8 JSON: {exc}") from exc

    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(manifest),
        key=lambda error: (tuple(map(str, error.path)), error.message),
    )
    if errors:
        first = errors[0]
        location = "/".join(map(str, first.path)) or "<root>"
        raise ValueError(f"schema error at {location}: {first.message}")

    papers = manifest["papers"]
    excluded = manifest["excluded_candidates"]
    _unique([paper["paper_id"] for paper in papers], "paper_id")
    _unique(
        [paper["doi"].lower() for paper in papers if paper["doi"] is not None],
        "DOI",
    )
    _unique([candidate["candidate_id"] for candidate in excluded], "excluded candidate id")

    selected_ids = {paper["paper_id"] for paper in papers}
    overlap = selected_ids.intersection(candidate["candidate_id"] for candidate in excluded)
    if overlap:
        raise ValueError(f"candidate is both selected and excluded: {', '.join(sorted(overlap))}")

    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if canonical.encode("utf-8") != raw:
        raise ValueError("manifest is not canonical JSON (sorted keys, two-space indent, trailing newline)")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=DEFAULT_MANIFEST, help="manifest JSON to validate"
    )
    args = parser.parse_args()
    try:
        manifest = validate_manifest(args.manifest)
    except (OSError, ValueError, jsonschema.SchemaError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(
        "VALID: "
        f"{len(manifest['papers'])} reference-paper candidates; "
        f"{len(manifest['excluded_candidates'])} exclusions; "
        f"{args.manifest.stat().st_size} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
