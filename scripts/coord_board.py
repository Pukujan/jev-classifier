#!/usr/bin/env python3
"""Agent-facing gate over the GitHub coordination records (#22 protocol).

Parses `coord:proposal` / `coord:verdict` / `coord:claim` / `coord:receipt`
markers and legacy `## Claim` prose from GitHub issue comments (pure parser:
jev_classifier.coord.records) and answers the two questions an agent cannot
answer from its own machine:

  "May I build this design?"       coord_board.py --proposal P-x --can-build
  "May I take this issue?"         coord_board.py --issue-open N --agent <id>
  "What is the whole board?"       coord_board.py            (readable) / --json

Cross-device claim truth = live claim records + reserved branch refs on origin
(first create-ref wins; merged PR heads release their ref — PR `merged_at`,
because this repo squash-merges, plus a merge-base fallback). The local SQLite
stores (.coord/, .ops/) are caches; GitHub wins. A closed issue is never FREE:
re-building delivered work is the costliest duplicate, so the gate checks issue
state and blocks.

`by=`/`agent=` are self-declared (single shared GitHub account): authoritative
-ness is filtered against records.AUTHORITATIVE_AGENTS to stop accidental
overrides; deliberate forgery is out of scope (evidence, not enforcement).

Exit codes: 0 allowed/ok; 2 usage/parse/config; 3 blocked.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from functools import partial
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

# The gate is coordination tooling, not classifier code: it must run on a
# bare interpreter even when package extras (httpx via jev_classifier.__init__)
# are missing. Prefer the normal import; fall back to loading the pure-stdlib
# records module directly from src.
try:
    from jev_classifier.coord import records as R  # type: ignore
except ImportError:  # pragma: no cover - depends on ambient env
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "jev_coord_records",
        str(_REPO_ROOT / "src" / "jev_classifier" / "coord" / "records.py"),
    )
    R = _ilu.module_from_spec(_spec)
    import sys as _sys
    _sys.modules["jev_coord_records"] = R
    _spec.loader.exec_module(R)

DEFAULT_REPO = "Pukujan/jev-classifier"


class BoardError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int = 120) -> str:
    try:
        # encoding is explicit: text=True alone uses the locale default (cp1252
        # on Windows), which raises on GitHub's UTF-8 comment text and leaves
        # stdout None.
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise BoardError(f"{cmd[0]} not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise BoardError(f"{' '.join(cmd[:3])} timed out after {timeout}s") from exc
    if proc.returncode != 0:
        detail = (proc.stderr or "").strip().splitlines()[:1] or ["no detail"]
        raise BoardError(f"{cmd[0]} failed: {detail}")
    return proc.stdout


def gh_get(endpoint: str, *params: str, paginate: bool = False) -> str:
    """gh api GET. `-X GET` is REQUIRED: gh silently POSTs when -f is present."""
    cmd = ["gh", "api", "-X", "GET", endpoint]
    if paginate:
        cmd.append("--paginate")
    for p in params:
        cmd += ["-f", p]
    cmd += ["--jq", "."]
    return _run(cmd, timeout=180)


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


def fetch_comments(repo: str) -> list[dict]:
    out = gh_get(f"repos/{repo}/issues/comments", "per_page=100", paginate=True)
    return [to_fold_comment(item) for item in decode_stream(out)]


def fetch_issue_state(repo: str, issue: int) -> str:
    """open|closed|unknown (unknown never blocks; live API errors are surfaced)."""
    try:
        out = gh_get(f"repos/{repo}/issues/{issue}")
    except BoardError:
        return "unknown"
    try:
        return str(json.loads(out).get("state") or "unknown")
    except json.JSONDecodeError:
        return "unknown"


def fetch_refs() -> list[str]:
    out = _run(["git", "ls-remote", "--heads", "origin"], timeout=60)
    return [line.split("\trefs/heads/")[1] for line in out.splitlines()
            if "\trefs/heads/" in line]


def merged_heads(repo: str) -> set[str]:
    """Branch names whose PR merged (authoritative under squash-merge)."""
    try:
        out = gh_get(f"repos/{repo}/pulls", "state=all", "per_page=100", paginate=True)
    except BoardError:
        return set()
    heads = set()
    for pr in decode_stream(out):
        if pr.get("merged_at"):
            head = (pr.get("head") or {}).get("ref")
            if head:
                heads.add(head)
    return heads


def ancestor_refs(refs: list[str]) -> set[str]:
    """Fallback: refs already inside origin/main by ancestry."""
    try:
        _run(["git", "fetch", "--quiet", "origin", "main"], timeout=120)
    except BoardError:
        return set()
    out = set()
    for ref in refs:
        if ref == "main":
            continue
        probe = subprocess.run(
            ["git", "merge-base", "--is-ancestor", f"origin/{ref}", "origin/main"],
            capture_output=True, timeout=30,
        )
        if probe.returncode == 0:
            out.add(ref)
    return out


def live_claim_issues(state: R.CoordState) -> list[int]:
    """Issue numbers that still hold a live claim — the settle candidates."""
    out = set()
    for c in state.live_claims():
        n = str(c.attrs.get("issue", ""))
        if n.isdigit():
            out.add(int(n))
    return sorted(out)


def build_state(repo: str, comments_file: str | None, no_refs: bool,
                issue_state=None):
    if comments_file:
        blob = Path(comments_file).read_text(encoding="utf-8")
        comments = [to_fold_comment(item) for item in decode_stream(blob)]
        refs: list[str] = []
        merged: set[str] = set()
    else:
        comments = fetch_comments(repo)
        if no_refs:
            refs, merged = [], set()
        else:
            try:
                refs = fetch_refs()
            except BoardError as exc:
                print(f"coord_board: ref check unavailable ({exc}); comments only",
                      file=sys.stderr)
                refs = []
            merged = merged_heads(repo) | ancestor_refs(refs)
    state = R.fold(comments)
    if merged:
        # A claim whose reserved branch merged is released even when the agent
        # never posted state=released (docs/AGENT_PROPOSALS.md claim rule).
        R.settle_claims(state, merged_branches=merged)
    # The same rule releases a claim whose issue closed. ops_sync has always
    # passed that signal; the gate did not, so the live board kept showing
    # claims on delivered work the committed COORD.md had already dropped
    # (#50). Only issues still holding a live claim are looked up, and
    # fetch_issue_state degrades to "unknown" on API failure, which settles
    # nothing rather than guessing.
    if issue_state is not None:
        lookup = issue_state
    elif comments_file or no_refs:
        lookup = None  # offline modes stay offline: no per-issue API calls
    else:
        lookup = partial(fetch_issue_state, repo)
    if lookup is not None:
        closed = [n for n in live_claim_issues(state) if lookup(n) == "closed"]
        if closed:
            R.settle_claims(state, closed_issues=closed)
    return state, refs, merged


def verdict_for_display(state: R.CoordState, pid: str, p: R.Record):
    """Applied verdict for a proposal: own key first, then issue-level ratify."""
    v = state.applied_verdicts.get(pid)
    if v is None:
        issue = p.attrs.get("issue", "")
        if issue:
            v = state.applied_verdicts.get(f"issue:{issue}")
    return v


def render(state: R.CoordState, refs: list[str], merged: set[str]) -> str:
    lines = [f"coord board: {len(state.proposals)} proposals, "
             f"{len(state.applied_verdicts)} applied verdicts, "
             f"{sum(len(v) for v in state.advisory_verdicts.values())} advisory, "
             f"{len(state.all_claims)} claims, "
             f"{len(state.receipts)} receipts, "
             f"{len([r for r in refs if r not in merged])} unmerged refs"]
    for pid, p in sorted(state.proposals.items()):
        dec = state.decision(pid)
        adv = state.advisory_verdicts.get(pid)
        if p.attrs.get("status") == "withdrawn":
            status = "withdrawn"
        elif dec == "open" and adv:
            status = f"OPEN (advisory {adv[-1].attrs.get('decision')} from {adv[-1].attrs.get('by')})"
        elif dec == "open":
            status = "OPEN - do not build"
        else:
            v = verdict_for_display(state, pid, p)
            ratified = v is not None and v.key.startswith("issue:")
            status = dec.upper() + (" (issue-level ratify)" if ratified else "")
        lines.append(f"  P {pid:>10} issue={p.attrs.get('issue', '?'):>3} {status}")
    for c in state.live_claims():
        holder = c.attrs.get("agent", "?")
        writer = c.attrs.get("writer")
        if writer and writer != holder:
            holder = f"{holder}->{writer}"
        marker = "coord" if c.marker == "coord" else "prose"
        lines.append(f"  CLAIM issue={c.attrs.get('issue', '?'):>3} agent={holder} "
                     f"branch={c.attrs.get('branch', '?')} [{marker}]")
    for issue, cs in sorted(state.collisions().items()):
        agents = ", ".join(sorted({c.attrs.get("agent", "?") for c in cs}))
        lines.append(f"  !! COLLISION issue={issue}: live claims by {agents}")
    for iss, cid, err in state.malformed:
        lines.append(f"  !! MALFORMED issue={iss} comment={cid}: {err}")
    orphan_refs = [r for r in refs
                   if r not in merged
                   and (n := R.ref_issue_number(r)) is not None
                   and not any(c.attrs.get("branch") == r for c in state.all_claims)]
    for ref in orphan_refs:
        lines.append(f"  !! REF-WITHOUT-CLAIM branch={ref} (issue={R.ref_issue_number(ref)}): "
                     "claim comment missing or lost")
    for run_id, rcpt in sorted(state.receipts.items()):
        a = rcpt.attrs
        pv = R.provenance_for
        lines.append(
            f"  RUN {run_id} outcome={a.get('outcome')}[{pv(a, 'outcome')}] "
            f"task={a.get('task', '?')} pr={a.get('pr', '-')} "
            f"commit={a.get('commit', '-')[:8]}[{pv(a, 'commit')}] "
            f"agent={a.get('agent_alias', '—')}[{pv(a, 'agent_alias')}] "
            f"model={a.get('model_alias', '—')}/{a.get('model_version_alias', '—')}"
            f"[{pv(a, 'model_alias')}] "
            f"temp={a.get('temperature', '—')}[{pv(a, 'temperature')}] "
            f"tools={a.get('tools', '—')}[{pv(a, 'tools')}]"
        )
    if not (state.open_proposals() or state.collisions() or state.live_claims()
            or state.malformed or state.receipts):
        lines.append("  board clear")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--comments-file", help="offline comment JSON (tests)")
    parser.add_argument("--no-refs", action="store_true")
    parser.add_argument("--proposal", help="report one proposal id")
    parser.add_argument("--can-build", action="store_true",
                        help="with --proposal: exit 3 unless accepted authoritatively")
    parser.add_argument("--issue-open", type=int, dest="check_issue")
    parser.add_argument("--agent", help="your agent id (for --issue-open)")
    parser.add_argument("--issue-state", choices=("open", "closed"),
                        help="pre-fetched issue state (skips live lookup)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        state, refs, merged = build_state(args.repo, args.comments_file, args.no_refs)
    except (BoardError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"coord_board: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "proposals": {k: v.as_dict() for k, v in sorted(state.proposals.items())},
            "applied_verdicts": {k: v.as_dict() for k, v in sorted(state.applied_verdicts.items())},
            "advisory": {k: [v.as_dict() for v in vs] for k, vs in sorted(state.advisory_verdicts.items())},
            "claims": [c.as_dict() for c in state.all_claims],
            "receipts": {k: v.as_dict() for k, v in sorted(state.receipts.items())},
            "collisions": {str(k): [c.as_dict() for c in v] for k, v in sorted(state.collisions().items())},
            "malformed": state.malformed,
            "refs": sorted(refs),
            "merged_refs": sorted(merged),
        }, indent=2))
        return 0

    if args.proposal:
        p = state.proposals.get(args.proposal)
        if p is None:
            print(f"coord_board: no coord:proposal id={args.proposal}", file=sys.stderr)
            return 2
        dec = state.decision(args.proposal)
        v = verdict_for_display(state, args.proposal, p)
        print(f"PROPOSAL {args.proposal}: {dec}"
              + (f" by {v.attrs.get('by')}" if v else " - awaiting adjudication"))
        if args.can_build and dec != "accepted":
            print("coord_board: blocked - no accepted authoritative verdict", file=sys.stderr)
            return 3
        return 0

    if args.check_issue is not None:
        issue_state = args.issue_state
        if issue_state is None and not args.comments_file:
            issue_state = fetch_issue_state(args.repo, args.check_issue)
        if issue_state == "closed":
            print(f"CLOSED issue={args.check_issue} - work here is delivered; "
                  "file a follow-up leaf instead of rebuilding")
            return 3
        holders = state.claim_for_issue(args.check_issue)
        mine = [c for c in holders
                if R.agent_matches(c.attrs.get("agent", ""), args.agent or "")]
        others = [c for c in holders
                  if not R.agent_matches(c.attrs.get("agent", ""), args.agent or "")]
        if mine:
            print(f"CLAIMED-BY-YOU issue={args.check_issue} agent={args.agent}")
            return 0
        if others:
            h = others[-1]
            print(f"CLAIMED issue={args.check_issue} agent={h.attrs.get('agent')} "
                  f"branch={h.attrs.get('branch')}")
            # Distinct-holder rule matches records.collisions(): the reserved
            # branch is the mutex, so prose+coord double rows on ONE branch
            # are CLAIMED, not a collision (only >1 lock alarms).
            distinct = {
                c.attrs.get("branch") or f"agent:{c.attrs.get('agent', '?')}"
                for c in others
            }
            if len(distinct) > 1:
                print("  !! COLLISION: multiple different locks held here; "
                      "escalate to main agent", file=sys.stderr)
            return 3
        released = state.released_branches(args.check_issue)
        for ref in refs:
            if ref in merged or ref in released:
                continue
            if R.ref_issue_number(ref) == args.check_issue:
                print(f"CLAIMED-BY-REF issue={args.check_issue} branch={ref} "
                      "(unmerged reserved ref; no live claim comment — ask the main agent)")
                return 3
        print(f"FREE issue={args.check_issue}")
        return 0

    print(render(state, refs, merged))
    return 0


def _pin_utf8_stdio() -> None:
    """Pin stdout/stderr to UTF-8 for redirected output (#52).

    Windows encodes a redirected or piped stdout with the locale default
    (cp1252), so a single character outside it -- and the board renders agent
    ids, branches and receipt fields straight from GitHub text -- raises
    UnicodeEncodeError mid-render. Interactive console output uses the console
    API and is unaffected, which is why piping is what breaks. errors=replace
    matches the read side (#44): mangle an unknown glyph, never crash.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):  # detached, closed, or not a TextIO
            pass


if __name__ == "__main__":
    _pin_utf8_stdio()
    raise SystemExit(main())
