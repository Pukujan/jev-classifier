# HOLDOUT PROTOCOL — how the hidden paper split is frozen and kept out of development

**Audience:** contributor, reviewer, and agent. **Status:** protocol accepted by
the authoritative ruling on
[#81](https://github.com/Pukujan/jev-classifier/issues/81); the enforcement it
names is not implemented yet. **Owner:** issue
[#81](https://github.com/Pukujan/jev-classifier/issues/81), leaf of
[#21](https://github.com/Pukujan/jev-classifier/issues/21).

Parent [#21](https://github.com/Pukujan/jev-classifier/issues/21) requires a
paper-level hidden holdout: the claim-fidelity target is measured on papers the
development path never sees, frozen before any tuning. This page states how that
split is chosen, who may see what, and how the freeze is evidenced. It is a
protocol, not a mechanism — the modules that enforce it are named in §10 and
marked *(planned)*, because none of them exists yet.

Where this page and the code disagree, **the code is reality and this page has a
bug** — file it on
[#81](https://github.com/Pukujan/jev-classifier/issues/81). The ten selected
papers, their versions, and their rights notes live in
[`datasets/reference_papers.json`](../datasets/reference_papers.json) and
[`docs/DATASET_CARD.md`](DATASET_CARD.md); this page adds only the custody rules.

---

## 1. What is hidden, and what is not

State this plainly, because a reader could otherwise assume more secrecy than
exists:

- **The paper identities are public.** The ten selected papers, their versions,
  and their bibliographic records are already published in
  `datasets/reference_papers.json` and the merged dataset card
  ([`docs/DATASET_CARD.md`](DATASET_CARD.md)). Anyone can read that list today.
- **What is hidden is the assignment and the annotations.** Which papers are
  held out, and the human-reviewed labels for those papers, are withheld from
  the development path. "Hidden holdout" here means withheld assignment and
  withheld labels, not unknown papers.

The feasible boundary for this pool is therefore a **custody** boundary, not a
secrecy boundary. No part of this protocol claims that a reader cannot learn
which public papers exist.

*(Inferred.)* Hiding the assignment and the labels is sufficient here because the
ground truth is **human adjudication** — evidence spans, bitemporal links, and
epistemic status — which is not derivable from source text that anyone can
already read. Identity secrecy would only be load-bearing if the reference
graphs themselves were published, or if the task were open-ended retrieval with
no supplied sources. Neither holds for this benchmark.

## 2. Roles and the access matrix

Four roles, named so a rule can refer to them:

- **Custodian** — holds the split map and the freeze salt outside the
  repository; freezes the assignment and publishes only the commitment and
  counts. The custodian is not an annotator, developer, or evaluator.
- **Annotator** — produces human-reviewed reference labels for the papers they
  are assigned. An annotator may see the papers they label; they are not told
  which side of the split those papers are on.
- **Developer** — the ordinary development identity: builds and tunes the
  pipeline against development papers only. Holdout access is denied to this
  identity by an enforced boundary (§2.3), not by a flag.
- **Evaluator** — runs the authorized frozen evaluation on the custodian path
  after the design freeze, and is the only role that publishes holdout results,
  in the authorized report (§5).

### 2.1 What each role may read

| Artifact | Custodian | Annotator | Developer | Evaluator |
|---|---|---|---|---|
| Split map (which paper is which side) | yes — holds it | **no** | **no** | yes, on the custody path |
| Source records (paper metadata, public full-text route) | yes | yes — assigned papers | yes — development papers | yes |
| Labels (human-reviewed annotations) | yes — stores them | yes — assigned papers | yes — development labels only | yes |
| Predictions | no | no | yes — development only | yes — the submitted set |
| Per-paper scores | yes — the report copy | no | yes — development only, aggregate in routine output | yes |

### 2.2 What each role may publish

| Artifact | Custodian | Annotator | Developer | Evaluator |
|---|---|---|---|---|
| Split map | counts only, plus the freeze commitment | nothing | nothing | nothing |
| Source records | nothing new (already public) | nothing | nothing | nothing |
| Labels | nothing | nothing | development labels inside the development workspace; never a paper-keyed holdout roster | holdout labels only inside the authorized report |
| Predictions | nothing | nothing | development predictions in iteration work | results, in the authorized report |
| Per-paper scores | nothing routine | nothing | development aggregates in routine output; never holdout | aggregate and per-paper, in the authorized report |

### 2.3 The boundary is enforced, not a flag

The development identity is denied holdout access by a repository and runner
boundary, not by a command-line switch:

- the split map and the holdout annotations live outside tracked files, on an
  evaluator-controlled path, so they cannot be opened from a checkout;
- ordinary development scoring rejects a holdout input **by default**, rather
  than accepting it behind a flag;
- the authorized path (§10) runs where the custodian material already exists, so
  passing an argument is not what grants access.

A flag a developer can pass is not access control. If the ordinary development
path can read a holdout artifact, that is a bug — file it on
[#81](https://github.com/Pukujan/jev-classifier/issues/81).

## 3. The split rule

1. **Whole paper only.** Every source record, claim, and score for a paper
   follows that paper's single assigned split. A paper's records are never
   divided across development and holdout. Its claims share a source, a
   vocabulary, and one annotation style, so a record-level split would leak the
   paper into the side it is supposed to be hidden from.
2. **At least 20% and at least two papers.** With ten selected papers, 20% is
   two, so the floor is two papers held out; a larger holdout is allowed. The
   floor is a minimum, not a target to tune down to.
3. **Frozen before annotation and before tuning.** The assignment is fixed
   before any human label is written and before any development iteration that
   could tune against holdout behavior. Freezing after either would make the
   holdout a record of what was already seen.

*(Planned)* A synthetic test asserts that the development and holdout paper-id
sets are disjoint and that every source and claim record for a paper follows
that paper's single assigned split.

## 4. Freeze evidence

The freeze is recorded as a commitment, not as a published list:

- the record carries three fields, `{scheme, salt, tag}`: `scheme` names the
  construction and its canonicalization, `salt` names the salt the custodian
  holds, and `tag` is the HMAC of the assignment under that salt;
- **the salt is held by the custodian outside the repository.** The published
  record does not carry the salt's value — publishing it would restore exactly
  the enumeration the salt exists to prevent;
- the commitment binds its inputs: it records the protocol version and the exact
  paper, source, and annotation-schema versions in force when the split was
  frozen, so the freeze can be re-checked without republishing membership;
- the record shows the freeze preceded annotation and tuning (its dates plus
  those input versions).

**Why a bare digest is rejected.** Ten papers with a minimum of two held out
give only 45 candidate splits. An unsalted SHA-256 over the assignment can be
recomputed for every candidate in milliseconds, so the digest discloses exactly
what it claims to protect. A salt held outside the repository removes the
attacker's ability to enumerate: the tag is checkable only by someone who
already holds the salt.

The custodian publishes the commitment and counts ("N of 10 held out"). The
commitment stays checkable later by recomputing the HMAC from the custodian-held
assignment and salt.

## 5. Output policy

Aggregate **and** per-paper results are both released. Parent
[#21](https://github.com/Pukujan/jev-classifier/issues/21) requires per-paper
results alongside the aggregate, and this protocol does not reduce that. What it
controls is *where* and *when* they appear:

- **Only** in the authorized frozen-evaluation report, after the design freeze.
  The evaluator produces it on the custody path; it carries the aggregate and
  the per-paper numbers.
- **Never** in routine development output: prompts, public fixtures, iteration
  logs, CI artifacts, telemetry, commit messages, or PR bodies. A per-paper
  holdout score is the signal a tuner would use, so it belongs in the one
  artifact published after tuning stops, not in the loop that tunes.

Routine development output is aggregate only; a paper-keyed development roster
is withheld for the reason in §6.

## 6. No complement leakage

The ten papers are public, and the holdout is the complement of the development
set inside that list. Publishing which papers are in development therefore
publishes the holdout, by subtraction, without ever naming it. So:

- do not publish a development roster — not in docs, PRs, commit messages, logs,
  telemetry, or fixtures;
- publish counts instead ("N of 10 held out"), or nothing;
- the same reasoning is why the freeze commitment is salted (§4) and why routine
  per-paper output is withheld (§5): a paper-keyed number, on either side,
  narrows the complement.

A holdout whose membership is recoverable by subtraction is not a holdout.

### 6.1 Development artifacts that need per-paper detail

Development iterations legitimately need per-paper detail to debug, which looks
like it collides with the rule above. It does not, if the detail is carried
under **anonymous local ids**: inside development artifacts a paper appears as
`dev_01`, `dev_02`, …, and the map from those ids to real paper ids lives only in
a custodian-held or gitignored local file. Real development paper ids then never
enter a tracked or logged artifact, so the complement stays unrecoverable while
the iteration record keeps the detail it needs.

Routine output stays aggregate (§5); the id map is never committed. This is the
one sanctioned way to keep per-paper detail in development work.

## 7. What the tests can and cannot show

*(Planned)* Synthetic tests verify repository and runner boundaries:

- the development and holdout paper-id sets are disjoint, and every source and
  claim record for a paper follows its single assigned split;
- the ordinary development runner rejects a holdout input rather than scoring
  it;
- the routine output path withholds holdout labels and per-paper holdout scores.

They cannot prove that an unknown external copy, a future human action, or a
later code change never reveals a public paper's labels. The boundary is a
control on this repository and its runners, not a proof about the world, and
this page does not imply otherwise.

Tests carry synthetic ids throughout. They must not embed the real assignment or
the real ids of the held-out papers — a fixture that did would become the leak
it exists to prevent.

## 8. Rights boundary

This protocol changes custody, not rights. It copies no full text and no PDF
into Git; the repository stores paper records and links, never paper content. It
does not restrict the exact evidence excerpts already permitted by
[#37](https://github.com/Pukujan/jev-classifier/issues/37) (the reference-graph
evidence-span contract, module R in [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §R)
and by [#29](https://github.com/Pukujan/jev-classifier/issues/29) (the
paper-specific rights review recorded in
[`docs/DATASET_CARD.md`](DATASET_CARD.md)). A holdout label is a custody
question; it is not a new rights question.

## 9. Host requirement

The MacBook Pro agent remains the required host for the eventual heavy
sequential frozen run, per the owner's execution decision on
[#21](https://github.com/Pukujan/jev-classifier/issues/21); record the host,
runtime, tool, and resource details on the issue when that run happens. Host
choice does not define access control. Custody is the repository and runner
boundary plus the access matrix in §2 — running on the required host is not by
itself authorization to read holdout material.

## 10. Enforcement (planned)

None of this exists yet; these are the names the boundary will use:

- `jev_classifier.holdout` — the module that owns the split map, the
  custodian-held path, and the freeze record (`{scheme, salt, tag}`). It fails
  closed: an unknown or ambiguous assignment is an error, not a default.
- `scripts/eval_claims.py --custody PATH` — the ordinary scoring path gains a
  custody argument; a holdout input under a custody path is **refused**, not
  scored.
- `scripts/eval_claims.py --custody PATH --evaluator` — the authorized evaluator
  path for the frozen run; the only path that may read holdout labels and emit
  per-paper holdout results.

Until these land, the boundary is a written rule, and the test limit in §7
applies.

## 11. What this page does not establish

- **Identity secrecy.** It does not make the ten papers unknown; they are public
  (§1).
- **An implemented boundary.** The enforcement in §10 is planned. Until it
  lands, nothing in the repository stops development code from opening a future
  annotated graph; the ruling accepts this document as the protocol while the
  boundary is built.
- **An absolute boundary.** Synthetic tests cover this repository and its
  runners, not an external copy or a later human action (§7).
- **A result.** No paper has been assigned, annotated, run, or scored under this
  protocol yet. No split, label, or score is published here.
- **A rights change.** See §8.

## 12. Where to go next

- The selected papers, versions, and rights notes:
  [`docs/DATASET_CARD.md`](DATASET_CARD.md) and
  [`datasets/reference_papers.json`](../datasets/reference_papers.json).
- The reference-graph evidence contract (module R):
  [`schemas/reference_claim_graph.schema.json`](../schemas/reference_claim_graph.schema.json)
  and [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §R.
- The pre-registered metric and offline scorer:
  [`docs/SYSTEM_SPEC.md`](SYSTEM_SPEC.md) §E and
  [`scripts/eval_claims.py`](../scripts/eval_claims.py).
- What the project is allowed to claim, in plain language:
  [`docs/EPISTEMIC_SYSTEM.md`](EPISTEMIC_SYSTEM.md).
- The managed-document inventory: [`docs/INDEX.md`](INDEX.md).

*(One next action.)* If you can read a holdout artifact — an assignment, a
holdout label, or a per-paper holdout score — from the ordinary development
path, that is a bug: file it on
[#81](https://github.com/Pukujan/jev-classifier/issues/81) with the path you
used.
