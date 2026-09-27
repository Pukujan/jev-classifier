#!/usr/bin/env python3
"""Agent-to-agent message post/read helpers over GitHub comments (#61 Stage 1).

Messages are coord:message comment markers parsed by
jev_classifier.coord.records (grammar in docs/AGENT_PROPOSALS.md). This tool
only transports: posting is append-only, reading dedupes by stable message id
(at-least-once delivery), and retry after an uncertain post checks GitHub for
the same idempotency key before reposting. Messages carry NO authority: they
cannot claim, adjudicate, label, merge, or change issue state — the arbiter
ruling on #61 (comment 5851128354) keeps those powers in coord:claim /
coord:verdict only.

No local inbox/outbox cache in Stage 1: the rebuildable SQLite cache is a
separate, unaccepted stage.

Commands:
  read   --repo R [--issue N] [--kind K] [--to ALIAS] [--thread TID] [--json]
  post   --repo R --issue N --from AGENT --kind K --message TEXT
         [--to ALIAS] [--task ID] [--reply-to MSG_ID] [--thread TID]
         [--idem KEY] [--msg-id ID] [--dry-run]
  check  --repo R --issue N --idem KEY        # exit 0 if that key exists

Exit codes: 0 ok, 2 usage/config/fetch, 3 id collision (another sender holds
this message id).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT / "src"), str(_REPO_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load the pure parser directly so this helper runs without httpx, matching
# coord_ready.py's pattern.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    "jev_coord_records",
    str(_REPO_ROOT / "src" / "jev_classifier" / "coord" / "records.py"),
)
R = _ilu.module_from_spec(_spec)
sys.modules["jev_coord_records"] = R
_spec.loader.exec_module(R)

DEFAULT_REPO = "Pukujan/jev-classifier"
PROVENANCE_BLANKET = "agent_declared"  # sender attests every envelope field


class MsgError(RuntimeError):
    pass


def _gh(cmd_args: list[str], timeout: int = 180) -> str:
    try:
        proc = subprocess.run(["gh", *cmd_args], capture_output=True, text=True,
                              timeout=timeout)
    except FileNotFoundError as exc:
        raise MsgError("gh CLI not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise MsgError("gh timed out") from exc
    if proc.returncode != 0:
        raise MsgError(f"gh {' '.join(cmd_args[:3])} failed: "
                       f"{(proc.stderr or '').strip().splitlines()[:1]}")
    return proc.stdout


def decode_stream(text: str) -> list[dict]:
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
    return {"body": item.get("body") or "", "author": str(author),
            "created_at": str(created), "issue": int(issue),
            "comment_id": int(item.get("id") or 0)}


def fetch_issue_comments(repo: str, issue: int) -> list[dict]:
    out = _gh(["api", "-X", "GET", f"repos/{repo}/issues/{issue}/comments",
               "--paginate", "-f", "per_page=100", "--jq", "."])
    return [to_fold_comment(i) for i in decode_stream(out)]


def default_message_id(issue: int, sender: str, body: str) -> str:
    """Stable message id derived from issue + sender + body hash.

    A retry of the same logical message recomputes the same id, which is what
    lets `post` recognize an idempotent replay; different bodies never
    collide.
    """
    digest = hashlib.sha256(f"{issue}|{sender}|{body}".encode()).hexdigest()[:10]
    return f"m-{issue}-{digest}"


def render_marker(*, msg_id: str, task: str, sender: str, kind: str,
                  recipient: str, reply_to: str, thread: str, idem: str) -> str:
    attrs = [f"id={msg_id}", f"task={task}", f"from={sender}", f"kind={kind}"]
    if recipient:
        attrs.append(f"to={recipient}")
    if reply_to:
        attrs.append(f"reply_to={reply_to}")
    if thread:
        attrs.append(f"thread={thread}")
    if idem:
        attrs.append(f"idem={idem}")
    attrs.append(f"provenance={PROVENANCE_BLANKET}")
    return "<!-- coord:message " + " ".join(attrs) + " -->"


def read_messages(repo: str, issues: list[int] | None, *,
                  kind: str | None, to_alias: str | None,
                  thread: str | None) -> list:
    """Collect coord:message records from live comments, deduped by id.

    With an issue filter this stays per-issue (the documented polling
    discipline: watch claimed issues, not the firehose); without one it scans
    the repo-wide comments endpoint.
    """
    if issues:
        raw: list[dict] = []
        for n in issues:
            raw.extend(fetch_issue_comments(repo, n))
    else:
        out = _gh(["api", "-X", "GET", f"repos/{repo}/issues/comments",
                   "--paginate", "-f", "per_page=100", "--jq", "."])
        raw = [to_fold_comment(i) for i in decode_stream(out)]
    state = R.fold(raw)
    msgs = sorted(state.messages.values(), key=lambda r: (r.created_at, r.comment_id))
    if kind:
        msgs = [m for m in msgs if m.attrs.get("kind") == kind]
    if to_alias:
        msgs = [m for m in msgs if R.agent_matches(m.attrs.get("to", ""), to_alias)]
    if thread:
        msgs = [m for m in msgs if m.attrs.get("thread") == thread]
    return msgs


def cmd_read(args: argparse.Namespace) -> int:
    issues = [args.issue] if args.issue is not None else None
    try:
        msgs = read_messages(args.repo, issues, kind=args.kind,
                             to_alias=args.to, thread=args.thread)
    except MsgError as exc:
        print(f"coord_messages: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([m.as_dict() for m in msgs], indent=2))
        return 0
    print(f"coord_messages: {len(msgs)} message(s) "
          "(deduped by id; at-least-once transport)")
    for m in msgs:
        a = m.attrs
        arrow = "->" + (a.get("to") or "broadcast")
        print(f"  [{a.get('kind','?'):<8}] {a.get('id','?')} "
              f"{a.get('from','?')} {arrow} task={a.get('task','?')} "
              f"issue=#{m.issue} {m.created_at[:16]}"
              + (f" reply_to={a['reply_to']}" if a.get("reply_to") else ""))
    return 0


def cmd_post(args: argparse.Namespace) -> int:
    if args.issue is None or not args.message or not args.sender or not args.kind:
        print("coord_messages: post needs --issue --from --kind --message",
              file=sys.stderr)
        return 2
    if args.kind not in R.MESSAGE_KINDS:
        print(f"coord_messages: kind '{args.kind}' not in "
              f"{sorted(R.MESSAGE_KINDS)}", file=sys.stderr)
        return 2
    msg_id = args.msg_id or default_message_id(args.issue, args.sender,
                                               args.message)
    idem = args.idem or msg_id
    marker = render_marker(
        msg_id=msg_id, task=args.task or f"issue-{args.issue}",
        sender=args.sender, kind=args.kind, recipient=args.to or "",
        reply_to=args.reply_to or "", thread=args.thread or msg_id, idem=idem,
    )
    full = marker + "\n\n" + args.message + "\n"
    if args.dry_run:
        print(full, end="")
        return 0

    # At-least-once discipline (verdict conditions): check the target issue
    # for this id/idem before posting. The comparison is id-based on BOTH
    # sides: an existing message posted without an explicit id carries its
    # own content-derived hash, so recomputing it here matches a genuine
    # replay of same sender + body + issue — exactly the uncertain-post case.
    try:
        existing = read_messages(args.repo, [args.issue], kind=None,
                                 to_alias=None, thread=None)
    except MsgError as exc:
        print(f"coord_messages: pre-check failed ({exc}); aborting, do not guess",
              file=sys.stderr)
        return 2
    collision = None
    for m in existing:
        same = (m.attrs.get("id") in (msg_id, idem)
                or m.attrs.get("idem") in (idem, msg_id))
        if same:
            if m.attrs.get("from") == args.sender:
                print(f"coord_messages: message {msg_id} already exists on "
                      f"#{args.issue} (idempotent replay skipped)")
                return 0
            collision = m
    if collision is not None:
        print(f"coord_messages: id collision: {msg_id} already posted by "
              f"{collision.attrs.get('from')}", file=sys.stderr)
        return 3
    try:
        _gh(["api", "-X", "POST", f"repos/{args.repo}/issues/{args.issue}/comments",
             "-f", "body=" + full])
    except MsgError as exc:
        print(f"coord_messages: {exc}", file=sys.stderr)
        return 2
    print(f"posted {msg_id} kind={args.kind} issue=#{args.issue}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    try:
        existing = read_messages(args.repo, [args.issue], kind=None,
                                 to_alias=None, thread=None)
    except MsgError as exc:
        print(f"coord_messages: {exc}", file=sys.stderr)
        return 2
    for m in existing:
        if m.attrs.get("idem") == args.idem or m.attrs.get("id") == args.idem:
            print(f"found idem={args.idem} (message {m.attrs.get('id')})")
            return 0
    print(f"no message with idem={args.idem} on #{args.issue}")
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=DEFAULT_REPO)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("read", help="list coord:message records (deduped by id)")
    r.add_argument("--issue", type=int)
    r.add_argument("--kind", choices=sorted(R.MESSAGE_KINDS))
    r.add_argument("--to", help="recipient alias to filter by")
    r.add_argument("--thread", help="thread/correlation id to filter by")
    r.add_argument("--json", action="store_true")

    p = sub.add_parser("post", help="append one coord:message comment")
    p.add_argument("--issue", type=int, required=True)
    p.add_argument("--from", dest="sender", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--message", required=True, help="markdown body (no secrets)")
    p.add_argument("--to", default="")
    p.add_argument("--task", default="")
    p.add_argument("--reply-to", default="")
    p.add_argument("--thread", default="")
    p.add_argument("--idem", default="")
    p.add_argument("--msg-id", default="")
    p.add_argument("--dry-run", action="store_true")

    c = sub.add_parser("check", help="exit 0 if an idempotency key exists")
    c.add_argument("--issue", type=int, required=True)
    c.add_argument("--idem", required=True)

    args = ap.parse_args(argv)
    if args.cmd == "read":
        return cmd_read(args)
    if args.cmd == "post":
        return cmd_post(args)
    if args.cmd == "check":
        return cmd_check(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
