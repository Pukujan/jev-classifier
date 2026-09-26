# jev-classifier

## Purpose

Build a mostly-deterministic **JEV-based classifier** that turns correlated AI-research transcripts and papers into medium-quality research papers with **provenance, lineage, and citations**. Classification and epistemic judgments that must be deterministic use **TypeSafe JEV only** (OpenRouter Decisions API). An OWL2 ontology plus JEV helpers encode claim structure; PCM (`Pukujan/project-continuity-modules`) supplies continuity/helper patterns for epistemic-bitemporal records.

## Scope

- Typed JEV decisions (`choice` / `score` / `noul`) over compact structured state derived from transcripts/papers.
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

## Success definition

1. Smoke: one live OpenRouter Decisions call with pinned `typesafe/jev-1.13` returns a legal typed answer; secrets never printed/committed.
2. Ontology: OWL2 TTL skeleton loads (syntax check) with claim + provenance + valid/transaction time hooks.
3. Classifier: one fixture (transcript/paper fragment) yields a closed label set via JEV + locally validated probabilities; output record carries epistemic status + provenance fields.
4. Process: GitHub issue #1 drives work; PRs land on feature branches, not force-pushed main.

## Phases (lean)

| Phase | Name | Outcome |
|------:|------|---------|
| 0 | Bootstrap | This plan + AGENTS + research notes + issue #1 draft |
| 1 | JEV client + smoke | OpenRouter Decisions client; fixture smoke; fail-closed parse |
| 2 | Ontology + first classify | OWL2 skeleton; first classification fixture with claim record |
| 3+ | (later issues) | Bias question packs, paper assembly, PCM claim-ledger alignment |

Iteration details and verify steps live in `docs/ISSUE_1_DRAFT.md`.