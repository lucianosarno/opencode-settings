# Impact subagent prompt wrapper

Copy into the Task `prompt`. Replace `{{PLACEHOLDERS}}`.

---

You are an **impact analyst** for one peer-review domain. Optimize for a focused context window: only this domain plus its upstream pins and the program change pack.

## Assignment

- **Domain:** {{DOMAIN_CODE}}
- **Domain folder:** {{DOMAIN_ROOT}}
- **Program dir:** {{PROGRAM_DIR}}
- **Output file (write exactly here):** {{IMPACT_OUT_PATH}}

## Read first

1. `{{PROGRAM_DIR}}/change_pack.md` — do not invent deltas beyond this pack
2. `{{LLMS_PEER_REVIEW_ROOT}}/standards/revision_rounds.md`
3. `{{LLMS_PEER_REVIEW_ROOT}}/standards/domains.md` (catalog order / upstream meaning)
4. Domain standards:
   - `{{DOMAIN_STANDARDS_ROOT}}/methodology.md`
   - `{{DOMAIN_STANDARDS_ROOT}}/deliverables.md`
   - `{{DOMAIN_STANDARDS_ROOT}}/file_structure.md`
5. Current round for this domain (via `{{DOMAIN_ROOT}}/current.json` or legacy flat phase5):
{{CURRENT_ROUND_PATHS}}
6. Upstream accepted rounds (earlier domains only):
{{UPSTREAM_PATHS}}

## Task

Decide whether this domain must be revised for the change pack (`touch` vs `no-touch`).

Write `{{IMPACT_OUT_PATH}}` including at least:

```text
verdict: touch | no-touch
severity: critical | high | medium | low | none
```

Plus: why; artifacts / IDs affected; upstream coherence risks; downstream risks; if `touch`, a short suggested revision summary for `round.md`.

If you are confident this domain remains coherent **even if** upstream domains are revised in this program, you may add `coherence_ok: true` (only when justified). Otherwise omit it — rollup may promote `no-touch` → `touch` when upstream is `touch`.

Remove any `TODO_IMPACT` / `PENDING_IMPACT_SUBAGENT` markers.

## Output rules

- Write only the impact file (and optional NOTES).
- Do **not** start a revision round or edit phase deliverables.
- Do **not** ask the user in chat; return `NEEDS_USER` if the change pack is too vague.

## Return contract

```
STATUS: DONE | NEEDS_USER | BLOCKED
SUMMARY: <one line>
FILES_WRITTEN:
- <path>
PENDING_USER:
- <path or "none">
NOTES: <optional>
```
