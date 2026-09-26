# CURRENT — next priority

Updated: 2026-09-26 (America/New_York) — authoritative agent

## Authority

**GitHub issues/PRs are canonical.** The authoritative agent (main agent
session acting for @Pukujan) is the sole arbiter of proposals, collisions, and
sequencing. Product agents propose only; they do not self-arbitrate. **The
project does not stop for anyone.** See [`AUTHORITY.md`](AUTHORITY.md).

Local `.coord/` and `.ops/` SQLite DBs are execution aids / rebuildable
projections — never a second source of truth. If SQLite and GitHub disagree,
**GitHub wins**. Committed `ops/ledger/` is a readable projection; see
[`OPS_LEDGER.md`](OPS_LEDGER.md).

## Just completed

- Issue #1 bootstrap merged via PR #2 — `main` @ `e09343d` (pytest 12; smoke PASS typesafe/jev-1.13).
- Issue #3 multi-agent coordination scaffold merged via PR #4 — `main` @ `2765d50`.
- Issue #5 paper-assembly scaffolding merged via PR #7 — `main` @ `fe0da95`.
- Issue #6 bias-detection question pack merged via PR #8 — `main` @ `d47bca5` (full suite **34 passed**).
- Issue #10 PCM claim-ledger field alignment merged via PR #13 — `main` @ `12f0e2e` (suite **46 passed**).
- Issue #11 optional live bias-pack smoke merged via PR #16 — `main` @ `e2ae7e4` (suite **49 passed**).
- Issue #12 multi-source classify + paper e2e merged via PR #17 — `main` @ `641e5b9` (suite **52 passed**).
- Issue #18 operational local DB + committed ops ledger merged via PR #19 —
  `main` @ `7e3daa7` (suite **56 passed**). Ledger: `ops/ledger/`; sync:
  `python scripts/ops_sync.py`; board refresh PR #20 @ `67e6e1d`.
- Issue #24 authoritative-agent policy + CI gate merged via PR #25 — `main` @
  `a030c59`. `docs/AUTHORITY.md`; CI: offline pytest (3.11+3.12) + OWL2 rdflib
  parse + hygiene (secret scan, 2MB tracked-file cap, 2MB fixture cap).
- **Branch protection ENABLED on `main`**: required status checks `test (3.11)`,
  `test (3.12)`, `hygiene`; strict; force-push and deletion blocked. PRs cannot
  merge red or bypass the storage/secret gate.
- **#15 Grok research-source bot** completed and closed after PR #27 merged to
  `main` at `e763206`. The branch checkpoint records 74 offline tests at merge
  time; its one capped live smoke returned HTTP 404, so live Grok capture was
  not verified. Grok output remains untrusted source material and is not
  automatically sent through JEV or the paper assembler.
- **GO issued**: authoritative agent ACCEPTED #15 and #18 and posted
  `COLLAB_GO` on parent #14
  ([comment](https://github.com/Pukujan/jev-classifier/issues/14#issuecomment-5848946788)).

## In flight (claimed / accepted)

- **#22** Coordination layer v2 — ACCEPTED, writer: **coordination-flagger
  agent**, branch `feat/coordination-layer-22` (reserved @ `67eaa8b`). The
  reserved-branch mutex fired against the arbiter's own dogfood push and
  resolved the collision deterministically; the arbiter adjudicates, the flagger
  agent implements. Scope now includes the owner's append-only **run-receipt
  telemetry** with opaque aliases and per-field provenance marking.
- **#30** Versioned system spec — claimed by `claude-code-main` on
  `feat/system-spec-30`; module-contract corrections and offline verification
  are complete on that issue-linked branch, and a PR is being prepared.

## Adjudicated (accepted, sequenced)

- **#21** Modular quality program (≥30 iterations, ≥10 reverse-analyzed papers,
  ≥0.80 claim-level F1 on a hidden paper-level holdout) — **ACCEPT-DECOMPOSE**.
  Becomes a parent with 7 bounded child leaves; children 1 (versioned system
  spec + module contracts) and 2 (dataset card + reference-paper selection) are
  **unblocked now**. Writer: Codex project agent coordinates children.
  Owner execution decision: run resource-intensive test benches serially on the
  MacBook Pro agent, not Windows; record host/runtime/tool and resource details
  on the relevant GitHub issue.
- **#23** Memory-context-contamination benchmark — **ACCEPT-DEFERRED**. Goal
  accepted, implementation **BLOCKED** on #21 + #15 + #22. Do not claim or
  branch it. Unblocked contribution today: the privacy-reviewed
  stimulus-manifest schema, proposed under a #21 child leaf.

## Next (queued)

1. **#21 child leaves 1 and 2** — file as separate issues and claim per
   protocol. These are the critical path for #23.
2. Small offline **dataset fixtures** for claim-type + cross-source
   contradiction classification (research in flight; commit only sub-50KB
   samples — storage watchdog).
3. **Bitemporal + PROV-O ontology** expansion: valid-time vs transaction-time
   pattern, `prov:wasDerivedFrom` lineage on the claim graph.
4. Calibration sets / PCM ledger follow-ons when filed.

## Storage watchdog note

Owner monitors local PC storage; GitHub is authoritative so local disk is
disposable. Keep the tree lean: no large binaries, no committed datasets,
external downloads to gitignored `data/` referenced by name+revision. CI
enforces a secret scan, a 2MB tracked-file cap, and a 2MB fixture cap.
`scripts/watchdog_storage.py` (#22) must stay read-only and abort-safe.

<!-- continuity:current {"schema":"project-continuity.current.v1","protocol_version":"0.1.0-draft","active_task":"JEV-0030","active_task_file":"tasks/TASK-JEV-0030-system-spec.md"} -->
