# Examples (generic)

Illustrative only — do **not** hardcode consumer repo paths into the skill or process.

## Scenario

A product needs flexible categorization systems (e.g. multiple taxonomies) and tax rules that vary by category and geography. Several domains already have accepted rounds; the change is product-wide.

## Steps

1. Record each stakeholder request (one file, meaning suffix on the name):

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" record-change \
  --meaning "multi taxonomy" --title "Multiple taxonomies" \
  --summary "An offer may carry more than one taxonomy."
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" record-change \
  --meaning "geo tax" --title "Geo tax rules" \
  --summary "Tax rules vary by category and geography."
```

Creates `program_changes/changes/PC-YYYYMMDD-001_multi_taxonomy.md` and `PC-YYYYMMDD-002_geo_tax.md` (the date is the UTC day of the command).

2. Scaffold:

```bash
python ~/.config/opencode/skills/peer-review-delta-reassessment/scripts/delta_orchestrator.py \
  --peer-review-root "/path/to/peer_review" --cause taxonomy_and_tax \
  scaffold --summary "Multi-taxonomy + geo tax rules"
```

Creates `program_changes/{ts}_taxonomy_and_tax/` with `change_pack.md` and impact stubs.

3. Index the recorded ids in `change_pack.md` (id, micro-reminder, path to the suffixed file). The statement stays in the `PC-…_{meaning}.md` file.

4. Dispatch **one impact subagent per domain** (parallel). Each reads that domain’s standards + current round + upstream currents + the change pack; writes `impact_by_domain/{domain}.md`.

5. `rollup-impact` → human reviews `impact_assessment.md` → `approve-impact`.

6. Suppose touch order is `d01_scope` → `d03_…` → `d04a_…` → `d04b_…`:

- `init-round --kind revision` on d01 → orchestrator 0–5 → human accept → `accept-domain`
- Repeat for d03 (pins now include the new d01 round), then d04a, then d04b

7. `next-action` → `done`; add coherence note to `execution_log.md`.
