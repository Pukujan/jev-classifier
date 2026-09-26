# CURRENT — next priority

Updated: 2026-09-26 (America/New_York)

## Just completed

- Issue #1 bootstrap merged via PR #2 → `main` @ `e09343d` (pytest 12 passed; smoke PASS with typesafe/jev-1.13).

## In flight

- **Issue #3** — Multi-agent coordination scaffold (`feat/agent-coord-scaffold`): local SQLite coord store + `docs/AGENT_COORD.md` + red-first tests.

## Next (queued)

1. Paper-assembly scaffolding — deterministic template assembler (claim JSON → medium-quality markdown research-paper skeleton); prose templates are code/strings only; no non-JEV LLM for claim labels.
2. Bias-detection question pack — closed JEV choice/noul packs; local aggregation; fixtures with expected legal option sets; fail-closed.

## Authority reminder

GitHub issues/PRs are authority. Local `.coord/` SQLite is an execution aid only (see `docs/AGENT_COORD.md`).
