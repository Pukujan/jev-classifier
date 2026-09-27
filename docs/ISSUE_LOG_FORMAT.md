# Issue log format

**Audience:** agents writing issue logs, progress comments, and pull-request
openings. **Status:** shipped. **Owner:** continuity helper (PCM issue-log-format
1.2.0), with human-title rule from issue
[#79](https://github.com/Pukujan/jev-classifier/issues/79).

The short form lives in `AGENTS.md` inside the `pcm:issue-log-format` block.
This page is the expanded reference.

## Titles must be plain human sentences

Issue titles, commit subjects, and PR titles follow
[`HUMAN_NAMING.md`](HUMAN_NAMING.md). Write one plain sentence of what is wrong
or what the reader gets. Do not lead with `feat:` / `fix:` / `chore:` or with
internal codes such as `M5` or `known_gap`. Put those in the body.

## Core tier (every issue log)

- **Title** — plain human sentence (see above).
- **Summary** — 1–3 paragraphs: who/what is affected, the consequence, and what
  this proposes.
- **Identity and lineage** — leaf owning issue, parent ancestry or none, task
  ID, primary writer, branch.
- **Observed facts vs interpretation** — label inferences *inferred*.
- **Acceptance criteria** — numeric thresholds marked *(proposed)* when
  untested.
- **Boundaries / non-goals** and one next action.

## Investigation tier (incidents, failures, research, design)

Add numbered symptoms; hypotheses with Status, confirm/refute, and experiment;
evidence with provenance; a **Counter-signal** when one exists; an honest
caveat; problems-vs-gaps; a **Proposal** labelled *(proposal)* unless named as
existing.

## Pull requests (reader-first)

- **PR title** — plain human sentence of the user-visible or maintainable
  change (same rule as issue titles and commit subjects).
- Body: problem and consequence, what changes, how to verify, what stays
  unchanged; lineage links; evidence and one next action.
- Reference issues with `Refs #<number>`; use closing keywords only when
  closing at merge is intended.

## Readability

Give every SHA, comment id, flag, file path, or tool name a plain-word meaning
in the same sentence before it carries load. Write evidence as the claim first,
numbers as support. No unexplained acronym on first use. No private absolute
paths or secrets.

## Related

- [`HUMAN_NAMING.md`](HUMAN_NAMING.md) — naming rules and CGM pins
- `AGENTS.md` — operating rules and the embedded issue-log-format policy block
