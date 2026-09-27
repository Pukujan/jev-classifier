#!/usr/bin/env python3
"""Validate the managed documentation manifest (issue #63). Read-only.

Checks ``docs/docs_manifest.json`` with jev_classifier.docs.validate: shape,
identity, on-disk path and source resolution, exclusions, the tree page, the
reviewed digest, relative markdown links, and the private-path scan. The
command never writes or repairs anything; a violation exits 1.

  python scripts/validate_docs.py
  python scripts/validate_docs.py --json
  python scripts/validate_docs.py --no-freshness --root path/to/root
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from jev_classifier.docs import DocsManifestError, load_manifest, validate_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--manifest",
        default=None,
        help="manifest path (default: <root>/docs/docs_manifest.json)",
    )
    parser.add_argument(
        "--root",
        default=None,
        help="repository root the manifest paths resolve against (default: repo root)",
    )
    parser.add_argument(
        "--no-freshness",
        action="store_true",
        help="skip the reviewed_sha256 freshness check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable result instead of prose",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else _REPO_ROOT
    manifest_path = Path(args.manifest) if args.manifest else root / "docs" / "docs_manifest.json"
    check_freshness = not args.no_freshness

    result: dict[str, object] = {
        "ok": False,
        "manifest": str(manifest_path),
        "root": str(root),
        "check_freshness": check_freshness,
    }
    try:
        manifest = load_manifest(manifest_path)
        validate_manifest(manifest, root=root, check_freshness=check_freshness)
    except DocsManifestError as exc:
        result["error"] = str(exc)
        result["kind"] = exc.kind
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"docs manifest INVALID ({exc.kind}): {exc}", file=sys.stderr)
        return 1

    documents = manifest.get("documents", [])
    result["ok"] = True
    result["documents"] = len(documents)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"docs manifest OK: {len(documents)} documents validated ({manifest_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
