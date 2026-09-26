# TASK-JEV-0001 — Grok Source Bot

<!-- continuity:task {"acceptance":["Mocked request proves configured Grok model and bounded web-search settings; parser preserves citations, usage, and raw response.","Canonical artifact serialization produces a stable SHA-256 content hash, excluding retrieval-time metadata.","Malformed/missing identifiers fail closed without invented citations or claims.","CLI writes an inspectable versioned source artifact and never writes credentials.","Offline tests pass without an API call; any live smoke is capped, optional, and recorded on issue #15.","PROJECT.md, docs/CURRENT.md, and source documentation describe the source-only/JEV-only boundary."],"depends_on":[],"goal":"Capture Grok web research as a source-only, cited, provenance-bearing artifact; never use Grok for deterministic classifier outputs.","id":"JEV-0001","issue_url":"https://github.com/Pukujan/jev-classifier/issues/15","next_action":"No further implementation action: PR #27 is merged and issue #15 is closed. Create a new issue for follow-up work.","owner":"Codex project agent","priority":"P1","protocol_version":"0.1.0-draft","schema":"project-continuity.task.v1","status":"completed","why":"Add a model-agnostic research source for correlated transcripts while preserving JEV as the sole semantic decision model and keeping evidence auditable."} -->

- Status: completed (PR #27 merged; issue #15 closed)
- Owner: Codex project agent
- Priority: P1
- Depends on: none

## Goal

Capture Grok web research as a source-only, cited, provenance-bearing artifact; never use Grok for deterministic classifier outputs.

## Why

Add a model-agnostic research source for correlated transcripts while preserving JEV as the sole semantic decision model and keeping evidence auditable.

## Allowed files

- src/jev_classifier/sources/
- scripts/grok_research.py
- tests/test_grok_research.py and tests/fixtures/grok/
- docs/GROK_SOURCE.md, PROJECT.md, and docs/CURRENT.md
- .env.example, pyproject.toml, schemas/v1/, and .continuity/config.json only as needed for this leaf
## Human outcome

Researchers can collect and inspect a Grok research transcript with citations, request/model provenance, retrieval time, usage, and a stable content hash. The transcript remains untrusted source material; TypeSafe JEV remains the only model producing deterministic classifier judgments.
## Scope and boundaries

- In scope: source-only OpenRouter Grok adapter (default x-ai/grok-4.1-fast), bounded OpenRouter web search, versioned artifact, citation parsing, canonical hashing, safe CLI, offline mocked tests, documentation.
- Out of scope: Grok/JEV prompt substitution for labels; adding Grok prose to claim graph or paper; uncapped or repeated live experiments; storing credentials.
- Dependencies/uncertainty: #10 and #12 are needed for later claim-ledger integration; OpenRouter web-search is beta, so malformed/missing annotations stay visible and fail closed.
## Acceptance criteria

- [x] Mocked request validates configured model and bounded search parameters and preserves raw response, citations, and usage.
- [x] Canonical hash is stable for the same source payload and excludes retrieval time.
- [x] Missing or malformed identifiers/citations never become invented claims or citations.
- [x] CLI writes a versioned inspectable artifact without credential data.
- [x] Offline tests pass with no live API request (**74 passed** across the repository suite).
- [x] The one optional live smoke was capped, followed offline verification, and has a non-secret issue receipt; provider returned HTTP 404, so no response artifact was produced and no retry was made.
- [x] JEV-only deterministic output boundary is explicit in code/docs.
## Evidence and sources

- OpenRouter Web Search server tool guide: https://openrouter.ai/docs/guides/features/server-tools/web-search
- OpenRouter Grok 4.1 Fast catalog: https://openrouter.ai/x-ai/grok-4.1-fast/benchmarks
- Repository authority: accepted decision on issue #15 comment 5848935840; JEV constraints in AGENTS.md.
## Reproduction details (only when needed)

Starting revision, material inputs/configuration, runtime, exact command or prompt, observed result, and limitations.

## Related records

- Leaf: #15; parent: #14; dependencies for capture: none; later integration: #10 and #12.
- Primary writer: Codex project agent; branch: feat/grok-source-bot; task: JEV-0001.
- Authoritative decision: https://github.com/Pukujan/jev-classifier/issues/15#issuecomment-5848935840.
- As of: 2026-09-26; issue #15 is closed and PR #27 is merged to `main` at `e763206`.
## Checkpoint log

- 2026-09-26: Implementation and mocked tests complete. Full Python suite: 74 passed; CLI help and JSON schema syntax checked. One capped live smoke returned HTTP 404; current official OpenRouter docs confirm the configured Chat Completions endpoint and model listing, but the runtime cause is unknown. No second live request was made. Heavy iterative benchmarks are separately owner-directed to run serially on the MacBook Pro under #21.

## Handoff

Read PROJECT → CURRENT → this task → minimum relevant spec. Checkpoint before stopping.
