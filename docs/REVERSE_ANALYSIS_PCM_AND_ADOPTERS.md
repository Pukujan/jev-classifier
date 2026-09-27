# Reverse analysis of PCM and related repository examples

This is a source-grounded design comparison for the README method, not a controlled usability study.

## Reused method

[Project Continuity Modules](https://github.com/Pukujan/project-continuity-modules) demonstrates a human problem followed by consequences, a concrete mechanism, reader paths, evidence, boundaries, and setup. The jev-classifier README reuses that order because research provenance is easier to understand when it starts with a reader's task rather than an internal module list.

The target does not copy PCM's product story, exact headings, or brand. It explains the target's own case: a researcher comparing claims across AI-generated research accounts.

## Target-specific differences

- PCM is a continuity helper; jev-classifier is a prototype classifier and record renderer.
- The classifier keeps semantic judgment on TypeSafe JEV and leaves source transcripts untrusted.
- The target's current unit is one fragment. Synthetic multi-source tests do not establish real-paper quality.
- The target records bitemporal fields but has documented validation gaps.
- GitHub issues and PRs are canonical; local SQLite and PCM are helpers.

The content-generation helper is separately pinned at the draft commit listed in [.content-system/system-version.json](../.content-system/system-version.json). Its modules inform the documentation process; they do not govern classifier architecture.

## Limitations

The reviewed PCM and other adopter READMEs are design examples, not randomized comparisons or hidden holdouts. This analysis cannot establish that a particular storytelling method increases reader comprehension. The human review tasks in [README_QUALITY_TDD.md](README_QUALITY_TDD.md) remain unrun until recorded.
