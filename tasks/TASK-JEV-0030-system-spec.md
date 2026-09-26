# TASK-JEV-0030 — Versioned system specification

<!-- continuity:task {"schema":"project-continuity.task.v1","protocol_version":"0.1.0-draft","id":"JEV-0030","status":"active","owner":"claude-code-main","priority":"P1","depends_on":[],"goal":"Document the existing JEV classifier modules with accurate versioned input/output contracts, roles, invariants, known gaps, and test evidence.","why":"The system spec is the contract reference for independently replaceable modules and must not claim behavior the current code or tests do not provide.","acceptance":["docs/SYSTEM_SPEC.md and docs/spec/modules.json identify all modules with matching names and per-module contract versions.","The M1 source-capture status and JEV-0001 PCM projection match merged PR #27 and closed issue #15.","M2 normalization, M3 Decisions behavior, M4 claim validation, M5 provenance/time limits, and M7 assembly limits match inspected code.","Offline contract tests map each module to existing evidence and prevent prose/index drift.","PROJECT.md and docs/CURRENT.md distinguish shipped behavior from planned outcomes.","Full offline tests and OWL2 parsing pass; no non-JEV model is specified as a deterministic classifier.","An issue-linked PR records exact verification evidence and leaves unresolved semantics explicit."],"next_action":"Await review and merge of PR #34; keep issue #30 active until merged.","issue_url":"https://github.com/Pukujan/jev-classifier/issues/30"} -->

- Status: active; PR #34 is open and required CI has passed; merge remains.
- Owner: `claude-code-main` (per the existing #30 claim)
- Parent: #21; grandparent: #14
- Branch: `feat/system-spec-30`
- PCM is a continuity projection; GitHub issue #30 remains canonical.

## Scope

Correct and version the current module contracts without rewriting product
modules. Keep code behavior, permitted JEV/non-JEV roles, validation ownership,
and known gaps explicit. Reconcile stale #15/PR #27 status projections.

## Checkpoint log

- 2026-09-26: Re-audited current code and identified inaccurate module inputs,
  timestamp/provenance guarantees, test mappings, and stale merged-source status.
- 2026-09-26: Added module-title/version drift checks and mocked Decisions
  client contract tests; targeted checks passed (33 tests).
- 2026-09-26: Final full offline test suite passed (109 tests); OWL2 parse is
  covered by the suite.
- 2026-09-26: PR #34 CI passed on Python 3.11 and 3.12, including the hygiene
  job (run 36270138029).
- 2026-09-26: Independent review found answer `type` is optional in the current
  normalizers. Corrected the spec/index to match and added focused tests for
  absent `type`; PR #34 remains open pending merge.
- 2026-09-26: Re-review clarified that the fail-closed row means missing
  required answer values, not the optional `type` field.

### 2026-09-26 21:10:08 UTC — claude-code-main

<!-- continuity:checkpoint {"agent":"claude-code-main","blocked":[],"changed":["docs/SYSTEM_SPEC.md, docs/spec/modules.json, tests/test_normalize.py, tests/test_normalize_noul.py, tasks/TASK-JEV-0030-system-spec.md"],"completed":["Aligned the M2 answer-type contract and index with normalizer behavior; added focused omission tests."],"decisions":["Document current behavior: type is optional; when supplied it must match the primitive. No normalization behavior change."],"evidence":["pytest tests/test_normalize.py tests/test_normalize_noul.py tests/test_system_spec.py -q: 39 passed; git diff --check clean; source commit 6d9963b pushed to feat/system-spec-30."],"next_action":"Wait for CI and review on PR #34; resolve the remaining JEV-0001 stale-worktree PCM preflight error only through a safe registered-worktree cleanup.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"JEV-0030","timestamp":"2026-09-26T21:10:08Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"cccfdebb9056299bf21f4d65c82d492e6f4e86efdb1112e8d81bcdbcba61b4b1","request_id":"JEV-0030-optional-type-6d9963b","schema":"project-continuity.checkpoint-operation.v1","task_id":"JEV-0030"} -->

Completed:
- Aligned the M2 answer-type contract and index with normalizer behavior; added focused omission tests.

Evidence:
- pytest tests/test_normalize.py tests/test_normalize_noul.py tests/test_system_spec.py -q: 39 passed; git diff --check clean; source commit 6d9963b pushed to feat/system-spec-30.

Decisions:
- Document current behavior: type is optional; when supplied it must match the primitive. No normalization behavior change.

Changed:
- docs/SYSTEM_SPEC.md, docs/spec/modules.json, tests/test_normalize.py, tests/test_normalize_noul.py, tasks/TASK-JEV-0030-system-spec.md

Blocked/uncertain:
- none

Next:
- Wait for CI and review on PR #34; resolve the remaining JEV-0001 stale-worktree PCM preflight error only through a safe registered-worktree cleanup.

### 2026-09-26 21:11:50 UTC — claude-code-main

<!-- continuity:checkpoint {"agent":"claude-code-main","blocked":[],"changed":["docs/SYSTEM_SPEC.md, tasks/TASK-JEV-0030-system-spec.md"],"completed":["Clarified that fail-closed missing-field behavior applies to required answer values; omitted answer type remains optional."],"decisions":["Keep the implementation unchanged; document the observed accepted shape and test it."],"evidence":["pytest tests/test_system_spec.py tests/test_normalize.py tests/test_normalize_noul.py -q: 39 passed; git diff --check clean; commit 31f7667 pushed to feat/system-spec-30."],"next_action":"Wait for CI on updated PR #34 and continue only with current GitHub issue ownership.","protocol_version":"0.1.0-draft","schema":"project-continuity.checkpoint.v1","task_id":"JEV-0030","timestamp":"2026-09-26T21:11:50Z"} -->
<!-- continuity:checkpoint-operation {"payload_sha256":"b3255ff44ae96669b01fe33c11cbd8b2bb69597f1371140415f5acc1167bb5a6","request_id":"JEV-0030-required-values-31f7667","schema":"project-continuity.checkpoint-operation.v1","task_id":"JEV-0030"} -->

Completed:
- Clarified that fail-closed missing-field behavior applies to required answer values; omitted answer type remains optional.

Evidence:
- pytest tests/test_system_spec.py tests/test_normalize.py tests/test_normalize_noul.py -q: 39 passed; git diff --check clean; commit 31f7667 pushed to feat/system-spec-30.

Decisions:
- Keep the implementation unchanged; document the observed accepted shape and test it.

Changed:
- docs/SYSTEM_SPEC.md, tasks/TASK-JEV-0030-system-spec.md

Blocked/uncertain:
- none

Next:
- Wait for CI on updated PR #34 and continue only with current GitHub issue ownership.

## Handoff

Await review and merge of PR #34. Do not change the #22 coordination
implementation or claim its branch.
