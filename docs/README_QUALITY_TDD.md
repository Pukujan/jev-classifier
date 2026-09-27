# Test design for human-facing project claims

## Deterministic checks

- The nine required README headings are present.
- Required content guides and references are linked.
- Local relative links and images resolve inside the repository.
- The content brief validates the required claim status, support, limit, revision, and timestamp fields.
- Prompt-record and asset-manifest hashes match the committed images.
- A heading and bold-anchor scan communicates the reader problem, current capability, boundary, and next action.

The pinned helper checks only its declared structure, schema, evidence identity, citation presence, and hashes. The target script checks local links, required section order, and each contract-required reference link. Neither it nor the manifest validator proves research accuracy, citation quality, or reader comprehension.

## Human review tasks

Optional reader QA can give the README to a reader without the issue or conversation. Ask them to:

1. Explain what one unit of classification is.
2. Distinguish untrusted source capture from the JEV classifier role.
3. Name one implemented limit.
4. Find the synthetic example and explain why it is not accuracy evidence.
5. Find the smallest reproducible next step.

Record reader responses before claiming the README improves comprehension. This task records a review checklist, not results from a human-participant study.

## Holdout status

No private README holdout was used for this deliverable. The classifier holdout belongs to the separate #21 program. Keep hidden labels and source packet keys outside the model-visible tree.
