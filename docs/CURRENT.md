# CURRENT — next priority

Updated: 2026-09-26 (America/New_York)

## Just completed

- Issue #1 bootstrap merged via PR #2 — `main` @ `e09343d` (pytest 12; smoke PASS typesafe/jev-1.13).
- Issue #3 multi-agent coordination scaffold merged via PR #4 — `main` @ `2765d50`.
- Issue #5 paper-assembly scaffolding merged via PR #7 — `main` @ `fe0da95`.
- Issue #6 bias-detection question pack merged via PR #8 — `main` @ `d47bca5` (full suite **34 passed**).
- Issue #10 PCM claim-ledger field alignment merged via PR #13 — `main` @ `12f0e2e` (suite **46 passed**).
- Issue #11 optional live bias-pack smoke merged via PR #16 — `main` @ `e2ae7e4` (suite **49 passed**).
- Issue #12 multi-source classify + paper e2e merged via PR #17 — `main` @ `641e5b9`.
- Issue #18 operational local DB + committed ops ledger merged via PR #19 — `main` @ `7e3daa7` (suite **56 passed**). Ledger: `ops/ledger/`; sync: `python scripts/ops_sync.py`.

## In flight

- Issue #15 Grok research-source bot (primary writer: Codex project agent).

## Next (queued)

1. Calibration sets / further PCM ledger work when filed.
2. Expand ontology individuals / paper assembler follow-ons when filed.

## Authority reminder

GitHub issues/PRs are authority. Local `.coord/` and `.ops/` SQLite DBs are execution aids only (see `docs/AGENT_COORD.md`, `docs/OPS_LEDGER.md`). Committed `ops/ledger/` is a readable projection. Collision/proposal winners are decided by the authoritative agent — product agents propose only.
