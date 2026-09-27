# Content research and evidence map

This guide records how the README story was derived from the target repository. It is not a user study and does not replace the technical system specification.

## Primary reader and task

The primary reader is a researcher who receives related AI-generated accounts of a paper and needs to check what each claim points to. A maintainer and a fresh coding agent are secondary readers: they need to distinguish current code from planned research.

The concrete repository example is the synthetic two-fragment test. One fragment describes an imagined study protocol; another describes its imagined result. The test passes fixture text and mocked JEV answers through the prototype. It demonstrates data flow only. It does not establish accuracy on real papers.

## Evidence inspected

| Repository source | What it establishes | What it leaves open |
| --- | --- | --- |
| src/jev_classifier/sources/grok.py and docs/GROK_SOURCE.md | A bounded source-capture artifact shape and untrusted-source boundary | Live provider behavior and automatic connection to classification |
| src/jev_classifier/classify.py and src/jev_classifier/normalize.py | A one-fragment closed-choice path and choice/score/noul validation | Automatic multi-transcript claim extraction and paper-level accuracy |
| src/jev_classifier/consolidate.py and src/jev_classifier/paper/assemble.py | Deterministic consolidation of supplied claims by explicit topic, including conflict preservation and bitemporal resolution; an optional Synthesis section renders caller-supplied topic records | Topic inference and claim extraction from raw transcripts, narrative prose, citation correctness, and preservation of every caveat |
| src/jev_classifier/reference/validate.py and schemas/reference_claim_graph.schema.json | Reference claims with source-version identifiers, byte spans, temporal fields, review records, and validated cross-record links | Human annotation quality and real-paper summary fidelity |
| tests/test_multisource_e2e.py and tests/fixtures/multisource/ | One synthetic two-fragment path with mocked responses | Generalization to research corpora or live outputs |
| ontology/jev_classifier_claims.ttl and ontology parse tests | A parsable Turtle vocabulary | SHACL constraints and full OWL2 reasoner entailment |
| docs/DATASET_CARD.md, scripts/eval_claims.py, and GitHub issue #21 | Ten candidate papers are selected and `claim_metric_v1` is pre-registered | Reverse-analysis annotations, a frozen holdout score, and completion of the 30-iteration program |

The project brief stores more granular claim/support/limit/source records. See [.content-system/project-brief.json](../.content-system/project-brief.json).

## Editorial choices

- Lead with source-to-claim traceability rather than claiming autonomous research.
- Describe the actual single-fragment behavior before the future multi-source goal.
- Distinguish the shipped claim-record consolidator from the still-missing raw-transcript ingestion path.
- Say “untrusted source transcript” for non-JEV research output.
- Say “JEV judgment” only for the bounded semantic classifier role.
- Treat bias checks as measured signals, not proof.
- Put numerical quality thresholds beside their issue status and call them planned; distinguish selected candidate papers from completed reverse-analysis annotations.
- Scope timestamp and evidence-reference limits to the legacy M5 claim builder; describe M8 and reference-graph validation separately.

The heading, image, and bold-anchor pattern is a documentation contract. Its effectiveness has not been measured with reader participants.
