# Agent coordination protocol

**Authority:** GitHub issues and PRs are the source of truth for work items, ownership, and delivery. The local SQLite store (`jev_classifier.coord.CoordStore`) is an **execution aid only** — a rebuildable projection that helps concurrent agents avoid colliding and retry safely.

## What the store tracks

| Table | Purpose |
|-------|---------|
| `checkpoints` | Idempotent progress keys (`checkpoint_key` PRIMARY KEY). Second insert with the same key is a no-op that returns the original row. |
| `ownership` | Who currently claims an `issue` / `pr` / `sub_issue` / `branch`. Same-agent reclaim is fine; different-agent claim → `CollisionError` + `collision_flags` row. |
| `send_log` | Who sent what (channel, target, summary) with optional `idempotency_key` for safe retries. |
| `collision_flags` | Contradiction / collision events for humans or later agents to resolve. |

Default on-disk path recommendation: `.coord/agents.db` (gitignored). Tests use `:memory:`.

## Protocol

1. **Claim before write.** Before opening a PR or pushing product commits for an issue, call `claim_ownership(resource_type="issue", resource_id="<n>", agent_id="<you>")`. If `CollisionError`, stop and comment on the GitHub issue — do not overwrite the other agent's branch.
2. **Checkpoint after verifiable milestones.** Use stable keys like `issue-<n>/<milestone-id>`. Retries must be idempotent: `put_checkpoint` must not duplicate rows.
3. **Log outbound messages.** When commenting on issues/PRs, `log_send(..., idempotency_key=...)` so a crashed retry does not double-post from the store's point of view (GitHub remains the real audit log).
4. **Release on handoff or merge.** `release_ownership` when the issue is closed, PR merged, or work is explicitly handed off.
5. **Never treat SQLite as authority.** If SQLite and GitHub disagree, **GitHub wins**. Rebuild or delete `.coord/` freely.

## Anti-patterns

- Using the store instead of filing/updating a GitHub issue.
- Claiming `main` as an ownership resource for product commits (product work stays on feature branches + issue-backed PRs).
- Storing secrets, API keys, or `.env` contents in checkpoint payloads.
- Force-pushing or committing directly to `main` because a local claim "won".

## Minimal usage

```python
from jev_classifier.coord import CoordStore, CollisionError

with CoordStore(".coord/agents.db") as store:
    store.claim_ownership(resource_type="issue", resource_id="3", agent_id="jev-agent")
    store.put_checkpoint("issue-3/schema-v1", agent_id="jev-agent", issue_number=3)
    store.log_send(
        agent_id="jev-agent",
        channel="github_issue_comment",
        target="issue/3",
        summary="schema landed",
        idempotency_key="issue-3-schema-comment",
    )
```

## Verify

```bash
python -m pytest tests/test_coord.py -v
```
