# Peer review orchestrator — reference

## Path resolution

| Concept | Pattern |
|---------|---------|
| Process root | `LLMS_PEER_REVIEW_ROOT` from `config/settings.json` (override `--llms-root`) |
| Consumer workspace | Any repo — **do not** assume shortlist/prompts live in the cwd |
| Repo root | parent of `LLMS_PEER_REVIEW_ROOT` |
| Shortlist (default) | `{repo}/tools/llm_selection/reports/ranking_shortlist_cursor_capability_weighted_latest.json` |
| Generic phase prompt | `{LLMS_PEER_REVIEW_ROOT}/phases/phase{N}_*.md` |
| Domain standards | `{LLMS_PEER_REVIEW_ROOT}/domains/{domain_code}/` (fallback: `standards/domains/{domain_code}/`) |
| Domain phase override | `{domain}/phases/phase{N}_*.md` |
| Review artifacts | `{REVIEW_ROOT}/…` (timestamped round folder) |
| Domain folder | `{peer_review_root}/{domain}/` with `current.json` |
| Round id | `YYYYMMDDTHHMMSSZ`, one per review, shared by every domain folder of that review |
| Revision contract | `{LLMS_PEER_REVIEW_ROOT}/standards/revision_rounds.md` |

### Domain code from review folder

Prefer parent domain folder when `REVIEW_ROOT` is a round id (`20260401T120000Z` → parent `d06_…`).
Otherwise folder name prefix: `d06_verification_assurance` → domain folder `d06_verification_assurance`.

Also read `phase0_setup.md` / `round.md` for explicit domain paths under **Deliverable profile** /
**Domain standards**.

### Precedence (from `overview.md`)

If `{domain}/phases/phaseN_*.md` exists → use it; undefined parts fall back to generic
`process/phases/phaseN_*.md`.

Cross-cutting standards (always relevant):

- `standards/sources.md`, `standards/relevant_questions.md`, `standards/file_structure.md`, `standards/client_deliverables.md`
- Domain `methodology.md`, `deliverables.md`, `file_structure.md` when present
- Domain `sources/sources.md` when present (catalog); citations point at `sources/normalized/<file>.md#slug` clean mirrors — open those excerpts for claims, not only the URL list. Layout: `{domain}/sources/{sources.md, raw/, normalized/}`

## Phase folder map

All phases live under the **round** folder (`REVIEW_ROOT`).

| Phase | Review folder | Entry criterion |
|-------|---------------|-----------------|
| 0 | `phase0_setup.md` (+ `round.md`) | Round created (`init-round`); user confirmed frame |
| 0 | `phase0_setup.md` (+ `round.md`), `program_manifest.md` at peer-review root | Round created; manifest frozen |
| 1 | `phase1_questions/proposals/`, `critiques/`, `revisions/`, `decisions/{pair_id}/`, `decisions/_index.md`, `coverage.md`, `escalations.md` (when needed) | Phase 0 done; one cycle for all pairs |
| 2 | `phase2_initial_proposals/llm{N}_{alias}/` (`overview.md` + `artifact_manifest.json`) | Phase 1 cycle complete and stakeholder gate clear |
| 3 | `phase3_crossed_critiques/llm{i}_vs_llm{j}.md` | Phase 2 all overviews and manifests |
| 4 | `phase4_final_proposals/llm{N}_{alias}/` (+ `artifact_manifest.json`, `_internal/post_critique_revision_log.md` when N>1) | Phase 3 all ordered pairs |
| 5 | `phase5_unified_answer_{leader}/` (+ manifest, `_internal/consolidation_matrix.md` when N>1, `_internal/boundary_audit.json`) | Phase 4 complete; audit `pass` |

Pair id: `{dX_id}_vs_{dY_id}` with the short domain id (`d04b_contracts_draft` → `d04b`). Decision file: `pr{priority}tp{tp}cl{cl}_{slug}.md` (see `phase1_questions.md`).

**Revisions:** `init-round --kind revision --round-id <reassessment ts> --reassessment-ref <run>/reassessment.md --change-id <PC-…>` (same phases 0–5). Product-wide programs: **peer-review-delta-reassessment** under `program_changes/{datetimestamp}_{cause}/`. Do not use obsolete phases 6–10.

CLI helpers: `init-round`, `resolve-review-root`, `set-current`, `phase1-gate`, `guard`.

## Model map (shortlist-first)

Dispatch uses **Cursor Task** `model` slugs. Primary ranking source:

`ranking_shortlist_cursor_capability_weighted_latest.json` (billing=`cursor`, track=`capability_weighted`).

### Application key selection

| Peer-review phase | Shortlist application phase | Prefer |
|-------------------|-----------------------------|--------|
| 0, 1, 2, 4 | 2 | `{dXX}_*_phase2` then `generic_phase2_proposal` |
| 3 | 3 | `{dXX}_*_phase3` → `generic_phase3_critique` → domain phase2 |
| 5 | 5 | `{dXX}_*_phase5` then `generic_phase5_leader` |

Optional `--project finance` selects overlays like `d06_architecture_phase5_finance`.

### llm_code → Task slug

[config/task_model_map.json](config/task_model_map.json):

- Only `task_allow_list` targets are dispatchable.
- Effort variants (`gpt-5-6-luna-low`, `…-medium`, `…-non-reasoning`, …) collapse to one Task slug / **family**. Ranking keeps the winning `llm_code` score; the Task `model` is the UI-default effort slug on `task_allow_list` (today: `gpt-5.6-luna-low`, `gpt-5.6-sol-none`). That is a Cursor allow-list limit, not a second ranking pass.
- Unmapped rows (e.g. `mimo-v2-5-0424`) are skipped — they may still win the lean shortlist for BYOK/non-Task use.
- `folder_alias` maps each family → phase0 folder label (`gpt-5.6-luna` → `gpt56_luna`).

### Slot fill order

- Proposer phases: `llm1`, `llm2`, … in shortlist rank among Task-mapped unique
  **families** and unique **providers** (`family_provider` in the Task map).
- Phase 5: fill **highest** slot first (`llmN` → … → `llm1`) so the conventional leader
  slot gets rank #1. Rank order for phase 5 comes from **pure quality**
  (`ranking_calculation_latest.json` → `calculation.quality.value`), filtered to the
  phase-2 / phase0 participant families when `leader_selection.among_participants_only`
  is true — **not** from capability_weighted value/cost. See skill `config/settings.json`
  → `leader_selection`.
- Gaps: [models.yaml](models.yaml) (skip families **and** providers already taken).
- Overrides: `{REVIEW_ROOT}/peer_review.models.yaml` > `peer_review.models.local.yaml`.
  A second override from the same vendor is rejected (`provider_collisions` in status).

**Provider diversity (hard):** one peer review never mixes two OpenAI lines (Luna/Sol/Terra/GPT-5.5)
or two Anthropic lines (Fable/Opus/Sonnet/…). Lower-ranked same-vendor rows are skipped with
`duplicate_provider:<Vendor>`; an unresolved slot is preferred over a same-vendor pair.

### Roster sizing (auto seat count)

Config: `roster_sizing` in [config/settings.json](config/settings.json).

| Knob | Role |
|------|------|
| `min_slots` | Always attempt this many seats (fallback may pad). |
| `max_slots` | Hard ceiling. |
| `tau_vs_leader` | Keep seat *k* only if `score_k / score_1 ≥ tau`. |
| `rho_vs_prev` | Keep seat *k* only if `score_k / score_{k-1} ≥ rho` (cliff detector). |

**Cliff/retention run only for candidates after `min_slots`.** A sharp drop between llm2 and llm3 is ignored when `min_slots ≥ 3`. Status / `resolve-shortlist` expose `roster_sizing` (`chosen_k`, `stop_reason`, ratios). `--slots N` forces seat count and sets `applied: false`.

`phase0_setup.md` names folder suffixes from `suggested_folder_suffix`. The orchestrator
looks up **slot** (`llm4`, `llm5`) for the Task `model` parameter. Status reports
`alias_mismatches` when phase0 labels disagree with the resolved family — fix phase0
before writing artifacts under a stale path.

```bash
python scripts/orchestrator.py resolve-shortlist --domain d06 --phase 2
python scripts/orchestrator.py resolve-model --slot llm5 --domain d06 --phase 5
```

## Participants parsing

Primary source: `phase0_setup.md` table under **Participants** / **Strategist LLMs**.

Columns used:

- **Slot** → order for phase 1 (`llm1`, `llm2`, …) and key for model resolution
- **Model alias** → must match resolved `folder_alias` (e.g. `gpt56_luna`, not a leftover `composer`)
- **Folder suffix** → subfolder name (`llm1_gpt56_luna`, …) = `suggested_folder_suffix`

Phase 1 uses **all** strategist slots in table order.

**Availability** table (`## Availability`, required): one row per participant slot (and the leader when not a participant) with `Result` = `available` and a `YYYYMMDDTHHMMSSZ` stamp in `Checked (UTC)`. `availability_gaps` in status lists every slot that fails; an empty list is the precondition for the roster approval. Revision rounds drop this section on copy (`init_round --kind revision`), so each round re-probes.

Leader (phase 5): **Leader LLM** table → folder like `phase5_unified_answer_fable`
(use the leader slot’s `folder_alias`).

Fallback when phase0 has no table: scan `{REVIEW_ROOT}/phase1_questions/proposals/llm*_*/` directories sorted by name.

## Subagent read list by phase

### Phase 1 (propose / critique / revise / consolidate)

- Process overview + `phase1_questions.md` + `question_pyramid.md` (generic + domain)
- `phase0_setup.md`, `program_manifest.md`, and the parked decisions of pinned earlier rounds that target this domain
- Propose: own drafts only as output; read the manifest order and the parked decisions first
- Critique: the other list's drafts (`phase1_questions/proposals/llm{j}_*`)
- Revise: own critiques and own drafts
- Consolidate (leader): all proposals, critiques, revisions
- Domain `sources/sources.md` when present (and normalized excerpts when a question is grounded in an external fact)

### Phase 2

- Phase 2 prompts + domain deliverables/file_structure
- Phase 0 + phase 1 all Q&A
- Domain methodology
- Domain `sources/sources.md` + relevant `sources/normalized/*.md#slug` excerpts for claimed grounding

### Phase 3 (critic *i*)

- Phase 3 prompt
- All phase 2 `overview.md` (+ domain subfolders)
- Phase 1 Q&A
- Domain source mirrors when contesting factual / standards claims

### Phase 4

- Phase 4 prompt
- Own phase 2 proposal + all phase 3 critiques **against own proposal**
- May read others' critiques for context; focus on critiques received
- Re-check domain `sources/sources.md` + normalized excerpts for revised claims

### Phase 5 (leader)

- Phase 5 prompt
- All phase 4 final proposals
- Phase 3 critique history (reference)
- Domain source mirrors for claims kept or improved in the unified answer

## Phase 3 critique file count

For *N* participants: **N × (N − 1)** files `llm{i}_vs_llm{j}.md` for all ordered pairs *i ≠ j*.

Example *N=5*: 20 files.

## Phase 1 gate signals

The cycle is **complete** when: every participant has at least one draft in `proposals/` and in `revisions/`; every ordered critique file exists; `decisions/_index.md` and `coverage.md` exist; every pair from this domain forward has a `coverage.md` row; and every decision file name follows `pr{NNN}tp{NNN}cl{NNN}_{slug}.md` inside its pair folder.

The **stakeholder gate** is open (phase 1 pauses) while any own decision with `Origin: stakeholder-appetite` and `Enters this deliverable: yes` has an empty `## Stakeholder decision` section. Parked stakeholder decisions from earlier pinned rounds that target this domain block phase 2 instead. An explicit deferral or withdrawal in the section counts as answered.

## NEEDS_USER (phases 2–5)

Subagent returns `NEEDS_USER` only when a **stakeholder-owned** decision blocks deliverables
and cannot be deferred in writing. Should be rare after phase 1.

Parent agent must not advance until user responds.
