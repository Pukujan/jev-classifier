# SYSTEM SPEC — jev-classifier module contracts

```yaml
spec_version: 0.3.0
status: draft
updated: 2026-09-26
owner: authoritative agent (claude-code-main)
parent_issue: 21
leaf_issue: 30
```

This spec is **normative for module boundaries**. It documents the contracts that
already exist so every module is independently replaceable and testable, and so
a fresh agent session can see which roles are JEV and which are deterministic
Python without reading the source.

Authority order: `docs/AUTHORITY.md` (who decides) → this spec (what the
contracts are) → `AGENTS.md` (operating rules) → module source (implementation).
If this spec and the code disagree, **the code is reality and this spec has a
bug** — file it, do not silently "fix" the code to match prose.

---

## 0. The one rule that overrides everything

**Deterministic classifier outputs (labels, scores, and semantic judgments that
enter the paper's claim graph) come exclusively from TypeSafe JEV** via
`POST https://openrouter.ai/api/alpha/decisions`, pinned `typesafe/jev-1.13`.

Any other model producing such output is **prohibited**. Non-JEV models
(including Grok) may produce *untrusted source material* only — never a label,
score, gold answer, or canonical claim.

Corollary: **JEV never writes prose.** Paper text is templates + deterministic
assembly. JEV does not generate narrative, summaries, or citations.

---

## 1. Pipeline

```
[1] Source capture ──▶ [2] Normalization ──▶ [3] JEV decisions ──▶ [4] Claim record
    (untrusted)          (deterministic)       (JEV ONLY)            (deterministic)
                                                                        │
                          [7] Paper assembly ◀── [6] Ontology/SHACL ◀── [5] Provenance
                             (deterministic)        (deterministic)       /bitemporal
                                                                          (deterministic)

Cross-cutting: [C] Coordination (SQLite aid) · [O] Ops ledger (projection) · [B] Bias signals
```

Each module is independently replaceable **provided its contract holds**. A
replacement may change internals freely; it may not change the contract without
bumping `spec_version` and a ruling from the authoritative agent.

---

## 2. Module contracts

### M1 — Source capture

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/sources/grok.py`, `scripts/grok_research.py` (issue #15, merged via PR #27) |
| Role | **non-JEV** (untrusted input producer) |
| Input | bounded research query string; client configuration is supplied at construction; result caps are module constants |
| Output | versioned **SourceArtifact**: exact non-secret request/prompt, requested model, provider-surfaced model, provider/request IDs when available, raw response, citation annotations, usage, retrieval time, deterministic content hash |
| Invariants | hash stable across repeated canonical serialization; retrieval timestamp is separate metadata, never folded into the hash; no credential ever persisted; malformed/missing identifiers → error or review state, **never invented citations** |
| Fail-closed | yes |
| Tests | `tests/test_grok_research.py` |

**Boundary:** a SourceArtifact may *suggest* research leads. It may not emit a
canonical label, score, or claim, and may not call M2/M3 to promote itself.

### M2 — Answer normalization

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/normalize.py` |
| Role | **deterministic** |
| Input | one Decisions answer object, or a response body plus question id and legal options / noul threshold |
| Output | validated typed answer preserving native probability map + confidence |
| API | `normalize_choice_answer(answer, *, legal_options, question_id)` · `extract_choice_from_response(...)` · `normalize_score_answer(answer, *, legal_scores, question_id)` · `extract_score_from_response(...)` · `normalize_noul_answer(...)` · `extract_noul_from_response(...)` · `NormalizeError(kind="parse_error")` |
| Invariants | when answer `type` is present it must match the expected primitive; omission of `type` is accepted; `choice` must be a non-empty string **in** `legal_options`; probability keys must not exceed the legal set; `legal_options` must be non-empty; `score` must be a level **in** the ordered rubric legend, and a provider-surfaced `legend` that disagrees with the requested rubric fails closed |
| Fail-closed | yes — missing required answer values, a supplied wrong `type`, wrong-typed values, out-of-set choices/scores/probability keys, a mismatched or malformed surfaced `legend`, or malformed answers → `NormalizeError`; an omitted optional `type` is accepted |
| Tests | `tests/test_normalize.py`, `tests/test_normalize_noul.py`, `tests/test_normalize_score.py` |

**Closed (issue #32).** The `score` primitive is implemented:
`normalize_score_answer` / `extract_score_from_response` validate the chosen
level against an explicit ordered rubric (`legal_scores`), preserve the native
probability map, legend, and confidence, and never fabricate a level. A
provider-surfaced `legend` is preserved when it matches the requested rubric and
fails closed when it does not, so a rubric disagreement routes to a parse error
rather than a guessed score. `QuestionType` is `Literal["choice","score","noul"]`.

### M3 — JEV semantic decisions

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/decisions.py` |
| Role | **JEV ONLY** — the sole permitted source of semantic judgment |
| Input | `state` (compact structured evidence) + `questions` (non-empty mapping) |
| Output | raw parsed JSON body (M2 normalizes; this module does **not**) |
| API | `DecisionsClient(api_key=, base_url=, model=, timeout=)`, `.decide(state=, questions=, model=)`; `DecisionsError(status_code=)` |
| Invariants | defaults to the pinned OpenRouter Decisions URL and `typesafe/jev-1.13`; recognized Chat Completions and OpenCode URLs are skipped; `questions` must be non-empty; provider body is returned raw and is not normalized here; **no `stream=true`, no Chat Completions** |
| Fail-closed | yes — HTTP ≥400, non-JSON body, non-object root, transport error → `DecisionsError` |
| Tests | `tests/test_decisions_client.py` (mocked/offline) |
| Smoke | `scripts/smoke_jev.py` (live, opt-in) |

**Configuration gaps:** an explicit URL is accepted when its path ends in
`/api/alpha/decisions` or `/alpha/decisions`; the client does not allowlist the
host. The OpenRouter tilde alias `~typesafe/jev-latest` currently falls back to
the pinned model; a non-tilde `typesafe/jev-*` identifier is accepted only when
explicitly configured. These are implementation observations, not recommended
production overrides. Use the pinned default unless a separately reviewed
canary is intended. The claim builder records the model string surfaced in the
response but does not compare it with the requested model before storing it.
The JEV-only restriction is the project policy; these runtime checks are still
incomplete.

**Question-construction rules (AGENTS.md):** evidence in `state`; judgment in
`instructions`; every option described in `criteria`; questions atomic (combine
in code); include `other`/`none` when the set is not exhaustive; `criteria` keys
must match `closed_label_set` exactly.

**Consequence of atomicity:** anything requiring a *delta between two states*
(e.g. sycophancy: original vs challenged) **cannot** be one question — it needs
two calls with the difference computed locally in Python. Metacognitive questions
("are you order-biased?") are invalid; permutation invariance is a harness
concern (see #32).

### M4 — Claim record build + validate

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/classify.py` |
| Role | **deterministic** |
| Input | `classify_fragment` accepts one fragment fixture plus an optional Decisions client; `validate_claim_record` accepts a raw claim dict; `build_claim_record` accepts claim fields |
| Output | `ClaimRecord` JSON |
| API | `build_claim_record(...)`, `validate_claim_record(claim, *, legal_labels, migrate=True)`, `classify_fragment(fragment, *, client=, evidence_path=)`, `migrate_legacy_claim(raw)`, `load_fragment_fixture(path)`, `REQUIRED_CLAIM_KEYS` |
| Required keys | `label`, `epistemic_status`, `recorded_at`, `evidence`, `model` |
| Optional keys | `valid_from`, `valid_to`, `supersedes`, `probabilities`, `confidence`, `response_id`, `independence_class`, `id` |
| Invariants | `label ∈ legal_labels`; `epistemic_status` non-empty string; `recorded_at` is non-empty string; `evidence` is an object containing `fragment_id` and/or `path` (referential existence is not checked); `model` non-empty string; `supersedes` is null or a non-empty string (empty string rejected); `valid_from`/`valid_to` are null or non-empty strings; `independence_class` null or non-empty string. Timestamp strings are **not parsed** as ISO-8601 and valid-time ordering is not checked. |
| Migration | legacy camelCase → canonical snake_case; **canonical key wins** over legacy when both present |
| Fail-closed | yes — missing key, out-of-set label, bad type → `NormalizeError` |
| Tests | `tests/test_ontology_and_classify.py` (required keys and out-of-set labels); `tests/test_claim_schema.py` (key set, migration, supersedes shapes). Timestamp syntax and valid-time order have no dedicated test. |

**Confidence ≠ correctness.** The native probability map is preserved verbatim
and never collapsed into a truth bit or used to fabricate a label.

### M5 — Provenance and bitemporal fields

| | |
|---|---|
| Version | `0.1.0` |
| Code | deterministic Python across `classify.py` (time fields), `ontology/*.ttl` (vocabulary), `paper/assemble.py` (lineage rendering) |
| Role | **deterministic** |
| Contract | **valid time ≠ transaction time**, always two distinct axes |
| Valid time | `valid_from` / `valid_to` — when the claim holds *in the world* |
| Transaction time | `recorded_at` — when *this record* was written |
| Lineage | `supersedes` is stored as a claim identifier; the validator does not check that the predecessor exists |
| Invariants | the schema permits separate valid-time fields and recorded time; evidence may contain a fragment id or path, but source existence/linkage is not validated here |
| Tests | `tests/test_claim_schema.py` (supersedes shapes); `tests/test_multisource_e2e.py` (synthetic multi-claim assembly). Neither test validates timestamp syntax/order or evidence-reference existence. |

This module currently **records fields**; it does not validate ISO-8601 syntax,
valid-time order, evidence-reference existence, or PROV-O Activity/Agent linkage.
The assembler renders supplied claim data, but preservation of disagreements or
limitations is not guaranteed by a dedicated validator.
The claim builder also records a response model string without checking it
against the model requested from the Decisions client; the JEV-only rule is
therefore not enforced end-to-end by this path yet.

**Design ruling (recorded so it is not relitigated):** validity stays **flat**
(`validFrom`/`validTo` datatype properties). Rationale: no OWL reasoner is
installed (`owlrl`, `pyshacl`, `owlready2`, `pyoxigraph` all absent; the
`ontology` extra declares rdflib only), so reified intervals would add triples
and validation surface for expressivity nothing in the pipeline can consume —
and supersession already models multi-period history structurally. Revisit only
if overlapping validity on a single IRI becomes a requirement.

**No standard ontology supplies valid time.** PROV-O contains no valid-time,
transaction-time, or bitemporal construct, and OWL-Time explicitly declines
("Valid time: not resolved explicitly"). `jcc:validFrom`/`validTo`/`recordedAt`
are a deliberate **domain extension** — do not replace them with an import.

**Closed (issue #31).** The JEV call that *generated* a claim was previously
unmodeled — no `prov:Activity`, no `prov:SoftwareAgent`, so
`prov:wasGeneratedBy` / `wasAssociatedWith` / `used` had no endpoints, and
`jcc:modelId` sat on `jcc:Claim`. The vocabulary now declares
`jcc:ClassificationActivity` (⊑ `prov:Activity`) and `jcc:ClassifierAgent`
(⊑ `prov:SoftwareAgent`), wires those three edges, and moves the model id onto
the activity/agent (`jcc:modelId` = requested, on the agent;
`jcc:surfacedModelId` = provider-surfaced, on the activity). The `prov:` terms
are declared locally with `rdfs:seeAlso`, so the offline parse still fetches
nothing.

### M6 — Ontology and SHACL checks

| | |
|---|---|
| Version | `0.1.0` |
| Code | `ontology/jev_classifier_claims.ttl` |
| Role | **deterministic** |
| Contract | OWL2 Turtle vocabulary for Claim, SourceFragment, EpistemicStatus, bitemporal + lineage properties, and the ClassificationActivity/ClassifierAgent that produced each claim |
| Invariants | parses offline via rdflib with **no network fetch** (therefore `rdfs:seeAlso`, never `owl:imports` of a remote document); classes are `prov:`-aligned; epistemic status is a closed vocabulary and **not a truth bit** |
| Current state | vocabulary defines `jcc:Claim`, `jcc:SourceFragment`, `jcc:ClassificationActivity`, `jcc:ClassifierAgent`, and epistemic status terms; current tests check Turtle parsing and the asserted activity/agent edges, not a full OWL2 reasoner entailment |
| Tests | `tests/test_ontology_and_classify.py::test_rdflib_parses_claims_ttl`, CI ontology-parse step |

SHACL constraints are **not yet implemented** (no `pyshacl` dependency). Until
they are, M6 validation means "parses + asserted triple shape in tests". Adding
SHACL requires a new dependency decision and a leaf issue — do not import it
silently.

### M7 — Deterministic paper assembly

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/paper/assemble.py` |
| Role | **deterministic** (templates only; **no LLM**) |
| Input | sequence of claim-like mappings; callers are responsible for full ClaimRecord validation |
| Output | markdown paper draft |
| Required sections | `Title`, `Abstract`, `Claims`, `Provenance`, `Lineage`, `Citations` |
| API | `assemble_paper(...)`, `validate_paper_markdown(...)`, `REQUIRED_SECTIONS`, `AssembleError` |
| Invariants | each rendered claim includes its supplied evidence id(s); output is deterministic for fixed inputs and timestamp. The assembler checks required-key presence, non-empty label, evidence mapping, and at least one evidence id; it does not call `validate_claim_record` or enforce a legal label/time/model type. |
| Fail-closed | yes — empty claims or a claim missing an evidence id → `AssembleError`; a missing required section is detected by `validate_paper_markdown` |
| Tests | `tests/test_paper_assemble.py` (section/evidence-id rendering and fixed-time determinism); `tests/test_multisource_e2e.py` (synthetic multi-claim flow) |

The output is a **draft skeleton**, not a research paper or evidence synthesis.
It renders supplied records; it does not independently establish that citations
support claims or preserve omitted disagreements and limitations. Its
`Citations` section is an evidence-id-to-claim index, not a bibliography or a
set of source URLs.

### C — Coordination

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/coord/store.py`; protocol `docs/AGENT_COORD.md` |
| Role | **deterministic**, execution aid — **never authority** |
| API | `CoordStore(path=":memory:")`, `put_checkpoint`, `get_checkpoint`, `claim_ownership`, `release_ownership`, `get_owner`, `log_send`, `list_sends`, `list_collisions`, `resolve_collision`; `CollisionError`; `CheckpointResult`; `OwnershipClaim` |
| Tables | `checkpoints` (idempotent by `checkpoint_key` PK) · `ownership` (resource_type/id → agent) · `send_log` (idempotency_key) · `collision_flags` |
| Invariants | same-agent reclaim is **not** a collision; different-agent claim → `CollisionError` + a flag row; duplicate checkpoint key is a no-op returning the original row |
| Tests | `tests/test_coord.py` |

**Verified limitation being fixed in #22:** this store is a *gitignored local
file* and all agents share one GitHub account, so `CollisionError` can never
fire **across devices**. #22 adds a cross-device reserved-branch mutex
(atomic GitHub create-ref) plus machine-readable `coord:claim` comments. That
mutex has already fired once in production — see §4.

### O — Ops ledger

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/ops/store.py`, `scripts/ops_sync.py`; committed projection `ops/ledger/`; docs `docs/OPS_LEDGER.md` |
| Role | **deterministic** projection — never authority |
| Contract | `SCHEMA_VERSION = 1`; default DB `.ops/ops.db`; `ops/ledger/` holds `ISSUE_LOG.md`, `DISCREPANCIES.md`, `README.md`, `issues/` |
| API | `OpsStore`, `begin_sync_run`, `finish_sync_run`, `get_sync_run`, `list_sync_runs`, `upsert_issue_snapshot`, `get_issue_snapshot`, `list_issue_snapshots`, `replace_all_snapshots`, `clear_discrepancies`; `IssueSnapshot`, `DiscrepancyFlag`, `SyncRun` |
| Invariants | sync is **idempotent** for a given fixture; discrepancy detectors are deterministic and fail-closed (unknown → flagged, never guessed); **no secrets** in ledger output |
| Tests | `tests/test_ops.py` (incl. `test_no_secrets_in_ledger_output`) |

`ops/ledger/` is the **only committed board**. `scripts/coord_board.py` (#22,
merged via PR #36; the earlier name `coord_ledger.py` shipped nowhere) is a
point-query gate importing the same records — it must not become a second board.

### B — Bias signals

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/bias/packs.py`, `aggregate.py`, `sycophancy.py`; `scripts/smoke_bias.py` |
| Role | **JEV** for the closed questions; **deterministic** for aggregation |
| Contract | `BiasPack(pack_id, version, questions)`, `BiasQuestion`, `validate_pack`, `legal_options_for`, `aggregate_bias_answers`, `get_pack`; shipped pack `bias_pack_v1` |
| Invariants | every question is closed (`choice`/`score`/`noul`) with a legal option set; `score` questions carry an ordered `legend`; `flags_on` values must be legal for their question; pack_id and version required; unknown pack → `NormalizeError`; live smoke **skips without a key** |
| Tests | `tests/test_bias_packs.py`, `tests/test_bias_sycophancy.py`, `tests/test_bias_position.py`, `tests/test_smoke_bias.py` |

**Bias signals are measured signals** validated against explicit fixtures. They
are never presented as proof of bias, and never as proof of correctness.

**Closed (issue #32).** The bias pack now supports `score` questions with an
explicit ordered rubric; raised flags come from each question's declared
`flags_on` values (validated to be legal), so the dead hardcoded entries `"high"`
/ `"yes_biased"` are gone. Noul signals record the `yes_threshold` that produced
their label. The `overconfidence` question now asks about the classifier's own
stated confidence against its evidence (calibration), not a property of the
source text. Sycophancy is a two-call pattern with ΔP computed locally in
`sycophancy.py` (raw state, then appended pushback; questions inside one request
stay atomic). Position bias is a pure-Python harness in `tests/test_bias_position.py`,
never a pack question.

### R — Reference claim schema

| | |
|---|---|
| Version | `0.1.0` |
| Code | `schemas/reference_claim_graph.schema.json`, `schemas/context_stimulus_manifest.schema.json`, `src/jev_classifier/reference/validate.py` |
| Role | **deterministic** |
| Input | a reference claim-graph document, or a privacy-safe context-stimulus manifest |
| Output | validated records, or `ReferenceSchemaError(kind="schema_error")` |
| Contract | JSON Schema (draft 2020-12) for record shape; `validate_reference_graph` / `validate_stimulus_manifest` for the cross-record invariants |
| Invariants | every claim resolves to an immutable paper + source version and carries a non-empty evidence span with `byte_end > byte_start`; relationship endpoints resolve to claims and are never self-referential; valid time (`valid_from`/`valid_to`) and transaction time (`recorded_at`) are separate fields; absent/uncertain dates stay `null` and are never inferred; review records accumulate and a superseding review never deletes the one it replaces; paired counterfactual cases share one condition family and source packet with distinct roles; public records carry no URL, no raw private content, and no low-entropy digest of it |
| Fail-closed | yes — any shape or cross-record violation raises `ReferenceSchemaError`; nothing is repaired, defaulted, or guessed |
| Tests | `tests/test_reference_schema.py` |

**Records only (issue #37).** This module defines and validates formats; it does
not select a corpus (#29), run a benchmark (#23), or assign gold labels.
Deterministic labels entering the classifier remain TypeSafe JEV-only; these
human-reviewed records are the evaluation reference, not classifier output.

**JSON Schema is normative here; SHACL is deferred.** The issue body names SHACL
constraints, but M6 already records that SHACL is unimplemented and that adding
`pyshacl` needs its own leaf issue. The cross-record invariants SHACL would carry
are implemented as explicit fail-closed Python checks instead, which gives the
same guarantee with no new runtime dependency. `jsonschema` is declared in the
`dev` extra so the schema documents are validated in CI.

**Privacy is structural.** The manifest schema has no field able to carry raw
private text and rejects unknown keys, so a producer cannot smuggle transcript
content into a case; private material is referenced only by an opaque
`audit:` pointer, and public fixtures are synthetic.

---

### E — Claim-level evaluation

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/eval/metric.py`, `scripts/eval_claims.py` |
| Role | **deterministic** |
| Input | a validated reference claim graph (module `R`) plus a sequence of predicted claims |
| Output | a score report: primary claim-level micro P/R/F1, per-paper P/R/F1, citation coverage, ontology status |
| Contract | metric version `claim_metric_v1`; matching rule `span_containment_v1` |
| Invariants | a predicted claim matches a reference claim only when paper id, source id, and epistemic status agree *and* the predicted span is contained in the reference span; matching is one-to-one with the smallest span winning and ties broken by claim id; a prediction with no usable span, an inverted span, or a non-integer offset is a **miss**, never an exclusion; the graph is validated through module `R` and a malformed graph is rejected rather than partially scored; identical inputs produce identical output |
| Fail-closed | yes — an unscoreable prediction counts against the metric; a malformed graph raises `ReferenceSchemaError` |
| Tests | `tests/test_eval_metric.py` |

**The metric is pre-registered (issue #66).** The matching rule is the
deliverable, and it is frozen before any reference paper exists so the 0.80
target is measured by a definition nobody could have tuned. A result that does
not name `claim_metric_v1` is not a valid pre-registered result.

**Containment, not overlap.** Overlap would let one sprawling prediction take
credit for several reference claims at once, inflating recall without fidelity.
A span wider than the reference span is therefore a miss, not a partial match.

**Two honest gaps are reported as numbers, not hidden.** First, `classify.py`
emits `evidence: {fragment_id, path}` and does not produce byte spans, so every
such prediction is a miss under this rule; the report exposes the usable-span
count so the gap is visible rather than papered over with a source-level
fallback. Worse, and measured rather than assumed: even a prediction that covers
a whole fragment still fails containment, because the fragment span is *wider*
than a sentence-level reference span. Emitting a span is not enough — the span
must be at least as tight as the human's. Until the pipeline localizes evidence,
the primary metric is 0 by construction, and `predictions_with_usable_span`
distinguishes a run that failed for lack of a span from one that failed for lack
of precision. Second, module `R` uses lowercase epistemic values while
`classify.py` emits capitalized ones, so the status comparison normalizes case
and the report records that it did. Reconciling either vocabulary is a separate
leaf.

**No substitutes.** Lexical similarity as a proxy for claim fidelity and any
LLM-as-judge are prohibited by the parent program ruling (5849173786) and are
not implemented; a test asserts neither is imported. The harness makes no
network call and produces no label — it scores already-structured claims.

---

## 3. Role table (JEV vs deterministic)

| Module | JEV permitted | Deterministic Python |
|---|---|---|
| M1 Source capture | ✗ (untrusted input only) | ✓ hash, ids, timestamps, validation |
| M2 Answer normalization | ✗ | ✓ parsing and fail-closed checks |
| M3 Decisions | **✓ sole semantic judge** | ✓ state reduction, option sets, retries |
| M4 Claim record | ✗ | ✓ schema, validation, migration |
| M5 Provenance/bitemporal fields | ✗ | ✓ field storage; referential and temporal validation are gaps |
| M6 Ontology/SHACL | ✗ | ✓ Turtle parse only; SHACL is not implemented |
| M7 Paper assembly | ✗ | ✓ template rendering from supplied records |
| C Coordination | ✗ | ✓ claims, checkpoints, collisions |
| O Ops ledger | ✗ | ✓ snapshots, discrepancy detection |
| B Bias signals | **✓ closed questions only** | ✓ aggregation, thresholds, flags |
| R Reference claim schema | ✗ | ✓ JSON Schema + cross-record validation |
| E Claim-level evaluation | ✗ | ✓ matching, P/R/F1, coverage; no model call |

No module assigns a non-JEV model a deterministic-output role. If a future leaf
proposes one, it is rejected by this table — escalate to the authoritative agent.

---

## 4. Cross-cutting invariants

1. **Fail closed everywhere.** Provider, parse, schema, or option-set failure →
   an error or review state. Never a fabricated label, citation, or timestamp.
2. **Confidence ≠ correctness.** Native probability maps are preserved and
   reported; they are never promoted to truth.
3. **GitHub is authority.** Local SQLite (`.coord/`, `.ops/`) is a rebuildable
   projection. On disagreement, GitHub wins; delete and rebuild local DBs freely.
4. **Secrets never persist.** No API key or `.env` value in code, logs, issues,
   artifacts, ledgers, or commits. CI enforces a secret scan.
5. **Storage stays lean.** No large binaries or committed datasets; external
   data goes to gitignored `data/` / `.research_cache/`, referenced by name and
   revision. CI caps tracked files and fixtures at 2 MB each.
6. **The project does not stop.** A blocked leaf does not block others; the
   slimmest plausible fix is applied, recorded, and work continues.

### The mutex has already fired once (evidence, not theory)

On 2026-09-26 the arbiter attempted to reserve `feat/coordination-layer-22` and
the push was **rejected** because the coordination-flagger agent had reserved it
17 minutes earlier (`67eaa8b`). The correct response per protocol: stop, do not
force-push, comment, and let the prior claim stand. That is invariant 3 and the
`docs/AUTHORITY.md` claim protocol behaving as designed across devices.

---

## 5. Verification

```bash
python -m pip install -e ".[dev]"
python -m pytest tests/ -q          # current count is reported by pytest
python scripts/smoke_jev.py         # live, opt-in; requires OPENROUTER_API_KEY
```

CI (`.github/workflows/ci.yml`): offline pytest on 3.11 and
3.12, OWL2 rdflib parse, and a hygiene job (secret scan, 2 MB tracked-file cap,
2 MB fixture cap). GitHub branch protection was recorded as strict with
force-push and deletion blocked in the remote settings snapshot dated
2026-09-26; local tests do not verify live GitHub settings.

Contract index: [`docs/spec/modules.json`](spec/modules.json) — machine-readable
projection of §2 and §3. `tests/test_system_spec.py` asserts the prose modules
and the index agree on names and versions, so this document cannot drift from
the code silently.

---

## 6. Change control

- Bump `spec_version` on any contract change; note the leaf issue.
- Contract changes that weaken a fail-closed invariant, the JEV-only rule, or a
  storage/secret rule require an explicit ruling from the authoritative agent.
- Product agents propose spec changes via the proposal layer on the owning leaf;
  they do not edit this file unilaterally while a claim is active elsewhere.
