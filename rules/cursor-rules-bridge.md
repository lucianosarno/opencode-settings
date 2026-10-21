# Bridge: project rules originally authored for Cursor

Some repositories contain project rules written for Cursor. Whenever you start working in a repository (first task of a session, or after switching repos), check for these sources and treat them as project-level constraints:

- `.cursor/rules/*.mdc` (and `.cursor/rules/*.md`)
- `.cursorrules` (legacy single file)
- `CURSOR_RULES.md` / `.cursor/rules/CURSOR_RULES.md`

## How to read a `.mdc` file

YAML frontmatter + markdown body. Frontmatter fields: `name`, `description` (summary used for discovery), `alwaysApply` (true = always binding), `globs` (file patterns the rule attaches to). The body is the rule text itself.

## Applicability semantics (mirror Cursor)

- `alwaysApply: true` → binding for the whole session in that repo.
- `globs` present (without alwaysApply) → binding only when working on matching files.
- only `description` (no globs, alwaysApply false) → on-demand: read it once when the task clearly matches the description; if unsure, read it to decide.

## How to apply

Read the applicable files once per repository session, before planning, then follow them together with the global rules. Do not ignore them because they were authored for Cursor. If a project rule conflicts with a global rule, follow the stricter safety/conduct one and flag the conflict to the user. If the repo has no such files, continue silently — do not create any unless asked.
