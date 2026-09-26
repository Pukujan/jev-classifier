# jev-classifier

## Purpose

Build a mostly-deterministic **JEV-based research-synthesis workflow** that helps people inspect correlated AI-research transcripts and papers with claim provenance, lineage, citations, epistemic status, and separate valid and recorded time. This repository is a prototype with replaceable components; it is not yet a complete multi-source transcript-to-paper system. Deterministic semantic judgments are permitted only through TypeSafe JEV (OpenRouter Decisions API). Python owns parsing, validation, aggregation, time handling, and rendering. The OWL2 vocabulary and PCM (`Pukujan/project-continuity-modules`) provide claim-structure and continuity helpers.

## Scope

- The Grok/OpenRouter source-capture module is implemented for bounded artifacts
  with citation annotations, but the recorded live provider smoke returned HTTP
  404. Treat capture as untrusted source evidence; it is not automatically
  integrated into classification or paper assembly. TypeSafe JEV remains the
  only permitted model for deterministic classifier judgments; local code owns
  validation, aggregation, and reporting.

- JEV answer normalization currently implements `choice` and `noul`. `score` is
  declared in project policy but is not implemented yet (tracked in issue #32).
- Current classification handles one supplied fragment at a time; multi-source
  examples use synthetic fixtures and are not a real-paper benchmark.
- OWL2 ontology skeleton for claims, provenance (PROV-aligned), epistemic status, and bitemporal validity.
- Deterministic local code for control flow, aggregation, validation, thresholds, supersession links, and paper assembly scaffolding.
- Bias/detection *signals* as closed JEV questions + local calibration against fixtures (confidence ≠ correctness).
- Coordination via GitHub issues/PRs; lean, verifiable milestones.

## Non-goals

- Any non-JEV LLM for **deterministic classifier outputs** (prohibited).
- Treating JEV as a chat/completion model or streaming text generator.
- Promoting JEV answers to objective gold without fixtures/verifiers.
- Full paper-quality NLG from JEV (JEV does not write prose; assembly stays code/templates or explicitly non-deterministic helper paths outside the classifier contract).
- Graph DB / second canonical store as authority (prefer Git + structured artifacts; DB only as derived cache if ever needed).
- Rewriting eval-lab history or depending on the historical OpenCode `eval_lab.jev` defaults.

## Target outcomes (not all shipped)

1. A live OpenRouter Decisions call with pinned `typesafe/jev-1.13` returns a
   legal typed answer; credentials never appear in logs or artifacts.
2. The OWL2 Turtle vocabulary parses offline and exposes claim, source, and
   time/provenance terms; SHACL validation remains unimplemented.
3. A supplied fragment can receive a closed JEV label and a claim record, while
   timestamp syntax, evidence-reference existence, and surfaced-model matching
   still have documented validation gaps.
4. Research drafts preserve source links and disagreement through validated
   structured evidence; paper assembly currently renders a six-section draft
   skeleton rather than narrative analysis.
5. A human-reviewed, paper-level benchmark establishes claim fidelity and bias
   signal limits; the ≥10-paper, ≥30-iteration, and ≥0.80 hidden-holdout goals
   remain planned until evidence is recorded under their owning issues.

## Phases (lean)

| Phase | Name | Outcome |
|------:|------|---------|
| 0 | Bootstrap | This plan + AGENTS + research notes + issue #1 draft |
| 1 | JEV client + smoke | OpenRouter Decisions client; fixture smoke; fail-closed parse |
| 2 | Ontology + first classify | OWL2 skeleton; first classification fixture with claim record |
| 3 | Agent coordination | Local SQLite coord scaffold + AGENT_COORD protocol (GitHub remains authority) |
| 4 | Paper assembly | Deterministic claim-JSON ? markdown paper skeleton (templates only; no non-JEV LLM for labels) |
| 5 | Bias packs | Closed JEV choice/noul bias signals; local aggregation; fail-closed fixtures |
| 6+ | (later issues) | PCM claim-ledger alignment, calibration sets |

Iteration details and verify steps live in `docs/ISSUE_1_DRAFT.md`.

Live next-priority note: `docs/CURRENT.md`. Coordination protocol: `docs/AGENT_COORD.md`.

<!-- continuity:project {"schema":"project-continuity.project.v1","protocol_version":"0.1.0-draft","id":"jev-classifier","title":"jev-classifier"} -->
