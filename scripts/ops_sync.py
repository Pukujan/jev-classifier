#!/usr/bin/env python3
"""Sync GitHub issue/PR state into local OpsStore + committed ops/ledger/.

GitHub remains authority. Local SQLite is an execution aid. The ledger is a
readable projection for other agents. This script does **not** decide proposal
winners or arbitration.

Usage:
  python scripts/ops_sync.py --fixture tests/fixtures/ops/snapshot.json
  python scripts/ops_sync.py --repo Pukujan/jev-classifier
  python scripts/ops_sync.py --fixture PATH --db .ops/ops.db --ledger-dir ops/ledger
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow running without install when repo root is cwd
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from jev_classifier.ops.store import (  # noqa: E402
    DEFAULT_OPS_DB_PATH,
    IssueSnapshot,
    OpsStore,
)

# Secret-ish patterns that must never appear in ledger output
_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password|authorization)\s*[:=]\s*\S+"),
    re.compile(r"(?i)sk-[a-zA-Z0-9]{10,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"(?i)OPENROUTER_API_KEY\s*=\s*\S+"),
)

_ISSUE_REF_RE = re.compile(
    r"(?:(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+)?#"
    r"(\d+)|(?:https?://github\.com/[^/\s]+/[^/\s]+/(?:issues|pull)/(\d+))",
    re.IGNORECASE,
)

_CURRENT_IN_FLIGHT_RE = re.compile(
    r"(?im)^##\s+In flight\s*$([\s\S]*?)(?=^##\s+|\Z)"
)
_ISSUE_NUM_RE = re.compile(r"#(\d+)")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_secrets(text: str) -> str:
    """Strip secret-looking substrings from text destined for the ledger."""
    if not text:
        return text
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    # Never echo .env-looking assignments
    out = re.sub(
        r"(?m)^[A-Z][A-Z0-9_]*(?:KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)[A-Z0-9_]*\s*=\s*.+$",
        "[REDACTED_ENV_LINE]",
        out,
    )
    return out


def excerpt_body(body: str | None, *, max_len: int = 400) -> str | None:
    if not body:
        return None
    cleaned = redact_secrets(body.strip().replace("\r\n", "\n"))
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1] + "…"


def parse_linked_issue_numbers(text: str | None) -> list[int]:
    if not text:
        return []
    found: list[int] = []
    for m in _ISSUE_REF_RE.finditer(text):
        n = m.group(1) or m.group(2)
        if n:
            found.append(int(n))
    # unique, stable order
    seen: set[int] = set()
    out: list[int] = []
    for n in found:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def load_fixture(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("fixture root must be an object")
    data.setdefault("issues", [])
    data.setdefault("pull_requests", [])
    data.setdefault("current_md", "")
    data.setdefault("coord_claims", [])
    return data


def fetch_via_gh(repo: str) -> dict[str, Any]:
    """Pull issues + PRs with `gh`. Raises on failure."""

    def _gh_json(args: list[str]) -> Any:
        proc = subprocess.run(
            ["gh", *args],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(proc.stdout) if proc.stdout.strip() else []

    issues = _gh_json(
        [
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,title,state,author,assignees,labels,body,url,updatedAt",
        ]
    )
    prs = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            repo,
            "--state",
            "all",
            "--limit",
            "200",
            "--json",
            "number,title,state,author,assignees,labels,body,url,updatedAt",
        ]
    )
    return {"issues": issues, "pull_requests": prs}


def _norm_login(obj: Any) -> str | None:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return obj.get("login") or obj.get("name") or obj.get("id")
    return str(obj)


def snapshots_from_payload(payload: dict[str, Any]) -> list[IssueSnapshot]:
    ts = _utc_now()
    out: list[IssueSnapshot] = []

    for raw in payload.get("issues") or []:
        assignees = [
            a
            for a in (_norm_login(x) for x in (raw.get("assignees") or []))
            if a
        ]
        labels = []
        for lab in raw.get("labels") or []:
            if isinstance(lab, dict):
                labels.append(str(lab.get("name") or lab))
            else:
                labels.append(str(lab))
        body = raw.get("body")
        out.append(
            IssueSnapshot(
                number=int(raw["number"]),
                title=str(raw.get("title") or ""),
                state=str(raw.get("state") or "open").lower(),
                is_pr=False,
                author=_norm_login(raw.get("author")),
                assignees=tuple(assignees),
                labels=tuple(labels),
                body_excerpt=excerpt_body(body),
                url=raw.get("url"),
                updated_at=raw.get("updatedAt") or raw.get("updated_at"),
                synced_at=ts,
                linked_issue_numbers=tuple(parse_linked_issue_numbers(body)),
            )
        )

    for raw in payload.get("pull_requests") or []:
        assignees = [
            a
            for a in (_norm_login(x) for x in (raw.get("assignees") or []))
            if a
        ]
        labels = []
        for lab in raw.get("labels") or []:
            if isinstance(lab, dict):
                labels.append(str(lab.get("name") or lab))
            else:
                labels.append(str(lab))
        body = raw.get("body") or ""
        linked = parse_linked_issue_numbers(body)
        # gh closingIssuesReferences when present
        for ref in raw.get("closingIssuesReferences") or []:
            n = ref.get("number") if isinstance(ref, dict) else None
            if n is not None and int(n) not in linked:
                linked.append(int(n))
        # fixture-friendly explicit field
        for n in raw.get("linked_issue_numbers") or []:
            if int(n) not in linked:
                linked.append(int(n))
        state = str(raw.get("state") or "open").lower()
        if state == "merged":
            state = "closed"
        out.append(
            IssueSnapshot(
                number=int(raw["number"]),
                title=str(raw.get("title") or ""),
                state=state,
                is_pr=True,
                author=_norm_login(raw.get("author")),
                assignees=tuple(assignees),
                labels=tuple(labels),
                body_excerpt=excerpt_body(body),
                url=raw.get("url"),
                updated_at=raw.get("updatedAt") or raw.get("updated_at"),
                synced_at=ts,
                linked_issue_numbers=tuple(linked),
            )
        )
    return out


def detect_discrepancies(
    snapshots: list[IssueSnapshot],
    *,
    current_md: str = "",
    coord_claims: list[dict[str, Any]] | None = None,
    coord_db_path: Path | None = None,
) -> list[dict[str, str]]:
    """Deterministic discrepancy detectors. Returns list of {kind, subject_type, subject_id, detail}."""
    flags: list[dict[str, str]] = []
    issues = [s for s in snapshots if not s.is_pr]
    prs = [s for s in snapshots if s.is_pr]
    open_issue_nums = {s.number for s in issues if s.state == "open"}
    closed_issue_nums = {s.number for s in issues if s.state == "closed"}
    all_issue_nums = {s.number for s in issues}

    # 1) Open PR without linked issue
    for pr in prs:
        if pr.state != "open":
            continue
        # Empty linked_issue_numbers means discrepancy
        if not pr.linked_issue_numbers:
            flags.append(
                {
                    "kind": "open_pr_without_linked_issue",
                    "subject_type": "pr",
                    "subject_id": str(pr.number),
                    "detail": (
                        f"Open PR #{pr.number} ({pr.title!r}) has no linked issue "
                        f"reference in body/closingIssuesReferences."
                    ),
                }
            )

    # 2) CURRENT.md vs open issues (in-flight section mentions)
    if current_md:
        m = _CURRENT_IN_FLIGHT_RE.search(current_md)
        section = m.group(1) if m else ""
        mentioned = {int(x) for x in _ISSUE_NUM_RE.findall(section)}
        # Ignore empty / "none" board
        none_board = bool(
            re.search(r"(?i)_\(none|board clear|none —", section)
        ) or not section.strip()
        if not none_board:
            for n in sorted(mentioned):
                if n not in open_issue_nums:
                    flags.append(
                        {
                            "kind": "current_md_vs_open_issues",
                            "subject_type": "issue",
                            "subject_id": str(n),
                            "detail": (
                                f"docs/CURRENT.md In flight mentions #{n} but that "
                                f"issue is not open in the synced snapshot."
                            ),
                        }
                    )
            # Open issues that look active but absent from CURRENT when CURRENT lists specifics
            # (soft): only flag if CURRENT named some issues and an open leaf is missing?
            # Keep detector narrow: CURRENT mentions closed/missing issue only.

        # Also: if CURRENT says "none" but there are open product leaves beyond parent — stub note
        # (not flagged as error; ownership stubs cover collisions)

    # 3) Ownership / collision stubs from fixture or coord DB
    claims = list(coord_claims or [])
    if coord_db_path and coord_db_path.is_file():
        claims.extend(_read_coord_claims(coord_db_path))

    # Collision: same resource claimed by >1 active agent in the claim list
    by_resource: dict[tuple[str, str], list[str]] = {}
    for c in claims:
        if str(c.get("status") or "active") != "active":
            continue
        key = (str(c.get("resource_type") or "issue"), str(c.get("resource_id") or ""))
        agent = str(c.get("agent_id") or "")
        if not key[1] or not agent:
            continue
        by_resource.setdefault(key, [])
        if agent not in by_resource[key]:
            by_resource[key].append(agent)

    for (rtype, rid), agents in sorted(by_resource.items()):
        if len(agents) > 1:
            flags.append(
                {
                    "kind": "ownership_collision_stub",
                    "subject_type": rtype,
                    "subject_id": rid,
                    "detail": (
                        f"Ownership collision stub: {rtype}/{rid} claimed by "
                        f"{', '.join(agents)}. Authoritative agent decides; "
                        f"this store does not pick a winner."
                    ),
                }
            )

    # 4) Closed issue still claimed in coord
    for c in claims:
        if str(c.get("status") or "active") != "active":
            continue
        if str(c.get("resource_type") or "") != "issue":
            continue
        rid = str(c.get("resource_id") or "")
        try:
            n = int(rid)
        except ValueError:
            continue
        if n in closed_issue_nums:
            flags.append(
                {
                    "kind": "closed_issue_still_claimed",
                    "subject_type": "issue",
                    "subject_id": rid,
                    "detail": (
                        f"Closed issue #{n} still has active coord claim by "
                        f"{c.get('agent_id')!r}. GitHub (closed) is authority; "
                        f"release the local claim."
                    ),
                }
            )

    return flags


def _read_coord_claims(path: Path) -> list[dict[str, Any]]:
    """Best-effort read of CoordStore ownership rows. Missing/unreadable → []."""
    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM ownership").fetchall()
        except sqlite3.Error:
            return []
        finally:
            conn.close()
        return [dict(r) for r in rows]
    except (OSError, sqlite3.Error):
        return []


def write_ledger(
    ledger_dir: Path,
    snapshots: list[IssueSnapshot],
    discrepancies: list[dict[str, str]],
    *,
    source: str,
    sync_run_id: int | None = None,
) -> None:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    issues_dir = ledger_dir / "issues"
    issues_dir.mkdir(parents=True, exist_ok=True)

    issues = [s for s in snapshots if not s.is_pr]
    prs = [s for s in snapshots if s.is_pr]
    ts = _utc_now()

    # Per-issue JSON (no secrets)
    # Clear prior issue JSON files for idempotent projection
    for old in issues_dir.glob("*.json"):
        old.unlink()

    for snap in sorted(snapshots, key=lambda s: (s.is_pr, s.number)):
        kind = "pr" if snap.is_pr else "issue"
        payload = {
            "kind": kind,
            "number": snap.number,
            "title": redact_secrets(snap.title),
            "state": snap.state,
            "author": snap.author,
            "assignees": list(snap.assignees),
            "labels": list(snap.labels),
            "url": snap.url,
            "updated_at": snap.updated_at,
            "synced_at": snap.synced_at or ts,
            "linked_issue_numbers": list(snap.linked_issue_numbers),
            "body_excerpt": redact_secrets(snap.body_excerpt or "") or None,
        }
        # Ensure serialized form has no secret patterns
        text = redact_secrets(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        (issues_dir / f"{kind}-{snap.number:04d}.json").write_text(text, encoding="utf-8")

    # ISSUE_LOG.md
    lines = [
        "# Issue log (ops ledger projection)",
        "",
        f"Synced: `{ts}` (source: `{source}`"
        + (f", sync_run_id={sync_run_id}" if sync_run_id else "")
        + ")",
        "",
        "> **Authority:** GitHub issues/PRs. This file is a readable projection for agents.",
        "> Local `.ops/ops.db` is an execution aid only. Proposal winners are decided by the",
        "> **authoritative agent** — this ledger does not arbitrate.",
        "",
        "## Open issues",
        "",
    ]
    open_issues = [s for s in issues if s.state == "open"]
    if not open_issues:
        lines.append("_(none)_")
        lines.append("")
    else:
        lines.append("| # | Title | Assignees | Labels |")
        lines.append("|---|-------|-----------|--------|")
        for s in sorted(open_issues, key=lambda x: x.number):
            asg = ", ".join(s.assignees) or "—"
            labs = ", ".join(s.labels) or "—"
            lines.append(
                f"| #{s.number} | {redact_secrets(s.title)} | {asg} | {labs} |"
            )
        lines.append("")

    lines.extend(["## Open pull requests", ""])
    open_prs = [s for s in prs if s.state == "open"]
    if not open_prs:
        lines.append("_(none)_")
        lines.append("")
    else:
        lines.append("| # | Title | Linked issues | Assignees |")
        lines.append("|---|-------|---------------|-----------|")
        for s in sorted(open_prs, key=lambda x: x.number):
            linked = ", ".join(f"#{n}" for n in s.linked_issue_numbers) or "—"
            asg = ", ".join(s.assignees) or "—"
            lines.append(
                f"| #{s.number} | {redact_secrets(s.title)} | {linked} | {asg} |"
            )
        lines.append("")

    lines.extend(["## Closed / other (recent snapshot)", ""])
    closed = [s for s in issues if s.state != "open"] + [
        s for s in prs if s.state != "open"
    ]
    if not closed:
        lines.append("_(none in snapshot)_")
        lines.append("")
    else:
        lines.append("| Kind | # | State | Title |")
        lines.append("|------|---|-------|-------|")
        for s in sorted(closed, key=lambda x: (x.is_pr, x.number)):
            kind = "PR" if s.is_pr else "Issue"
            lines.append(
                f"| {kind} | #{s.number} | {s.state} | {redact_secrets(s.title)} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Per-item JSON",
            "",
            "See `ops/ledger/issues/` for one JSON file per issue/PR in this projection.",
            "",
        ]
    )
    (ledger_dir / "ISSUE_LOG.md").write_text(
        redact_secrets("\n".join(lines)), encoding="utf-8"
    )

    # DISCREPANCIES.md
    dlines = [
        "# Discrepancies (ops ledger projection)",
        "",
        f"Synced: `{ts}` (source: `{source}`"
        + (f", sync_run_id={sync_run_id}" if sync_run_id else "")
        + ")",
        "",
        "> Deterministic flags only. **Do not** treat this list as arbitration.",
        "> GitHub remains authority; the authoritative agent decides proposal winners.",
        "",
    ]
    if not discrepancies:
        dlines.append("_(no discrepancies detected)_")
        dlines.append("")
    else:
        dlines.append(f"Count: **{len(discrepancies)}**")
        dlines.append("")
        for i, d in enumerate(discrepancies, 1):
            dlines.append(
                f"### {i}. `{d['kind']}` — {d.get('subject_type', '?')}/{d.get('subject_id', '?')}"
            )
            dlines.append("")
            dlines.append(redact_secrets(d["detail"]))
            dlines.append("")

    (ledger_dir / "DISCREPANCIES.md").write_text(
        redact_secrets("\n".join(dlines)), encoding="utf-8"
    )


def ensure_ledger_readme(ledger_dir: Path) -> None:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    readme = ledger_dir / "README.md"
    if readme.exists():
        return
    readme.write_text(
        """# ops/ledger — committed projection for agents

This directory is a **committed, human- and agent-readable projection** of
GitHub issue/PR state plus discrepancy flags.

## Authority

| Layer | Role |
|-------|------|
| GitHub issues/PRs | **Authority** for work items, ownership, delivery |
| `.ops/ops.db` (gitignored) | Local execution aid (snapshots, sync runs, flags) |
| `ops/ledger/` (this tree) | Readable projection other agents can open on GitHub |

**Proposal / arbitration winners are decided by the authoritative agent.**
This ledger and the local DB do **not** pick winners.

## Files

| Path | Contents |
|------|----------|
| `ISSUE_LOG.md` | Summary tables of open/closed issues and PRs |
| `DISCREPANCIES.md` | Deterministic discrepancy flags from last sync |
| `issues/*.json` | Per-issue / per-PR JSON snapshots (redacted) |
| `README.md` | This file |

## How agents should use it

1. Prefer live GitHub when deciding what to work on.
2. Read `ISSUE_LOG.md` / `DISCREPANCIES.md` for a quick board + collision hints.
3. If ledger and GitHub disagree, **GitHub wins** — re-run sync.
4. Never store or expect secrets here.

## Refresh

```bash
python scripts/ops_sync.py --repo OWNER/REPO
# offline / CI:
python scripts/ops_sync.py --fixture tests/fixtures/ops/snapshot.json
```

See `docs/OPS_LEDGER.md` for full protocol.
""",
        encoding="utf-8",
    )


def run_sync(
    *,
    fixture: Path | None,
    repo: str,
    db_path: Path,
    ledger_dir: Path,
    current_md_path: Path | None,
    coord_db_path: Path | None,
) -> dict[str, Any]:
    source = "fixture" if fixture else "gh"
    if fixture:
        payload = load_fixture(fixture)
        current_md = str(payload.get("current_md") or "")
        coord_claims = list(payload.get("coord_claims") or [])
    else:
        payload = fetch_via_gh(repo)
        current_md = ""
        coord_claims = []
        if current_md_path and current_md_path.is_file():
            current_md = current_md_path.read_text(encoding="utf-8")
        # live mode: still allow empty coord_claims; file path handled in detect

    if not current_md and current_md_path and current_md_path.is_file():
        current_md = current_md_path.read_text(encoding="utf-8")

    snapshots = snapshots_from_payload(payload)
    # Normalize state values
    for i, s in enumerate(snapshots):
        state = s.state.lower()
        if state not in ("open", "closed"):
            # gh returns OPEN/CLOSED sometimes already lowercased above
            state = "open" if state in ("open", "OPEN") else "closed"
            snapshots[i] = IssueSnapshot(
                number=s.number,
                title=s.title,
                state=state,
                is_pr=s.is_pr,
                author=s.author,
                assignees=s.assignees,
                labels=s.labels,
                body_excerpt=s.body_excerpt,
                url=s.url,
                updated_at=s.updated_at,
                synced_at=s.synced_at,
                linked_issue_numbers=s.linked_issue_numbers,
            )

    with OpsStore(db_path) as store:
        run_id = store.begin_sync_run(source=source)
        try:
            store.replace_all_snapshots(snapshots)
            store.clear_discrepancies(unresolved_only=True)
            flags = detect_discrepancies(
                snapshots,
                current_md=current_md,
                coord_claims=coord_claims,
                coord_db_path=coord_db_path,
            )
            for f in flags:
                store.add_discrepancy(
                    kind=f["kind"],
                    detail=f["detail"],
                    subject_type=f.get("subject_type"),
                    subject_id=f.get("subject_id"),
                    sync_run_id=run_id,
                )
            ensure_ledger_readme(ledger_dir)
            write_ledger(
                ledger_dir,
                snapshots,
                flags,
                source=source,
                sync_run_id=run_id,
            )
            issue_count = sum(1 for s in snapshots if not s.is_pr)
            pr_count = sum(1 for s in snapshots if s.is_pr)
            store.finish_sync_run(
                run_id,
                status="ok",
                issue_count=issue_count,
                pr_count=pr_count,
                discrepancy_count=len(flags),
            )
            return {
                "ok": True,
                "sync_run_id": run_id,
                "source": source,
                "issue_count": issue_count,
                "pr_count": pr_count,
                "discrepancy_count": len(flags),
                "discrepancies": flags,
                "db_path": str(db_path),
                "ledger_dir": str(ledger_dir),
            }
        except Exception as exc:  # noqa: BLE001 — record failure then re-raise
            store.finish_sync_run(
                run_id,
                status="error",
                notes=str(exc)[:500],
            )
            raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Offline JSON fixture (skips gh). Path relative to cwd or absolute.",
    )
    parser.add_argument(
        "--repo",
        default="Pukujan/jev-classifier",
        help="GitHub repo for live gh sync (default: Pukujan/jev-classifier)",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(DEFAULT_OPS_DB_PATH),
        help=f"Ops SQLite path (default: {DEFAULT_OPS_DB_PATH})",
    )
    parser.add_argument(
        "--ledger-dir",
        type=Path,
        default=Path("ops/ledger"),
        help="Committed ledger directory (default: ops/ledger)",
    )
    parser.add_argument(
        "--current-md",
        type=Path,
        default=Path("docs/CURRENT.md"),
        help="Path to docs/CURRENT.md for discrepancy checks",
    )
    parser.add_argument(
        "--coord-db",
        type=Path,
        default=Path(".coord/agents.db"),
        help="Optional CoordStore DB to read ownership claims",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary JSON to stdout",
    )
    args = parser.parse_args(argv)

    result = run_sync(
        fixture=args.fixture,
        repo=args.repo,
        db_path=args.db,
        ledger_dir=args.ledger_dir,
        current_md_path=args.current_md,
        coord_db_path=args.coord_db,
    )
    if args.json:
        # Never include secret material; flags are already redacted in detail text
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            f"ops_sync ok source={result['source']} issues={result['issue_count']} "
            f"prs={result['pr_count']} discrepancies={result['discrepancy_count']} "
            f"ledger={result['ledger_dir']} db={result['db_path']}"
        )
        for d in result["discrepancies"]:
            print(f"  - {d['kind']}: {d['subject_type']}/{d['subject_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
