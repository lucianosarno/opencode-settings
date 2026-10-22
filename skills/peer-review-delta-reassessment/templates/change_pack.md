# Change pack

**Cause:** {{CAUSE}}  
**Program timestamp:** {{TIMESTAMP}}  
**Summary:** {{SUMMARY}}

Index of the program change ids this reassessment covers. The statement of each change stays in its own file; this table only points at it.

{{CHANGE_TABLE}}

## What changed (product-wide)

Describe the stakeholder / product modification in concrete terms (paths, decisions, before→after). Do **not** leave this vague — impact subagents must not invent deltas. Each change statement lives in its `PC-…_{meaning}.md` file; cite it by id here.

## Why reassessment

…

## Out of scope

…

## Constraints for impact subagents

- Cite only facts in the listed change files and the current domain round artifacts.
- Record one effect row per change id in `impact_by_domain/{domain}.md` (`touch` or `no-touch`).
- Later domains must stay coherent with the latest accepted upstream rounds (`revision_rounds.md`).
