# Mechanism + impact (no dual theater)

For every substantive point in responses, docs, questions, and suggestions, cover both:

1. **How it works** — enough technical mechanism to make the claim trustworthy
2. **What it changes** — decision, cost, risk, or next step, in simple language

## How to write it

Weave both into the **same short paragraphs**. Do not split every topic into labeled subsections.

```markdown
<!-- ❌ BAD — mandatory dual headers -->
## Catalog API
### Architectural/technical explanation
Premier Catalog API (Pull/Push, JSON)...
### Practical explanation
Bom para commerce.

<!-- ✅ GOOD — one readable block -->
## Catalog API
A Premier Catalog API devolve o catálogo da sua conta (JSON, pull ou push)
com preço negociado, descrições e imagens. Na prática isso serve bem para
compra B2B; não substitui um PIM com atributos técnicos tipados por MPN.
```

## When the user asks for dual sections

Only if they explicitly request the Architecture / Practical template, use those headers. Otherwise prefer fluent prose (see `fluent-readable-prose`).

## Priority

If this rule conflicts with slide-like brevity or nested-bullet-only answers, **prose readability wins**.

