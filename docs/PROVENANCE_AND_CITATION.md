# Provenance and citation guide

Use this guide when a project claim needs to be checked against the file, test, owner decision, run, or external reference that supports it.

## Evidence record

For each material documentation claim, record:

| Field | Meaning |
| --- | --- |
| Claim | The bounded statement a reader may rely on |
| Source | File, fixture, issue, run, or publication |
| Status | Shipped, experimentally supported, planned, or unknown |
| Supports | What the source establishes |
| Limits | What it leaves unproven |
| Source revision | Commit, path, locator, URL, or issue record |
| Recorded time | When this version of the evidence note was recorded |
| Valid time | Optional interval in which a time-bound claim applies |

A citation provides traceability, not truth. The author must still ensure the source supports the wording.

## Temporal distinction

The legacy M5 claim record can carry `valid_from` and `valid_to` fields for when a claim applies, and `recorded_at` for when the project recorded the version. That path does not parse timestamp strings, check valid-time ordering, or resolve its evidence pointers. Other modules have narrower checks: M8 consolidation validates bitemporal inputs and supersession chains, while the reference-graph validator checks source spans and cross-record links. These checks do not make the project a general bitemporal query service.

## Provenance boundary

The project ontology is PROV-aligned but small. Current records do not link every JEV decision through a complete PROV Activity and Agent chain. The Markdown assembler prints supplied evidence identifiers; it does not resolve them to source URLs or verify citation support.

For entity, activity, agent, and derivation vocabulary, see [W3C PROV-O](https://www.w3.org/TR/prov-o/). The target implementation remains the authority for its own fields and validation.

## Citation practice

Use immutable repository links for code claims. Use direct primary references for outside research or standards. Record access dates for pages that can change. Keep unsupported assumptions as unknown, and keep a plan separate from a shipped claim. See [.content-system/project-brief.json](../.content-system/project-brief.json) for this README's evidence ledger.
