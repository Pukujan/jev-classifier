"""Offline claim-level evaluation runner (issue #66).

Scores a predicted claim set against a human-reviewed reference claim graph
using ``claim_metric_v1``. No network, no provider call, no label production:
it reads two JSON files and prints a score.

    python scripts/eval_claims.py --graph G.json --predictions P.json

Holdout custody (issue #81): when a split assignment is configured -- through
``--custody`` or the ``JEV_HOLDOUT_ASSIGNMENT`` environment variable -- the
default path is *development* and refuses to score a graph that names a
holdout paper, so a held-out label is never read. Scoring holdout papers is
the authorized evaluator path and must be requested with ``--evaluator``.

    python scripts/eval_claims.py --graph G.json --predictions P.json --evaluator --custody split.json
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
from jev_classifier.holdout import (  # noqa: E402
    ASSIGNMENT_ENV_VAR,
    HoldoutError,
    SplitAssignment,
    assert_development_safe,
    load_assignment,
    load_configured_assignment,
)
from jev_classifier.reference import ReferenceSchemaError  # noqa: E402


def _load(path: str) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _graph_paper_ids(graph: object) -> list[str]:
    """Return every ``paper_id`` in a reference graph, failing closed on shape."""
    if not isinstance(graph, dict):
        raise HoldoutError(
            "reference graph must be a JSON object to resolve its paper split",
            kind="schema_error",
        )
    papers = graph.get("papers")
    if not isinstance(papers, list):
        raise HoldoutError(
            "reference graph has no papers array; refusing to score without knowing "
            "each paper's split",
            kind="schema_error",
        )
    paper_ids: list[str] = []
    for idx, paper in enumerate(papers):
        if not isinstance(paper, dict) or not isinstance(paper.get("paper_id"), str):
            raise HoldoutError(
                f"graph.papers[{idx}] must be an object with a string paper_id",
                kind="schema_error",
            )
        paper_ids.append(paper["paper_id"])
    return paper_ids


def _resolve_assignment(custody: str | None) -> SplitAssignment | None:
    """Return the split assignment to enforce, or ``None`` when none is configured."""
    if custody is not None:
        return load_assignment(custody)
    return load_configured_assignment()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", required=True, help="reference claim graph JSON")
    parser.add_argument("--predictions", required=True, help="predicted claims JSON")
    parser.add_argument("--json", action="store_true", help="emit machine JSON only")
    parser.add_argument(
        "--custody",
        default=None,
        help=f"holdout split assignment JSON (default: ${ASSIGNMENT_ENV_VAR})",
    )
    parser.add_argument(
        "--evaluator",
        action="store_true",
        help="authorized evaluator path: holdout labels may be read and scored",
    )
    args = parser.parse_args(argv)

    graph = _load(args.graph)
    predictions = _load(args.predictions)
    if not isinstance(predictions, list):
        print("predictions file must be a JSON array", file=sys.stderr)
        return 2

    try:
        assignment = _resolve_assignment(args.custody)
    except HoldoutError as exc:
        print(f"holdout custody: {exc}", file=sys.stderr)
        return 2

    if args.evaluator:
        if assignment is None:
            print(
                "--evaluator requires custody: pass --custody PATH or set "
                f"{ASSIGNMENT_ENV_VAR}",
                file=sys.stderr,
            )
            return 2
        # ``--json`` promises machine JSON only, so the marker moves to stderr
        # rather than making stdout unparseable.
        marker_stream = sys.stderr if args.json else sys.stdout
        print(
            f"holdout custody: authorized evaluator path -- scoring under "
            f"{assignment.split_version} (custodian {assignment.custodian})",
            file=marker_stream,
        )
    elif assignment is not None:
        try:
            assert_development_safe(_graph_paper_ids(graph), assignment)
        except HoldoutError as exc:
            print(f"holdout custody: {exc}", file=sys.stderr)
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
