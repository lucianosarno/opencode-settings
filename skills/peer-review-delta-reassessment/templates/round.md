---
kind: revision
round_id: {{ROUND_ID}}
baseline_round_id: {{BASELINE_ROUND_ID}}
reassessment_ref: {{REASSESSMENT_REF}}
change_ids:
  - {{CHANGE_ID}}
summary: |
  {{SUMMARY}}
upstream_pins:
  {{UPSTREAM_PINS_YAML}}
---

# Round `{{ROUND_ID}}`

Revision round of a delta reassessment. `change_ids` lists only the change ids whose impact row is `touch` for this domain. See `process/standards/revision_rounds.md`.
