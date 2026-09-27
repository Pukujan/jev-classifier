#!/usr/bin/env python3
"""Read-only ready-set derivation over GitHub coordination evidence (#60 Stage 1).

Answers one question for a dispatching human or agent: "which open leaf can
safely start RIGHT NOW, per the records?" — READY / NEEDS-VERDICT / CLAIMED /
BLOCKED-DEPS, computed from live GitHub state in ONE snapshot.

STRICTLY READ-ONLY (arbiter ruling on #60): never claims, comments, merges,
spawns, or decides proposals. The claim gate `scripts/coord_board.py
--issue-open` remains the per-agent lock; this helper only ranks candidates.
PRs (GitHub's /issues endpoint returns them too) are never leaves and are
dropped before bucketing.

Freshness invariant (the #37 double-adjudication lesson): every answer is
computed from a single fetch stamped `snapshot_utc`; callers must re-run
rather than reuse old output, and --max-age-s makes the tool refuse when its
own fetch window was pathologically slow (stale-by-clock => exit 3).
Unknown/unverifiable dependencies fail closed to BLOCKED, never READY.
Deferred rulings (ACCEPT-DEFERRED, #23) also land in BLOCKED: sequencing is
the arbiter's, not the dispatcher's.

Offline mode (--fixtures DIR) reads issues.json + comments.json snapshots so
CI pins the derivation with no network and no third-party deps: this file is
stdlib-only and loads records.py directly (no httpx needed).

Exit codes: 0 ok, 2 config/fetch failure, 3 stale snapshot refused.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# records.py is pure stdlib; load it directly so the ready tool runs on a bare
# interpreter (no httpx needed), same fallback shape coord_board uses.
_rspec = importlib.util.spec_from_file_location(
    "jev_coord_records", str(_REPO_ROOT / "src" / "jev_classifier" / "coord" / "records.py")
)
R = importlib.util.module_from_spec(_rspec)
sys.modules["jev_coord_records"] = R
_rspec.loader.exec_module(R)

DEFAULT_REPO = "Pukujan/jev-classifier"
FRESHNESS_LIMIT_S = 300  # a fetch that stalls past 5 min => refuse (stale-by-clock rule)

# Dependency phrases: only explicit blocker/depends lines, not "Parent:" links.
_DEP_RE = re.compile(
    r"(?im)^\s*(?:[-*]\s*)?(?:depends(?:\s+on)?|dependencies|blocked\s+by)\s*[:=]?\s*([^\n]+)"
)
_ISSUE_REF_RE = re.compile(r"#(\d+)")


class ReadyError(RuntimeError):
    pass


def _gh_get(endpoint: str, *params: str, paginate: bool = False) -> str:
    cmd = ["gh", "api", "-X", "GET", endpoint]
    if paginate:
        cmd.append("--paginate")
    for p in params:
        cmd += ["-f", p]
    cmd += ["--jq", "."]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError as exc:
        raise ReadyError("gh CLI not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReadyError("gh api timed out") from exc
    if proc.returncode != 0:
        raise ReadyError(f"gh api failed: {(proc.stderr or '').strip().splitlines()[:1]}")
    return proc.stdout


def decode_stream(text: str) -> list[dict]:
    """Parse concatenated JSON objects/arrays produced by --paginate."""
    decoder = json.JSONDecoder()
    items: list[dict] = []
    idx = 0
    while idx < len(text):
        while idx < len(text) and text[idx] in " \n\r\t":
            idx += 1
        if idx >= len(text):
            break
        value, idx = decoder.raw_decode(text, idx)
        items.extend(value if isinstance(value, list) else [value])
    return items


def to_fold_comment(item: dict) -> dict:
    """Normalize REST- or gh-shaped comment JSON to records.fold input."""
    author = item.get("author")
    if isinstance(author, dict):
        author = author.get("login")
    author = author or (item.get("user") or {}).get("login") or "?"
    issue = item.get("issue")
    if issue is None:
        tail = str(item.get("issue_url") or "").rsplit("/", 1)[-1]
        issue = int(tail) if tail.isdigit() else 0
    created = item.get("created_at") or item.get("createdAt") or ""
    return {
        "body": item.get("body") or "",
        "author": str(author),
        "created_at": str(created),
        "issue": int(issue),
        "comment_id": int(item.get("id") or 0),
    }


def dep_issue_numbers(body: str) -> list[int]:
    """Issue numbers named as dependencies/blockers in an issue body.

    Only lines under an explicit dependency label count; a parent initiative
    is lineage, not a blocker — scanning the whole body would deadlock the
    ready set on every child. Within a dependency line, a trailing
    parenthetical ("#21 (#14 parent)") is an annotation, so refs are scanned
    only up to the first "(".
    """
    out: list[int] = []
    for m in _DEP_RE.finditer(body or ""):
        clause = m.group(1).split("(", 1)[0]
        out.extend(int(n) for n in _ISSUE_REF_RE.findall(clause))
    seen: set[int] = set()
    return [n for n in out if not (n in seen or seen.add(n))]


def _deferred(verdict) -> bool:
    """True when an accepted ruling is actually deferred (raw ACCEPT-DEFERRED).

    normalize_decision folds ACCEPT-DEFERRED to "accepted" for proposal-open
    logic, but for DISPATCH a deferred leaf must never read READY — the #23
    ruling literally says do not claim or branch it. decision_raw is the
    evidence; older records without it fall back to the canonical token.
    """
    if verdict is None:
        return False
    raw = verdict.attrs.get("decision_raw") or verdict.attrs.get("decision", "")
    return "defer" in raw.lower()


def proposal_state_for(state: R.CoordState, issue: int) -> str:
    """'accepted' | 'deferred' | 'open' | 'rejected' | 'none' for one issue."""
    ratify = state.applied_verdicts.get(f"issue:{issue}")
    if ratify is not None:
        return "deferred" if _deferred(ratify) else "accepted"
    pids = [pid for pid, p in state.proposals.items()
            if p.attrs.get("issue") == str(issue)]
    if not pids:
        return "none"
    statuses = {
        "deferred" if _deferred(state.applied_verdicts.get(pid))
        else state.decision(pid)
        for pid in pids
    }
    if "accepted" in statuses:
        return "accepted"
    if statuses <= {"rejected", "superseded"}:
        return "rejected"
    if "deferred" in statuses:
        return "deferred"
    return "open"


def classify(issue: dict, state: R.CoordState, claims_by_issue: dict[int, list],
             open_issue_nums: set[int], all_issue_nums: set[int]) -> tuple[str, str]:
    """Return (bucket, reason) for one open issue dict."""
    n = int(issue["number"])
    deps = [d for d in dep_issue_numbers(issue.get("body") or "") if d != n]
    pending = [d for d in deps if d in open_issue_nums]
    unverifiable = [d for d in deps if d not in all_issue_nums]
    if pending or unverifiable:
        bits = [f"#{d} open" for d in pending] + [f"#{d} unknown" for d in unverifiable]
        return "BLOCKED-DEPS", "unmet deps: " + ", ".join(bits)
    holders = claims_by_issue.get(n, [])
    if holders:
        who = ", ".join(sorted({h.attrs.get("agent", "?") for h in holders}))
        return "CLAIMED", f"live claim: {who}"
    status = proposal_state_for(state, n)
    if status == "deferred":
        return "BLOCKED-DEPS", "deferred by ruling (do not claim yet)"
    if status == "open":
        return "NEEDS-VERDICT", "proposal awaiting adjudication"
    if status == "rejected":
        return "NEEDS-VERDICT", "rejected/superseded; needs re-ruling or closure"
    return "READY", ""


def ready_set(issues: list[dict], state: R.CoordState) -> dict:
    """Pure derivation over one snapshot of issue dicts + folded records."""
    issues = [i for i in issues if "pull_request" not in i]
    open_issue_nums = {int(i["number"]) for i in issues if i.get("state") == "open"}
    all_issue_nums = {int(i["number"]) for i in issues}
    claims_by_issue: dict[int, list] = {}
    for c in state.live_claims():
        try:
            claims_by_issue.setdefault(int(c.attrs.get("issue", "0")), []).append(c)
        except ValueError:
            continue
    buckets: dict[str, list[dict]] = {
        "READY": [], "NEEDS-VERDICT": [], "CLAIMED": [], "BLOCKED-DEPS": [],
    }
    for issue in issues:
        if issue.get("state") != "open":
            continue
        bucket, reason = classify(issue, state, claims_by_issue,
                                  open_issue_nums, all_issue_nums)
        entry = {"number": int(issue["number"]), "title": (issue.get("title") or "")[:80]}
        if reason:
            entry["reason"] = reason
        buckets[bucket].append(entry)
    return {"counts": {k: len(v) for k, v in buckets.items()}, **buckets}


def fetch_snapshot(repo: str) -> tuple[list[dict], R.CoordState, str, float]:
    """One fetch window: issues + comments, folded, stamped at completion."""
    started = time.monotonic()
    issues = decode_stream(_gh_get(f"repos/{repo}/issues", "state=all",
                                   "per_page=100", paginate=True))
    comments_raw = decode_stream(_gh_get(f"repos/{repo}/issues/comments",
                                         "per_page=100", paginate=True))
    state = R.fold([to_fold_comment(c) for c in comments_raw])
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return issues, state, stamp, time.monotonic() - started


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--fixtures", help="offline dir with issues.json + comments.json")
    ap.add_argument("--max-age-s", type=int, default=FRESHNESS_LIMIT_S,
                    help="refuse if the snapshot fetch took longer (0=off)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.fixtures:
            root = Path(args.fixtures)
            issues = json.loads((root / "issues.json").read_text(encoding="utf-8"))
            comments = json.loads((root / "comments.json").read_text(encoding="utf-8"))
            state = R.fold([to_fold_comment(c) for c in comments])
            stamp, elapsed = "offline", 0.0
        else:
            issues, state, stamp, elapsed = fetch_snapshot(args.repo)
    except (ReadyError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"coord_ready: {exc}", file=sys.stderr)
        return 2

    if args.max_age_s and elapsed > args.max_age_s:
        print(f"coord_ready: fetch window took {elapsed:.0f}s > {args.max_age_s}s; "
              "refusing stale-by-clock snapshot — re-run", file=sys.stderr)
        return 3

    result = ready_set(issues, state)
    result["snapshot_utc"] = stamp
    result["read_only"] = True
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    print(f"coord_ready @ {stamp} (read-only; always re-run, never reuse)")
    for bucket in ("READY", "NEEDS-VERDICT", "CLAIMED", "BLOCKED-DEPS"):
        lines = result[bucket]
        print(f"{bucket} ({len(lines)}):")
        for e in sorted(lines, key=lambda x: x["number"]):
            why = f"  <- {e['reason']}" if e.get("reason") else ""
            print(f"  #{e['number']} {e['title']}{why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
