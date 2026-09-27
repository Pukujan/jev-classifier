# Annotation protocol for reference claim graphs

**Audience:** annotators, reviewers, and the custodian. **Status:** partial —
the protocol and its tooling exist; no paper is annotated yet. **Owner:** issue
[#90](https://github.com/Pukujan/jev-classifier/issues/90).

This page is the human half of the reference-graph work. The machine half is
`src/jev_classifier/annotation/`, which turns an annotator's quote selection
into exact offsets and refuses anything it cannot verify. The schema that both
obey is `schemas/reference_claim_graph.schema.json`, validated by
`src/jev_classifier/reference/validate.py`.

Read this before annotating a paper. It states what a claim is, where a claim
begins and ends, and what to do when two people disagree.

## 1. Why this page exists

The project's primary quality metric scores the classifier against
human-reviewed reference claim graphs. That makes the graphs the ground truth
of the whole program: a metric cannot be more trustworthy than the annotations
it is computed from. A graph built by one person in one sitting, with no stated
unit and no recorded disagreement, is not ground truth — it is one opinion with
a schema wrapped around it.

Everything below exists to make the graph auditable rather than merely present.

## 2. What a claim is

**A claim is one atomic proposition the paper asserts, recorded at the
tightest span of text that still carries the assertion.**

Three consequences follow, and each is a rule:

**Atomic.** One proposition per claim. A sentence asserting two independent
things is two claims. A sentence asserting half a thing is half a claim — the
span may end mid-sentence. The unit is the proposition, not the sentence, and
not the paragraph.

**Tightest.** The span covers the words that carry the assertion and nothing
more. A span that includes a neighbouring sentence is wrong even though it
contains the right words, because it would let a classifier score by
over-covering. The metric requires a predicted span to be *contained in* the
reference span, so an over-wide reference span silently makes the metric
easier. Tight spans are the defence.

**Asserted by the paper.** The claim is what the paper says, not what is true
about the world. A paper reporting a flawed study still *claims* its result,
and that claim belongs in the graph. Truth is not the annotator's question.

### What is not a claim

- A heading, caption, or table label with no assertion.
- A definition, unless the paper uses it to assert something.
- A description of what the paper will do ("this section reviews..."), unless
  the paper's own method is the object of study.
- Anything the paper does not say, however strongly it is implied. An
  implication the annotator supplies is recorded as `inferred`, and the
  distinction from `observed` is the next section's subject.

## 3. Epistemic status

Every claim carries exactly one status from the closed vocabulary defined in
`src/jev_classifier/reference/validate.py`. The vocabulary has one definition in
the tree; this page describes how to choose, it does not restate the list.

The decision rule:

- **`observed`** — the source reports it as a finding, result, measurement, or
  stated fact of its own work. The paper is asserting it directly.
- **`inferred`** — the claim is the annotator's reading rather than the paper's
  statement: a conclusion the text supports but does not assert, or a
  relationship between two of the paper's own statements.

When it is genuinely unclear, record `inferred` and say why in a review. An
`observed` that should have been `inferred` overstates the paper's confidence,
which is the more damaging error of the two.

**Do not** use the status field to record whether you believe the claim. That
is not what it measures.

## 4. Spans and offsets

**Every offset is a UTF-8 byte offset, never a character index.**

This is not a stylistic choice. The metric compares integer offsets against
reference byte spans. For ASCII text the two are identical, so a
character-index bug passes every test written in English and then silently
mismatches on the first paper containing an accented letter, a dash, or a
non-Latin script. The repository has been bitten by this class of defect
before.

Annotators never type offsets. `build_claim` takes the source text and the
selected quote and derives the offsets, so the number cannot be transcribed
wrongly:

```python
from jev_classifier.annotation import build_claim

claim = build_claim(
    claim_id="claim:paper-x-001",
    paper_id="paper:paper-x",
    source_id="source:paper-x-abstract",
    source_text=source_text,
    quote="the treatment group showed a significant improvement",
    text="The treatment group improved significantly on the primary endpoint.",
    epistemic_status="observed",
    recorded_at="2026-09-27T00:00:00+00:00",
)
```

`pick_span` refuses a quote that appears **zero times** (`kind="not_found"`) and
refuses one that appears **more than once** (`kind="ambiguous_match"`). A
refusal is the correct outcome — guessing which occurrence was meant is how a
graph acquires an offset that points at the wrong sentence.

If a quote legitimately repeats and you mean a specific occurrence, pass
`occurrence=` explicitly. That is a deliberate act with a visible record, which
is the point.

### The line-ending trap

Offsets are over the exact bytes supplied. A source stored with CRLF line
endings yields different offsets than the same source stored with LF. The
protocol therefore fixes the source form: **sources are normalised to LF before
annotation, and the normalised bytes are what the graph's offsets refer to.**
`tests/test_annotation.py` pins this with a metamorphic test asserting that the
same quote in LF and CRLF copies of a source produces the documented,
predictable offset relationship.

## 5. The six properties

These are not advice. `validate_protocol` in
`src/jev_classifier/annotation/protocol.py` checks each one, and the test suite
exercises a violation of every property. A graph that breaks a hard property
does not ship.

| Property | Rule | On violation |
| --- | --- | --- |
| **P1 Minimality** | No claim's span strictly contains another's on the same source, unless they assert different propositions (different text or status). | raises `containment` |
| **P2 Atomicity** | One proposition per span. A span joining two independent assertions via a coordinating conjunction is flagged. | advisory finding |
| **P3 Verbatim** | The recorded quote appears byte-identically at the recorded offsets in the named source. | raises `not_verbatim` |
| **P4 Bitemporality** | `recorded_at` (when annotated) and `valid_from`/`valid_to` (when the claim holds in the paper's terms) are distinct; `valid_from <= valid_to`. | raises `bitemporal` |
| **P5 Epistemic honesty** | Status is drawn from the closed vocabulary. | raises `unknown_status` |
| **P6 Disagreement preserved** | Every claim with two or more reviews carries them as review records; supersession chains terminate. | raises `disagreement_lost` |

**P1 is the one annotators find surprising.** If claim A's span contains claim
B's span and they say the same thing, B is not a claim — it is a fragment of A,
and one of them should be deleted. If they say different things, both are
legitimate and P1 permits them. The rule catches accidental double-annotation,
not legitimate specificity.

**P2 is advisory on purpose.** Deciding whether a span holds one proposition or
two is a judgement about meaning, and a regex cannot make it. The tooling flags
candidates for a human; it never auto-splits. An auto-split would produce two
claims nobody reviewed.

**P3 needs the source text.** Because the repository must not commit restricted
full text, the checker is given sources by the caller. When a source text is
not supplied, P3 records a skipped finding rather than passing silently — an
unchecked graph must never look like a checked one.

## 6. Disagreement and adjudication

Disagreement is data. It is recorded, never resolved by quietly picking a
value.

**Procedure.** Two annotators work independently on the same paper. They do not
discuss before annotating — a scheme that lets annotators converge by
conversation measures the conversation, not the protocol. Each annotator's
decisions are recorded as `review` records on the claims.

**Reporting agreement.** `agreement.py` computes Cohen's kappa from the review
records and returns the counts behind the number, not just the ratio. Report
**both** the raw percentage agreement and the chance-corrected coefficient; a
coefficient can look respectable while the raw agreement is poor, and the
counts let a reader see which happened.

The degenerate case is handled explicitly: when both annotators used one
category exclusively, expected agreement is 1.0 and the coefficient is
undefined by its own formula. The module returns 1.0 flagged as degenerate
rather than dividing by zero. A degenerate result is a signal that the sample
is too uniform to measure agreement, not a signal of perfect agreement.

**Adjudication.** A third party resolves a disagreement and records the
resolution as a new review with `supersedes_review_id` naming the review it
replaces. The chain is preserved — P6 checks that it terminates — so a reader
can always see that a disagreement occurred and how it was settled. A graph
where the disagreement has been erased is worse than one where it is visible,
because the erased version claims a certainty nobody had.

## 7. Ordering: the freeze comes first

The development/holdout split is frozen **before** annotation begins, per
[`HOLDOUT_PROTOCOL.md`](HOLDOUT_PROTOCOL.md) §3.3. Annotate with the split
already fixed, so that no annotation decision can be influenced by which papers
will be used for tuning.

The annotator does not need to know which side a paper is on. Annotate every
paper to the same standard; the split is the custodian's concern.

## 8. Rights

Only papers whose licence permits the use are annotated, and restricted full
text is never committed. The per-paper licence, the version it applies to, and
the rights boundary are already recorded in
`datasets/reference_papers.json`; consult it before starting a paper.

Where the licence covers the article but not an associated dataset or figure,
the article text may be annotated and the dataset may not. That distinction is
recorded per paper and is not generalisable — check the entry.

## 9. What the tooling does not do

- It does not read a paper for you, summarise it, or suggest claims. Claim
  identification is the annotator's work.
- It does not decide whether a span holds one proposition or two (P2 is
  advisory).
- It does not adjudicate a disagreement.
- It does not verify that a claim is *correct* about the world — only that it
  is verbatim, contained, and internally consistent.
- It never repairs a malformed graph. Every failure raises with a named `kind`.

## 10. Status of this page

The protocol and the tooling are written and tested. **No paper has been
annotated.** The properties are enforced against synthetic fixtures; the first
real paper is the first real test of whether the protocol is workable, and it
may change the page. Where it does, the change is recorded rather than made
quietly.
