# AGENTS.md — operating rules for jev-classifier

## Authority

- **The authoritative agent is the sole arbiter.** Disagreements, proposal
  collisions, and sequencing disputes are decided by the main agent session
  acting for the owner; its ruling on the issue is final. Product agents
  propose only. **The project does not stop for anyone — including the owner.**
  On a blocker, apply the slimmest plausible fix, record it, keep moving.
  Full policy: [`docs/AUTHORITY.md`](docs/AUTHORITY.md).
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

## Multi-agent coordination

- Prefer GitHub issues/PRs for ownership and delivery status.
- Optional local aid: `jev_classifier.coord.CoordStore` (SQLite under `.coord/`, gitignored). See `docs/AGENT_COORD.md`.
- Optional ops projection: `jev_classifier.ops.OpsStore` (`.ops/ops.db`, gitignored) + committed `ops/ledger/` via `scripts/ops_sync.py`. See `docs/OPS_LEDGER.md`. Does **not** decide proposal winners.
- Claim issue ownership before pushing product work; use idempotent checkpoint keys; never treat SQLite as authority over GitHub.
- **Coordination layer v2 (#22):** the cross-device claim mutex is the *reserved branch* (`feat/<slug>-<issue#>`: push the marker commit before any product code; GitHub create-ref rejects the second claimant) plus a `coord:claim` comment on the issue. Gate every issue before product commits: `python scripts/coord_board.py --issue-open <n> --agent <you>` (exit 0 = go, 3 = blocked or CLOSED). Record grammar, session-id format, and adjudication mechanics: [`docs/AGENT_PROPOSALS.md`](docs/AGENT_PROPOSALS.md). `ops/ledger/COORD.md` is the only committed board (regenerated projection; GitHub comments remain the record).

<!-- pcm:issue-log-format:start -->
## Issue log format (issue-log-format 1.2.0)

<!-- pcm:policy {"id":"issue-log-format","policy_version":"1.2.0","protocol_version":"0.1.0-draft"} -->

Write issue logs, progress updates, and pull requests in one plain-language shape a newcomer can follow. Pick the tier by the kind of issue, not by preference. **Core tier (every issue log):** title states the problem and intended direction; a 1-3 paragraph summary naming who/what is affected, the consequence, and what this proposes; identity and lineage (leaf owning issue, parent ancestry or none, task ID, primary writer, branch); observed facts vs interpretation, with inferences labelled *inferred*; acceptance criteria with numeric thresholds marked *(proposed)* when untested; boundaries/non-goals and one next action. **Investigation tier (incidents, failures, research, design issues):** numbered symptoms; hypotheses with Status, confirm/refute, and experiment; evidence with provenance; a **Counter-signal** entry when one exists; honest caveat; problems-vs-gaps; a **Proposal** labelled *(proposal)* stating none of it exists unless named as existing. **Pull requests open reader-first:** problem and consequence, what changes, how to verify, and what stays unchanged; lineage links; evidence and one next action; long logs collapsed or linked; reference issues with "Refs #<number>" and use closing keywords only when closing at merge is intended. **Diagrams (mermaid):** when a record describes a flow with 4+ ordered steps or 2+ branches, add a fenced mermaid diagram *and* keep an adjacent text list or table so the record survives render failure; default to `graph TD` (vertical) because wide `LR` flows shrink to illegible strips on phones — reserve `LR` for 4 or fewer short nodes; cap 8 nodes and 6-word labels; wrap diagrams that may exceed the container width inside `<details>` (GitHub mounts the renderer lazily on expand); preview the rendered diagram before publishing (broken syntax shows a visible parse error) and never cite renderer URLs as standalone sources. **Readability rules:** give every SHA, comment id, flag, file path, or tool name a plain-word meaning in the same sentence before it carries load; write evidence as the claim first, numbers as support (“nothing this change could break failed (263 tests, same six machine-environment failures as before)”), never bare counts; no unexplained acronym or bare identifier on first use in any tier; PR openings and checkpoint Completed/Next lines start with one problem sentence a newcomer can follow; the rule set applies to CURRENT projections and checkpoint entries exactly as to issue logs. No private absolute paths or secrets; link rather than paste long logs. See `docs/ISSUE_LOG_FORMAT.md` for the full format, exemplar, and examples.
<!-- pcm:issue-log-format:end -->
