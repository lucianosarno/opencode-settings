---
name: branch-pr-audit
description: >-
  Audits unmerged git branches against GitHub PR state and tags branch tips with
  audit/* refs (open, merged, closed, no-pr) for Git Graph visibility. Supports
  local apply and team-wide push to origin. Use when the user asks to audit branch
  tips, tag abandoned branches, visualize unmerged branches in Git Graph, or run
  branch PR audit.
---

# Branch PR audit

Tags **unmerged** branch tips with lightweight refs under `audit/*` so Git Graph shows PR state at each tip. Designed for **team-wide** use: push tags to `origin` so everyone sees the same labels after `git fetch --tags`.

## Prerequisites

- `git` and [GitHub CLI](https://cli.github.com/) (`gh`) installed
- `gh auth login` completed for the repo remote
- Run from the **repository root**

## Tag convention (team contract)

| Situation | Tag example |
|-----------|-------------|
| PR open | `audit/pr-42-open` |
| PR merged, branch still exists | `audit/pr-42-merged` |
| PR closed without merge | `audit/pr-42-closed` |
| No PR for branch | `audit/no-pr-feature-my-work` |

Only refs matching `audit/*` are managed by this tool. Never use `audit/` for release tags.

## Script location

```text
~/.config/opencode/skills/branch-pr-audit/scripts/audit.py
```

Project copy (when committed in a repo):

```text
.cursor/skills/branch-pr-audit/scripts/audit.py
```

Prefer the project copy when present; otherwise use the personal skill path above.

## Agent workflow

When the user asks to audit branches or refresh Git Graph labels:

1. `cd` to repo root
2. Run with fetch + apply + push (team default):

```bash
python ~/.config/opencode/skills/branch-pr-audit/scripts/audit.py --fetch --apply --push
```

If `.cursor/skills/branch-pr-audit/scripts/audit.py` exists in the repo, use that path instead.

3. Show the printed table; highlight `closed`, `merged`, and `no-pr` rows as cleanup candidates
4. Remind: teammates run `git fetch --tags` (or `git fetch --prune --tags`) to see remote audit tags in Git Graph

### Git Graph visibility (tags not showing?)

Audit tags sit on **unmerged branch tips** — commits not on `develop` yet. In Git Graph:

1. **Branches** dropdown → **Show All** (not only `develop`)
2. Repository **gear** → **Show Tags** on
3. **Reload** Git Graph after audit; or click **Fetch**
4. **Ctrl+F** → search `audit/pr-94-open` to jump to a tagged commit
5. Tag appears on the **commit row** (often right of message), next to the branch label

## Commands

| Intent | Command |
|--------|---------|
| Preview (default) | `python .../audit.py` |
| Local tags only | `python .../audit.py --fetch --apply` |
| Team sync (recommended) | `python .../audit.py --fetch --apply --push` |
| Custom base branch | `python .../audit.py --base main --apply --push` |
| Remove all audit tags | `python .../audit.py --clean --push` |

## Suggested actions (report to user)

- **open** — keep; work in progress with open PR
- **merged** — delete branch (integrated; tag is cleanup signal)
- **closed** — delete branch or document abandonment
- **no-pr** — open a PR or confirm WIP / delete if obsolete

## Team adoption

1. Copy `.cursor/skills/branch-pr-audit/` into each repo (or symlink from a shared dotfiles repo)
2. Document in team onboarding: after merging/closing PRs, whoever cleans up runs `--fetch --apply --push`
3. Optional: add a VS Code / Cursor task `"Branch PR audit"` pointing at the script with `--fetch --apply --push`
4. Do **not** use `git push --tags` blindly — the script pushes only `audit/*` individually with `--force` when tips move

See `reference.md` for install paths and FAQ.

## Safety

- `--dry-run` is the default when neither `--apply`, `--push`, nor `--clean` is passed
- `--push` uses force per tag so moved branch tips update remote labels
- Script never deletes git branches — only `audit/*` tags
