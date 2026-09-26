# CURRENT — project status and next priority

Updated: 2026-09-26 22:39 UTC from GitHub issues and pull requests.

## Authority

GitHub issues and pull requests are canonical for work, ownership, and decisions. The authoritative agent decides proposals and collisions. PCM, local SQLite files, and this page are continuity and status-projection helpers. See [AUTHORITY.md](AUTHORITY.md) and [OPS_LEDGER.md](OPS_LEDGER.md).

## Recently completed

- Issue #15 source capture is closed after PR #27; its source transcript remains untrusted, and its single capped live provider smoke returned HTTP 404 with no retry or live artifact.
- Issue #22 coordination layer is closed after its coordination and ledger follow-ups. GitHub remains the decision and ownership authority.
- Issue #30 and PR #34 for the earlier module-spec leaf are closed. Issue #28 remains open as the current #21 child for versioned module contracts.
- Issue #33 synthetic offline fixtures are closed after PR #43 merged. Those fixtures support offline shape checks; they are not a real-paper benchmark.

## Open program work

- Issue #21 is the modular quality-program parent. Its paper selection, claim graph, split, and metric-harness work remain in progress.
- Issue #28 is open for versioned system specification and module contracts; #29 is open for dataset-card and reference-paper selection; #37 is open for the reference claim graph and privacy-safe context stimulus schema.
- Issue #31 tracks an ontology provenance/activity gap. Issue #32 tracks the unimplemented score primitive and bias-pack defects. Do not describe either as resolved.
- Issue #23 is open under the updated title “model/vendor framing and research-goal drift across iterative prompts.” Its current study question compares changes to the research goal and outputs across the supplied prompt sequence; the Discord memory-on example is a separate comparator. The existing authoritative decision still marks implementation accepted-but-deferred until its stated #21/#15/#22 gates are satisfied. This status entry does not reopen that work or resolve conflicts between later owner scope text and the recorded proposal decision.

## Current writer claim

- Issue #35 is accepted for the README and supporting documentation under CGM 0.4.0. The reserved branch is `feat/cgm-docs-35` and the writer claim is recorded on issue #35.
- This task updates public documentation and evidence manifests only. It does not change classifier semantics, the coordination implementation, or the technical specification owned by its issue.
- Resource-intensive classifier benchmark runs are assigned to the MacBook Pro agent because of the Windows machine's RAM, storage, and package/container constraints.

## Next

1. Finish and validate the #35 README, evidence brief, image provenance notes, and linked reader guides.
2. Continue #21 through its open children #28, #29, and #37; keep #23 implementation gated by its authoritative decision.
3. Keep user-history and research-output evaluations separate from claims the current prototype has validated.

## Storage

Keep source datasets and research caches in ignored folders. Commit small fixtures and summaries only. Never put secrets, large datasets, or hidden holdout labels in this repository.
## Continuity projection note

The machine-readable PCM pointer below still names task JEV-0030, whose task record remains marked active even though canonical GitHub issue #30 and PR #34 are closed. Treat this as a stale continuity projection, not a current ownership claim or a status override; GitHub remains authoritative. The legacy pointer is retained for compatibility with the existing system-spec check and is not the active #35 writer claim.
<!-- continuity:current {"schema":"project-continuity.current.v1","protocol_version":"0.1.0-draft","active_task":"JEV-0030","active_task_file":"tasks/TASK-JEV-0030-system-spec.md"} -->
