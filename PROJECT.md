# jev-classifier project guide

## Purpose

Build a mostly deterministic workflow that turns supplied AI research fragments into structured claim records with source pointers, epistemic status, lineage, citations, and distinct valid and transaction times. It is a prototype for research review, not an autonomous research agent or completed paper-writing system.

The boundary is strict: TypeSafe JEV through the OpenRouter Decisions API is the only permitted source of semantic classifier judgments. Other research models can provide untrusted source transcripts only. Python owns validation, aggregation, thresholds, timestamps, provenance fields, and deterministic rendering.

## What exists now

| Area | Repository evidence | Current limit |
| --- | --- | --- |
| Source capture | Bounded Grok/OpenRouter adapter in docs/GROK_SOURCE.md and src/jev_classifier/sources/grok.py | Source text is untrusted; live provider smoke was not successful, so live capture is unverified. |
| Decisions client | src/jev_classifier/decisions.py uses the Decisions endpoint and pins the default model family | The classifier path does not yet prove surfaced model identity matches the requested identity in every case. |
| Normalization | src/jev_classifier/normalize.py validates choice and noul responses | Score is declared in project policy but not implemented; see issue #32. |
| Classification | src/jev_classifier/classify.py builds one claim from one supplied fragment and a closed label set | It is not an automatic multi-transcript research classifier. |
| Provenance | Claim records carry evidence pointers and separate transaction/optional valid-time fields | Timestamp parsing/order, evidence-reference existence, and full activity/agent linkage are gaps. |
| Ontology | ontology/jev_classifier_claims.ttl defines a small PROV-aligned vocabulary | Turtle parse tests do not provide SHACL validation or full OWL2 reasoning. |
| Paper assembly | src/jev_classifier/paper/assemble.py renders six sections with deterministic templates | A structural draft skeleton is not paper-quality narrative synthesis or citation verification. |
| Bias signals | src/jev_classifier/bias/ contains closed JEV questions and local aggregation | Signals are not proof of model bias, agent bias, or correctness. |
| Offline dataset fixtures | docs/DATASETS.md and scripts/generate_synthetic_fixtures.py record deterministic claim-type and contradiction examples | Samples are hand-authored synthetic shapes, not source-corpus text or benchmark evidence. |
| Multi-source example | tests/fixtures/multisource/ and tests/test_multisource_e2e.py exercise mocked answers | Examples are synthetic and do not measure real-paper accuracy. |

## Quality program and sequencing

Issue #21 owns the planned paper-level quality program: at least 10 research papers for reverse analysis, at least 30 recorded development iterations, a paper-level hidden holdout, and a target of 0.80 claim-level F1. These are acceptance goals and have not been achieved or measured by this README task.

GitHub owns issue status, proposals, review, and sequencing. Issue #23 is accepted but deferred by the authoritative agent until its prerequisite work is complete; see that issue for the current decision. Resource-intensive benchmark runs belong on the designated MacBook Pro agent. PCM and local SQLite are continuity helpers only; GitHub is canonical.

## Work paths

- First-time users: start with README.md and the synthetic multi-source fixture.
- Developers: read docs/SYSTEM_SPEC.md and docs/GROK_SOURCE.md.
- Researchers: read docs/RESEARCH_NOTES.md, docs/HOLDOUT_EVALUATION.md, and issue #21.
- Agents: read AGENTS.md, docs/AUTHORITY.md, docs/AGENT_COORD.md, and docs/CURRENT.md.

## Local setup

Python 3.11 or newer is required. From the repository root:

    python -m pip install -e ".[dev]"
    python -m pytest tests/ -q

A live Decisions smoke is optional and requires OPENROUTER_API_KEY:

    python scripts/smoke_jev.py

Do not put credentials in source, issues, artifacts, or logs. See .env.example.
