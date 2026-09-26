"""Run one bounded Grok research-source capture and write its JSON artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jev_classifier.sources.grok import GrokSourceClient, GrokSourceError  # noqa: E402


def write_artifact(artifact: dict, output: str | Path, *, root: str | Path = PROJECT_ROOT) -> Path:
    root_path = Path(root).resolve()
    output_path = Path(output)
    candidate = (root_path / output_path if not output_path.is_absolute() else output_path).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("output path must stay inside the controlled project folder") from exc
    candidate.parent.mkdir(parents=True, exist_ok=True)
    try:
        with candidate.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    except FileExistsError as exc:
        raise ValueError(f"output already exists: {candidate.relative_to(root_path)}") from exc
    return candidate


def main(argv: list[str] | None = None, *, root: str | Path = PROJECT_ROOT) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="One research query to send to Grok")
    parser.add_argument("--output", required=True, help="New JSON artifact path inside the project")
    parser.add_argument("--model", help="OpenRouter model id (defaults to GROK_SOURCE_MODEL or Grok 4.1 Fast)")
    args = parser.parse_args(argv)

    try:
        artifact = GrokSourceClient(model=args.model).capture(args.query)
        output = write_artifact(artifact, args.output, root=root)
    except (GrokSourceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(output), "response_id": artifact["response"]["response_id"], "content_sha256": artifact["content_sha256"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    load_dotenv(PROJECT_ROOT / ".env")
    raise SystemExit(main())
