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
| See the exact module contracts and which parts use a model | [`SYSTEM_SPEC.md`](SYSTEM_SPEC.md) | contributor, maintainer |
| Know who decides what when agents disagree | [`AUTHORITY.md`](AUTHORITY.md) | contributor, agent |
| Read or write a claim record | [`CLAIM_SCHEMA.md`](CLAIM_SCHEMA.md) | contributor |
| Find the machine-readable module catalog | [`spec/modules.json`](spec/modules.json) | agent, tooling |
| Check a page's reader-usefulness before publishing | [`HUMAN_REVIEW_CHECKLIST.md`](HUMAN_REVIEW_CHECKLIST.md) | reviewer |
| See which reference papers are selected, and their rights | [`DATASET_CARD.md`](DATASET_CARD.md) | contributor, reviewer |

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
│   ├── GROK_SOURCE.md             source-capture adapter
│   ├── RESEARCH_NOTES.md          bootstrap notes (non-normative)
│   ├── ISSUE_1_DRAFT.md           historical draft
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
*(partial)* Orphan detection — flagging an in-scope document that is not
registered — is **not** implemented; only registered documents are checked.

## What this page does not establish

Being listed here means a document is **managed**, not that its content is
correct or complete. Status labels are per document in the manifest; a
`planned` or `unknown` entry is a gap, not a result. See
[`EPISTEMIC_SYSTEM.md`](EPISTEMIC_SYSTEM.md) §4 for the project-wide limits.

*(One next action.)* Pick the row above that matches what you came to do, and
follow its link.
