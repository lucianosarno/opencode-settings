# Hierarquia visual nas respostas

Use Markdown para tornar respostas longas navegáveis — sem transformar o texto em telegrama.

## Quando usar headers

- Respostas com **2+ tópicos** ou subníveis: use headers.
- Respostas **curtas** (1–3 frases, um único ponto): texto direto, sem forçar `#` / `##`.

## Níveis

- `#` — tema principal (só se a mensagem for longa / multi-seção)
- `##` — tópico
- `###` — subtópico real sob um `##`
- Não pule níveis; não invente seções vazias só para “parecer estruturado”

## Parágrafos vs listas

- **Padrão:** parágrafos curtos (2–5 frases) sob cada header.
- **Listas:** só para itens homogêneos — passos numerados, links, comparações sim/não, checklists.
- Não quebre cada cláusula em bullet. Evite corpo feito só de fragmentos.

```markdown
<!-- ❌ BAD -->
## Warranty
- TechDirect API
- OAuth client credentials
- Service Tag
- Sem captcha

<!-- ✅ GOOD -->
## Warranty
A API de garantia do TechDirect autentica o sistema (OAuth) e consulta por Service Tag. Na prática você obtém entitlement sem captcha — útil para inventário, não para catálogo de specs por MPN.
```

## Compatibilidade

- Hierarquia não significa texto longo: corte repetição, mantenha conectivos.
- Não repita o mesmo conteúdo no header e no primeiro bullet.
- Em relatórios pedidos pelo usuário, respeite o outline dele; sob cada heading, prosa primeiro, tabela/lista depois se ajudar a comparar muitos itens.
- Se conflitar com templates rígidos Architecture/Practical, siga `fluent-readable-prose`.

