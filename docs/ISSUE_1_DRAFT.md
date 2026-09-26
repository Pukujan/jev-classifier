# Draft — GitHub issue #1

> Paste into https://github.com/Pukujan/jev-classifier/issues/new (repo currently has zero issues). Do not auto-close until milestones below pass.

## Title

Bootstrap: JEV client smoke + OWL2 claim skeleton + first classification fixture

## Goal

Stand up the minimum verifiable path for **jev-classifier**: OpenRouter Decisions (pinned JEV) as the only deterministic judgment engine; OWL2 ontology hooks for epistemic/bitemporal provenance; one end-to-end fixture that classifies a short research fragment into a closed label set with a claim record.

## Scope

**In**

- Repo bootstrap docs (`PROJECT.md`, `AGENTS.md`, research notes) on branch `feat/bootstrap-plan`.
- Thin OpenRouter Decisions client (pin `typesafe/jev-1.13`); smoke script/test.
- OWL2 TTL skeleton (Claim + provenance/time fields).
- One fixture: input fragment → JEV `choice` (and optional atomic `noul`s) → validated JSON claim record.
- Issue/PR workflow per `AGENTS.md`.

**Out**

- Full paper generation pipeline.
- Non-JEV models for classifier labels.
- PCM package dependency hard-requirement (align fields only).
- Force-push / direct commits to `main`.
- Printing or committing secrets.

## Done when

1. Branch `feat/bootstrap-plan` (or successor) contains plan docs and this issue body filed as issue #1.
2. `OPENROUTER_API_KEY` present locally via `.env` (gitignored); smoke call succeeds **or** documents a typed skip when key absent in CI.
3. Smoke: POST Decisions with pinned model; legal `choice` returned; probabilities preserved when present; no secret leakage in logs.
4. `ontology/jev_classifier_claims.ttl` (or equivalent) passes an OWL/RDF syntax check (e.g. rdflib parse).
5. Fixture under `tests/fixtures/` + runner produces a claim JSON with: label, epistemic_status, recorded_at, evidence pointer, model id; out-of-set answers fail closed.
6. PR opened linking this issue; CI or local verify commands listed in the PR body.

## Lean iteration milestones (easy to verify)

### Iteration 0 — Plan & authority

- [ ] Commit bootstrap markdown on `feat/bootstrap-plan` (not `main`).
- [ ] File this issue as #1; link from PR.
- **Verify:** `git branch --show-current` ≠ main; issue URL exists; files present: `PROJECT.md`, `AGENTS.md`, `docs/RESEARCH_NOTES.md`.

### Iteration 1 — JEV smoke client

- [ ] Client module targeting `https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.13`.
- [ ] One `choice` question with descriptive criteria; fail-closed normalize.
- [ ] `scripts/smoke_jev.py` or `pytest` marked smoke.
- **Verify:** With key set, exit 0 and prints only non-secret fields (choice, probs keys, model). Without key, exit non-zero with clear message (no traceback of secrets). Optional: mock unit test for out-of-set → parse_error.

### Iteration 2 — Ontology + first classification fixture

- [ ] OWL2 TTL skeleton: Claim, SourceFragment, epistemicStatus, validFrom/validTo, recordedAt, supersedes; PROV-O alignment comments/imports as lean as practical.
- [ ] Fixture: short synthetic “transcript/paper” snippet + expected closed label set.
- [ ] Classifier path: reduce snippet → JEV questions → local aggregate → write claim record JSON(+ optional TTL individuals).
- **Verify:** `rdflib` (or robot/owl) parses TTL; fixture test asserts label ∈ legal set and required provenance keys present; one golden claim file committed.

## Notes for implementers

- Historical eval-lab `jev.py` defaults are OpenCode — do not copy URL/key/model.
- Confidence is routing metadata, not gold.
- Prefer PCM-0050-compatible claim field names where cheap (`epistemic_status`, `valid_from`/`valid_to`, `recorded_at`, `supersedes`, `independence_class`).