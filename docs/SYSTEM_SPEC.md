# SYSTEM SPEC — jev-classifier module contracts

```yaml
spec_version: 0.2.0
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
| API | `normalize_choice_answer(answer, *, legal_options, question_id)` · `extract_choice_from_response(...)` · `normalize_noul_answer(...)` · `extract_noul_from_response(...)` · `NormalizeError(kind="parse_error")` |
| Invariants | when answer `type` is present it must match the expected primitive; omission of `type` is accepted; `choice` must be a non-empty string **in** `legal_options`; probability keys must not exceed the legal set; `legal_options` must be non-empty |
| Fail-closed | yes — out-of-set, missing, wrong-typed, or malformed → `NormalizeError`, never a guessed label |
| Tests | `tests/test_normalize.py`, `tests/test_normalize_noul.py` |

**Known gap (issue #32):** the declared `score` primitive is **not implemented**
(`QuestionType = Literal["choice","noul"]`; no `normalize_score_answer`). Either
implement it or strike it from AGENTS.md/PROJECT.md. Docs must not claim a
capability the code lacks.

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

**Known gap (issue #31):** the JEV call that *generated* a claim is unmodeled —
no `prov:Activity`, no `prov:SoftwareAgent`, so `prov:wasGeneratedBy` /
`wasAssociatedWith` / `used` have no endpoints, and `jcc:modelId` sits on
`jcc:Claim` rather than on the activity/agent.

### M6 — Ontology and SHACL checks

| | |
|---|---|
| Version | `0.1.0` |
| Code | `ontology/jev_classifier_claims.ttl` |
| Role | **deterministic** |
| Contract | OWL2 Turtle vocabulary for Claim, SourceFragment, EpistemicStatus, bitemporal + lineage properties |
| Invariants | parses offline via rdflib with **no network fetch** (therefore `rdfs:seeAlso`, never `owl:imports` of a remote document); classes are `prov:`-aligned; epistemic status is a closed vocabulary and **not a truth bit** |
| Current state | vocabulary defines `jcc:Claim`, `jcc:SourceFragment`, and epistemic status terms; current tests check Turtle parsing, not a full OWL2 reasoner entailment |
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

`ops/ledger/` is the **only committed board**. `coord_ledger.py` (#22) is a
point-query gate importing the same records — it must not become a second board.

### B — Bias signals

| | |
|---|---|
| Version | `0.1.0` |
| Code | `src/jev_classifier/bias/packs.py`, `aggregate.py`; `scripts/smoke_bias.py` |
| Role | **JEV** for the closed questions; **deterministic** for aggregation |
| Contract | `BiasPack(pack_id, version, questions)`, `BiasQuestion`, `validate_pack`, `legal_options_for`, `aggregate_bias_answers`, `get_pack`; shipped pack `bias_pack_v1` |
| Invariants | every question is closed (choice/noul) with a legal option set; pack_id and version required; unknown pack → `NormalizeError`; live smoke **skips without a key** |
| Tests | `tests/test_bias_packs.py`, `tests/test_smoke_bias.py` |

**Bias signals are measured signals** validated against explicit fixtures. They
are never presented as proof of bias, and never as proof of correctness.

**Issue #32 reports** defects in the bias pack and score primitive. The current
aggregate code passes `yes_threshold` to the noul normalizer, so that reported
threshold defect requires correction at the issue record. Existing signals
measure source text; they are not validated as a detector of classifier or
agent bias.

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
