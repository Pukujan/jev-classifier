# Coordination board (ops ledger projection)

> Parsed from `coord:proposal` / `coord:verdict` / `coord:claim` comment
> markers and legacy `## Claim` prose (docs/AGENT_PROPOSALS.md, #22).
> GitHub comments are the authority; this file is a regenerated projection.
> `by=` / `agent=` are self-declared under the shared account: evidence,
> not enforcement. This board does not arbitrate.

## Proposals

| id | issue | scope | status | decision |
|----|-------|-------|--------|----------|
| P-31-1 | #31 | ontology-prov | open | accepted |
| P-32-1 | #32 | score-bias-fixes | open | accepted |
| P-35-1 | #35 | CGM_0.4.0_README_and_docs | open | accepted |

## Live claims

| issue | agent | branch | marker |
|-------|-------|--------|--------|
| #31 | claude-code-main@desktop-utf8-44 | `feat/ontology-prov-activity-31` | coord |
| #35 | Pukujan | `feat/cgm-docs-35` | prose |
| #35 | claude-code-main@desktop-jev35 | `feat/cgm-docs-35` | coord |
| #53 | coordination-flagger | `fix/claim-holder-collision-53` | coord |

## Run receipts

| Run/task | Agent alias | Model alias / version alias | Temperature + source | Tools/version/count + source | Outcome / evidence |
|---|---|---|---|---|---|
| r-36-1 / JEV-0022 | A-FLAGGER (owner_recorded) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,continuity,python (agent_declared) | merged (runtime_observed) [no link] |
| r-36-1-fix1 / JEV-0022 | A-FLAGGER (agent_declared) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,continuity,python (agent_declared) | merged (runtime_observed) [no link] |
| r-45-1 / JEV-41 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | sh,launchctl,pytest,gh,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-45-1-fix1 / JEV-41 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | sh,launchctl,pytest,gh,python3 (agent_declared) | merged (runtime_observed) [no link] |

## Collisions

_(none detected)_
