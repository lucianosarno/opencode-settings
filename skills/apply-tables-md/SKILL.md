---
name: apply-tables-md
description: >-
  Reformats Markdown tables and wide comparison grids for readability using
  process/standards/tables.md (topic sections, HTML rowspan/colspan, or small
  GFM pipe tables). Presentation-only: never changes document meaning or
  wording. Use when the user asks to apply tables.md, make tables readable,
  reflow comparison matrices, convert wide pipe tables to topic sections or
  HTML-in-Markdown, or improve table layout in a given .md file.
metadata:
  opencode/slash: "true"
  opencode/autoinvoke: "false"
---

# Apply tables.md (presentation only)

Reformat tables in a **given `.md` file** so they follow the project's readable-table standard. **Content is frozen** — only layout/shape may change.

## Hard invariant (non-negotiable)

- **Do not** change wording, punctuation, links, IDs, numbers, majority counts, or meaning.
- **Do not** shorten, paraphrase, merge, split, or invent cell/prose text.
- **Do not** drop, reorder for "logic", or invent Refs / Decision / options.
- **Allowed:** move the **same** strings into a different shape (topic section, HTML `<table>`, or small GFM pipe table); adjust Markdown/HTML structure, headings levels for the new shape, and whitespace around the reformatted block.
- If a readability improvement would require rewriting text → **stop**, show the conflict, and ask. Never silently edit content.

## Standard source

1. Prefer the workspace file `process/standards/tables.md` (read it this session before editing).
2. If that path is missing, follow the rules summarized below (same shapes as that standard).

GFM = GitHub Flavored Markdown pipe tables (`| col |`). No cell merge in GFM.

## When to run

User points at a `.md` (or path) and asks to apply `tables.md`, fix table readability, reflow a matrix, etc. Scope = that file (or the sections they name). Do not roam the repo rewriting other docs unless asked.

## Workflow

```
Progress:
- [ ] 1. Read target .md + process/standards/tables.md
- [ ] 2. Inventory tables / wide comparison blocks
- [ ] 3. Choose shape per block (§1)
- [ ] 4. Rewrite structure only; paste strings verbatim
- [ ] 5. Diff-check: content unchanged except presentation
- [ ] 6. Report shapes used + any blocked blocks
```

### 1. Inventory

For each table or options×topics matrix, note:

- Columns / options (e.g. LLM1…LLM5)
- Whether a Decision / Rationale / Refs column (or band) exists
- Whether cells are short phrases or long prose
- Whether a merged topic label or decision band would help

### 2. Choose shape (`tables.md` §1)

| Situation | Prefer |
|-----------|--------|
| Multi-option comparison + shared decision / long rationale | **Topic sections** (§2) |
| Shared category label + decision band under options | **HTML table in `.md`** (§3) |
| Small grid (≤ ~4 meaningful columns, short cells, no merges) | Ordinary **GFM** pipe table (§4) |
| Process / dependency narrative | Leave as prose/steps/diagram — do not force a dense matrix |

**Default** for phase-5-style consolidation matrices: topic sections. Use HTML when `rowspan` / `colspan` clearly helps **and** the same text can be placed without rewriting.

### 3. Apply shapes (verbatim content)

#### Topic sections (§2)

One heading per former topic/row. Under it, keep **exactly** the same option strings and the same Decision / Refs text:

- **Pattern A:** narrow options pipe table + `**Decision…**` + `**Refs:**…` (or whatever labels already exist in the source)
- **Pattern B:** bullets `- **Option:** …` + Decision + Refs — only if the source already uses short option lines that map 1:1

Preserve existing label wording (`Decision (3-2 majority):`, `Refs:`, ADR titles, micro-reminders). Do not "normalize" labels.

#### HTML-in-Markdown (§3)

Use raw `<table>` **only** for the table block when merges help:

- `rowspan` for topic label spanning option + decision rows
- `colspan` for a decision band under all option columns

Rules:

1. HTML **only** for that table; leave surrounding narrative in Markdown.
2. Put long rationale in the merged decision cell **using the same text** that was in the Decision column/cells.
3. Do not wrap the whole document in HTML.
4. No decorative spreadsheet CSS unless the project already has a preview stylesheet.
5. If the environment strips HTML, use topic sections instead.

Escape only what HTML requires (`<`, `>`, `&` in cell text) so rendered text matches the original. Prefer `<code>` only where the source already used backticks / code styling for that span — do not newly code-ify words.

#### GFM (§4)

Keep or restore a pipe table when all hold: few columns, short cells, no merge need. If a Decision/Rationale column is a paragraph → switch to §2 or §3 **without** editing that paragraph's words.

### 4. Content-preservation check

Before finishing, mentally (or via diff) verify:

- Every option string still present once per topic
- Every decision / rationale string intact
- Every ref / link / ID intact
- No new facts, no removed facts
- Only structure, heading placement for topics, and table markup changed

### 5. Report to user

Briefly list:

- Blocks reformatted and which shape (§2 / §3 / §4)
- Blocks left unchanged and why (already fine, or would need content edits)
- Reminder: presentation-only; no wording changes

## Anti-patterns (do not do)

| Anti-pattern | Instead |
|--------------|---------|
| Rewrite decision to be "clearer" | Move the same sentence to full-width Decision / `colspan` |
| Trim option cells to fit the standard's "short phrase" advice | Keep full option text; only change layout. Flag if still unreadable |
| Convert whole deliverable to `.html` | HTML fragment inside `.md` or topic sections |
| Duplicate or invent ADR summaries | Keep existing refs as-is |
| Reorder topics/options "for clarity" | Preserve source order unless user asks to reorder |

## Out of scope

- Applying `dry.md` content rules (dedupe definitions, rewrite pointers) — unless the user separately asks
- Changing non-table prose for style
- Migrating folders to HTML

## Dual response (when summarizing)

# What changed
## Architectural/technical
- Which `tables.md` shape and why (GFM limits, merge need, scan path)
## Practical
- What the reader can scan more easily; confirm wording was untouched
