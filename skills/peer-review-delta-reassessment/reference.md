# Delta reassessment — reference

## Paths

| Concept | Pattern |
|---------|---------|
| Peer review root | Consumer folder with `d01_*`, `d03_*`, … |
| Program change file | `{peer_review_root}/program_changes/changes/PC-YYYYMMDD-NNN_{meaning}.md` |
| Program folder | `{peer_review_root}/program_changes/{YYYYMMDDTHHMMSSZ}_{cause}/` |
| Change pack | `{program}/change_pack.md` (index of the run's change ids) |
| Run contract | `{program}/reassessment.md` (`change_refs`, `run_status`, `touch_order`) |
| Per-domain impact | `{program}/impact_by_domain/{domain}.md` (one effect row per change id) |
| Rollup | `{program}/impact_assessment.md` |
| Execution | `{program}/execution_log.md` |
| Domain round | `{peer_review_root}/{domain}/{YYYYMMDDTHHMMSSZ}/` (id = run timestamp for delta rounds) |
| Active round | `{domain}/current.json` |
| Program manifest | `{peer_review_root}/program_manifest.md` |
| Process contract | `{llms_peer_review}/process/standards/revision_rounds.md` |
| Orchestrator | `~/.config/opencode/skills/peer-review-orchestrator` |

The timestamp prefix of the run folder is the review round id. Each change file keeps the id `PC-YYYYMMDD-NNN` and adds `_{meaning}` so a directory listing shows what the change is about. `record-change` writes that name. Slug rules live only in `process/standards/revision_rounds.md`.

## Obsolete (do not extend)

- `changes_log/{cause}_delta_reassessment/` under a single domain
- `change_pack_ref` as the only link of a round (use `reassessment_ref` + `change_ids`; `change_pack_ref` is legacy only)
- Phases `phase6_*` … `phase10_*`
- Slot verdicts REDO/PATCH/NONE / legacy `peer-review-impact-review`
- A per-domain `verdict:` line as the only impact signal

## Impact file contract

One row per change id of the run:

```text
| change_id | effect | reason |
| --- | --- | --- |
| PC-20261015-001 | touch | why |
| PC-20261015-002 | no-touch | why |
```

The domain is `touch` when any row is `touch`. A domain with no `coherence_ok: true` that stays `no-touch` after an earlier domain is `touch` is promoted: every row becomes `touch` and the file gets `promoted_for_upstream_coherence: true`. A row is missing → `rollup-impact` refuses.

## Run status and execution

`run_status`: `draft` → `awaiting_plan_approval` (after rollup) → `approved` (after approve-impact; `touch_order` frozen) → `executing` (first domain leaves `pending`) → `complete` (every touch domain `accepted`). `abandoned` is terminal and only allowed before `executing`.

Execution status per touch domain (`execution_log.md`): `pending` → `in_progress` → `awaiting_human` → `accepted`. `skipped` is illegal for a touch domain.

Application status per change (`changes-status`, derived): `n/a` (proposed, rejected, superseded), `uncovered`, `assessing`, `planned`, `in_progress`, `partially_applied`, `applied`. A newer draft run that lists the id is reported as `open_recheck` and does not change the governing run's status.

## CLI

```bash
# Record a stakeholder change (filename PC-YYYYMMDD-NNN_{meaning}.md); set disposition accepted to allow a run
python scripts/delta_orchestrator.py --peer-review-root PEER record-change --meaning "taxonomy flexibility" --title "Taxonomy flexibility" --summary "…" --disposition accepted

# Open a run for accepted change ids (status draft)
python scripts/delta_orchestrator.py --peer-review-root PEER --cause taxonomy_fees scaffold --change-id PC-20261015-001 --summary "…"

# Domains present
python scripts/delta_orchestrator.py --peer-review-root PEER list-domains

# After impact subagents
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG rollup-impact
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG approve-impact

# Loop
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG status
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG set-domain-status --domain d01_scope --status in_progress --round-id RUN_TS
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG accept-domain --domain d01_scope

# Cross-run view and stop
python scripts/delta_orchestrator.py --peer-review-root PEER changes-status
python scripts/delta_orchestrator.py --peer-review-root PEER --program-dir PROG abandon --reason "…"
```

## Upstream pins

`orchestrator.py init-round --kind revision` writes `upstream_pins` from each earlier domain’s `current.json`. After accepting domain X in this program, later domains’ new rounds pick up the new pin automatically on their `init-round`.
