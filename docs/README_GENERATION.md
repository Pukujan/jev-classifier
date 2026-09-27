# README generation and validation record

This record makes the exact CGM entry points and verification commands explicit. The helper is pinned at `Pukujan/content-generation-modules` commit `f85e88bc00362c53061d95ac7811bd9c6ada8e32` (contract 0.4.0, draft).

## README authoring entry point

CGM's six modules are instruction modules, not a README-generation CLI. The authoring workflow reads these pinned files in order:

1. `modules/content-context/SKILL.md` to extract repository claims, limits, and immutable evidence into `.content-system/project-brief.json`.
2. `modules/brand-foundation/SKILL.md` and `.content-system/brand-language.json` to set the target's wording.
3. `modules/visual-direction/SKILL.md`, `.content-system/visual-style.json`, and `docs/IMAGE_GUIDE.md` to define image roles and review rules.
4. `modules/writing-direction/SKILL.md`, `templates/readme-contract.json`, and `docs/README_PLAYBOOK.md` to draft the nine-section `README.md`.
5. `modules/image-generation/SKILL.md` to document and review the supplied image assets.

For this revision, the target inputs were the checked-out product source/tests and project docs, `AGENTS.md`, the pinned issue #35 scope, and the adapter files above. The README was authored as a manual agent workflow; no CGM command or model was run to generate its prose. The helper's `modules/html-demo/SKILL.md` is not used because this deliverable is a Markdown README, not an HTML demo.

## Image entry point and limits

The asset manifest records the provider as Codex's built-in `image_gen` workflow. The original image-generation invocations and verbatim prompts were not retained with these files. The linked prompt records are explicitly reconstructed intent, so they document the visible message and review constraints without claiming exact regeneration. The tool has no repository CLI or stable seed/model settings recorded here. A future replacement asset should be generated through the Codex built-in ImageGen tool (`image_gen.imagegen`) using the corresponding prompt record, then visually reviewed and re-hashed; that is a regeneration instruction, not a claim that this invocation produced the existing files.

## Validation entry points

Run from the repository root with Python available:

```powershell
python .cache/cgm-pinned/scripts/validate_content_system.py --root .cache/cgm-pinned --adapter .content-system --project-root .
python scripts/validate_readme_docs.py --root .
python scripts/validate_docs.py
git diff --check
```

The first command validates the adapter contract and manifest hashes. The target script checks the nine required README headings, contract-required references, and local Markdown links. `python scripts/validate_docs.py` checks the managed-documents manifest and its links/hashes. `git diff --check` checks patch whitespace. These commands do not check remote-link availability, factual truth, narrative comprehension, narrow-screen rendering, or research quality. `docs/README_REVIEW.md` is optional reader/visual QA; the owner waived separate sign-off as a merge gate. Leave it unchecked unless an actual reviewer records a result.

The helper is ignored build material. From the repository root in PowerShell, create the cache and check out the exact pinned commit before validating:

```powershell
New-Item -ItemType Directory -Force -Path .cache | Out-Null
git clone https://github.com/Pukujan/content-generation-modules.git .cache/cgm-pinned
git -C .cache/cgm-pinned checkout f85e88bc00362c53061d95ac7811bd9c6ada8e32
git -C .cache/cgm-pinned rev-parse HEAD
```

The final command must print `f85e88bc00362c53061d95ac7811bd9c6ada8e32`. Do not validate against a moving branch.
