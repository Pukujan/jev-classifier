# EPISTEMIC SYSTEM — how this project decides what it is allowed to say

**Audience:** anyone reading a claim, paper draft, or score this project
produces. **Status:** shipped for the rules it describes; partial where it says
so. **Owner:** issue [#63](https://github.com/Pukujan/jev-classifier/issues/63),
leaf of [#14](https://github.com/Pukujan/jev-classifier/issues/14).

This page is the plain-language companion to the normative contracts. It does
not replace them: [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) is normative for module
boundaries, [`docs/CLAIM_SCHEMA.md`](CLAIM_SCHEMA.md) for the claim ledger, and
[`schemas/reference_claim_graph.schema.json`](../schemas/reference_claim_graph.schema.json)
with [`src/jev_classifier/reference/validate.py`](../src/jev_classifier/reference/validate.py)
(module **R**, issue [#37](https://github.com/Pukujan/jev-classifier/issues/37))
for the reference-record format. If this page and those disagree, **they win and
this page has a bug** — file it.

---

## 1. The situation you are in

You have a research paper in front of you, or a claim extracted from one, or a
number the project computed. You want to know one thing: **how much should I
believe this, and what would it take to check it?**

That question is hard here for a specific reason. The project reads *untrusted*
source material (retrieved web text, model answers) and turns it into structured
claims that a downstream reader will treat as findings. Between those two ends
there are several different kinds of statement, and they do not deserve the same
trust. Flattening them — calling everything "a result" — is the failure mode
this page exists to prevent.

## 2. The concrete friction

Three things go wrong when a pipeline like this is read carelessly:

- **A model's answer is read as a fact.** A language model was asked a question;
  its answer is a *judgment by that model*, not evidence about the world. If the
  reader cannot tell which claims came from a model and which came from the
  source text, the model's guess inherits the source's authority. It should not.
- **Confidence is read as correctness.** The system preserves the model's own
  probability for an answer. A high probability means the model was sure, not
  that it was right. Reported without that caveat, a probability looks like an
  accuracy figure. It is not.
- **Time is read as one thing.** A claim can be true *as of* some date (valid
  time) and also have been *recorded* on some date (transaction time). These
  differ. "X is the best method" recorded in 2026 about a 2019 result means
  something different from the same sentence recorded in 2019.

## 3. What the project does about it

### 3.1 Every statement carries its kind

The project separates statements by how they were produced. Read a claim by its
label first:

| Kind | Where it comes from | What it is worth |
|---|---|---|
| **Source fact** | Text captured from a source document, with a byte span into that document | As good as the source, and no better. The span is how you check it. |
| **JEV judgment** | A TypeSafe JEV decision (`choice` / `score` / `noul`) via the OpenRouter Decisions API | A *model's* classification. Deterministic for a pinned model, but still a judgment, not a fact. |
| **Inference** | A conclusion the pipeline derives from facts and judgments | Only as strong as its inputs and its stated rule. |
| **Unknown** | Anything the system declined to decide | **Nothing.** An explicit gap, recorded so it is not filled by guesswork. |
| **Proposal** | A suggested change, not a result | Nothing until accepted. Labelled *(proposal)* wherever it appears. |

*(shipped)* The vocabulary and its enforcement live in
[`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §3 (role table) and §4 (cross-cutting
invariants); the reference-record form is in module R.

### 3.2 Only one model may produce a judgment, and it never writes prose

*(shipped)* Deterministic outputs that enter the claim graph — labels, scores,
yes/no judgments — come **only** from TypeSafe JEV, pinned
`typesafe/jev-1.13`. Any other model producing such output is prohibited; other
models may supply *untrusted source material* only. The corollary matters for
reading anything here: **JEV never writes prose.** Paper text is templates plus
deterministic assembly, so a fluent sentence in a draft is not evidence that a
model "understood" the paper. See [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §0.

### 3.3 Judgments stay separate from facts, and confidence stays separate from correctness

*(shipped)* Native probability maps are preserved and reported next to a
judgment; they are never promoted to truth. A claim record therefore carries
both what was decided and how sure the decider was — and a reader must keep
those two apart. [`docs/CLAIM_SCHEMA.md`](CLAIM_SCHEMA.md) defines the record;
`confidence_is_not_correctness` is a cross-cutting invariant in
[`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §4.

### 3.4 Valid time and record time are different fields

*(shipped)* A claim record carries `valid_from` / `valid_to` (when the claim is
said to hold) as distinct from `recorded_at` (when the system recorded it).
*(partial)* The validator does **not** yet parse these timestamps or check their
order, and it does not check that an evidence reference resolves — those are
recorded gaps in [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §M5, not features. An
absent date stays `null`; it is never inferred to "now".

### 3.5 Nothing is fabricated on failure

*(shipped)* Provider, parse, schema, or option-set failure produces an error or
a review state — never a guessed label, citation, or timestamp. This is the
"fail closed" rule ([`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §4.1). When you see
a gap in the data, it is deliberate.

### 3.6 Evidence sits next to the claim it supports

*(shipped for the reference format)* Module R requires every reference claim to
carry an evidence span — a quote plus byte offsets into a named, versioned
source. A claim that cannot point at its evidence cannot be represented. The
reference format is normative:
[`schemas/reference_claim_graph.schema.json`](../schemas/reference_claim_graph.schema.json).

## 4. What this does **not** establish

Stated plainly, because a reader deserves the boundary:

- **A passing structural check is not truth.** Module R validates *shape and
  cross-record consistency*: that a span exists, that endpoints resolve, that
  paired cases share a family. It does not check that a claim is *true*, and it
  does not check that a quote was read correctly.
- **A metric is not accuracy on the world.** The claim-level metric
  ([`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §E, issue
  [#66](https://github.com/Pukujan/jev-classifier/issues/66)) scores predictions
  against a *human-reviewed reference graph*. It measures agreement with that
  reference and nothing else. Today it is **0 by construction** until a
  localization step exists, because the pipeline classifies a whole fragment
  while the reference span is a sentence — and a wider span fails containment.
  That number is a statement about the pipeline's granularity, not about the
  world.
- **Synthetic fixtures are not results.** The checked-in claim graphs are
  synthetic. Nothing measured on them is an accuracy claim about any real paper.
- **SHACL is not implemented.** Ontology checks parse Turtle and check a closed
  status vocabulary; they do not run SHACL. Recorded as a known gap in
  [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §M6.
- **A human review is not a comprehension proof.** Where a checklist records a
  reviewer, it records *that a person looked and what they concluded* — not that
  readers will understand the result.

## 5. How to verify a claim yourself

A short, ordered path from "I read a sentence" to "I checked it":

1. **Find the label.** Is it a source fact, a JEV judgment, an inference, an
   unknown, or a proposal? Section 3.1 says what each is worth.
2. **Follow the evidence.** For a reference claim, open the named source at the
   recorded byte span and read the quote. If there is no span, you cannot check
   it — treat it as unverified.
3. **Check the model and the date.** Which model produced any judgment, and on
   what date was it recorded? Separate `recorded_at` from `valid_from`/`valid_to`.
4. **Read the limits.** Section 4, and the "what this does not establish" lines
   beside any number you are relying on.
5. **Re-run the offline checks** (no model, no network needed):
   ```bash
   python -m pytest tests/ -q
   python scripts/validate_docs.py
   ```

## 6. Where to go next

- Normative contracts: [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md),
  [`docs/CLAIM_SCHEMA.md`](CLAIM_SCHEMA.md).
- Reference-record format (module R): [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §R.
- The managed-docs entry point and folder tree: [`docs/INDEX.md`](INDEX.md).
- Reader review checklist for pages like this one:
  [`docs/HUMAN_REVIEW_CHECKLIST.md`](HUMAN_REVIEW_CHECKLIST.md).

*(One next action.)* If you can name a statement in this project whose kind you
could not determine from the label, that is a real gap — open an issue on
[#63](https://github.com/Pukujan/jev-classifier/issues/63) naming the statement
and where you saw it.
