# PR markdown task lists (`- [ ]` / `- [x]`)

GitHub’s “N of M tasks” counter is **only** unchecked boxes in the PR body/comments. It does **not** reflect Actions/status checks.

## Prefer

- **Do not** put `- [ ]` in the PR body for items that CI already proves (e.g. “l2-* green”, “tests pass”). Use a short Test plan in prose instead.
- Keep intentional human checklists only where a person must affirm something CI cannot (e.g. stub-blacklist in a repo’s `.github/pull_request_template.md`).

## If you do use task lists

- Before merge (or when closing the PR), **mark every completed item `[x]`**.
- For items that became N/A, mark `[x]` and say why (or remove the line) — do not leave stale `[ ]`.
- Leaving unchecked boxes after the work is done creates false “tasks remaining” noise on merged/closed PRs.

