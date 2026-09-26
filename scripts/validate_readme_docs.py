#!/usr/bin/env python3
"""Check README section order, required references, and repository-local links."""

from __future__ import annotations

import argparse
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

    contract = root / ".content-system" / "readme-contract.json"
    if not contract.is_file():
        errors.append(".content-system/readme-contract.json is missing")

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
        if not resolved.is_file():
            errors.append(f"local README link does not exist: {target}")

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
    print("VALID: required README sections and local links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
