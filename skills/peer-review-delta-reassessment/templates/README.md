# Templates

| File | Role |
| --- | --- |
| `change_pack.md` | Index of the run's change ids (the statements stay in `changes/`) |
| `impact_assessment.md` | Parent rollup stub (written by `rollup-impact`) |
| `impact_by_domain/_template.md` | Per-domain impact: one effect row per change id |
| `execution_log.md` | Touch-domain execution statuses (written by the orchestrator) |
| `round.md` | Reference for revision round front matter (`reassessment_ref`, `change_ids`); `init-round` writes the live file |

`reassessment.md` has no template here: `scaffold` writes it, and the orchestrator updates `run_status` and `touch_order`.

Program folder naming: `program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` (timestamp **first**).

One stakeholder change is `program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md`, written by `record-change` (not from these templates). `{meaning}` is a short slug; the id is the `PC-YYYYMMDD-NNN` prefix. Rules: `process/standards/revision_rounds.md`.
