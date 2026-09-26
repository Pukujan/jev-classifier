# Dataset fixtures and licensing

Offline CI uses **first-party synthetic fixtures** only. This card records what
was considered, what was omitted and why, and the sha256 of each committed
fixture file. Binding ruling: GitHub issue
[#33](https://github.com/Pukujan/jev-classifier/issues/33) (arbiter
synthetic-first corrections).

## Committed fixtures (synthetic)

| File | Kind | Label shapes modeled on | sha256 |
|---|---|---|---|
| `tests/fixtures/datasets/claim_type_shapes.json` | synthetic | SciCite `background` / `method` / `result` | 263ac157115ee68f018b351db710a65f243709ee57d08714a6d8e4fedb114b09 |
| `tests/fixtures/datasets/contradiction_shapes.json` | synthetic | SciNLI `entailment` / `contrasting` / `neutral` / `reasoning` | a2c5ceb147b44feba890c7bbd42e4d9739aba5ccb0a490f89416101291eab0c0 |

Machine-readable twin: `tests/fixtures/datasets/PROVENANCE.json` (regenerated
by the same script; tests assert file bytes match recorded hashes).

**Generator (deterministic):** `scripts/generate_synthetic_fixtures.py`

```bash
python scripts/generate_synthetic_fixtures.py          # write fixtures + PROVENANCE
python scripts/generate_synthetic_fixtures.py --check  # verify committed == generated
```

Samples are hand-authored. They are **not** benchmark items and must not be
cited as SciCite/SciNLI performance evidence.

## Sources considered

| Dataset | Intended use | License findings | Commit? |
|---|---|---|---|
| **SciCite** | claim-type closed set | Code repo Apache-2.0; Hugging Face `dataset_infos.json` has empty/`unknown` license for corpus text | **NO** corpus text — synthetic label-shape fixtures only |
| **SciNLI** | contradiction/agreement | Issue body claimed Apache-2.0 but distribution URL/license field not pinned from a primary dataset card | **NO** until a pinned card+license is recorded — synthetic only |
| **SciFact** | (considered / rejected) | Upstream LICENSE.md NOASSERTION; issue research records NC component concerns | **NEVER** — runtime `.research_cache/` only if used |

## Omissions (explicit)

1. **SciCite corpus text** — code license ≠ dataset-text clearance; HF metadata
   unknown. Omitted from git.
2. **SciNLI corpus text** — license/distribution not verified for commit.
   Omitted from git.
3. **SciFact any component** — arbiter ruling: never commit under any
   split-license theory.
4. **Copyleft bias suites** (StereoSet, CrowS-Pairs, HolisticBias) — reference
   only; not fixtures for this leaf.
5. **SciTail** — code Apache-2.0 does not clear corpus text; not used.

## Runtime fetch (optional, not required for this PR)

Uncleared or large corpora may be fetched locally into the already-gitignored
`.research_cache/` (or `data/`) for interactive evaluation. Offline tests and
CI must not depend on that path. Document name + revision + hash if a future
leaf authorizes a specific cleared component.

## Provenance honesty

- Fixture `provenance.kind` is always `synthetic`.
- Hashes below are of the committed UTF-8 JSON bytes (sorted keys, 2-space
  indent, trailing newline) as produced by the generator.
- If a later primary source clears a corpus for commit, append a new section
  rather than rewriting this card's omission rationale silently.

## Fixture hashes (authoritative after generate)

<!-- hashes:start -->
| File | sha256 | bytes |
|---|---|---|
| `claim_type_shapes.json` | 263ac157115ee68f018b351db710a65f243709ee57d08714a6d8e4fedb114b09 | 2182 |
| `contradiction_shapes.json` | a2c5ceb147b44feba890c7bbd42e4d9739aba5ccb0a490f89416101291eab0c0 | 2339 |
<!-- hashes:end -->

Regenerate the hash table by running the generator, then copying values from
`PROVENANCE.json` into the table above (tests require the sha256 strings to
appear in this file).
