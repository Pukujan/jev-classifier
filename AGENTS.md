# AGENTS.md — operating rules for jev-classifier

## Authority

- **GitHub issues** are the authority for work items. Do not invent parallel task systems.
- Prefer small PRs against feature branches. **Never force-push** shared history. **Do not commit classifier product work to `main`/`master` without an issue-backed PR.**
- PCM (`Pukujan/project-continuity-modules`) is a **helper** for continuity, claim/epistemic patterns, and process — not a second product owner for this repo.

## JEV-only deterministic outputs

- Deterministic classifier outputs (labels, scores, yes/no judgments that enter the paper's claim graph) **MUST** use TypeSafe JEV via OpenRouter Decisions API.
- Authorized endpoint: `POST https://openrouter.ai/api/alpha/decisions`.
- Pinned model: `typesafe/jev-1.13`. Rolling `~typesafe/jev-latest` is canary-only, never the scientific/pinned arm.
- Primitives only: `choice`, `score`, `noul`. Not Chat Completions. No `stream=true`.
- **Any non-JEV model for deterministic classifier output is PROHIBITED.**
- Application code owns: state reduction, option sets, validation, aggregation, thresholds, retries, escalation, side effects.
- Confidence ≠ correctness. Preserve native probability maps; never fabricate labels on provider/parse failure.

## Secrets

- Credentials live in ignored `.env` (see `.env.example`). **Never print, log, or commit API keys or `.env` values.**
- Prefer env var `OPENROUTER_API_KEY`. Do not echo headers or raw auth responses in docs/issues.

## Research integrity

- Put evidence in `state`; judgment in `instructions`; every option described in `criteria`.
- Atomic questions; combine in code. Add `other`/`none` when the set is not exhaustive.
- Record requested model and surfaced model when the provider returns it.
- Fail closed: malformed / out-of-set answers → parse/review state, not a guessed label.

## PR workflow

1. Open/claim a GitHub issue with done-when criteria.
2. Branch from default branch: `feat/...` or `fix/...`.
3. Commit draft docs and code; push branch; open PR linking the issue.
4. Keep milestones verifiable (command + expected artifact).

## Out of scope for agents unless an issue says otherwise

- Pushing to `main`/`master` directly.
- Live paid experiments beyond a single smoke without an issue.
- Copying secrets from eval-lab or other repos into this tree.