# INDEX — where to start, and what is where

**Audience:** newcomer first, then contributor. **Status:** shipped.
**Owner:** issue [#63](https://github.com/Pukujan/jev-classifier/issues/63).

If you have just arrived, read this page top to bottom once. It is a map, not a
manual: every entry says what the document is for and who it is for, so you can
skip to what you need.

## Start here, by what you want to do

| If you want to… | Read | Who it is for |
|---|---|---|
| Understand what the project is allowed to claim, in plain language | [`EPISTEMIC_SYSTEM.md`](EPISTEMIC_SYSTEM.md) | newcomer, reviewer |
| Get the short project purpose, limits, and setup path | [`../PROJECT.md`](../PROJECT.md) | newcomer, developer |
| See the exact module contracts and which parts use a model | [`SYSTEM_SPEC.md`](SYSTEM_SPEC.md) | contributor, maintainer |
| Know who decides what when agents disagree | [`AUTHORITY.md`](AUTHORITY.md) | contributor, agent |
| Read or write a claim record | [`CLAIM_SCHEMA.md`](CLAIM_SCHEMA.md) | contributor |
| Find the machine-readable module catalog | [`spec/modules.json`](spec/modules.json) | agent, tooling |
| Use an optional reader-usefulness checklist | [`HUMAN_REVIEW_CHECKLIST.md`](HUMAN_REVIEW_CHECKLIST.md) | reviewer |
| Write issue titles, commit subjects, PR titles, or new file names in plain human words | [`HUMAN_NAMING.md`](HUMAN_NAMING.md) | agent, contributor |
| See which reference papers are selected, and their rights | [`DATASET_CARD.md`](DATASET_CARD.md) | contributor, reviewer |
| Understand the README's evidence map and editorial choices | [`CONTENT_RESEARCH.md`](CONTENT_RESEARCH.md) | contributor, maintainer |
| Find prior-work analysis and source comparisons | [`PRIOR_WORK.md`](PRIOR_WORK.md) and [`REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md`](REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md) | contributor |
| Rebuild or verify the README workflow | [`README_GENERATION.md`](README_GENERATION.md) and [`README_PLAYBOOK.md`](README_PLAYBOOK.md) | contributor, agent |
| Understand how the hidden holdout is frozen and kept out of development | [`HOLDOUT_PROTOCOL.md`](HOLDOUT_PROTOCOL.md) | contributor, reviewer |

## Folder tree (curated)

Only the parts of the repository a reader of the docs needs to see. Excluded
paths — secrets, local databases, caches, worktrees, and restricted holdout data
— are listed in [`docs_manifest.json`](docs_manifest.json) and never appear
here.

```
jev-classifier/
├── README.md                      project entry point
├── AGENTS.md                      operating rules for agents in this repo
├── PROJECT.md                     project intent and scope
├── docs/
│   ├── INDEX.md                   ← you are here (navigation)
│   ├── EPISTEMIC_SYSTEM.md        plain-language guide to what may be claimed
│   ├── SYSTEM_SPEC.md             normative module contracts
│   ├── CLAIM_SCHEMA.md            claim-ledger record schema
│   ├── AUTHORITY.md               who decides; the claim protocol
│   ├── AGENT_COORD.md             optional local coordination aid
│   ├── AGENT_PROPOSALS.md         proposal / verdict / receipt mechanics
│   ├── OPS_LEDGER.md              ops projection protocol
│   ├── DATASETS.md                fixtures and licensing
│   ├── DATASET_CARD.md            reference-paper selection and rights
│   ├── BRAND_DIRECTION.md         target voice and visual direction
│   ├── CONTENT_RESEARCH.md        README evidence map and editorial choices
│   ├── HOLDOUT_EVALUATION.md      quality goals and evaluation limits
│   ├── HOLDOUT_PROTOCOL.md        how the hidden holdout is frozen and kept out
│   ├── GROK_SOURCE.md             source-capture adapter
│   ├── IMAGE_GUIDE.md             image roles, accessibility, and reuse
│   ├── RESEARCH_NOTES.md          bootstrap notes (non-normative)
│   ├── PRIOR_WORK.md              prior work and research references
│   ├── PROVENANCE_AND_CITATION.md evidence and citation practice
│   ├── README_GENERATION.md       pinned CGM workflow and verification
│   ├── README_PLAYBOOK.md         reader-first project-story workflow
│   ├── README_QUALITY_*.md        product, design, and test quality notes
│   ├── README_REVIEW.md           optional reader/visual QA checklist
│   ├── REVERSE_ANALYSIS_PCM_AND_ADOPTERS.md prior-work comparison
│   ├── MIGRATING_TO_0.*.md        CGM contract migration notes
│   ├── ISSUE_1_DRAFT.md           historical draft
│   ├── HUMAN_NAMING.md            plain-human titles for issues, commits, PRs, files
│   ├── HUMAN_REVIEW_CHECKLIST.md  reader-usefulness review rubric
│   ├── CURRENT.md                 live continuity card (rewritten per task)
│   ├── docs_manifest.json         machine-readable inventory of the above
│   └── spec/
│       └── modules.json           machine-readable module catalog
├── schemas/                       JSON Schemas (records and manifest)
├── src/jev_classifier/            implementation
├── tests/                         offline test suite
└── scripts/                       entry points (smoke, validators, ops sync)
```

## What is authoritative, and in what order

When two documents disagree, the earlier entry wins:

1. [`AUTHORITY.md`](AUTHORITY.md) — who decides.
2. [`SYSTEM_SPEC.md`](SYSTEM_SPEC.md) — what the module contracts are.
3. `AGENTS.md` — operating rules.
4. Source code — and if the code and the spec disagree, **the code is reality
   and the spec has a bug**; file it rather than editing the code to match prose.

## The documentation manifest

`docs/docs_manifest.json` is the machine-readable inventory behind this page. It
records, per managed document, what it is for, who it is for, its status
(shipped / partial / planned / unknown), the code and specs its facts come from,
its owning issue, and whether a human has reviewed it. The deterministic
validator [`scripts/validate_docs.py`](../scripts/validate_docs.py) checks that
every path and source resolves, that a reviewed file has not silently changed,
that local links resolve, and that excluded paths never appear:

```bash
python scripts/validate_docs.py            # check (default)
python scripts/validate_docs.py --json     # machine-readable result
python scripts/validate_docs.py --no-freshness   # skip the file-hash check
```

*(shipped)* The manifest, schema, and validator are on `main` as of issue #63.
The validator also scans `docs/*.md` and fails when an in-scope document is not
registered. `docs/CURRENT.md` is the sole documented exception because it is
rewritten as a continuity projection on each task.

## What this page does not establish

Being listed here means a document is **managed**, not that its content is
correct or complete. Status labels are per document in the manifest; a
`planned` or `unknown` entry is a gap, not a result. See
[`EPISTEMIC_SYSTEM.md`](EPISTEMIC_SYSTEM.md) §4 for the project-wide limits.

*(One next action.)* Pick the row above that matches what you came to do, and
follow its link.
