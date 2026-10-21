# Delta reassessment — reference

## Paths

| Concept | Pattern |
|---------|---------|
| Peer review root | Consumer folder with `d01_*`, `d03_*`, … |
| Program change file | `{peer_review_root}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md` |
| Program folder | `{peer_review_root}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` |
| Change pack | `{program}/change_pack.md` |
| Per-domain impact | `{program}/impact_by_domain/{domain}.md` |
| Rollup | `{program}/impact_assessment.md` |
| Execution | `{program}/execution_log.md` |
| Domain round | `{peer_review_root}/{domain}/{YYYYMMDDTHHMMSSZ}/` |
| Active round | `{domain}/current.json` |
| Process contract | `{llms_peer_review}/process/standards/revision_rounds.md` |
| Orchestrator | `~/.config/opencode/skills/peer-review-orchestrator` |

Timestamp **prefixes** program folders and round ids so lexical sort = chronological order. One reassessment run uses one timestamp: that prefix is the round id of every touch domain's revision round (`{peer_review_root}/{domain}/{YYYYMMDDTHHMMSSZ}/`). Each change file keeps the id `PC-YYYYMMDD-NNN` and adds `_{meaning}` so a directory listing shows what the change is about (same role as `{cause}` on the folder). `record-change` writes that name. Slug rules live only in `process/standards/revision_rounds.md`.

## Obsolete (do not extend)

- `changes_log/{cause}_delta_reassessment/` under a single domain
- Phases `phase6_*` … `phase10_*`
- Slot verdicts REDO/PATCH/NONE / legacy `peer-review-impact-review`

## Impact file contract

Required machine-readable lines (also human prose OK):

```text
verdict: touch
severity: high
```

Optional:

```text
coherence_ok: true
```

If an **earlier** catalog domain is `touch` and this domain stays `no-touch` **without** `coherence_ok: true`, `rollup-impact` promotes it to `touch` and sets `promoted_for_upstream_coherence: true`.

## Execution statuses

`pending` → `in_progress` → `awaiting_human` → `accepted` (or `skipped`).

## CLI

```bash
# One stakeholder change (filename PC-YYYYMMDD-NNN_{meaning}.md)
python scripts/delta_orchestrator.py --peer-review-root PEER record-change --meaning "taxonomy flexibility" --title "Taxonomy flexibility" --summary "…"

# Scaffold
python scripts/delta_orchestrator.py --peer-review-root PEER --cause taxonomy_fees scaffold --summary "…"

# Domains present
python scripts/delta_orchestrator.py --peer-review-root PEER list-domains

# After impact subagents
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG rollup-impact
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG approve-impact

# Loop
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG next-action
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG set-domain-status --domain d01_scope --status in_progress --round-id …
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG accept-domain --domain d01_scope
```

## Upstream pins

`orchestrator.py init-round --kind revision` writes `upstream_pins` from each earlier domain’s `current.json`. After accepting domain X in this program, later domains’ new rounds pick up the new pin automatically on their `init-round`.
