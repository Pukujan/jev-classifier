# Content research and evidence map

This guide records how the README story was derived from the target repository. It is not a user study and does not replace the technical system specification.

## Primary reader and task

The primary reader is a researcher who receives related AI-generated accounts of a paper and needs to check what each claim points to. A maintainer and a fresh coding agent are secondary readers: they need to distinguish current code from planned research.

The concrete repository example is the synthetic two-fragment test. One fragment describes an imagined study protocol; another describes its imagined result. The test passes fixture text and mocked JEV answers through the prototype. It demonstrates data flow only. It does not establish accuracy on real papers.

## Evidence inspected

| Repository source | What it establishes | What it leaves open |
| --- | --- | --- |
| src/jev_classifier/sources/grok.py and docs/GROK_SOURCE.md | A bounded source-capture artifact shape and untrusted-source boundary | Live provider behavior and automatic connection to classification |
| src/jev_classifier/classify.py and src/jev_classifier/normalize.py | A one-fragment closed-choice path and choice/noul validation | Multi-fragment classification and score normalization |
| src/jev_classifier/paper/assemble.py | A six-section Markdown draft renderer | Narrative synthesis, citation correctness, and preservation of every caveat |
| tests/test_multisource_e2e.py and tests/fixtures/multisource/ | One synthetic two-fragment path with mocked responses | Generalization to research corpora or live outputs |
| ontology/jev_classifier_claims.ttl and ontology parse tests | A parsable Turtle vocabulary | SHACL constraints and full OWL2 reasoner entailment |
| GitHub issue #21 | Planned paper-level evaluation goals | Any completed quality score or holdout result |

The project brief stores more granular claim/support/limit/source records. See [.content-system/project-brief.json](../.content-system/project-brief.json).

## Editorial choices

- Lead with source-to-claim traceability rather than claiming autonomous research.
- Describe the actual single-fragment behavior before the future multi-source goal.
- Say “untrusted source transcript” for non-JEV research output.
- Say “JEV judgment” only for the bounded semantic classifier role.
- Treat bias checks as measured signals, not proof.
- Put numerical quality thresholds beside their issue status and call them planned.
- Keep bitemporal field presence separate from timestamp and reference validation.

The heading, image, and bold-anchor pattern is a documentation contract. Its effectiveness has not been measured with reader participants.
