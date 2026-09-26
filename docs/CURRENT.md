# CURRENT — next priority

Updated: 2026-09-26 (America/New_York) — authoritative agent

## Authority

**GitHub issues/PRs are canonical.** The authoritative agent (main agent
session acting for @Pukujan) is the sole arbiter of proposals, collisions, and
sequencing. Product agents propose only; they do not self-arbitrate. **The
project does not stop for anyone.** See [`AUTHORITY.md`](AUTHORITY.md).

Local `.coord/` and `.ops/` SQLite are execution aids / rebuildable
projections — never a second source of truth. If SQLite and GitHub disagree,
GitHub wins.

## Just completed

- Issue #1 bootstrap merged via PR #2 — `main` @ `e09343d` (pytest 12; smoke PASS typesafe/jev-1.13).
- Issue #3 multi-agent coordination scaffold merged via PR #4 — `main` @ `2765d50`.
- Issue #5 paper-assembly scaffolding merged via PR #7 — `main` @ `fe0da95`.
- Issue #6 bias-detection question pack merged via PR #8 — `main` @ `d47bca5` (full suite **34 passed**).
- Issue #10 PCM claim-ledger field alignment merged via PR #13 — `main` @ `12f0e2e` (suite **46 passed**).
- Issue #11 optional live bias-pack smoke merged via PR #16 — `main` @ `e2ae7e4` (suite **49 passed**).
- Issue #12 multi-source classify + paper e2e merged via PR #17 — `main` @ `641e5b9` (suite **52 passed**).
- **GO issued**: authoritative agent ACCEPTED #15 and #18, posted `COLLAB_GO`
  on parent #14 ([comment](https://github.com/Pukujan/jev-classifier/issues/14#issuecomment-5848946788)).
- **Policy + CI**: `docs/AUTHORITY.md`, CI workflow (offline tests + ontology
  parse + secret/size/fixture hygiene gates) committed this change.

## In flight (claimed / accepted)

- **#15** Grok research-source bot — ACCEPTED, writer: Codex project agent, branch `feat/grok-source-bot`.
- **#18** Ops ledger + local DB — ACCEPTED, writer: jev-classifier product agent, branch `feat/ops-ledger`.

## Next (queued — awaiting leaves)

1. **CI required-check gate**: once this workflow lands on `main`, mark it a
   required status check so PRs cannot merge red (authoritative agent / owner
   branch-protection action).
2. Small offline **dataset fixtures** for claim-type + cross-source
   contradiction classification (research in progress; commit only sub-50KB
   samples — storage watchdog).
3. **Bitemporal + PROV-O ontology** expansion: valid-time vs transaction-time
   pattern, prov:wasDerivedFrom lineage on the claim graph.
4. Calibration sets / PCM ledger follow-ons when filed.

## Storage watchdog note

Owner monitors local PC storage; GitHub is authoritative so local disk is
disposable. Keep the tree lean: no large binaries, no committed datasets,
external downloads to gitignored `data/` referenced by name+revision. CI
enforces secret scan, 2MB tracked-file cap, and 2MB fixture cap.
