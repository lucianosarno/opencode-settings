# Atomic commit & git-flow — reference

## Partitioning examples (d03 peer review)

### LLM2 pattern already in history

| Commit | Contents |
|--------|----------|
| `87b68e3` | 4 question files + partial `_index.md` |
| `1217556` | Answer confirmations in question files |
| `18b3213` | Merge into `main` |

When LLM3 files include both questions **and** answers in one session, acceptable splits:

**Option A (mirror LLM2):**
1. `feat(d03): LLM3 (gpt55) phase 1 — 4 architecture decision driver questions`
2. `feat(d03): LLM3 phase 1 answers recorded — elicitations and synthesis complete`
3. `_index.md` LLM3 section in commit 2 or a small commit 3

**Option B (single deliverable):**
1. `feat(d03): LLM3 (gpt55) phase 1 — questions, answers, and index synthesis`

Prefer **Option A** when answer edits are large or happened in a visibly separate step.

### Phase 1 vs phase 2

| Path pattern | Branch suggestion |
|--------------|-----------------|
| `phase1_questions/llm3_gpt55/` | `peer-review/d03-phase1-llm3-gpt55` |
| `phase2_initial_proposals/llm1_composer/` | `feature/peer-review-d03-phase2-llm1-composer` |
| `phase2_initial_proposals/llm2_fable/` | `feature/peer-review-d03-phase2-llm2-fable` |

Never mix phase 1 and phase 2 in one commit.

## Branch reuse checklist

Before creating a branch, search:

```powershell
git branch -a | Select-String "d03|peer-review|llm3"
```

Reuse when:
- Branch tip is ancestor of current work or same task was interrupted
- Branch name matches domain + phase + author

Create new when:
- Prior branch was merged and closed
- Work is a correction → use `fix/…` off `develop`

## Common drift scenarios

| Observation | Action |
|-------------|--------|
| On `main`, uncommitted docs | Do **not** commit to `main`; branch from `develop` |
| `main` ahead of `develop` (merged features) | Merge or cherry-pick into `develop`, report to user |
| Dirty tree spans merged + new work | Commit new work on new branch; handle old merges separately |
| Same files on wrong branch | Stash, checkout correct branch, stash pop, recommit |

## Pre-commit hook failure

1. Read hook output.
2. Fix formatting/lint issues in working tree.
3. Stage fixes with `git add` on affected paths only.
4. New commit (or amend only if amend rules satisfied).

## Files to never commit

- `.env`, `*.pem`, `credentials.json`, `service-account*.json`
- Large binaries unless explicitly gitignored and policy allows
- `metrics/metrics_db.sqlite` local-only experiments without `mdd export` when MDD applies

## Verification checklist (docs)

- [ ] Frontmatter / status markers (`✅ Answered`, `✅ Closed`) consistent
- [ ] `_index.md` links resolve (no broken relative paths)
- [ ] Phase exit criteria text matches closed LLM sections
- [ ] No duplicate LLM sections or conflicting status rows
