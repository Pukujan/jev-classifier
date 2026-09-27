# Coordination board (ops ledger projection)

> Parsed from `coord:proposal` / `coord:verdict` / `coord:claim` comment
> markers and legacy `## Claim` prose (docs/AGENT_PROPOSALS.md, #22).
> GitHub comments are the authority; this file is a regenerated projection.
> `by=` / `agent=` are self-declared under the shared account: evidence,
> not enforcement. This board does not arbitrate.

## Proposals

| id | issue | scope | status | decision |
|----|-------|-------|--------|----------|
| P-23-1 | #23 | framing_drift_study | open | accepted |
| P-29-1 | #29 | dataset_card_and_reference_selection | open | accepted |
| P-31-1 | #31 | ontology-prov | open | accepted |
| P-32-1 | #32 | score-bias-fixes | open | accepted |
| P-35-1 | #35 | CGM_0.4.0_README_and_docs | open | accepted |
| P-37-1 | #37 | reference_claim_graph_and_stimulus_schema | open | accepted |
| P-60-1 | #60 | coordination | open | accepted |
| P-61-1 | #61 | coordination | open | accepted |
| P-63-1 | #63 | documentation_management | open | deferred |
| P-63-2 | #63 | epistemic_documentation_ux | open | accepted |
| P-66-1 | #66 | metric_harness | open | accepted |

## Live claims

| issue | agent | branch | marker |
|-------|-------|--------|--------|
| #35 | Pukujan | `feat/cgm-docs-35` | prose |
| #35 | claude-code-main@desktop-jev35 | `feat/cgm-docs-35` | coord |
| #63 | claude-code-main@desktop-utf8-44 | `feat/epistemic-docs-63` | coord |
| #72 | jev-classifier@teresa | `feat/subject-assignment-72` | coord |

## Run receipts

| Run/task | Agent alias | Model alias / version alias | Temperature + source | Tools/version/count + source | Outcome / evidence |
|---|---|---|---|---|---|
| 2026-09-26T23-37r1 / JEV-37 | A-JEV37 (owner_recorded) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,uv (agent_declared) | merged (runtime_observed) [no link] |
| 2026-09-27T00-37r1 / JEV-66 | A-JEV66 (owner_recorded) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,uv (agent_declared) | merged (runtime_observed) [no link] |
| r-29-1 / JEV-0003 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | gh,git (agent_declared) | merged (runtime_observed) [no link] |
| r-36-1 / JEV-0022 | A-FLAGGER (owner_recorded) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,continuity,python (agent_declared) | merged (runtime_observed) [no link] |
| r-36-1-fix1 / JEV-0022 | A-FLAGGER (agent_declared) | unavailable / unavailable | unavailable (unavailable) | gh,git,pytest,continuity,python (agent_declared) | merged (runtime_observed) [no link] |
| r-45-1 / JEV-41 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | sh,launchctl,pytest,gh,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-45-1-fix1 / JEV-41 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | sh,launchctl,pytest,gh,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-55-1 / JEV-53 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | gh,git,pytest,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-57-1 / JEV-57 | coordination-flagger (agent_declared) | JEV-PIN / V-20260917 | unavailable (unavailable) | python3.12-venv,httpx,gh,git,pytest (agent_declared) | merged (runtime_observed) [no link] |
| r-60-s1 / JEV-60 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | gh,git,pytest,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-67-1 / JEV-61 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | gh,git,pytest,python3 (agent_declared) | merged (runtime_observed) [no link] |
| r-70-1 / JEV-69 | coordination-flagger (agent_declared) | unavailable / — | unavailable (unavailable) | gh,git,pytest,python3 (agent_declared) | merged (runtime_observed) [no link] |

## Collisions

_(none detected)_

## Malformed records

- issue #66 comment 5851155281: coord:claim missing branch= (comment 5851155281); a claim without a reserved ref is not a lock
