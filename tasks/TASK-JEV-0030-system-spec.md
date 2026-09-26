# TASK-JEV-0030 — Versioned system specification

<!-- continuity:task {"schema":"project-continuity.task.v1","protocol_version":"0.1.0-draft","id":"JEV-0030","status":"active","owner":"claude-code-main","priority":"P1","depends_on":[],"goal":"Document the existing JEV classifier modules with accurate versioned input/output contracts, roles, invariants, known gaps, and test evidence.","why":"The system spec is the contract reference for independently replaceable modules and must not claim behavior the current code or tests do not provide.","acceptance":["docs/SYSTEM_SPEC.md and docs/spec/modules.json identify all modules with matching names and per-module contract versions.","The M1 source-capture status and JEV-0001 PCM projection match merged PR #27 and closed issue #15.","M2 normalization, M3 Decisions behavior, M4 claim validation, M5 provenance/time limits, and M7 assembly limits match inspected code.","Offline contract tests map each module to existing evidence and prevent prose/index drift.","PROJECT.md and docs/CURRENT.md distinguish shipped behavior from planned outcomes.","Full offline tests and OWL2 parsing pass; no non-JEV model is specified as a deterministic classifier.","An issue-linked PR records exact verification evidence and leaves unresolved semantics explicit."],"next_action":"Record the verified branch diff and full-suite result in GitHub issue #30, then open the issue-linked PR.","issue_url":"https://github.com/Pukujan/jev-classifier/issues/30"} -->

- Status: active; verification is complete, PR preparation remains.
- Owner: `claude-code-main` (per the existing #30 claim)
- Parent: #21; grandparent: #14
- Branch: `feat/system-spec-30`
- PCM is a continuity projection; GitHub issue #30 remains canonical.

## Scope

Correct and version the current module contracts without rewriting product
modules. Keep code behavior, permitted JEV/non-JEV roles, validation ownership,
and known gaps explicit. Reconcile stale #15/PR #27 status projections.

## Checkpoints

- 2026-09-26: Re-audited current code and identified inaccurate module inputs,
  timestamp/provenance guarantees, test mappings, and stale merged-source status.
- 2026-09-26: Added module-title/version drift checks and mocked Decisions
  client contract tests; targeted checks passed (33 tests).
- 2026-09-26: Full offline test suite passed (107 tests); OWL2 parse is covered
  by the suite.

## Handoff

Read the current #30 issue and PR state before editing. Do not change the #22
coordination implementation or claim its branch.
