# CURRENT — project status and next priority

Updated: 2026-09-27 02:06 UTC from GitHub issues and pull requests.

## Authority

GitHub issues and pull requests are canonical for work, ownership, and decisions. The authoritative agent decides proposals and collisions. PCM, local SQLite files, and this page are continuity and status-projection helpers. See [AUTHORITY.md](AUTHORITY.md) and [OPS_LEDGER.md](OPS_LEDGER.md).

## Recently completed

- Issue #15 source capture is closed after PR #27; its source transcript remains untrusted, and its single capped live provider smoke returned HTTP 404 with no retry or live artifact.
- Issue #22 coordination layer is closed after its coordination and ledger follow-ups. GitHub remains the decision and ownership authority.
- Issue #30 and PR #34 for the earlier module-spec leaf are closed; issue #28 is also closed after that specification work.
- Issue #31 and PR #56 are closed; PR #56 merged at `a44f0da` and added the JEV `ClassificationActivity` / `ClassifierAgent` ontology model.
- Issue #33 synthetic offline fixtures are closed after PR #43 merged. Those fixtures support offline shape checks; they are not a real-paper benchmark.
- Issue #29 selected ten candidate papers and added the dataset card; selection does not mean the papers have been reverse-analyzed or annotated.
- Issue #32 and PR #58 implemented score normalization and bias-pack score support.
- Issues #37 and #64 completed the reference-claim graph and privacy-safe context-stimulus schema.
- Issue #66 registered `claim_metric_v1` and its deterministic scorer; this is metric setup, not a holdout result.
- Issue #81 completed the holdout access and leakage protocol. No split has been assigned, annotated, or evaluated.

## Open program work

- Issue #21 remains the modular quality-program parent. Candidate selection, reference schemas, metric setup, and holdout access controls are complete; reverse-analysis annotations, an actual frozen split/evaluation, and the 30-iteration program remain unfinished.
- Issues #85 and #86 are open proposals for an iteration-log mechanism and tight classifier evidence spans. They are not authorized implementation tasks until the authoritative agent records decisions.
- Issue #23 includes the paired Version 1 / Version 2 multimodal-alignment results as a core comparison of memory-context effects; the owner identifies the supplied Version 2 PDF as produced without prior user-specific memory. Version 1's memory state is unknown and its conversation includes an additional follow-up, so the pair shows observed differences but cannot establish a causal memory effect. Separately, the study tracks research-goal/output changes across the iterative prompt sequence and model/vendor framing. The authoritative decision still defers implementation until the required #21 substrate and proposal gate are satisfied; #15 source capture and #22 coordination are now closed.

## Current writer claim

- Issue #35 delivered this README and its CGM 0.4.0 support records; consult its GitHub issue and PR #49 for current merge state.
- The owner waived separate reader/visual sign-off as a merge gate. The human checklist remains optional and unchecked; automated contract, factual-source, link, manifest, and CI gates determine readiness.
- This documentation task does not change classifier semantics, the coordination implementation, or the technical specification owned by its issue.
- Resource-intensive classifier benchmark runs are assigned to the MacBook Pro agent because of the Windows machine's RAM, storage, and package/container constraints.

## Next

1. Continue #21 through accepted leaves: freeze the paper-level split in a new authorized child using the completed #81 custody protocol, annotate development papers, then run the authorized evaluation and qualifying iterations on the designated MacBook Pro agent.
2. Track proposals #85 and #86 through the authoritative decision layer before implementation; keep #23 implementation deferred until its prerequisites and proposal gate are satisfied.
3. Keep user-memory effects separate from model/vendor framing and from claims the current prototype has validated.

## Storage

Keep source datasets and research caches in ignored folders. Commit small fixtures and summaries only. Never put secrets, large datasets, or hidden holdout labels in this repository.
## Continuity projection note

The machine-readable PCM pointer below still names task JEV-0030, whose task record remains marked active even though canonical GitHub issue #30 and PR #34 are closed. Treat this as a stale continuity projection, not a current ownership claim or a status override; GitHub remains authoritative. The legacy pointer is retained for compatibility with the existing system-spec check and is not the active #35 writer claim.
<!-- continuity:current {"schema":"project-continuity.current.v1","protocol_version":"0.1.0-draft","active_task":"JEV-0030","active_task_file":"tasks/TASK-JEV-0030-system-spec.md"} -->
