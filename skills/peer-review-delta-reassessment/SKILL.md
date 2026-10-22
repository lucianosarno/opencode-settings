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
| `PROGRAM_DIR` | `{PEER_REVIEW_ROOT}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` (holds `reassessment.md`) |
| `CHANGE_FILE` | `{PEER_REVIEW_ROOT}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md` |

## Before every run

1. Read this skill and [reference.md](reference.md).
2. Confirm `PEER_REVIEW_ROOT` and that `program_manifest.md` exists (process contract: `revision_rounds.md`).
3. Status of the run:

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "<PEER_REVIEW_ROOT>" --program-dir "<PROGRAM_DIR>" status
```

4. Application status of every change (derived, never stored in the change file):

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "<PEER_REVIEW_ROOT>" changes-status
```

5. Never paraphrase process prompts — pass paths. Reuse orchestrator Task slug rules — no silent model swap.

## Hard rules

| Rule | Detail |
|------|--------|
| **Parent owns user I/O** | Subagents write files only; pause on human gates. |
| **Accepted changes only** | A reassessment run covers `accepted` change files. `proposed`, `rejected`, `superseded` are `n/a`. |
| **Impact per change id** | Each domain's `impact_by_domain/{domain}.md` has one `\| PC-… \| touch\|no-touch \| reason \|` row per change id. A domain is touch if any row is touch. |
| **Upstream coherence** | Promote a `no-touch` domain to `touch` (every row) when an earlier domain is touch and the file lacks `coherence_ok: true`. |
| **Frozen after approval** | `approve-impact` writes `touch_order` and `run_status: approved`. Do not add, drop, or reorder touch domains afterwards. A new gap opens a new reassessment. |
| **Execution sequential** | Touch domains in catalog order; never start the next domain until the prior is **accepted**. |
| **Round id = run timestamp** | Every touch domain's revision round uses the reassessment timestamp as its round id. |
| **Abandon only before execution** | `abandon --reason` is allowed for `draft`, `awaiting_plan_approval`, `approved`. |
| **No phases 6–10** | Each touch domain = new timestamped round + orchestrator 0–5. |
| **Do not invent deltas** | Change files must be concrete; if unclear, pause for steward. |

## Workflow

### A — Record and scope the changes

Record one program-change file per stakeholder request. The filename suffix is a short meaning slug; the id stays `PC-YYYYMMDD-NNN`. Slug rules: `revision_rounds.md`. Disposition starts as `proposed`; the steward changes it to `accepted` (edit the front matter) before a run can cover it.

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" record-change \
  --meaning "taxonomy flexibility" --title "…" --summary "…" --disposition accepted
```

Open the run for those ids (it starts as `draft`):

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --cause "<cause>" scaffold \
  --change-id PC-YYYYMMDD-001 --change-id PC-YYYYMMDD-002 --summary "…"
```

### B — Impact assessment

1. For each domain (script: `list-domains`), dispatch an **impact subagent** with [prompts/impact_subagent_wrapper.md](prompts/impact_subagent_wrapper.md). Parallel OK. Each writes its effect table, one row per change id listed in `reassessment.md`.
2. Rollup (fails until every domain has a row for every change id; moves the run to `awaiting_plan_approval`):

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" rollup-impact
```

3. **Pause** — the steward reads `impact_assessment.md`, then approves:

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" approve-impact
```

### C — Sequential execution (touch domains)

`next-action` returns the next domain, its `round_id`, and its `change_ids`:

1. Mark the domain `in_progress` and open its revision round. Every touch domain uses the same round id (the run timestamp):

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" \
  set-domain-status --domain "<domain>" --status in_progress --round-id "<ROUND_ID>"
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py init-round \
  --domain-root "<PEER>/<domain>" --kind revision --round-id "<ROUND_ID>" \
  --reassessment-ref "<PROGRAM_DIR>/reassessment.md" --change-id "<PC-…>" [--change-id …] \
  --summary "…"
```

Git: create `delta/<ROUND_ID>_<cause>` from `develop` before the first domain, and one `feature/<domain>-<ROUND_ID>` per domain from that branch (`process/standards/git_flow.md`).

2. Run **peer-review-orchestrator** on the new round through phase 5, including the phase-2/4/5 `guard` and the phase-5 boundary audit.
3. Mark `awaiting_human` and **pause** for steward review.
4. On approval:

```bash
python scripts/delta_orchestrator.py --peer-review-root "<PEER>" --program-dir "<PROGRAM_DIR>" \
  accept-domain --domain "<domain>"
```

`accept-domain` refuses unless the domain is `awaiting_human`. It sets `current.json` to `accepted` and updates `run_status` (`executing`, then `complete` after the last touch domain).

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
