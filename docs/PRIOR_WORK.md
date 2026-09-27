# Prior work and references

This README adopts methods and evidence boundaries already present in the repository. It does not imply that an earlier implementation is a completed synthesis system.

## Repository history

- [Issue #14](https://github.com/Pukujan/jev-classifier/issues/14) is the parent project for the JEV research-synthesis classifier.
- [Issue #15](https://github.com/Pukujan/jev-classifier/issues/15) tracks the Grok source-capture path. The resulting transcript and citations are untrusted source material.
- [Issue #21](https://github.com/Pukujan/jev-classifier/issues/21) owns the modular quality program, reference-paper work, iterations, and hidden paper-level holdout.
- [Issue #35](https://github.com/Pukujan/jev-classifier/issues/35) records this README and documentation delivery.

GitHub issues, decisions, and pull requests are canonical. Local project-continuity and SQLite files help agents resume work but are not decision authorities.

## Continuity and provenance references

[Project Continuity Modules](https://github.com/Pukujan/project-continuity-modules) is a helper for continuity records and evidence-aware project work. This repository borrows that helper role and compatible terminology; it does not install PCM as a product dependency.

[W3C PROV-O](https://www.w3.org/TR/prov-o/) provides an interoperable Entity, Activity, Agent, and derivation vocabulary. The current ontology is smaller, and the runtime does not yet link every classification decision to a PROV Activity and Agent.

The pinned [Content Generation Modules 0.4.0 draft](https://github.com/Pukujan/content-generation-modules/tree/f85e88bc00362c53061d95ac7811bd9c6ada8e32) supplies the README and evidence-record workflow. It is a documentation helper, not runtime code and not authority over the target repository's technical design.

## Limits

References show where a pattern came from. They do not prove the classifier is correct, validate the project's ontology, or establish reader comprehension. Each product claim still needs its own implementation, fixture, run, or issue source.
