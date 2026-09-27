#!/usr/bin/env python3
"""Check README section order, required references, and repository-local links."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_HEADINGS = (
    "Why this exists",
    "What this project is",
    "What you can make or use",
    "How it works",
    "Evidence and boundaries",
    "Image generation and use",
    "Templates and guides",
    "Prior work and references",
    "Try it",
)


def markdown_targets(text: str) -> list[str]:
    targets: list[str] = []
    for chunk in text.split("](")[1:]:
        target = chunk.split(")", 1)[0].strip().strip("<>")
        if target:
            targets.append(target)
    return targets


def check(root: Path) -> list[str]:
    errors: list[str] = []
    readme_path = root / "README.md"
    if not readme_path.is_file():
        return ["README.md is missing"]
    text = readme_path.read_text(encoding="utf-8")

    positions = []
    for heading in REQUIRED_HEADINGS:
        position = text.find(f"## {heading}")
        if position < 0:
            errors.append(f"missing required heading: {heading}")
        positions.append(position)
    present = [position for position in positions if position >= 0]
    if present != sorted(present):
        errors.append("required README headings are out of order")

    contract_path = root / ".content-system" / "readme-contract.json"
    contract: dict[str, object] | None = None
    if not contract_path.is_file():
        errors.append(".content-system/readme-contract.json is missing")
    else:
        try:
            loaded = json.loads(contract_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"README contract is not readable JSON: {exc}")
        else:
            if not isinstance(loaded, dict):
                errors.append("README contract must be a JSON object")
            else:
                contract = loaded

    linked_paths: set[str] = set()
    for target in markdown_targets(text):
        parts = urlsplit(target)
        if parts.scheme or target.startswith("#") or not parts.path:
            continue
        local_path = unquote(parts.path)
        resolved = (root / local_path).resolve()
        try:
            resolved.relative_to(root.resolve())
        except ValueError:
            errors.append(f"link escapes the repository: {target}")
            continue
        linked_paths.add(resolved.relative_to(root.resolve()).as_posix())
        if not resolved.is_file():
            errors.append(f"local README link does not exist: {target}")

    if contract is not None:
        required = contract.get("required_references")
        if not isinstance(required, list) or any(
            not isinstance(path, str) or not path for path in required
        ):
            errors.append("README contract required_references must be a list of paths")
        else:
            for path in required:
                required_path = Path(path)
                required_resolved = (root / required_path).resolve()
                try:
                    canonical = required_resolved.relative_to(root.resolve()).as_posix()
                except ValueError:
                    errors.append(f"contract-required reference escapes the repository: {path}")
                    continue
                if canonical not in linked_paths:
                    errors.append(f"README does not link to contract-required reference: {path}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    errors = check(root)
    if errors:
        print("INVALID")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALID: required README sections, contract references, and local links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
