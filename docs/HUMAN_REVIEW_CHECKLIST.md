# HUMAN REVIEW CHECKLIST — reader usefulness of a managed document

**Status:** shipped (the checklist); a review is recorded per document in
`docs/docs_manifest.json` (`review_state`, `reviewed_commit`, `reviewed_sha256`).
**Owner:** issue [#63](https://github.com/Pukujan/jev-classifier/issues/63).

## What this is, and what it is not

The automated checks — `python scripts/validate_docs.py` — verify **objective**
things: that a manifest record's path and sources resolve, that a recorded file
hash still matches, that local links resolve, and that excluded paths never
appear. They cannot judge whether a page is *useful*.

This checklist covers the part a machine cannot: **can a person who did not
write this page get what they need from it?** Running it is a human act. A
passing automated check is **not** evidence that this checklist was done, and
finishing this checklist is **not** evidence that a reader will understand the
result — it records that one named person read it and what they concluded.

Do not mark a review complete without recording the reviewer and the result.

---

## How to use it

For one document at a time, read it as its declared audience (see the
`audience` field in `docs/docs_manifest.json`). Then answer every line below
**Yes / No / Not applicable**, and write the reviewer identity, the date, and
one sentence of the result. A single **No** is not a failure of the page — it is
a finding to record and act on.

## Section 1 — First-time reader

- [ ] The **first paragraph** says what the page is for and who it is for,
      without requiring the rest of the page.
- [ ] Reading only the **headings, first sentences, and bold anchors** gives an
      accurate outline. (The scanability test.)
- [ ] Every **undefined term** a newcomer would trip on is defined on first use
      or linked to where it is.
- [ ] The page states, or links to, **one concrete next action**.
- [ ] Nothing assumes a **private path, local setup, or unwritten context** the
      reader cannot reach.

## Section 2 — Evidence and boundaries

- [ ] Every **load-bearing claim** is labelled by kind: source fact, JEV
      judgment, inference, unknown, or proposal (see
      [`docs/EPISTEMIC_SYSTEM.md`](EPISTEMIC_SYSTEM.md) §3.1).
- [ ] Every **status label** (shipped / partial / planned / unknown) matches
      what the code and issues actually show.
- [ ] **Citations and lineage sit beside** the claims they support, not in a
      pile at the end.
- [ ] The page states **what it does not establish** — and no number here is
      presented as an accuracy or truth result when it is not one.
- [ ] **Valid time and record time** are not conflated where both appear.
- [ ] No **fixture, synthetic example, or placeholder** is presented as a real
      result.

## Section 3 — Navigation and accessibility

- [ ] The page is **reachable** from [`docs/INDEX.md`](INDEX.md) and links back
      into the tree.
- [ ] Every **internal link** resolves, and link text describes its destination
      rather than saying "here".
- [ ] **Headings are a clean hierarchy** (no skipped levels) so screen readers
      and the outline view both work.
- [ ] Any **diagram or table has a text equivalent** beside it, so meaning
      survives when the diagram does not render.
- [ ] Tables and code blocks stay **readable at narrow width**; nothing depends
      on colour alone.

## Recording a review

Fill this in and keep it with the review (in the PR, the issue, or the
manifest's review fields):

```
Document:            <path>
Reviewer:            <name / agent id>
Date:                <YYYY-MM-DD>
Audience reviewed as:<newcomer | contributor | maintainer | reviewer | agent>
Section 1:           <pass / findings>
Section 2:           <pass / findings>
Section 3:           <pass / findings>
Result:              <one sentence>
review_state:        <unreviewed | reviewed | stale>
```

Set `review_state` to `reviewed` only when the reviewer and result above are
recorded. `stale` means the document changed after the review commit and needs
re-reading.
