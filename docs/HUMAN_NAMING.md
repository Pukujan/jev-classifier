# Human-readable names

**Audience:** every agent and contributor who opens an issue, writes a commit,
opens a PR, or adds a file. **Status:** shipped. **Owner:** issue
[#79](https://github.com/Pukujan/jev-classifier/issues/79).

Owner ruling (2026-09-26): issue titles, **commit subjects** (the one line
shown in `git log --oneline` and in GitHub commit lists), **PR titles**, and
**new file / folder names** must read as plain human sentences or pronounceable
words. Internal module ids, milestone codes, and conventional-commit prefixes
belong in the body, not in the title.

This is forward-only. Do not rewrite history of already-merged commits.

## What must be human-readable

| Surface | Rule |
| --- | --- |
| Issue title | One plain sentence of what is wrong or what the reader gets. |
| Commit subject | Same voice: what changed for a human. This is the git subject line, not only the body. Prefer <=72 characters. |
| PR title | Readable summary of the user-visible or maintainable change, not a branch slug. |
| New file / folder names | Words a newcomer can pronounce. Keep existing public paths stable unless a rename is in scope. |

Ticket codes (`Refs #N`, `Closes #N`) stay in the commit body or trailer, not as the whole subject.

## Do not lead with agent codes

Do **not** start an issue title, commit subject, or PR title with conventional-commit prefixes such as `feat:`, `fix:`, `chore:`, `docs:`, or `test:` unless the human sentence truly needs those words. Prefer a plain sentence. Branch names may still use `feat/` / `fix/` prefixes for the reserved-branch claim protocol; that is a path, not a title.

## Before / after (from this repo)

| Bad (agent-coded) | Good (human sentence) |
| --- | --- |
| `feat: wire M5 known_gap ClassificationActivity edges` | Record which JEV call produced each claim |
| `feat: deterministic cross-source claim consolidation M8` | Merge claims that say the same thing across sources |
| `chore: claim marker for #78 (activity/agent edges)` | Reserve the branch for claim activity edges (#78) |
| `fix: collision holder identity is the reserved branch, not the label` | Treat the reserved branch, not the label, as the claim holder |
| File: `m5_kg_prov_act_edges_v2.md` | File: `claim_activity_edges.md` |

The good versions still leave room for `Refs #N` in the commit body.

## CGM pins (load these when writing titles and prose)

Pin [Pukujan/content-generation-modules](https://github.com/Pukujan/content-generation-modules) at revision
`c7d9c3f6b5b301d3a3bc89642d2f92fd08748979` (HSW 0.5.0 landed):

| Situation | Module / doc |
| --- | --- |
| Issue titles, commit subjects, PR titles, progress comments, general prose | **HSW** — [`modules/human-sounding-writing/SKILL.md`](https://github.com/Pukujan/content-generation-modules/blob/c7d9c3f6b5b301d3a3bc89642d2f92fd08748979/modules/human-sounding-writing/SKILL.md) |
| README / product-entry / human UX docs | [`modules/writing-direction/SKILL.md`](https://github.com/Pukujan/content-generation-modules/blob/c7d9c3f6b5b301d3a3bc89642d2f92fd08748979/modules/writing-direction/SKILL.md) |
| Soft router (when bold/voice rules might fight) | [`docs/WRITING_ROUTING.md`](https://github.com/Pukujan/content-generation-modules/blob/c7d9c3f6b5b301d3a3bc89642d2f92fd08748979/docs/WRITING_ROUTING.md) |
| Full HSW guide | [`docs/HUMAN_SOUNDING_WRITING.md`](https://github.com/Pukujan/content-generation-modules/blob/c7d9c3f6b5b301d3a3bc89642d2f92fd08748979/docs/HUMAN_SOUNDING_WRITING.md) |
| Machine rules | [`docs/human-sounding-rules.json`](https://github.com/Pukujan/content-generation-modules/blob/c7d9c3f6b5b301d3a3bc89642d2f92fd08748979/docs/human-sounding-rules.json) |

HSW asks for a plain title that states what happened — no colon-reveal slogans, no stack of ticket codes as the whole subject.

## Quick checklist before you push

- [ ] Issue title is a plain sentence a newcomer can skim.
- [ ] Commit subject (the `git log --oneline` line) is a plain sentence; no leading `feat:` / `fix:` unless the sentence needs it.
- [ ] PR title is a readable summary, not the branch slug.
- [ ] New paths use pronounceable words; existing public paths stay stable.
- [ ] History of merged commits is left alone.
