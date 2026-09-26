.content-system contains the pinned Content Generation Modules adapter used for this README. The helper is documentation tooling, not a runtime dependency of jev-classifier.

- `project-brief.json` records audience, problem, mechanism, evidence, status, source limits, and project boundaries.
- `brand-language.json` records approved wording and terms to avoid.
- `visual-style.json` records the target palette, composition, roles, and rejection rules.
- `asset-manifest.json` records visible image copy, dimensions, prompt intent, alt text, crop rules, review decisions, prompt records, and hashes.
- `review-rubric.json` lists deterministic review checks and human questions.
- `readme-contract.json` copies the required story order for the target.
- `docs/README_GENERATION.md` records the exact pinned CGM authoring modules, image workflow provenance limits, and reproducible validation entry points.

The delivered image files predate their saved prompt notes. Those notes are reconstructed prompt intent, not verbatim original prompts. The ignored pinned helper can be rebuilt at the commit recorded in `system-version.json`.

Run the pinned helper validator from the repository root:

    python .cache/cgm-pinned/scripts/validate_content_system.py --root .cache/cgm-pinned --adapter .content-system --project-root .

Run scripts/validate_readme_docs.py separately for target headings and local links, then complete docs/README_REVIEW.md. A passing helper check confirms structure and file hashes; it does not establish that claims are true or that readers understand the README.