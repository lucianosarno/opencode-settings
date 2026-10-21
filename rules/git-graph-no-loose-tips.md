# Git Graph — no limbo tips

Goal: every remote tip is **accounted for**. Keep branches for **traceability** after merge/close. What is forbidden is a tip with **no PR history** and **not merged** into the integration base (`develop` / `main`, or the repo’s equivalent).

If the repo has `.github/BRANCH_POLICY.md`, follow its §Merge method & tip hygiene as the canonical local contract.

## Merge method (hard)

- **Allowed:** merge commit only (`Create a merge commit`).
- **Forbidden:** squash merge and rebase merge.
  - Squash/rebase rewrite tip SHAs so the branch tip is **not** an ancestor of the base → orphan tip in Git Graph even when the work landed.
- Prefer GitHub PR into the integration branch (or promote to production). Local merge into the base must also be a **true merge** (or fast-forward), never squash.
- Do **not** use `gh pr merge --squash` / `--rebase`, nor UI squash/rebase buttons.

## Tip states (allowed vs forbidden)

| State | Keep branch? | Graph meaning |
|-------|--------------|---------------|
| **Merged** (merge commit into base) | **Yes** — keep for rastreabilidade | Tip is on the ancestry of the base (not a limbo tip) |
| **PR open** | **Yes** | Active work; expected tip |
| **PR closed** (without merge) | **Yes** — keep for rastreabilidade | Abandoned with a recorded decision (closed PR) |
| **No PR** and not merged | **Forbidden limbo** | Open a PR, merge, or close a PR that documents abandonment. Do not leave nameless tips. |

Do **not** auto-delete head branches on merge. Repo setting `delete_branch_on_merge` must stay **off**.

## Agent / developer checklist

- Before pushing a long-lived tip: ensure a PR exists (or create one), even if draft.
- When abandoning work: **close the PR** (with a one-line reason). Keep the branch if useful for history; do not leave `no-pr` tips.
- When finishing work: merge with **merge commit**; leave the branch in place for traceability unless the owner explicitly asks to delete it.
- Never use squash/rebase.

## Hygiene tool

Label remaining unmerged tips for Git Graph:

```bash
python ~/.config/opencode/skills/branch-pr-audit/scripts/audit.py --fetch --apply --push
```

- `open` / `merged` / `closed` — accounted for (OK to keep).
- `no-pr` — limbo; open/close a PR or otherwise resolve. That is the cleanup target.

