---
name: atomic-commit-git-flow
description: >-
  Audits uncommitted work, verifies quality, maps changes to atomic commit units
  and correct feature branches, then commits following ggteq git-flow (develop
  base, one branch per task, several atomic commits). Use when the user has
  uncommitted changes, asks to commit/save work, reconcile branches, or wants
  agent work split into developer-like atomic commits.
---

# Atomic commit & git-flow reconciliation

Turn messy or batched uncommitted work into **verified, atomic commits** on the **right branch(es)**, as close as possible to the ideal where each developer or agent committed their own slice at the right time.

## Git-flow contract (ggteq)

| Rule | Detail |
|------|--------|
| Integration branch | `develop` — day-to-day work lands here via feature branches |
| Release branch | `main` — stable; merge from `develop` when releasing, not for routine docs/features |
| Branch per task | One feature branch per coherent task (one LLM round, one doc set, one fix) |
| Atomic commits | Several small commits per branch; each commit = one logical step |
| Merge direction | `feature/*` → `develop` → `main` (not feature → `main` directly unless user explicitly overrides) |

### Branch naming (match existing repo patterns)

| Prefix | When |
|--------|------|
| `peer-review/…` | Peer-review domain work (`d01`, `d05` drivers, `d06` architecture, `d08` assurance, phase N, LLM id) — IDs follow current `llms_peer_review` numbering |
| `feature/…` | Product or research features |
| `docs/…` | Documentation-only changes |
| `fix/…` | Bug or correction on prior peer-review output |
| `chore/…` | Tooling, gitignore, metrics housekeeping |
| `task/…` | Small scoped corrections |

Examples already in repo: `peer-review/d03-phase1-llm2-fable`, `feature/peer-review-phase2-llm2-fable`, `docs/icecat-data-policy`.

### Commit message style

```
<type>(<scope>): <imperative summary>

Optional body — why, not file list.
```

| Type | Use |
|------|-----|
| `feat` | New questions, answers, proposals, capabilities |
| `docs` | Pure documentation edits |
| `fix` | Corrections to prior content |
| `chore` | Repo hygiene |
| `merge` | Merge commit when integrating a branch |

Scope examples: `d03`, `d01`, `peer-review`, domain shorthand from path.

Recent repo examples:
- `feat(d03): LLM2 (fable) phase 1 - 4 complementary architecture decision driver questions …`
- `feat(d03): LLM2 phase 1 answers recorded - confirm elicitations and synthesis complete`
- `merge(d03): LLM2 phase 1 questions and answers into main`

## When to run

User explicitly asks to commit, save work, reconcile branches, or invokes this skill. **Do not commit** unless the user requested it (this skill counts as explicit request).

## Agent workflow

Copy and track:

```
Progress:
- [ ] 1. Snapshot & branch audit
- [ ] 2. Verify work quality
- [ ] 3. Partition into atomic units
- [ ] 4. Plan branches & commits (show user)
- [ ] 5. Execute on correct branch(es)
- [ ] 6. Reconcile develop ↔ main if drifted
- [ ] 7. Final report
```

### Step 1 — Snapshot & branch audit

Run in parallel from repo root:

```powershell
git status
git branch -a
git log --oneline -15
git log --oneline develop..HEAD
git log --oneline HEAD..develop
git diff --stat
git diff --cached --stat
```

Record:
- Current branch (flag if on `main` with uncommitted feature work)
- Staged / unstaged / untracked files
- Whether `develop` and `main` have diverged
- Existing branches that **already own** part of the dirty tree (prefer reusing over duplicating)

Use [branch-pr-audit](~/.config/opencode/skills/branch-pr-audit/SKILL.md) optionally when many stale branches exist and ownership is unclear.

### Step 2 — Verify work quality

Before any commit:

1. **Read every changed file** (or meaningful diff hunks) — confirm content is complete, consistent, and intentional.
2. **Cross-check index / manifest files** — e.g. `_index.md` status matches closed sections.
3. **Secrets scan** — refuse to commit `.env`, credentials, keys, tokens.
4. **Tests & execution** — if code changed, run relevant tests and a smoke execution; if docs-only, spot-check links and markdown structure.
5. **MDD** — if `metrics/metrics_db.sqlite` exists, run `python -m mdd report` before and `python -m mdd export` after when metrics are touched.

Fix obvious issues **before** committing; note anything that remains intentionally incomplete.

### Step 3 — Partition into atomic units

Split the dirty tree into **commit units** — the set of commits you would have had if each agent committed at the end of its slice.

**Heuristics (apply in order):**

1. **Different domain / phase / LLM author** → separate branch (or separate commits if same branch and same session).
2. **Questions vs answers vs index synthesis** → separate commits when the repo already did so (see LLM2 d03 pattern: questions commit, then answers commit, then index if not bundled).
3. **Unrelated paths** → never one commit (e.g. `d03/phase1` vs `d03/phase2_initial_proposals`).
4. **Generated or mechanical follow-ups** → `chore:` commit separate from `feat:`.
5. **Single logical deliverable** → one commit is OK when splitting would be artificial (e.g. four question files created and answered together).

For each unit, define:

| Field | Example |
|-------|---------|
| `unit_id` | `d03-phase1-llm3-gpt55` |
| `branch` | `peer-review/d03-phase1-llm3-gpt55` (reuse if exists) |
| `base` | `develop` |
| `files` | explicit path list |
| `type` | `feat` / `docs` / `fix` / `chore` |
| `message` | draft subject (+ body if needed) |

### Step 4 — Plan branches & commits

Present a short plan **before** executing:

```markdown
## Commit plan

**Current branch:** main (⚠ should not commit feature work here)

### Unit 1 — d03 LLM3 phase 1 Q&A
- **Branch:** peer-review/d03-phase1-llm3-gpt55 (create from develop)
- **Commit 1:** feat(d03): LLM3 (gpt55) phase 1 — 4 architecture decision driver questions
- **Commit 2:** feat(d03): LLM3 phase 1 answers and index synthesis

### Unit 2 — d03 phase 2 LLM1 proposal
- **Branch:** feature/peer-review-d03-phase2-llm1-composer (create from develop)
- **Commit 1:** feat(d03): LLM1 phase 2 initial architecture proposal

### Reconciliation
- Merge peer-review/d03-phase1-llm2-fable commits from main into develop (3 commits ahead)
```

Adjust plan if user redirects. If branch ownership is ambiguous, ask once; default to **new branch from develop**.

### Step 5 — Execute on correct branch(es)

**Safety (never violate):**
- Never `git config` changes, `--no-verify`, force-push to `main`, or hard reset unless user explicitly requests.
- Never commit secret files.
- Prefer **new commits** over `--amend` unless amend rules below are fully satisfied.

**Per unit:**

```powershell
git fetch origin
git checkout develop
git pull origin develop
git checkout -b <branch-name>   # skip -b if branch exists and is correct base
# stage only this unit's files
git add <paths>
git commit -m "<subject>" -m "<body>"
```

Repeat for each atomic commit in the unit before switching to the next unit.

**PowerShell commit messages** (no bash HEREDOC on Windows):

```powershell
git commit -m "feat(d03): short subject" -m "Body paragraph when needed."
```

For multi-line body only, use a temp file:

```powershell
@'
feat(d03): subject line

Body line 1.
Body line 2.
'@ | Out-File -Encoding utf8 .git/COMMIT_EDITMSG_TEMP
git commit -F .git/COMMIT_EDITMSG_TEMP
Remove-Item .git/COMMIT_EDITMSG_TEMP
```

**Staging discipline:** `git add` only paths belonging to the current commit unit — never `git add -A` when multiple units are pending.

After each commit: if a pre-commit hook modifies files, fix and create a **new** commit (do not amend unless amend rules allow).

### Step 6 — Reconcile develop ↔ main

After feature branches are committed:

1. Merge each feature branch into `develop` (merge commit or FF per repo habit).
2. If `main` was incorrectly used earlier, merge `develop` into `main` **only** when user wants release sync — otherwise leave `main` and document drift.
3. Do **not** push unless user asks.

```powershell
git checkout develop
git merge --no-ff peer-review/d03-phase1-llm3-gpt55 -m "merge(d03): LLM3 phase 1 questions and answers into develop"
```

### Step 7 — Final report

Return:

1. Table of commits created (hash, branch, message).
2. Branches created vs reused.
3. Verification summary (what was read/tested).
4. Remaining dirty files, if any, and why they were excluded.
5. `develop` vs `main` state and recommended next step (push, PR, merge).

## Amend rules (strict)

Use `git commit --amend` only when **all** are true:
1. User requested amend, **or** pre-commit hook auto-modified files from a commit you just made this session.
2. HEAD was created by you in this conversation.
3. Commit has **not** been pushed (branch not ahead of remote for that commit).

If amend fails or hook rejects, fix and make a **new** commit.

## Ideal vs reality — how close to get

| Ideal | Acceptable approximation |
|-------|---------------------------|
| Each agent committed on its own branch at task end | One reconciliation pass groups by author/domain and splits commits |
| Perfect chronological history | Commit order follows logical dependency (content before index update) |
| develop always current | Catch-up merge when main was used by mistake |

Always **document in the report** where reality diverged from ideal.

## Related skills

- **branch-pr-audit** (`~/.config/opencode/skills/branch-pr-audit/SKILL.md`) — tag unmerged branch tips with PR state (optional cleanup pass).
- User commit rules in Cursor settings — HEREDOC on Unix; use `-m` / `-F` on Windows as above.

## Additional reference

- Branch prefix catalog and commit examples: [reference.md](reference.md)
