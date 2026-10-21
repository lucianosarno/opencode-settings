---
name: peer-review-delta-reassessment
description: >-
  Product-wide delta reassessment after stakeholder modifications: impact subagents
  per domain, rollup plan, human approval, then sequential revision rounds (phases 0–5)
  via peer-review-orchestrator with human gates between domains. Use when the user asks
  for delta reassessment, peer-review delta, reavaliar após mudanças do stakeholder,
  program_changes, or /peer-review-delta-reassessment. Legacy: phases 6–10 and
  peer-review-impact-review are obsolete.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Peer review delta reassessment (product-wide)

After accepted peer-review rounds exist, stakeholder / product modifications are handled as a **program change**, not as phases 6–10 inside one domain.

Depends on [peer-review-orchestrator](../peer-review-orchestrator/SKILL.md) for each domain’s phases 0–5. Process contract: `llms_peer_review/process/standards/revision_rounds.md`.

**Parent stays thin:** dispatch impact subagents (one per domain) and orchestrator runs; do not load every domain stack into one context window.

## Constants

| Symbol | Default |
|--------|---------|
| `SKILL_ROOT` | `~/.config/opencode/skills/peer-review-delta-reassessment` |
| `ORCH_ROOT` | `~/.config/opencode/skills/peer-review-orchestrator` |
| `PEER_REVIEW_ROOT` | Consumer folder that contains `d0X_*` domains |
| `PROGRAM_DIR` | `{PEER_REVIEW_ROOT}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` |
| `CHANGE_FILE` | `{PEER_REVIEW_ROOT}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md` |

## Before every run

1. Read this skill and [reference.md](reference.md).
2. Confirm `PEER_REVIEW_ROOT` and fill / scaffold the change pack.
3. Status:

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "<PEER_REVIEW_ROOT>" --cause "<cause>" status
```

4. Never paraphrase process prompts — pass paths.
5. Reuse orchestrator Task slug rules — no silent model swap.

## Hard rules

| Rule | Detail |
|------|--------|
| **Parent owns user I/O** | Subagents write files only; pause on human gates. |
| **Impact via subagents** | One Task per domain for `impact_by_domain/{domain}.md` (parallel OK). |
| **Execution sequential** | Touch domains in catalog order; never start the next domain until the prior is **accepted**. |
| **Upstream coherence** | Each revision pins latest accepted earlier domains (`upstream_pins`). Promote `no-touch`→`touch` when upstream touches and coherence is not proven. |
| **No phases 6–10** | Each touch domain = new timestamped round + orchestrator 0–5. |
| **Do not invent deltas** | Change pack must be concrete; if unclear, pause for steward. |

## Workflow

### A — Impact assessment

Record one program-change file per stakeholder request. The filename suffix is a short meaning slug (same idea as `{cause}` on the run folder). The id stays `PC-YYYYMMDD-NNN`. Slug rules: `revision_rounds.md`.

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" record-change \
  --meaning "taxonomy flexibility" --title "…" --summary "…"
```

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --cause "<cause>" scaffold --summary "…"
```

1. For each domain under `PEER_REVIEW_ROOT` (script: `list-domains`), dispatch an **impact subagent** with [prompts/impact_subagent_wrapper.md](prompts/impact_subagent_wrapper.md). Parallel OK.
2. Each writes `PROGRAM_DIR/impact_by_domain/{domain}.md` (`verdict: touch|no-touch`, severity, risks). Remove `PENDING_IMPACT_SUBAGENT` / `TODO_IMPACT` markers.
3. Rollup:

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" rollup-impact
```

4. **Pause** — steward approves the plan, then:

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" approve-impact
```

### B — Sequential execution (touch domains)

For each domain in touch order (`status` / `next-action`):

1. Refresh pins + open revision round. `--round-id` is the reassessment timestamp (`next-action` returns it as `round_id`) and is the same for every touch domain of this run:

```bash
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py init-round \
  --domain-root "<PEER>/<domain>" --kind revision --round-id "<ROUND_ID>" \
  --peer-review-root "<PEER>" --change-pack "<PROGRAM_DIR>/change_pack.md" \
  --summary "…"
```

Git: create `delta/<ROUND_ID>_<cause>` from `develop` before the first domain, and one `feature/<domain>-<ROUND_ID>` per domain from that branch. See `process/standards/git_flow.md`.

2. Mark `in_progress` in the program log; run **peer-review-orchestrator** on the new `REVIEW_ROOT` through phase 5.
3. Mark `awaiting_human`; **pause** for steward review.
4. On approval:

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" \
  accept-domain --domain "<domain>"
```

5. Next domain. When `next_action` is `done`, write a short coherence note in `execution_log.md`.

## Return contract (impact / orchestrator subagents)

Same family as orchestrator:

```text
STATUS: DONE | NEEDS_USER | BLOCKED
SUMMARY: <one line>
FILES_WRITTEN:
- <path>
PENDING_USER:
- <path or "none">
NOTES: <optional>
```

## Additional resources

- [reference.md](reference.md) — paths, promotion rules, CLI
- [examples.md](examples.md) — generic product-change walkthrough (no consumer-specific paths)
- [templates/](templates/) — change pack, impact, execution log
- [prompts/impact_subagent_wrapper.md](prompts/impact_subagent_wrapper.md)
