# Ops ledger protocol

**Authority:** GitHub issues and PRs are the source of truth for work items,
ownership, and delivery. Two local/projection layers help agents stay oriented:

| Layer | Path | Authority? | Purpose |
|-------|------|------------|---------|
| GitHub | issues / PRs | **Yes** | Canonical task board |
| Ops SQLite | `.ops/ops.db` (gitignored) | No | Live snapshots, sync runs, discrepancy flags |
| Committed ledger | `ops/ledger/` | No (projection) | Readable board + discrepancy report for agents on GitHub |
| Coord SQLite | `.coord/agents.db` (gitignored) | No | Ownership claims / checkpoints (see `docs/AGENT_COORD.md`) |
| Coordination board | `ops/ledger/COORD.md` (#22) | No (projection) | Live claims / proposals / verdicts / run receipts parsed from GitHub comments |

## Hard rules

1. **GitHub wins** when any local DB or ledger projection disagrees.
2. The ops store and ledger **do not** decide proposal winners or arbitration —
   only the **authoritative agent** does.
3. **Never** print, log, or commit secrets, API keys, or `.env` values into the
   ledger or issue comments.
4. JEV-only rules for classifier labels still hold; this work is **ops**, not
   classification.

## Schema (OpsStore)

Tables:

- `issue_snapshots` — last-seen issues and PRs (`number` + `is_pr` PK)
- `discrepancy_flags` — deterministic flags from the last sync
- `sync_runs` — history of fixture/`gh` sync executions
- `meta` — `schema_version`

Default path: `.ops/ops.db`.

## Discrepancy detectors

| Kind | Meaning |
|------|---------|
| `open_pr_without_linked_issue` | Open PR body/refs have no linked issue number |
| `current_md_vs_open_issues` | `docs/CURRENT.md` In flight mentions an issue that is not open |
| `ownership_collision_stub` | Fixture/coord shows >1 active claim on the same resource |
| `closed_issue_still_claimed` | Closed GitHub issue still has an active coord ownership claim |
| `coord_claim_collision` | >1 live claim holding **different** locks on one issue (holder = reserved branch, falling back to agent when a row has none; #53 — a same-branch prose+coord double-post is one lock, not a collision; see `docs/AGENT_PROPOSALS.md`) |
| `coord_record_malformed` | A `coord:*` comment marker is missing required fields (fail-closed; fix the comment) |
| `closed_issue_coord_claim` | A live GitHub-comment claim on a closed issue (auto-settled by `settle_claims`, flagged for audit) |

These are **hints**. Resolving them is a human/authoritative-agent matter.

## Sync command

```bash
# Live (requires gh auth)
python scripts/ops_sync.py --repo Pukujan/jev-classifier

# Offline / CI
python scripts/ops_sync.py --fixture tests/fixtures/ops/snapshot.json

# Custom paths
python scripts/ops_sync.py --fixture PATH --db .ops/ops.db --ledger-dir ops/ledger
```

The sync:

1. Loads issues/PRs from `gh` or a fixture JSON.
2. Upserts into OpsStore and records a `sync_runs` row.
3. Runs discrepancy detectors (optionally reading `.coord/agents.db`).
4. Rewrites `ops/ledger/ISSUE_LOG.md`, `DISCREPANCIES.md`, and `issues/*.json`.
5. Rewrites `ops/ledger/COORD.md` — only in live (`gh`) mode; fixture runs
   never touch the committed board (`write_coord` defaults to live-only).
   Claim rows whose branch merged or issue closed are settled out of Live
   claims automatically (`released_by=merged_pr|closed_issue`).

## How other agents should read the ledger

1. Open `ops/ledger/ISSUE_LOG.md` for a quick open-issue / open-PR board.
2. Open `ops/ledger/DISCREPANCIES.md` for collision / stale-claim hints, and
   `ops/ledger/COORD.md` for live claims, proposal decisions, and run receipts.
3. Drill into `ops/ledger/issues/*.json` when needed.
4. Confirm against live GitHub before claiming work or merging.
5. Comment on the relevant GitHub issue when acting — do not treat the ledger
   as a second task queue.

## Verify

```bash
python -m pytest tests/test_ops.py -v
```
