# No hard-wrap in Markdown prose

Hard-wrapping (inserting `\n` every ~72–80 characters inside a paragraph) is forbidden in Markdown prose. It is a terminal-era habit that LLMs copy from training data. Soft wrap in the editor handles display.

## Rules

- **One logical paragraph = one physical line.** Do not break a sentence or clause mid-paragraph to fit a column width.
- Insert a **blank line only between paragraphs** (and before/after headings, lists, tables, code fences).
- Hard newlines inside a paragraph are **forbidden**, except where Markdown syntax requires them: list items, table rows, headings, fenced code, blockquotes when each quoted line is intentional.
- Prefer editor soft-wrap / Prettier `proseWrap: "never"` over manual column wrapping.
- When editing an existing hard-wrapped paragraph, **reflow it** to a single line (do not preserve the old wraps).

## Examples

```markdown
<!-- ❌ BAD — hard-wrapped at ~80 columns -->
Technically, the answer determines which Concept IDs and logical attributes must
be mapped in DCON first; it does not freeze an OpenAPI, AsyncAPI, Avro, or
physical schema.

<!-- ✅ GOOD — one paragraph, one line -->
Technically, the answer determines which Concept IDs and logical attributes must be mapped in DCON first; it does not freeze an OpenAPI, AsyncAPI, Avro, or physical schema.
```

```markdown
<!-- ❌ BAD — hard wrap inside a list item continuation for column width -->
- [ ] **Nested Offer payload** — current price, availability, feed scope, and
  distributor-native evidence.

<!-- ✅ GOOD — keep the item on as few lines as syntax needs; no column wrap -->
- [ ] **Nested Offer payload** — current price, availability, feed scope, and distributor-native evidence.
```

## Out of scope

- Source code line-length limits (Python, TypeScript, etc.) follow language/formatter rules, not this file.
- Tables, ASCII diagrams, and fenced code may use intentional line breaks.

