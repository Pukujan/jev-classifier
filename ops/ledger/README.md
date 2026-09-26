# ops/ledger — committed projection for agents

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
