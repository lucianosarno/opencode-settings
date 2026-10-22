# Subagent prompt wrapper

Copy this template into the Task `prompt`. Replace `{{PLACEHOLDERS}}`. Do not shorten process
rules — point to files instead.

---

You are **{{PARTICIPANT_LABEL}}** in a multi-LLM peer review.

## Your assignment

- **Phase:** {{PHASE_NUMBER}} — {{PHASE_NAME}}
- **Review root (round folder):** {{REVIEW_ROOT}}
- **Domain:** {{DOMAIN_CODE}}
- **Folder suffix:** {{FOLDER_SUFFIX}}
- **Round kind:** {{ROUND_KIND}}

## Process (read these files first)

1. `{{LLMS_PEER_REVIEW_ROOT}}/overview.md`
2. `{{LLMS_PEER_REVIEW_ROOT}}/standards/revision_rounds.md` (especially when round kind is `revision`)
3. Generic phase prompt: `{{GENERIC_PHASE_PROMPT_PATH}}`
4. Domain phase override (if any): `{{DOMAIN_PHASE_PROMPT_PATH}}`
5. `{{REVIEW_ROOT}}/round.md` and `{{REVIEW_ROOT}}/phase0_setup.md`
6. Domain standards (when they exist):
   - `{{DOMAIN_STANDARDS_ROOT}}/methodology.md`
   - `{{DOMAIN_STANDARDS_ROOT}}/deliverables.md`
   - `{{DOMAIN_STANDARDS_ROOT}}/file_structure.md`
   - `{{DOMAIN_STANDARDS_ROOT}}/sources/sources.md` (catalog — always load when present)
   - Cited excerpts under `{{DOMAIN_STANDARDS_ROOT}}/sources/normalized/*.md#slug` that ground your claims (not only the URL list; use the original URL if a mirror is missing)
7. Cross-cutting: `{{LLMS_PEER_REVIEW_ROOT}}/standards/relevant_questions.md`,
   `{{LLMS_PEER_REVIEW_ROOT}}/standards/sources.md`,
   `{{LLMS_PEER_REVIEW_ROOT}}/standards/client_deliverables.md` (phases 2–5)

## Prior artifacts (read before writing)

{{PRIOR_ARTIFACTS_LIST}}

## Revision / upstream context (when applicable)

{{REVISION_CONTEXT}}

When `round.md` lists `upstream_pins`, stay coherent with those pinned accepted rounds of earlier domains. Do not cite obsolete upstream rounds when a newer accepted pin exists.

## Instructions

{{PHASE_SPECIFIC_INSTRUCTIONS}}

## Output rules

- Write deliverables under `{{REVIEW_ROOT}}` following domain `file_structure.md`.
- **Do not** ask the user questions in this chat.
- Phase 1: put questions and answers in per-question `.md` files; close session when done.
- Phases 2–5: user questions are **exceptional** — if blocked, return `NEEDS_USER` instead of
  guessing.
- Use English for deliverables unless `phase0_setup.md` says otherwise.
- Ground non-trivial claims in the domain's normalized source excerpts (or original URL if mirror missing), per `{{LLMS_PEER_REVIEW_ROOT}}/standards/sources.md`.

## Return contract

When finished, respond with **exactly** these lines (no extra prose before them):

```
STATUS: DONE | NEEDS_USER | BLOCKED
SUMMARY: <one line>
FILES_WRITTEN:
- <path>
PENDING_USER:
- <path or "none">
NOTES: <optional one line>
```

---

### Phase-specific instruction snippets

**Phase 1 — propose:** Read `program_manifest.md` (or the reassessment `touch_order`) and the parked
decisions from earlier pinned rounds. Write drafts to `phase1_questions/proposals/{{FOLDER_SUFFIX}}/dNN_slug.md`.
Each draft: at least three options, one recommended, `tp`/`cl` with citations, origin, pair, target domain,
enters-this-deliverable flag. Do not write `## Stakeholder decision`.

**Phase 1 — critique:** Write `phase1_questions/critiques/llm{i}_vs_llm{j}.md` covering every draft of the other
list. Check pair, origin, scores, and whether a draft would change an earlier accepted deliverable (then it goes to
`escalations.md`, not to a decision).

**Phase 1 — revise:** Update only your own drafts under `phase1_questions/revisions/{{FOLDER_SUFFIX}}/`.

**Phase 1 — consolidate (leader only):** Write `phase1_questions/decisions/{pair_id}/prNNNtpNNNclNNN_slug.md`,
`decisions/_index.md`, and `coverage.md` (one row per pair from this domain forward, zero rows explained).

**Phase 2:** Write `phase2_initial_proposals/{{FOLDER_SUFFIX}}/overview.md` — **client-facing
solution only** (no model names or peer-review narration) — and `artifact_manifest.json` (sources by role,
owned decision axes, handoffs; see `process/standards/boundary_guard.md`). Run
`orchestrator.py guard --proposal-folder <folder>` and fix every finding. Add `references.md` when the domain
requires References (`client_deliverables.md`: citation codes, no `phase1_questions/llm*` paths).
Optional subfolders per domain.

**Phase 3:** Write every critique file where critic = your slot:
`phase3_crossed_critiques/llm{i}_vs_llm{j}.md` for all j ≠ i.

**Phase 4:** Rewrite client `phase4_final_proposals/{{FOLDER_SUFFIX}}/overview.md` and
`references.md`, update `artifact_manifest.json`, and run `guard`. Write post-critique revision log to
`_internal/post_critique_revision_log.md` (or d01 `_internal/critique_disposition.md`) — not in overview.

**Phase 5 (leader):** Write client `phase5_unified_answer_{{LEADER_SUFFIX}}/overview.md`
(unified technical answer only), `artifact_manifest.json`, and consolidation matrix to
`_internal/consolidation_matrix.md`. The leader does not write `_internal/boundary_audit.json`.

**Phase 5 (boundary_adversary, separate subagent):** Verify ownership and consistency among manifest, overview,
decision records, diagrams, and handoffs. Do not propose architecture. Write `_internal/boundary_audit.json`
(`status`, `independent_of_leader: true`, `findings`; any `block` or `needs_human` blocks acceptance).
