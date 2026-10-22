---
name: peer-review-orchestrator
description: >-
  Orchestrates multi-LLM peer reviews using Cursor subagents. Reads prompts from
  llms_peer_review/process/phases and domain overrides under process/domains.
  Resolves Task model slugs from ranking_shortlist_cursor_capability_weighted_latest.json
  (llm_selection). Use when running or continuing peer review phases (phase0–phase5)
  inside a timestamped round folder, creating rounds (init-round), resuming a review,
  or when the user mentions peer review orchestration, llms_peer_review, or phase1–phase5
  multi-LLM workflow. For product-wide stakeholder deltas after an accepted round, hand
  off to peer-review-delta-reassessment (new revision rounds — not phases 6–10).
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Peer review orchestrator

Orchestrate the peer-review process defined in `llms_peer_review` by dispatching **subagents**
(separate Cursor agent sessions, each with its own LLM) while **you** (the parent agent) handle
all user interaction.

Works from **any consumer repo**: process prompts and the ranking shortlist live under the
`llms_peer_review` install path in [config/settings.json](config/settings.json), not under the
current workspace.

**REVIEW_ROOT** is the **timestamped round folder** (`{peer_review_root}/{domain}/{YYYYMMDDTHHMMSSZ}/`), not the domain folder. Create rounds with `init-round`. Product-wide deltas: skill **peer-review-delta-reassessment**.

## Constants

| Symbol | Default |
|--------|---------|
| `LLMS_PEER_REVIEW_ROOT` | `config/settings.json` → `llms_peer_review_process_root` |
| `SHORTLIST` | `{repo}/tools/llm_selection/reports/ranking_shortlist_cursor_capability_weighted_latest.json` |
| `REVIEW_ROOT` | Timestamped round folder (`…/d0X/YYYYMMDDTHHMMSSZ/`) |
| `DOMAIN_ROOT` | Parent domain folder (`…/d0X/`) |

`{repo}` = parent of `LLMS_PEER_REVIEW_ROOT` (`process/` → repo root). Override with
`--llms-root` / `--shortlist` when paths differ.

## Before every run

1. Read this skill fully.
2. Read [reference.md](reference.md) for phase folders and domain resolution.
3. Resolve models via **shortlist** (see **Model configuration**).
4. Ensure a round exists (or create one). Use the review's shared round id: generate one `YYYYMMDDTHHMMSSZ` value when the review starts and pass it to every domain. Omitting `--round-id` generates a fresh timestamp, which is only correct for the first domain of a review:

```bash
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py init-round \
  --domain-root "<DOMAIN_ROOT>" --kind initial --round-id "<REVIEW_ROUND_ID>"
```

`init-round` refuses to run while another domain of the same peer-review root has an open round (`in_progress` or `awaiting_human`) with a different id. Git branch naming for the review is in `llms_peer_review/process/standards/git_flow.md`.

5. Run status (round path or domain via `current.json`):

```bash
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py --review-root "<REVIEW_ROOT>"
# or:
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py --domain-root "<DOMAIN_ROOT>"
```

6. Read `REVIEW_ROOT/phase0_setup.md` and `REVIEW_ROOT/round.md` — participants, leader, domain, revision context, `upstream_pins`.
7. Never paraphrase process prompts when building subagent instructions; pass file paths and
   tell the subagent to read them.

## Hard rules

| Rule | Detail |
|------|--------|
| **Phase 1 is one cycle** | Propose → critique → revise → consolidate, once for the whole domain (all pairs). It is not a Q&A chain per LLM (`process/standards/question_pyramid.md`). Propose and critique fan out in parallel; the leader consolidates. |
| **Frozen manifest** | Phase 0 requires `{peer_review_root}/program_manifest.md` (`Frozen: yes`, `Order:`) for initial rounds. Revision rounds of a delta use the approved reassessment `touch_order`. Never add, drop, or reorder domains inside a run. |
| **Stakeholder gate** | Unanswered `stakeholder-appetite` decisions with `Enters this deliverable: yes` pause phase 1. Unanswered parked ones from earlier domains (targeting this domain) pause phase 2. Only the user writes `## Stakeholder decision`. |
| **Parent owns user I/O** | Subagents do not ask the user questions in chat. They write `.md` files; you pause and notify the user. |
| **Phase 2–4 parallel OK** | One subagent per participant per phase, same turn — unless any returns `NEEDS_USER`. |
| **NEEDS_USER stops the phase** | Do not start the next participant or next phase until resolved. |
| **Domain precedence** | Domain `phases/phaseN_*.md` overrides generic `process/phases/phaseN_*.md`. See [reference.md](reference.md). |
| **No silent model swap** | If a slug is missing from config or rejected by Task, stop and tell the user. |
| **Shortlist before YAML fallback** | Dispatch `model` from cursor capability_weighted shortlist (Task-mapped). `models.yaml` only fills gaps. |
| **One vendor per peer review** | Never assign two participants from the same provider (OpenAI, Anthropic, Cursor, …) in one review. Skip lower-ranked same-vendor rows; reject YAML overrides that collide. Prefer leaving a slot unresolved over violating this. |
| **Auto roster size** | Default seat count from `roster_sizing` (min floor + tau/rho on scores). Cliff/retention apply only **after** `min_slots`. `--slots N` forces a count. |
| **Alias matches resolved family** | Phase0 folder/alias must match `folder_alias`. Non-empty `alias_mismatches` → fix phase0 before writing. |
| **Ground in domain source mirrors** | When the domain has `sources/sources.md`, proposers / critics / leader must open it and the cited `sources/normalized/*.md#slug` excerpts that back non-trivial claims (or the original URL if a mirror is missing). Citation rules: `process/standards/sources.md`. |
| **Upstream coherence** | On revision rounds, honor `upstream_pins` in `round.md` — cite the pinned accepted rounds of earlier domains (`revision_rounds.md`). |
| **Boundary gate (phases 2, 4, 5)** | Each proposal folder has `artifact_manifest.json`. Run `orchestrator.py guard --proposal-folder <folder>` (wraps `tools/process_guard validate`) before delivery; a non-zero exit blocks the phase. |
| **Independent phase-5 audit** | Phase 5 needs `_internal/boundary_audit.json` with `status: pass`, `independent_of_leader: true`, and no `block` or `needs_human` finding. The auditor is a `boundary_adversary` subagent, never the leader (`process/standards/boundary_guard.md`). |
| **Revision round of a delta** | `init-round --kind revision` takes `--reassessment-ref` and one `--change-id` per change this domain applies. The round id must equal the reassessment timestamp, and the run must be `approved` or `executing`. |
| **No phases 6–10** | Revisions = new round + phases 0–5. Hand product-wide deltas to **peer-review-delta-reassessment**. |

## Model configuration

**Primary source (Cursor IDE billing):** lean shortlist produced by `llm_selection`:

`tools/llm_selection/reports/ranking_shortlist_cursor_capability_weighted_latest.json`

Shape: `{"fv":"…","applications":{"app":[["llm_code", score],…]}}`.

Resolution (scripted — do not hand-pick):

1. Pick application key from domain + phase (`d06_architecture_phase2`, else generic).
2. Walk ranked rows → map `llm_code` via [config/task_model_map.json](config/task_model_map.json).
3. Skip codes not on the Task allow-list; collapse effort variants to one **family**.
4. Keep **at most one family per provider** (`family_provider` in the Task map — e.g. Luna
   and Sol are both OpenAI; Sonnet and Fable are both Anthropic).
5. Auto-size seat count (`roster_sizing` in [config/settings.json](config/settings.json)):
   always take `min_slots` (pad with fallback if shortlist has fewer scored vendors);
   beyond that, keep seat *k* only if `s_k/s_1 ≥ tau` **and** `s_k/s_{k-1} ≥ rho`.
   Gaps inside the minimum floor are **not** cliffs.
6. Assign unique family+provider pairs to slots (`llm1…` proposers). **Phase 5 leader**
   is **not** the top capability_weighted value score: the skill re-ranks
   `ranking_calculation_latest.json` by pure `calculation.quality.value` (no `/ est_cost`)
   and, with `leader_selection.among_participants_only` (default), keeps only families
   already on the phase-2 proposer roster / phase0 participants. Highest slot (`llmN`)
   gets that quality winner so phase0 can name them as Leader.
7. Fill remaining seats from [models.yaml](models.yaml), still skipping used providers.
8. Name phase0 **Model alias** / **Folder suffix** from each slot’s `folder_alias` /
   `suggested_folder_suffix` (see `task_model_map.json`). Never keep a stale alias
   (e.g. `composer`) when the resolved family is different (e.g. `gpt-5.6-luna`).

| Precedence | File / source |
|------------|----------------|
| Highest | `{REVIEW_ROOT}/peer_review.models.yaml` |
| | `peer_review.models.local.yaml` |
| Default (proposers/critics) | **shortlist** cursor × capability_weighted |
| Default (phase 5 leader) | **quality** from `ranking_calculation_latest.json` among participants |
| Gap fill | `models.yaml` (auto-synced from ranking summary on `rank --log`) |

### Leader vs proposers (objective rule)

| Role | Score basis | Why |
|------|-------------|-----|
| Proposers / critics (phases 1–4) | `capability_weighted` = `((1+quality)**3) / est_cost_cursor` | Cost-aware roster |
| Leader (phase 5) | Pure `quality` among those participants | Synthesis should use the strongest model in the room, not the best $/quality |

Config: `leader_selection` in [config/settings.json](config/settings.json). If the calculation
report is missing, phase 5 falls back to the capability_weighted shortlist and sets
`leader_selection.error` in the resolve JSON.

### Effort variants vs Task slug

Shortlist may rank `gpt-5-6-luna-low` (or another effort) highest. Cursor Task exposes
only the UI-default effort slug for that family (see `task_allow_list`; today Luna→
`gpt-5.6-luna-low`, Sol→`gpt-5.6-sol-none`). The orchestrator keeps the **winning
llm_code’s score** for family selection, then maps every effort variant to that one Task
slug. Same for Sol/Terra. This is **not** preferring medium over low in the ranking.

### Folder naming (must match resolved family)

| When | Rule |
|------|------|
| Creating / refreshing phase0 | Alias + folder = `folder_alias` / `suggested_folder_suffix` from `resolve-shortlist` |
| Before first artifact for a slot | If `alias_mismatches` is non-empty → **update phase0 and paths first**; do not write under the stale name |
| After artifacts exist for a slot | Path stability — do not silently rename; pause and ask the steward |

Status JSON exposes `alias_mismatches[]` when phase0 labels diverge from the resolved
Task family. Treat a non-empty list as a **hard stop** before dispatch.

```bash
python scripts/orchestrator.py resolve-shortlist --domain d06 --phase 2
python scripts/orchestrator.py resolve-model --slot llm1 --domain d06 --phase 2
python scripts/orchestrator.py list-models --review-root "<REVIEW_ROOT>" --phase 2
```

If Task rejects a slug, tell the user — do not substitute silently.
Regenerate shortlist in the `llms_peer_review` repo: `python tools/llm_selection/llm_selection_tool.py rank --log`.

## Workflow overview

```
init-round → REVIEW_ROOT (timestamped)
Phase 0  → phase0_setup.md + program_manifest.md      [pause if frame unclear]
Phase 1  → propose ∥ → critique ∥ → revise ∥ → consolidate (leader)  [pause on stakeholder gate]
Phase 2  → all participants in parallel + manifest + guard  [pause on NEEDS_USER]
Phase 3  → all critics in parallel                  [pause on NEEDS_USER]
Phase 4  → all participants in parallel + manifest + guard  [pause on NEEDS_USER]
Phase 5  → leader, then boundary_adversary audit + guard    [pause on NEEDS_USER]
---
Product-wide stakeholder modifications → peer-review-delta-reassessment
(new revision rounds per touched domain; not phases 6–10).
```

## Step 0 — Resolve context

```bash
python scripts/orchestrator.py resolve-domain --review-root "<REVIEW_ROOT>"
python scripts/orchestrator.py resolve-prompt --review-root "<REVIEW_ROOT>" --phase <N>
python scripts/orchestrator.py list-participants --review-root "<REVIEW_ROOT>"
python scripts/orchestrator.py resolve-shortlist --review-root "<REVIEW_ROOT>" --phase <N>
```

Load for the subagent prompt bundle:

- `LLMS_PEER_REVIEW_ROOT/overview.md`
- Resolved phase prompt (generic + domain override paths printed by script)
- `REVIEW_ROOT/phase0_setup.md`
- Domain `methodology.md`, `deliverables.md`, `file_structure.md` when they exist
- Domain `sources/sources.md` when present — and encourage opening the cited `sources/normalized/*.md#slug` excerpts that ground claims for that domain (not only the URL list)
- All artifact paths listed in [reference.md](reference.md) for that phase

## Step 1 — Build subagent prompt

Use [prompts/subagent_wrapper.md](prompts/subagent_wrapper.md). Fill every `{{PLACEHOLDER}}`.
Include the **return contract** verbatim:

```text
When finished, respond with exactly these lines (no extra prose before them):

STATUS: DONE | NEEDS_USER | BLOCKED
SUMMARY: <one line>
FILES_WRITTEN:
- <path>
PENDING_USER:
- <path or question id, or "none">
NOTES: <optional>
```

## Step 2 — Dispatch subagent (Task tool)

```
Task(
  subagent_type="generalPurpose",
  model="<from resolve-model / resolve-shortlist>",
  description="<phase N — llmK alias>",
  prompt="<filled wrapper>"
)
```

**Before every Task call**, run `resolve-model --slot llmK --phase N` (or read `participant_models`
/ `dispatch_roster` from status JSON). Use the returned `model_slug` — never invent a slug.

Phase 3: each critic writes **all** `llm{i}_vs_llm{j}.md` files where *i* is their slot and
*j* ≠ *i*.

Phase 5: only the leader slot from `phase0_setup.md`; resolve with `--phase 5` (pure
quality among participants → highest slot first; see `leader_selection`).

## Phase 1 — one cycle, all pairs

Contract: `llms_peer_review/process/phases/phase1_questions.md` and `process/standards/question_pyramid.md`. The cycle runs once for the whole domain. Do not repeat it per pair or per LLM.

1. **Propose (parallel).** One subagent per participant writes `phase1_questions/proposals/{folder_suffix}/dNN_slug.md`. Each draft names its pair (`{this_id}_vs_{target_id}`), target domain, origin, `tp`, and `cl`.
2. **Critique (parallel).** Each participant critiques every other list once: `phase1_questions/critiques/llm{i}_vs_llm{j}.md`. A draft whose pair is wrong is retagged, not split into a new cycle.
3. **Revise (parallel).** Authors update `phase1_questions/revisions/{folder_suffix}/`.
4. **Consolidate (leader).** One subagent writes `decisions/{pair_id}/prNNNtpNNNclNNN_slug.md`, `decisions/_index.md`, `coverage.md` (one row per pair from this domain forward), and `escalations.md` when needed.

Check progress at any time:

```bash
python scripts/orchestrator.py --review-root "<REVIEW_ROOT>"
```

`phases.1.cycle` lists missing proposals, critiques, revisions, coverage rows, and malformed names. `phases.1.stakeholder_gate.own_blockers` lists decision files waiting for the user.

### Phase 1 user pause template

```markdown
## Phase 1 — answers needed

These decisions are waiting for your answer:

- [ ] `path/to/decisions/d03_vs_d03/pr024tp040cl060_....md`

Write your answer under **## Stakeholder decision** in each file (or record a deferral), then tell me "phase 1 answered".
```

Empty `## Stakeholder decision` means not reviewed. Never copy the recommendation into that section.

## Phases 2–4 — parallel protocol

1. Confirm prior phase complete via `orchestrator.py` status.
2. Launch **one Task per participant** in a **single message** (parallel).
3. Collect return contracts.
4. If **any** `NEEDS_USER` → stop; surface `PENDING_USER` list; wait for user.
5. If all `DONE` → validate artifacts (client `overview.md`, `_internal/` peer-process files when N>1, critique pairs, etc.) then next phase.

## Phase 5 — leader only

1. Confirm phase 4 complete for all participants.
2. Single Task for leader model → writes `phase5_unified_answer_{leader}/` (client `overview.md`, `artifact_manifest.json`, `_internal/consolidation_matrix.md` when multi-proposer).
3. Run `orchestrator.py guard --proposal-folder <phase5 folder>`. The only failure allowed before the audit exists is the missing audit.
4. Dispatch a separate `boundary_adversary` subagent (never the leader). It writes `_internal/boundary_audit.json` and does not propose architecture.
5. Re-run `guard`. Deliver only when the status shows `phases.5.boundary_audit` = `pass` and the guard exits 0.

## Resume

When the user says "continue peer review" or names a phase:

1. Run `orchestrator.py --review-root "<REVIEW_ROOT>"` (status).
2. Start at `next_action` from script output — never redo completed slots.
3. Re-read only artifacts required for the current phase.

## Phase 0

If `phase0_setup.md` is missing or incomplete (roles, domains, participants, leader):

- Run phase 0 yourself or via one subagent.
- Prefer `resolve-shortlist --domain <d> --phase 2` (proposers) and `--phase 5` (leader)
  when naming participants.
- Copy each slot’s `folder_alias` / `suggested_folder_suffix` and Task `model_slug` into
  the participants table (do **not** copy stale names from another domain’s phase0).
- **Pause** until the user confirms the frame.
- Do not start phase 1 until `phase0_setup.md` is complete and `alias_mismatches` is empty.

## Validation helpers

```bash
python scripts/orchestrator.py --review-root "<REVIEW_ROOT>"
python scripts/orchestrator.py phase1-gate --review-root "<REVIEW_ROOT>"
python scripts/orchestrator.py resolve-prompt --review-root "<REVIEW_ROOT>" --phase 2
python scripts/orchestrator.py guard --proposal-folder "<REVIEW_ROOT>/phase2_initial_proposals/<folder_suffix>"
python scripts/orchestrator.py resolve-shortlist --domain d06 --phase 2
```

## Progress checklist (copy each turn)

```text
Peer review progress @ REVIEW_ROOT
- [ ] phase0_setup validated (sections complete; program_manifest frozen)
- [ ] phase1 cycle: proposals → critiques → revisions → decisions/coverage
- [ ] phase1 stakeholder gate clear (own_blockers empty)
- [ ] phase2 all overviews + artifact_manifest.json + guard 0
- [ ] phase3 all critique pairs
- [ ] phase4 all final overviews + manifests + guard 0
- [ ] phase5 leader unified answer + manifest + boundary_audit pass + guard 0
Current: ___
Blocking: ___
```

## Additional resources

- Paths, shortlist mapping, artifacts: [reference.md](reference.md)
- Fallback lineup rationale: [models-rationale.md](models-rationale.md)
- Subagent prompt template: [prompts/subagent_wrapper.md](prompts/subagent_wrapper.md)
- Usage examples: [examples.md](examples.md)
