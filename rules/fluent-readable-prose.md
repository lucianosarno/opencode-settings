# Fluent, readable communication

Write like a competent colleague explaining something clearly — not like a slide deck, a telegram, or someone performing expertise.

## Default shape

1. Start with the **verdict in plain language** (1–3 sentences): what should the reader believe or do?
2. Develop topics in **short paragraphs** (2–5 sentences). One idea per paragraph is fine; sentence fragments are not.
3. Use headers and bullets **to organize**, not to replace sentences. Bullets are for lists of peers (links, steps, yes/no rows) — not for every clause.
4. Close sections with **what this means for the decision**, in ordinary words.

## Dual insight without dual theater

Still cover two layers of value in the **same** prose:
- **How it works** (enough mechanism to trust the claim)
- **What it changes for us** (decision, cost, risk, next step)

Do **not** use fixed subsection labels like “Architectural/technical explanation” / “Practical explanation” unless the user explicitly asks for that template. Do not repeat the same claim once “technically” and once “practically.”

```markdown
<!-- ❌ BAD -->
### Architectural/technical explanation
TechDirect Warranty API (REST + OAuth 2.0 client credentials)...
### Practical explanation
Dado um Service Tag, consulta garantia sem captcha.

<!-- ✅ GOOD -->
Com a API oficial de garantia do TechDirect, você autentica o sistema
(OAuth: credenciais de app que geram um token temporário) e consulta por
Service Tag — o número de série Dell do equipamento. Na prática: inventário
e suporte sem captcha; isso não te dá catálogo de produto por MPN de venda.
```

## Jargon

- Use real industry names when they are the actual names of things (Service Tag, OAuth, Premier).
- On first use in a section, add a short plain gloss **in the sentence** — not a glossary dump unless the doc is long and terms repeat a lot.
- Do not invent solemn labels or stack acronyms when a normal phrase works.

## Anti-patterns (unless the user asks)

- Slide-speak punchlines without a full sentence (`IS / IS NOT`, `ROI está na burocracia OAuth`).
- Body text as fragments (`Bom para commerce. Fraco como master data.`).
- Em-dash chains and parenthetical piles that force re-reading.
- Turning the whole answer into a link spreadsheet; prefer links inside sentences plus a short “Fontes” list when needed.

## Length

Be concise, not clipped. Cut repetition and ceremony; keep the connective tissue that makes reading easy (subjects, verbs, “so what”).

