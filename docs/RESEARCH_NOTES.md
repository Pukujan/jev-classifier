# Research notes (bootstrap)

Snapshot for plan drafting. Sources are local eval-lab docs (read 2026-09-26 on Teresa-Pujan), PCM issue #144 / PCM-0050 research note, and lean external OWL2/provenance pointers. **Do not treat this file as normative SPEC.**

## Citations — eval-lab

| Source | Path (machine) | Binding takeaway |
|--------|----------------|------------------|
| JEV research & usage audit | `D:\claude\eval-lab\docs\JEV_RESEARCH_AND_USAGE_AUDIT.md` | JEV = typed decision service, not chat; pattern: compact state → narrow primitive → validate → code executes |
| Integration contract | `D:\claude\eval-lab\docs\JEV_EVAL_LAB_INTEGRATION_CONTRACT.md` | OpenRouter Decisions only; pinned vs rolling; response normalization; no streaming |
| TASK-0010 | `D:\claude\eval-lab\docs\TASK-0010-OPENROUTER-JEV.md` | Model IDs, 32K context note, price snapshot, credential name |
| Historical client (shape only) | `D:\claude\eval-lab\src\eval_lab\jev.py` | Wire shape `model`+`state`+`questions`; error classes; local aggregation — **defaults are OpenCode historical; do not copy URL/key/model defaults** |

## JEV API constraints that bind jev-classifier design

1. **Route:** `POST https://openrouter.ai/api/alpha/decisions` (alpha Decisions API), not Chat Completions, not OpenCode Zen.
2. **Models:** pin `typesafe/jev-1.13`; keep `~typesafe/jev-latest` as a separate canary arm only.
3. **Request:** `{ "model", "state", "questions" }` where `state` is string | JSON object | array of text; questions share one state and are independent.
4. **Primitives:**
   - `choice` → selected option + full probabilities + confidence
   - `score` → ordered rubric level + legend + probabilities + confidence
   - `noul` → yes/no; returned value is P(yes); no separate confidence field
5. **Question design:** evidence in `state`, judgment in `instructions`, descriptive `criteria` per option; question IDs are join keys only.
6. **Response handling:** require legal typed answers; preserve `answers.<id>.probabilities` and native `confidence`; preserve resolved model/usage; reject out-of-set/malformed as parse/review — **never fabricate labels** on HTTP/auth/rate-limit failure.
7. **No streaming:** completed JSON decision only; parallelism = independent requests or multi-question fan-out.
8. **Confidence ≠ correctness:** retain distributions; calibrate against fixtures/gold locally.
9. **Determinism boundary:** arithmetic, aggregation, thresholds, supersession, and paper assembly scaffolding stay in ordinary code.
10. **Secrets:** `OPENROUTER_API_KEY` only via env/ignored `.env`; never print/commit.

### Historical `jev.py` caveat

`eval_lab.jev` still shows `DEFAULT_URL = https://opencode.ai/zen/v1/systemone`, `OPENCODE_API_KEY`, and `jev-1.13-free`. Eval-lab's own audit/contract mark that path historical; TASK-0024 stopped importing it for new work. **jev-classifier must implement the OpenRouter contract**, borrowing only client patterns (payload build, fail-closed normalize, rate-limit handling).

## PCM #144 / PCM-0050 (epistemic-bitemporal) — key sections

Issue: https://github.com/Pukujan/project-continuity-modules/issues/144  
Research note (merged): `docs/research/PCM-0050-epistemic-bitemporal-records.md`

Relevant for this project (helper alignment, not yet adopted as jev-classifier schema):

- **Problem:** prose records treated as truth without machine-readable provenance, confidence tier, or supersession.
- **Bitemporal:** valid time (when true in the world) vs transaction time (when recorded); never collapse unless identical.
- **PROV:** entity/activity/agent + derivation; epistemic status is a domain extension (Observed / Inferred / …).
- **Independence class:** N agents repeating one claim = one datum.
- **Recommended direction (PCM, pending owner Q1–Q5):** O2 claim-ledger overlay (`pcm:claim` with epistemic_status, actor, recorded_at, valid_from/to, evidence, supersedes, independence_class) + O4 adopter filer channel; warn-only validation for v1.
- **Canonical posture:** Git text + GitHub issues as authority; DB only as derived/rebuildable projection.
- **Prior art:** PCM-0015 S9 scoped assertions + `pcm:epistemicStatus` in provenance TTL — O2 ≈ promote S9 + valid-time + independence class.

Owner decision on PCM Q1–Q5 was still outstanding as of research fetch (2026-09-26); jev-classifier should keep claim fields **compatible** with a future `pcm:claim` shape without blocking on PCM merge.

## OWL2 / provenance patterns (lean external)

| Pattern | Why it matters here |
|---------|---------------------|
| [PROV-O](https://www.w3.org/TR/prov-o/) | Interoperable Entity/Activity/Agent + qualified relations for claim lineage |
| NdFluents / 4dFluents (Welty & Fikes; NdFluents ESWC) | OWL-friendly contextual/temporal parts without killing property reasoning |
| Bitemporal KG (valid + transaction intervals) | Aligns with PCM-0050 and Snodgrass-style as-of queries |
| Epistemic status as annotation, not “truth bit” | Matches JEV confidence-as-metadata + local gold |

**Design lean:** start with a small OWL2 TTL (Claim, SourceDocument, ProvenanceBundle, epistemicStatus, validFrom/validTo, recordedAt, supersedes) + PROV-O imports/alignments; defer NdFluents complexity until multi-context reasoning is needed.

## Open questions

1. Exact closed label taxonomy for v1 classification (claim-type? support-level? bias flags?) — freeze in issue #1 before smoke beyond hello-world.
2. How much transcript state fits in JEV's ~32K context after reduction — need compression rules.
3. Whether paper *prose* assembly uses templates only in early phases (recommended) vs a separately gated non-deterministic writer outside the classifier contract.
4. Degree of hard dependency on PCM packages vs copy-aligned schemas until PCM O2 ships.
5. Calibration set: synthetic fixtures vs held-out human labels for bias/detection questions.