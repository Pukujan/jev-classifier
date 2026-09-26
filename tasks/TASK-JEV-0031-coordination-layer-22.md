# TASK-JEV-0031 — Coordination Layer 22

<!-- continuity:task {"acceptance":["reserved-branch claim (marker push + coord:claim) rejects a second claimant across devices","coord_board gate returns FREE/CLAIMED/CLOSED with exit 0/3 from live GitHub state","advisory verdicts never void an authoritative decision; claims key per (issue, holder) so collisions stay visible","run receipts parse with per-field provenance and fail closed on unknown sources","merged/closed issues auto-release claim rows from the committed board","full offline test suite green, incl. tests/test_coord_board.py and tests/test_ops_coord_board.py"],"depends_on":[],"goal":"Coordination layer v2: cross-device claim mutex + adjudication grammar + run receipts","id":"JEV-0031","issue_url":"https://github.com/Pukujan/jev-classifier/issues/22","next_action":"none — delivered; follow-ons go to their own issues","owner":"coordination-flagger","priority":"P1","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"completed","why":"SQLite-only claims could not collide across devices; 4 agents on one account rebuilt the same work"} -->

- Status: completed
- Owner: coordination-flagger (arbiter: main agent session, `claude-code-main`)
- Priority: P1
- Depends on: none (#18/#25 merged bases extended, not replaced)

## Goal

Make duplicate work structurally impossible for the multi-agent fleet on this
repo: a cross-device claim mutex, a machine-readable proposal/verdict grammar
with one authoritative adjudicator, append-only run receipts with per-field
provenance (owner telemetry direction), and a read-only storage watchdog.

## Why

Every agent shares the `Pukujan` GitHub account and each machine's SQLite
ownership table is a gitignored local file — `CollisionError` could never fire
across devices, so two agents could build the same task until both PRs landed.
The #22 collision between the arbiter's own dogfood push and this branch
proved the reserved-branch mutex does fire.

## Allowed files

`src/jev_classifier/coord/records.py`, `scripts/coord_board.py`,
`scripts/watchdog_storage.py`, `scripts/ops_sync.py` (extension only),
`docs/AGENT_PROPOSALS.md`, `docs/AGENT_COORD.md`, `AGENTS.md`,
`ops/ledger/COORD.md`, `tests/test_coord_board.py`,
`tests/test_ops_coord_board.py`, `tests/test_watchdog_storage.py`,
`tests/fixtures/{ops/snapshot.json,coord/comments.json}`,
`.github/workflows/ci.yml` (step addition inside existing jobs only).

## Human outcome

A newcomer agent can answer, from GitHub alone, "is this issue taken, is this
design decided, may I build?" with one command (`scripts/coord_board.py`), and
the owner gets auditable per-run receipts whose every field states its
evidence class.

## Scope and boundaries

- In scope: claim/proposal/verdict/receipt grammar; gate CLI; COORD.md
  projection; settle-on-merge/close; watchdog; CI step.
- Out of scope: classifier logic; second boards; SQLite authority; alias→identity
  vault (owner-side by design).
- Dependencies/uncertainty: `by=`/`agent=` are self-declared under the shared
  account — roster filtering stops accidents, not deliberate forgery
  (documented as evidence-not-enforcement).

## Acceptance criteria

- [x] Reserved branch `feat/<slug>-<issue#>` + marker push claims an issue;
      second create-ref push is rejected (observed: arbiter's own dogfood push
      rejected against `67eaa8b`, recorded on #22).
- [x] `--issue-open` gate: FREE/CLAIMED/CLAIMED-BY-YOU/CLOSED with exit 0/3,
      live path exercised (`--issue-open 35` → CLAIMED rc=3 + collision note;
      `--issue-open 22` post-close → CLOSED rc=3; `--issue-open 33` → FREE rc=0).
- [x] Advisory (non-roster) verdicts never void an authoritative decision;
      issue-level ratifications key `issue:<n>` and fold ACCEPT/ACCEPT-DECOMPOSE.
- [x] Run receipts: `run=`+`outcome=` required, per-field provenance validated
      fail-closed against the 5-source vocabulary; append-only correction path
      exercised (r-36-1 → r-36-1-fix1 on #22).
- [x] Merged/closed auto-release: board regenerated post-#36 dropped the #22
      row (fix shipped in #38 after the first refresh proved the plumbing
      missing — regression tests pin both directions).
- [x] Offline suite green: 150 passed; CI adds coord_board smoke step inside
      the existing test job (required contexts unchanged).

## Evidence and sources

- Merged: PR #36 `ae8d7fd` (layer), PR #38 `c259310` (merged-PR settle fix +
  refreshed COORD.md), PR #39 `f98c991` (SYSTEM_SPEC tool-name correction).
- CI: runs 36272930329 / 36273321873 / 36273664478 / 36273911722 — hygiene +
  test (3.11) + test (3.12) pass on each head; "coord_board CLI smoke ok"
  observed in both matrix logs.
- Live JEV observation (this device, 2026-09-26 21:2x local): `scripts/smoke_jev.py`
  → choice returned with probability map from `typesafe/jev-1.13-20260917`;
  key handling: copied only the OpenRouter line into gitignored `.env`, never
  committed or printed.
- `continuity preflight --root .` → `MODE: TARGET_VALID`; `continuity validate`
  → VALID.

## Related records

- Leaf issue: #22; parent #14; program #21 untouched by this task.
- Primary writer: `coordination-flagger` on branch `feat/coordination-layer-22`
  (claim comment 5849038366, rekeyed 19:2x per arbiter correction 5849256745);
  delivered as of `ae8d7fd`/`c259310`.
- PCM engagement log: `Pukujan/project-continuity-modules` issue #208.

## Checkpoint log

- 2026-09-26T19:09Z — claim marker push `67eaa8b` + coord:claim (mutex armed).
- 2026-09-26T21:24Z — implementation rebased onto `37885a0`, pushed, PR #36 open.
- 2026-09-26T21:29Z — PR #36 merged green; receipt r-36-1 + correction posted.
- 2026-09-26T21:44Z — PR #38 merged green: merged-PR settle fix + board refresh.
- 2026-09-26T21:51Z — PR #39 merged green: spec name correction.

## Handoff

Read PROJECT → CURRENT → this task → `docs/AGENT_PROPOSALS.md` (mechanics) +
`docs/AUTHORITY.md` (policy). Gate before any product commit:
`python scripts/coord_board.py --issue-open <n> --agent <you>`.
