# Peer review orchestrator — examples

## Start d06 from phase 1 (any consumer repo)

User message:

```text
@peer-review-orchestrator Continue peer review at
00_docs/peer_review/d06_verification_assurance/
```

Orchestrator actions (cwd may be the product repo, not `llms_peer_review`):

1. `python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py --review-root "00_docs/peer_review/d06_verification_assurance"`
2. Read status → `shortlist_path` points at `llms_peer_review/.../ranking_shortlist_cursor_capability_weighted_latest.json`
3. `resolve-model --slot llm2 --phase 1` → Task slug from shortlist/fallback
4. Single Task for llm2 with that `model` and prior Q&A paths listed
5. Gate llm2 → if pending, pause user; else continue

## Resolve lineup before phase 2

```bash
python ~/.config/opencode/skills/peer-review-orchestrator/scripts/orchestrator.py resolve-shortlist --domain d06 --phase 2
```

Use each slot’s `model_slug` in parallel Task calls. Rows with `source: shortlist` came from the
capability_weighted cursor file; `fallback_models_yaml` filled gaps after Task filtering.
`roster_sizing` shows `chosen_k` / `stop_reason` (auto seat count; cliff only after `min_slots`).
Force a count with `--slots N` when needed.

## Run phase 2 for all participants

After phase 1 complete:

1. `resolve-prompt --phase 2`
2. `resolve-shortlist --review-root … --phase 2`
3. One parallel Task per participant with resolved slugs
4. Verify `phase2_initial_proposals/llm*/overview.md`

## Phase 5 leader

1. Confirm leader slot from phase0 (e.g. `llm5`)
2. `resolve-model --slot llm5 --domain d06 --phase 5` → quality winner among
   participants (`leader_selection`: pure `calculation.quality`, not value/cost).
   Check `leader_selection.applied` / `leader_llm_code` in the JSON.
3. One Task with that slug → `phase5_unified_answer_*`
4. Validate overview + consolidation matrix

## Override one seat for a single review

Create `{REVIEW_ROOT}/peer_review.models.yaml`:

```yaml
llm4: claude-sonnet-5-thinking-high
```

That seat wins over shortlist; other seats still come from shortlist/fallback.
Do **not** override a second Anthropic (or second OpenAI) seat in the same file — the
orchestrator rejects same-vendor collisions (`provider_collisions` in status).
