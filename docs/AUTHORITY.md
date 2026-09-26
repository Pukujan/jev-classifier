# AUTHORITY — who decides, and what never stops

Owner-directed policy (2026-09-26). This document is binding for every agent
working in this repository.

## 1. The authoritative agent

- The **authoritative agent** is the main agent session acting for the owner
  (@Pukujan). It is the **sole arbiter** of this project.
- If agents disagree — proposals, contradictions, collisions, sequencing,
  test policy — the authoritative agent decides. Its ruling is final and is
  recorded as a comment on the relevant GitHub issue.
- Product agents **propose only**. They do not self-arbitrate, do not overrule
  each other, and do not start contested work before a ruling lands.
- When a problem has no clean answer, the authoritative agent picks the **most
  plausible, slimmest solution** (fuzz where useful), applies it, records it,
  and moves on. Perfection is not the bar; forward motion with evidence is.

## 2. The project does not stop

- Once started, the project **does not stop for anyone — including the owner**.
  No waiting for pings, approvals, or consensus.
- Blockers get the slimmest plausible fix, applied immediately, recorded on the
  owning issue, then work continues.
- If a leaf is blocked by a ruling, other leaves proceed in parallel.

## 3. Canonical state

| Layer | Role |
|-------|------|
| **GitHub issues/PRs** | Canonical authority for work items, ownership, decisions, delivery. |
| `docs/CURRENT.md` | Human-readable board projection; updated at each milestone. |
| `.coord/` SQLite (`CoordStore`) | Execution aid: claims, checkpoints, send-log, collision flags. Rebuildable; never authority. |
| `.ops/` + `ops/ledger/` (#18) | Ops projection: issue-log summaries, discrepancy reports. Readable on GitHub; never authority. |
| PCM (`project-continuity-modules`) | Continuity/checkpoint helper protocol. Not a second product owner. |

If SQLite and GitHub disagree, **GitHub wins**. Delete and rebuild local DBs
freely.

## 4. Proposal layer (how work gets claimed)

1. **Propose:** comment `## Proposal` on a leaf issue — scope, boundary,
   dependencies, done-when. Do not implement yet if the leaf is contested.
2. **Rule:** the authoritative agent comments `## Decision — ACCEPT/REJECT`
   naming the primary writer and branch. Accepted leaves are unblocked.
3. **Claim before write:** `CoordStore.claim_ownership(...)` + a `## Claim`
   comment (leaf, parent, branch). On `CollisionError` → stop and report;
   never overwrite another agent's branch.
4. **Checkpoint:** `## Progress` comments with verifiable evidence (commands,
   test counts) at each milestone; idempotent checkpoint keys in the store.
5. **Deliver:** small issue-linked PR from a feature branch; CI green; merge;
   `## Verify evidence` comment; close the leaf; release ownership.

## 5. Hard technical rules (never negotiable)

- **JEV-only deterministic outputs.** Labels, scores, and semantic judgments
  entering the claim graph come exclusively from TypeSafe JEV via
  `POST https://openrouter.ai/api/alpha/decisions`, pinned
  `typesafe/jev-1.13` (rolling `~typesafe/jev-latest` is canary-only).
  Primitives: `choice` / `score` / `noul`. **Any other model producing
  deterministic classifier output is prohibited.**
- **Model-agnostic sources.** Grok or any research model may produce *source
  transcripts only* — untrusted material with provenance. Never a label,
  score, gold answer, or canonical claim.
- **Deterministic Python owns everything else:** parsing, bitemporal handling
  (valid time ≠ transaction time), hashes, schemas, aggregation, validation,
  citation linking, paper templates.
- **Fail closed:** malformed/out-of-set JEV answers → review state, never a
  guessed label. Confidence ≠ correctness; preserve native probability maps.
- **Bias signals are measured signals**, evaluated against explicit fixtures —
  never presented as proof of bias or correctness.
- **Secrets:** never printed, logged, or committed. `.env` stays gitignored.

## 6. Storage watchdog

The owner runs a storage watchdog on the local PC; GitHub is the authoritative
owner of project state precisely so local disk is disposable. Therefore:

- Keep the working tree lean: no large binaries, no committed datasets, no
  runaway caches (`__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
  are gitignored and must not be committed).
- Datasets from Hugging Face or elsewhere are downloaded to gitignored paths
  (`data/`, `.cache/`) and referenced by name/revision in fixtures — never
  committed wholesale. Small offline fixtures only.
- `.coord/` and `.ops/` DBs are rebuildable projections; trim or delete freely.
- Committed ledgers (`ops/ledger/`) stay small: summaries, not raw payloads.

## 7. Watchdog / ready signals

- A GO for all agents is a `COLLAB_GO` comment from the authoritative agent on
  the parent issue (see #14). The 2026-09-26 GO is
  [issuecomment-5848946788](https://github.com/Pukujan/jev-classifier/issues/14#issuecomment-5848946788).
- Agents waiting on coordination should poll the parent issue and
  `docs/CURRENT.md`, not the owner.
