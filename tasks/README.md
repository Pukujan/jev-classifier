# Tasks

Task projections for the `JEV` task prefix live here: one Markdown file per
tracked task, named `TASK-JEV-NNNN-<slug>.md` and validated against
`schemas/v1/task.schema.json`.

Each projection is a thin, machine-readable mirror of a GitHub issue (tracker:
GitHub, see `.continuity/config.json`), not a second source of truth:

- Authoritative discussion, acceptance, and closure happen on GitHub issues in
  this repository; each projection links its issue URL and carries the issue
  number that maps to its `JEV-NNNN` id.
- Projections record the fields a fresh agent needs to resume without chat
  history: goal, current state, evidence/receipts, blockers, and the exact next
  action.
- `docs/CURRENT.md` points at the active task via its `continuity:current`
  marker (`active_task` / `active_task_file`); when no task is active, those
  fields stay `null`.

Run `continuity validate --root .` to check this tree against the copied
schema set.
