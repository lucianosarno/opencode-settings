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

**Phase 1 — first participant:** No prior LLM questions. Apply relevance test. Write
`phase1_questions/{{FOLDER_SUFFIX}}/qNN_*.md` or `q00_no_valid_questions.md`.

**Phase 1 — subsequent participant:** Read ALL prior slots under `phase1_questions/`. Do not
repeat questions already asked. Write only new questions in your folder.

**Phase 2:** Write `phase2_initial_proposals/{{FOLDER_SUFFIX}}/overview.md` — **client-facing
solution only** (no model names or peer-review narration). Add `references.md` when the domain
requires References (`client_deliverables.md`: citation codes, no `phase1_questions/llm*` paths).
Optional subfolders per domain.

**Phase 3:** Write every critique file where critic = your slot:
`phase3_crossed_critiques/llm{i}_vs_llm{j}.md` for all j ≠ i.

**Phase 4:** Rewrite client `phase4_final_proposals/{{FOLDER_SUFFIX}}/overview.md` and
`references.md`. Write post-critique revision log to `_internal/post_critique_revision_log.md`
(or d01 `_internal/critique_disposition.md`) — not in overview.

**Phase 5 (leader):** Write client `phase5_unified_answer_{{LEADER_SUFFIX}}/overview.md`
(unified technical answer only). Write consolidation matrix to
`_internal/consolidation_matrix.md`.
