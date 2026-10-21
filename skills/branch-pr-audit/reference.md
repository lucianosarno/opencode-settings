# Branch PR audit — team reference

## Why audit tags?

Git Graph shows **git refs**, not GitHub PR state. Unmerged branches look equally "pending". Shared `audit/*` tags on branch tips give everyone the same visual hint in Git Graph after fetch.

## Install for the team

### Option A — per repository (recommended)

Commit this folder to the repo:

```text
.cursor/skills/branch-pr-audit/
├── SKILL.md
├── reference.md
└── scripts/
    └── audit.py
```

Cursor loads project skills automatically for anyone who clones the repo.

### Option B — personal skill (any repo)

Copy to `~/.config/opencode/skills/branch-pr-audit/` on each developer machine.

### Option C — global command

Add to PATH (example PowerShell profile):

```powershell
function Invoke-BranchPrAudit {
  param([string]$Repo = (Get-Location))
  python "$env:USERPROFILE\.config\opencode\skills\branch-pr-audit\scripts\audit.py" --fetch --apply --push @args
}
Set-Alias branch-pr-audit Invoke-BranchPrAudit
```

## Weekly hygiene (suggested)

Whoever touches stale branches:

```bash
python .cursor/skills/branch-pr-audit/scripts/audit.py --fetch --apply --push
```

Everyone else:

```bash
git fetch --prune --tags
```

Then refresh Git Graph.

## Tag lifecycle

1. Branch tip moves → re-run audit (old tag on previous commit is removed as stale)
2. Branch deleted → stale `audit/*` tag removed on next audit
3. PR merged and branch deleted → tag removed; no orphan if audit runs regularly

## FAQ

**Will this conflict with release tags?**  
No, if everyone respects the `audit/` prefix only for this tool.

**Force push on tags?**  
Yes, per tag, when the branch tip moves. Only `audit/*` refs are affected.

**Branch without PR shows `no-pr` — is it abandoned?**  
Not necessarily. It may be local WIP. The tag means "no GitHub PR found for this head ref."

**Two branches same commit?**  
Tags attach to commits. Two branches at the same tip share one tag name per branch audit row (each branch gets its own tag; if tips coincide, tags point to the same commit — expected).
