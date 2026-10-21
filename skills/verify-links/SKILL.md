---
name: verify-links
description: >-
  Verifica links (HTTP, arquivos locais, anchors) em quatro níveis: disponibilidade,
  destino correto, aderência ao que se afirma, e se a fonte citada é a versão mais
  recente (com ajuste leve ou discussão de impacto se houver mudança). Use quando
  o usuário pedir para conferir, validar ou auditar links; antes de citar uma URL
  como evidência; ao revisar docs, PRs ou respostas que dependem de referências
  externas; ao auditar sources.md / citações de padrões; ou quando houver dúvida
  se um link ainda funciona, diz o que se presume, ou está desatualizado.
---

# Verificação de links

Conferir **todo e qualquer link** citado ou em revisão, em **quatro níveis encadeados**. Só avance para o próximo nível se o anterior passar.

## Regra de ouro

**Nunca** afirmar que um link "confirma X" sem ter lido o conteúdo apontado nesta sessão. Status HTTP 200 (página encontrada) **não** prova destino correto, aderência ao que se disse, nem que a versão citada ainda é a vigente.

## Escopo do link

Antes de verificar, classifique o alvo:

| Tipo | Exemplos | Ferramenta principal |
|------|----------|----------------------|
| URL externa | `https://...` | `WebFetch` → `curl` → browser MCP |
| Arquivo local | `./docs/x.md`, `process/overview.md` | `Read` / `Glob` no workspace |
| Anchor | `#secao` em doc local ou URL | resolver base + buscar heading/id |
| Redirect | encurtadores, `301`/`302` | seguir cadeia; registrar URL final |

Se o contexto não disser **o que deveria estar no destino**, inferir a expectativa a partir do texto ao redor do link (título do link, frase que o cita, doc em edição).

## Fluxo (4 níveis)

### Nível 1 — Link funciona?

Objetivo: o recurso está **acessível**, sem erro técnico óbvio.

1. Tentar obter o recurso (`WebFetch` para URLs; `Read` para paths locais).
2. Se falhar ou vier vazio, usar `curl -sS -L -o /dev/null -w "%{http_code} %{url_effective}"` (URLs) ou confirmar existência do arquivo.
3. Se a página depender de JavaScript (SPA, paywall leve, conteúdo dinâmico), usar browser MCP (`browser_navigate` + `browser_snapshot`).

**Passa se:** status final 2xx ou redirect benigno para o mesmo domínio/recurso esperado; arquivo local existe e é legível.

**Falha comum:** 404, 410, 5xx, timeout, DNS, SSL, arquivo inexistente, redirect para login genérico.

Se falhar → **parar aqui**. Reportar falha e não inferir conteúdo.

### Nível 2 — Aponta para o conteúdo desejado?

Objetivo: mesmo vivo, o link leva ao **recurso certo** (não só "alguma página no ar").

Conferir pelo menos **dois** sinais independentes:

- URL final (após redirects) coerente com a intenção
- Título da página / `<title>` / heading principal
- Identificadores esperados: slug, ID de issue/PR, nome de arquivo, seção `#anchor`
- Metadados quando existirem: autor, data, produto, versão citada

**Passa se:** sinais convergem para o destino pretendido.

**Falha comum:** artigo homônimo, versão antiga da doc, issue errada, redirect para homepage, anchor inexistente, link relativo quebrado fora do contexto certo.

Se falhar → reportar **destino incorreto** com o que foi encontrado de fato.

### Nível 3 — O que dizemos bate com o conteúdo?

Objetivo: cada **afirmação derivada do link** no texto em revisão é suportada pelo conteúdo apontado.

1. Listar as **claims** (afirmações) ligadas ao link no contexto (doc, comentário, resposta).
2. Para cada claim, localizar trecho correspondente no conteúdo (busca por keywords, seções, listas, tabelas).
3. Classificar:

| Veredito | Significado |
|----------|-------------|
| ✅ Confirmado | O conteúdo diz explicitamente ou implica claramente |
| ⚠️ Parcial | Só parte da claim é suportada; nuances faltando |
| ❌ Não confirmado | Conteúdo omite ou contradiz |
| ❓ Indeterminado | Paywall, login, idioma, ou trecho ambíguo — declarar limite |

**Passa se:** todas as claims essenciais forem ✅ ou ⚠️ com ressalvas explícitas.

**Falha comum:** extrapolação além do texto, data/versão desatualizada, citação de feature que a doc não menciona, confundir blog com doc oficial.

### Nível 4 — Estamos na versão mais recente?

Objetivo: a fonte citada (padrão, doc oficial, framework, RFC, livro com edição, página de produto) é a **versão vigente** — ou o pin (versão fixa na URL/citação) é **consciente e justificado**.

#### Como detectar a versão vigente

Para cada fonte (não só o link isolado):

1. Extrair do texto/repo: designação (ex.: `ISO/IEC 15288:2015`), número de edição, tag `v1.2`, path `/latest/` vs `/v2/`, data de "última verificação", changelog citado.
2. Procurar no destino (e páginas irmãs típicas: "What's new", "Releases", "Previous versions", catálogo ISO/W3C/IETF, docs do vendor):
   - versão / edição / data de publicação no próprio recurso
   - link explícito para "latest", "current", ou edição sucessora
   - anúncio de supersession (substituição oficial: "replaced by", "withdrawn", "superseded")
3. Comparar **citado no repo** × **vigente encontrado**.

Se não houver sinal de versão (artigo estático, wiki histórica sem edição), marcar **N/A** e explicar por quê — não inventar "latest".

#### Se houve mudança: classificar severidade

| Severidade | Critério | Ação obrigatória |
|------------|----------|------------------|
| ✅ Atual | Citado = vigente, ou pin explícito ainda correto | Nenhuma (registrar data da checagem se o doc tiver campo de verificação) |
| 🟡 Leve | Renomeações cosméticas, URLs novas com mesmo sentido, clarificações, reorganização de seções, typos, exemplos trocados **sem** mudar regras/claims que o repo usa | **Pequeno ajuste** no conteúdo que usa a fonte: URL, designação, trecho citado, nota de versão — sem reabrir desenho do processo |
| 🔴 Maior | Nova edição/norma substituta; mudança de requisitos, escopo, vocabulário canônico, pilares, ou práticas que o repo **adota**; deprecação do que citamos como [CONSENSUS] / "What we adopt" | **Não** só patch silencioso. **Levantar discussão de impactos neste repo**: listar arquivos/domínios afetados, claims que podem ficar inválidas, opções (atualizar adoção, pin consciente na edição antiga, marcar [OWN] divergence) e pedir decisão antes de mudanças amplas |
| ❓ Indeterminado | Paywall de padrão pago, só overview público, sem changelog acessível | Declarar limite; sugerir checagem manual na página do editor / compra / membro |

#### O que contar como "impacto neste repo" (mudança maior)

Mapear onde a fonte é consumida:

- `sources.md` / tabelas de referência do domínio
- `methodology.md`, `deliverables.md`, fases que citam a fonte
- Claims do tipo "What we adopt" / [CONSENSUS] / alinhamento a framework

No relatório de discussão, incluir no mínimo:

1. **O que mudou** na fonte (edição antiga → nova; 2–5 bullets factuais)
2. **Onde o repo depende disso** (paths + claims)
3. **Riscos se não atualizar** vs **custo se atualizar**
4. **Pergunta explícita** ao usuário/time (não assumir a resposta)

#### Pin consciente

URL/`latest` vs versão pinned:

- Se o repo **quer** acompanhar latest → preferir URL estável de "current" e revalidar periodicamente
- Se o repo **fixou** uma edição (ex.: ISO 2015 enquanto existe 2023) → nível 4 passa só se o pin estiver **documentado** (por quê) e o nível 3 ainda bater com essa edição; caso contrário → 🔴 + discussão

## Execução em lote

Para vários links:

1. Extrair todos os links do artefato (`Grep` por `https?://`, `\[.*\]\(.*\)`, paths relativos).
2. Verificar **cada um** nos 4 níveis (não amostrar).
3. Priorizar links que sustentam conclusões, números, APIs, prazos, decisões ou entradas de `sources.md`.
4. Agrupar no resumo: falhas 1–3 separadas de **fontes desatualizadas** (🟡/🔴 do nível 4).

## Formato de saída

Usar este template por link (adaptar se o usuário pedir outro formato):

```markdown
### [rótulo curto ou URL]

**Nível 1 — Disponibilidade:** ✅ | ❌  
[status HTTP / erro / arquivo ok]

**Nível 2 — Destino:** ✅ | ❌ | ⚠️  
[URL final; o que se esperava vs o que foi encontrado]

**Nível 3 — Aderência:** ✅ | ⚠️ | ❌ | ❓  
| Claim no texto | Evidência no destino | Veredito |
|----------------|----------------------|----------|
| ... | trecho ou "não encontrado" | ✅/⚠️/❌/❓ |

**Nível 4 — Atualidade:** ✅ | 🟡 Leve | 🔴 Maior | ❓ | N/A  
- Citado no repo: [versão / edição / URL / "sem pin"]
- Vigente encontrado: [versão / edição / URL / evidência]
- Delta: [nenhum | resumo do que mudou]

**Ação sugerida:**
- [nenhuma | corrigir URL | atualizar texto (ajuste leve) | trocar fonte | remover claim]
- Se 🟡: listar edits mínimos nos arquivos afetados
- Se 🔴: **Discussão de impacto** (o que mudou / onde depende / riscos / pergunta ao time) — não aplicar refactor amplo sem acordo
```

Encerrar com **Resumo**: quantos links ok / com problema / claims não suportadas / fontes 🟡 leve / 🔴 maior (com discussão pendente).

## Limitações (declarar ao usuário)

- Conteúdo atrás de login, CAPTCHA ou paywall fechado → marcar ❓; não inventar.
- Rate limit ou bloqueio por bot → tentar browser MCP ou pedir ao usuário abrir manualmente.
- Páginas que mudam frequentemente → registrar data/hora da verificação.
- PDFs grandes → buscar seção relevante ou usar trecho citado como âncora de leitura.
- Padrões pagos (ISO etc.) → overview público pode não bastar para delta de edição; declarar ❓ e o que foi possível ver.

## Anti-padrões

- ❌ Confiar só no snippet de busca ou memória do modelo
- ❌ Tratar redirect para domínio genérico como sucesso no nível 2
- ❌ Ignorar diferença entre doc "latest" e versão pinned na URL
- ❌ Verificar só o nível 1 e responder como se os níveis 3–4 estivessem ok
- ❌ Tratar toda mudança de versão como "só atualizar o link" sem classificar leve vs maior
- ❌ Aplicar refactor amplo no repo por mudança 🔴 sem levantar discussão e obter decisão
- ❌ Assumir que overview de marketing = texto normativo da edição vigente
