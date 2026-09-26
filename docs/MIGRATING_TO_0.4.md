# Content Generation Modules 0.4 guide

CGM 0.4.0 is pinned as a draft at the reviewed immutable commit in [.content-system/system-version.json](../.content-system/system-version.json). This is a documentation workflow pin, not an application dependency.

## Evidence-record change

The v2 brief requires a bounded claim, source, status, what the source supports, what it leaves open, source revision, and timezone-aware record time. Optional valid-time bounds stay separate from the moment the record was written. Repository sources need a full commit, path, locator, and immutable URL. External sources need a direct URL and access date.

## What the validator does

The pinned helper checks file shapes, required README structure and references, source identity, citation presence, asset prompt fields, and image hashes. It does not establish that the citations are credible, that they support the wording, or that a first-time reader understands the page. The human review checklist remains part of acceptance.

See [.content-system/project-brief.json](../.content-system/project-brief.json), [PROVENANCE_AND_CITATION.md](PROVENANCE_AND_CITATION.md), and [README_QUALITY_TDD.md](README_QUALITY_TDD.md).
