"""Offline claim-level evaluation runner (issue #66).

Scores a predicted claim set against a human-reviewed reference claim graph
using ``claim_metric_v1``. No network, no provider call, no label production:
it reads two JSON files and prints a score.

    python scripts/eval_claims.py --graph G.json --predictions P.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jev_classifier.eval import METRIC_VERSION, score_claims  # noqa: E402
from jev_classifier.reference import ReferenceSchemaError  # noqa: E402


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, help="reference claim graph JSON")
    parser.add_argument("--predictions", required=True, help="predicted claims JSON")
    parser.add_argument("--json", action="store_true", help="emit machine JSON only")
    args = parser.parse_args(argv)

    graph = _load(args.graph)
    predictions = _load(args.predictions)
    if not isinstance(predictions, list):
        print("predictions file must be a JSON array", file=sys.stderr)
        return 2

    try:
        report = score_claims(graph, predictions)
    except ReferenceSchemaError as exc:
        print(f"malformed reference graph: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    primary = report["primary"]
    print(f"metric: {METRIC_VERSION} ({report['match_rule']})")
    print(
        f"claim-level micro: P={primary['precision']} R={primary['recall']} "
        f"F1={primary['f1']} (tp={primary['true_positives']})"
    )
    print(
        f"predictions: {report['predictions_total']} total, "
        f"{report['predictions_with_usable_span']} with a usable span, "
        f"{report['predictions_unmatched']} unmatched"
    )
    coverage = report["citation_coverage"]
    print(
        f"citation coverage: {coverage['predictions_citing_a_resolved_source']}/"
        f"{coverage['predictions']} (separate from the primary F1)"
    )
    print(f"shacl: {report['ontology']['shacl']} (reported separately)")
    for paper_id, row in sorted(report["per_paper"].items()):
        print(
            f"  {paper_id}: P={row['precision']} R={row['recall']} F1={row['f1']} "
            f"(ref={row['reference']} pred={row['predicted']})"
        )
    print("per-paper results are reported alongside; the aggregate is never alone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
