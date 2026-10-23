---
name: peer-review-general-topic
description: Use SOMENTE quando o usuário pedir revisão multi-LLM de um tema sem perfil d0X ou fallback aplicável — por exemplo, contrato jurídico, prescrição médica ou concepção de um novo d0X para o repo atual — seguindo as fases genéricas 1–5 do llms_peer_review.
---

# Peer review para temas sem perfil d0X aplicável

Esta skill aplica a separação de responsabilidades das fases 1–5 do `llms_peer_review` a um tema que não tem um perfil de entrega adequado no catálogo. Ela conserva a preparação, a elicitação, as propostas independentes, a crítica cruzada, a revisão e a consolidação, sem inventar uma pasta de domínio ou exigir artefatos próprios de arquitetura.

## Quando usar

Use esta skill somente depois de confirmar que o objetivo e o artefato pedidos não pertencem a um domínio formalizado nem a um perfil fallback existente. A classificação depende do que está sendo avaliado e do resultado esperado, não de uma palavra isolada: uma minuta jurídica não é um contrato OpenAPI, e uma revisão clínica não é uma revisão da arquitetura de um produto de saúde.

Para verificar o catálogo, leia `process/standards/domains.md` e `process/standards/domains_fallback.md` no `llms_peer_review_process_root` configurado em `skills/peer-review-orchestrator/config/settings.json`. Se um domínio formalizado ou fallback realmente definir aquele entregável, use `peer-review-orchestrator` com esse perfil. Para revisar uma mudança em entregáveis já aceitos dentro de um programa D0X, use `peer-review-delta-reassessment`.

Use esta skill, por exemplo, para revisar um contrato jurídico, conferir uma prescrição dentro dos limites abaixo, ou desenhar um novo perfil D0X que ainda não existe. Ao desenhar um D0X, o objeto da revisão é a proposta do novo perfil; o perfil candidato não governa a própria revisão.

## Fontes do processo e regras de adaptação

Resolva `llms_peer_review_process_root` lendo `skills/peer-review-orchestrator/config/settings.json`; não presuma que o repositório do processo seja o diretório de trabalho. Leia `overview.md`, os prompts genéricos `phases/phase0_setup.md` a `phase5_final_answer.md` e os padrões `standards/roles.md`, `standards/relevant_questions.md`, `standards/self_answered_questions.md`, `standards/sources.md`, `standards/dry.md`, `standards/language.md`, `standards/client_deliverables.md` e `standards/boundary_guard.md` antes de iniciar. Use inglês nos artefatos do processo conforme `standards/language.md`; preserve no idioma original os trechos citados e os nomes próprios do material revisado. Não carregue overrides `process/domains/dXX_*/phases/` para um tema sem domínio aplicável.

Adapte os prompts genéricos ao entregável real, preservando os objetivos das fases e os gates humanos. Não copie para esta revisão a pirâmide entre domínios nem os artefatos que dependem dela. Portanto, não crie `program_manifest.md`, IDs `dNN_*`, pares `dXX_vs_dYY`, pontuações `tp`/`cl`, `current.json` ou pastas com sufixo D0X. Use IDs locais como `Q-01` para perguntas e `R-01` para achados quando isso ajudar a rastrear decisões.

O validador automático (`process_guard`) e o schema de `artifact_manifest.json` só podem ser usados quando um perfil de domínio aplicável fornece o catálogo e as regras que eles validam. Sem esse perfil, registre no setup que esse guard determinístico não se aplica e substitua sua finalidade por rastreabilidade de fontes e decisões mais uma auditoria independente na fase 5; não invente campos D0X para fazer o validador passar. A auditoria independente da fase 5 continua sendo obrigatória.

## Preparação e roster

Abra uma revisão com objetivo, escopo, limites e versão das fontes claramente identificados. Na fase 0, registre pelo menos o artefato ou pergunta sob revisão, o resultado esperado, o que fica dentro e fora do escopo, os critérios de avaliação, as fontes e suas versões, quem responde por intenção e aceitação, quem responde por juízo especializado, idioma, confidencialidade e decisões humanas pendentes. Peça ao usuário apenas os dados materiais ausentes; não transforme uma revisão genérica em uma longa entrevista de requisitos.

Use o arranjo clássico multi-proposta — cada participante redige sua própria resposta — como padrão: pelo menos três participantes independentes, de provedores distintos, e um líder de fase 5 escolhido entre eles. A fase 0 do processo exige confirmar a disponibilidade de cada participante e líder pelo mesmo caminho de despacho que será usado no trabalho — uma sondagem mínima pode pedir a resposta literal `OK` — e apresentar o roster (lista de participantes e modelos) ao usuário antes da fase 1. Se não houver participantes distintos suficientes, modelos não responderem às sondagens ou o ambiente não permitir despacho para modelos diferentes, pare e explique a limitação; não apresente cópias do mesmo modelo como revisão independente.

Para resolver o roster genérico, use o script `scripts/orchestrator.py` dentro de `skills/peer-review-orchestrator` com `resolve-shortlist --domain generic --phase 2`, `--phase 3` ou `--phase 5`, passando `--slots N` para manter o número de participantes escolhido na fase 0. O token `generic` seleciona a aplicação genérica de ranking; ele não é um domínio, não cria uma pasta e não autoriza `init-round`. Use os `model_slug` retornados, respeite as famílias/provedores únicos e não troque um modelo sem registrar a indisponibilidade e obter a decisão humana necessária. Para a fase 5, use o roster resolvido entre os participantes da fase 2 e designe como líder o slot `llmN` (o primeiro da classificação de qualidade); se essa classificação não estiver disponível, registre a alternativa usada.

Quando houver um workspace e for preciso persistir os artefatos, siga o caminho de peer review já adotado pelo repositório e crie uma área separada, como `00_docs/peer_review/general_topics/{slug}/{YYYYMMDDTHHMMSSZ}/`. Se não existir convenção, use `peer_review/general_topics/{slug}/{YYYYMMDDTHHMMSSZ}/` na raiz do repositório, sem sobrescrever uma rodada existente. Sem workspace, mantenha os artefatos na sessão e entregue a consolidação no chat; não invente caminhos de arquivo.

Para material confidencial ou sensível, não duplique o documento-fonte nos artefatos: cite o caminho, a página, a cláusula ou o trecho mínimo necessário e remova identificadores pessoais quando não forem essenciais. Se o próprio relatório revelar dados que não devem ficar em um repositório versionado, mantenha a revisão em sessão ou peça ao usuário um destino apropriado antes de gravá-la.

O pacote de execução usa nomes neutros e só os artefatos que o caso precisa:

```text
{review_root}/
├── phase0_setup.md
├── phase1_questions/
│   ├── proposals/llm{N}.md
│   ├── critiques/llm{i}_vs_llm{j}.md
│   ├── revisions/llm{N}.md
│   ├── decisions.md
│   └── answers.md
├── phase2_initial_proposals/llm{N}/overview.md
├── phase3_crossed_critiques/llm{i}_vs_llm{j}.md
├── phase4_final_proposals/llm{N}/
│   ├── overview.md
│   └── _internal/post_critique_revision_log.md
└── phase5_unified_answer/
    ├── overview.md
    └── _internal/
        ├── consolidation_matrix.md
        └── independent_audit.md
```

Os arquivos podem ser combinados quando a revisão for pequena, desde que cada fase e cada autor continuem identificáveis. `overview.md` é o entregável de cada proposta e da consolidação, não um relato do debate entre modelos. Inclua outros artefatos apenas quando o entregável pedir, como uma matriz de cláusulas ou uma lista de verificações; a fase 0 registra a lista e a localização deles.

## Execução das fases 1–5

Antes de cada fase, confirme quais entradas estão completas e forneça a cada participante os caminhos das fontes, do setup e dos artefatos anteriores que ele deve ler. Aponte para os prompts genéricos originais da fase em vez de reescrevê-los como se fossem um novo processo. O agente principal controla toda interação com o usuário; participantes não fazem perguntas ao usuário no próprio chat. Use o contrato de retorno `STATUS: DONE | NEEDS_USER | BLOCKED`, resumo, arquivos escritos e pendências; qualquer `NEEDS_USER` ou `BLOCKED` interrompe o avanço até a decisão ou correção.

### Fase 1 — perguntas e decisões abertas

Faça exatamente um ciclo de propostas, críticas, revisões e consolidação para toda a revisão, não um ciclo por pergunta ou par de participantes. Cada participante identifica apenas dúvidas materiais: verifique primeiro o pedido, o documento, o repositório e as respostas anteriores; pesquise fatos verificáveis; direcione a pergunta a quem realmente detém a resposta; pergunte ao usuário somente sobre intenção, preferência, restrição ou aceitação que lhe pertença. Use `standards/relevant_questions.md` como filtro, mas não use pares de domínios nem pontuações `tp`/`cl`.

Os participantes propõem perguntas com IDs `Q-NN`, criticam as listas dos outros, revisam as próprias perguntas e deixam o líder consolidar `decisions.md`. Para cada pergunta sobrevivente, explique o que está em aberto, por que a resposta não pode ser obtida por leitura ou pesquisa, formule-a em linguagem que a pessoa possa responder, dê exemplos quando eles esclarecerem o assunto e indique se a resposta bloqueia a fase 2. Registre em `answers.md` a resposta humana recebida, preservando sua intenção; uma recomendação vazia ou sem resposta nunca significa concordância.

Não pergunte ao usuário por fatos pesquisáveis nem por decisões técnicas que cabem ao especialista. Se uma dúvida material puder ser fechada com fonte confiável, registre a pergunta auto-respondida, a fonte, a conclusão e seus limites em `decisions.md`; não registre consultas triviais. A fase 2 só começa quando as perguntas que realmente bloqueiam o entregável foram respondidas ou explicitamente adiadas pelo responsável.

### Fase 2 — propostas iniciais independentes

Cada participante produz sua própria resposta completa em `phase2_initial_proposals/llm{N}/overview.md`, usando o mesmo objetivo, as mesmas fontes e as respostas da fase 1, mas sem ler a proposta dos demais antes de terminar a sua. O formato vem do pedido: por exemplo, achados vinculados a cláusulas para um contrato, verificações textuais limitadas para uma prescrição, ou um pacote candidato de padrões para um novo D0X. Não use arquitetura/C4 como formato padrão.

Separe observações do documento, fatos externos, inferências, riscos, recomendações e incertezas. Sustente afirmações materiais com referências verificáveis conforme `standards/sources.md`; para documentos do usuário, cite a versão e o local exato. O entregável deve ficar claro sem expor nomes de modelos ou narrar a peer review.

### Fase 3 — crítica cruzada

Cada participante analisa todas as propostas dos demais e escreve uma crítica por par ordenado em `phase3_crossed_critiques/llm{i}_vs_llm{j}.md`, para todos `i ≠ j`. Aponte o trecho ou item, classifique a observação como erro factual, lacuna, inconsistência, risco, ambiguidade ou complemento, explique a consequência e cite a evidência que sustenta uma contestação factual. Concordância não é evidência; se as propostas repetirem a mesma premissa sem suporte, marque a premissa compartilhada como risco correlacionado.

### Fase 4 — propostas finais individuais

Cada participante revê a própria proposta à luz das críticas recebidas e dos pontos relevantes nas demais propostas, mantendo o mesmo entregável e os mesmos limites da fase 2. Escreva a versão final em `phase4_final_proposals/llm{N}/overview.md` e registre em `_internal/post_critique_revision_log.md` os itens mantidos, alterados, removidos ou não adotados, com motivo e referência. Não trate votação ou maioria como substituto de evidência ou de responsabilidade profissional.

### Fase 5 — consolidação e auditoria independente

O líder lê as propostas finais, as críticas e o pedido original e produz uma resposta coerente em `phase5_unified_answer/overview.md`; não faça média ou colagem. Registre em `_internal/consolidation_matrix.md` as contribuições relevantes, sua decisão final e o motivo. Preserve divergências reais, incertezas, perguntas sem resposta, limites do escopo e decisões reservadas ao usuário ou a um profissional habilitado.

Depois da consolidação, designe um auditor independente que não seja o líder e que não reescreva a solução. Ele verifica se a versão e o escopo estão certos, se os critérios e todas as partes relevantes foram cobertos, se as afirmações materiais têm apoio, se fontes e citações correspondem ao que está escrito, se há contradições ou premissas comuns sem evidência, se achados e recomendações respeitam os limites de responsabilidade e se o texto protege informação sensível. Registre `PASS`, `BLOCKED` ou `NEEDS_HUMAN`, itens verificados, evidências e ações pendentes em `_internal/independent_audit.md`. Resolva todo bloqueio antes de entregar; a auditoria é um gate dentro da fase 5, não uma fase 6.

Sem catálogo de propriedade D0X, o auditor usa a divisão de responsabilidades registrada em `phase0_setup.md`: o que o usuário decide, o que fontes resolvem, o que cabe ao papel especialista e o que permanece fora do escopo. Para uma proposta de novo D0X, confira também seus limites e dependências contra o catálogo existente, sem fingir que o domínio candidato já foi aceito.

## Limites para temas de alto impacto

Em revisão contratual, identifique cláusulas, ambiguidades, obrigações, riscos e perguntas para assessoria jurídica; não declare a validade ou a exequibilidade legal como fato sem base específica e revisão humana competente. Registre a jurisdição e a versão do documento quando forem relevantes para interpretar uma afirmação.

Em revisão de prescrição médica, não diagnostique, prescreva, altere, suspenda nem valide como segura uma terapia ou dose individual. Limite a análise à transcrição fiel, completude textual e inconsistências que possam ser apontadas com base nos dados e fontes explicitamente fornecidos; marque qualquer dúvida clínica ou possível discrepância para confirmação com farmacêutico ou prescritor antes de agir. Um resultado `PASS` da auditoria cobre apenas a qualidade do relatório, nunca a segurança clínica da prescrição.

Em outros temas regulados ou de segurança, defina em `phase0_setup.md` a jurisdição, a data/versão das fontes, o especialista humano responsável e quais decisões o modelo não pode tomar. Uma lacuna nesse contexto deve permanecer explícita, não ser preenchida por consenso dos modelos.

## Revisão de um novo D0X

Quando o entregável for propor um domínio novo para o próprio repositório, trate a proposta de perfil como artefato em avaliação. Examine o catálogo e os domínios vizinhos para verificar cobertura, duplicação, fronteiras de responsabilidade, gatilhos, pré-requisitos, sequência e handoffs. Especifique como parte do entregável a metodologia, o público e o papel do usuário, a barra de precisão, os artefatos requeridos, a estrutura de arquivos, fontes e, quando necessário, overrides de fase.

Não aplique os prompts ainda em elaboração ao próprio ciclo de revisão, não atribua número/slug definitivo se a posição no catálogo ainda não foi aprovada e não altere `domains.md` nem publique o pacote em `process/domains/` antes da aceitação humana da fase 5. A consolidação entrega a proposta e os passos de integração; a incorporação ao repositório é uma etapa posterior autorizada pelo usuário.

## Retomada e encerramento

Ao retomar uma rodada, leia `phase0_setup.md`, confira o último artefato concluído e prossiga da primeira ação pendente, sem refazer slots concluídos. Se o documento-fonte, seu escopo ou um requisito material mudar depois do início das propostas, congele a rodada e inicie uma nova pasta com timestamp; nunca misture versões diferentes na mesma consolidação e nunca invente fases 6–10.

Entregue ao usuário o resultado consolidado, o escopo e a versão avaliados, as conclusões prioritárias, divergências ou incertezas restantes, decisões humanas pendentes e os caminhos dos artefatos quando houver. Informe claramente se o gate independente passou. A aceitação final pertence ao usuário ou à autoridade humana definida na fase 0, nunca ao líder nem ao consenso dos modelos.
