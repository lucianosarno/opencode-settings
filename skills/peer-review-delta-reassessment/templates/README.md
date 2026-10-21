# Templates

| File | Role |
| --- | --- |
| `change_pack.md` | Product-wide delta SSOT |
| `impact_assessment.md` | Parent rollup stub (filled by `rollup-impact`) |
| `impact_by_domain/_template.md` | Per-domain impact (impact subagent output) |
| `execution_log.md` | Touch-domain execution statuses |
| `round.md` | Optional reference for revision round front matter (orchestrator `init-round` writes the live file) |

Program folder naming: `program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` (timestamp **first**).

One stakeholder change is `program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md`, written by `record-change` (not from these templates). `{meaning}` is a short slug; the id is the `PC-YYYYMMDD-NNN` prefix. Rules: `process/standards/revision_rounds.md`.
