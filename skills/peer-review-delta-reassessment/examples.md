# Examples (generic)

Illustrative only — do **not** hardcode consumer repo paths into the skill or process.

## Scenario

A product needs flexible categorization systems (e.g. multiple taxonomies) and tax rules that vary by category and geography. Several domains already have accepted rounds; the change is product-wide.

## Steps

1. Record each stakeholder request as an accepted change (one file, meaning suffix on the name):

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" record-change \
  --meaning "multi taxonomy" --title "Multiple taxonomies" \
  --summary "An offer may carry more than one taxonomy." --disposition accepted
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" record-change \
  --meaning "geo tax" --title "Geo tax rules" \
  --summary "Tax rules vary by category and geography." --disposition accepted
```

Creates `program_changes/changes/PC-YYYYMMDD-001_multi_taxonomy.md` and `PC-YYYYMMDD-002_geo_tax.md` (the date is the UTC day of the command).

2. Open the run for those ids (status `draft`):

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" --cause taxonomy_and_tax \
  scaffold --change-id PC-YYYYMMDD-001 --change-id PC-YYYYMMDD-002 --summary "Multi-taxonomy + geo tax rules"
```

Creates `program_changes/{ts}_taxonomy_and_tax/` with `reassessment.md`, `change_pack.md` (the index of both ids), and one impact stub per domain with a row per change id.

3. Dispatch **one impact subagent per domain** (parallel). Each reads that domain's standards, current round, upstream currents, and the listed change files; it writes one `| PC-… | touch|no-touch | reason |` row per change id.

4. `rollup-impact` → the steward reads `impact_assessment.md` → `approve-impact` (freezes `touch_order`).

5. Suppose the touch order is `d01_scope` → `d03_…` → `d04a_…` → `d04b_…`. For each domain, `next-action` returns its `round_id` and `change_ids`:

- `set-domain-status --status in_progress`, then `init-round --kind revision --reassessment-ref … --change-id …` → orchestrator 0–5 (including the phase-5 boundary audit) → `awaiting_human` → steward accepts → `accept-domain`
- Repeat for the next domain. Its new round picks up the accepted upstream pin on `init-round`.

6. `next-action` → `done`; add a coherence note to `execution_log.md`. `changes-status` then reports both ids as `applied`.
