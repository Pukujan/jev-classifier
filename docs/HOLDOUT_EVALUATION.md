# Holdout evaluation

The quality targets below belong to the owner-directed program in [issue #21](https://github.com/Pukujan/jev-classifier/issues/21). They are requirements for future evaluation, not results reported by the README task.

## Planned classifier evaluation

- Reverse-analyze at least 10 research papers.
- Record at least 30 documented development iterations.
- Separate paper families between development and hidden holdout.
- Preserve the proposed paper-level holdout and its claim-level F1 target of at least 0.80.
- Report citation support, omitted caveats, scope changes, abstention, and human readability as distinct outcomes.

The target repository currently contains synthetic fragment fixtures. They are useful for offline contract checks but cannot substitute for a human-annotated paper set. Keep hidden labels and test keys outside the model-visible checkout until the protocol is frozen.

## Execution placement and records

The owner assigned resource-intensive benches to the MacBook Pro agent because the Windows machine has RAM, storage, and package/container limits. Before a run, record its issue, source and dataset revisions, host/runtime, requested and surfaced model identity where available, temperature, tools, prompt/schema revision, run identifier, failures, and output hashes. An unavailable field stays marked unavailable rather than guessed.

## README review is not a holdout

The pinned CGM checker and target-side link/heading validator cover visible structure. This task has no blinded reader trial or hidden README holdout result. Complete the [human checklist](README_REVIEW.md) and report the absence of a holdout plainly.
